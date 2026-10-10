#!/usr/bin/env python3
"""Verify production monitoring; retain the isolated preview setup commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from candidate_ops import ROOT, DB, DB_NAME, event, run
from candidate_migrate import api, all_items, key_inventory, roster, sql_json, usage_totals, equal_totals, certified_history
from candidate_accept import check, login, native, record
from candidate_portal import guard, migration, state as portal_state
from customer_passwords import customer_password

BACKUP = ROOT / 'ops' / 'monitor-v2-before.json'
STATE = ROOT / 'ops' / 'monitor-v2-state.json'
SETTING_KEYS = ['channel_monitor_enabled', 'channel_monitor_mode',
                'channel_monitor_hide_user_ranking', 'channel_monitor_hide_throughput',
                'channel_monitor_show_quota']


def user_snapshot():
    return sql_json("""SELECT json_agg(t) FROM
      (SELECT id,email,username,role,status,balance,concurrency,rpm_limit,restrict_public_groups
       FROM users WHERE deleted_at IS NULL ORDER BY id) t;""")


def configure():
    current, keep = portal_state(), migration()
    monitors = all_items('channel-monitors')
    check({m['id'] for m in monitors} <= set(current['monitors'].values()), 'unexpected V1 monitors')
    settings = api('GET', '/api/v1/admin/settings')
    config = api('GET', '/api/v1/admin/channel-monitor-v2/config')
    if not BACKUP.exists():
        with BACKUP.open('x') as stream:
            json.dump({'settings': {k: settings[k] for k in SETTING_KEYS}, 'config': config,
                       'monitors': [{k: m[k] for k in ['id', 'name', 'enabled', 'check_mode']} for m in monitors],
                       'users': user_snapshot(), 'keys': key_inventory(), 'groups': keep['groups'],
                       'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
                      stream, ensure_ascii=False, indent=2)
    check(json.loads(BACKUP.read_text())['groups'] == keep['groups'], 'backup group scope differs')
    desired = {k: config[k] for k in ['version', 'health_thresholds', 'ignored_error_categories']}
    desired.update(enabled=True, refresh_interval_seconds=300,
                   group_ids=sorted(keep['groups'].values()),
                   platforms=[{'platform': 'openai', 'enabled': True, 'models': current['gpt_catalog']},
                              {'platform': 'deepseek', 'enabled': True, 'models': current['deepseek_catalog']}])
    saved = api('PUT', '/api/v1/admin/channel-monitor-v2/config', desired)
    api('PUT', '/api/v1/admin/settings', {'channel_monitor_enabled': True, 'channel_monitor_mode': 'v2',
        'channel_monitor_hide_user_ranking': True, 'channel_monitor_hide_throughput': True,
        'channel_monitor_show_quota': False})
    # Retain the previous monitor definitions and history while stopping their schedules.
    for monitor in monitors:
        if monitor['enabled']:
            api('PUT', '/api/v1/admin/channel-monitors/' + str(monitor['id']), {'enabled': False})
    result = {'mode': 'v2', 'version': saved['version'], 'groups': sorted(keep['groups'].values()),
              'platforms': ['openai', 'deepseek'], 'models': len(current['gpt_catalog']) + len(current['deepseek_catalog']),
              'refresh_interval_seconds': 300, 'legacy_monitors_disabled': len(monitors),
              'configured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    STATE.write_text(json.dumps(result, indent=2))
    event('customer_monitor_v2_configured', **result)


def delete_legacy():
    check(STATE.exists() and BACKUP.exists(), 'V2 must be configured and backed up first')
    settings = api('GET', '/api/v1/admin/settings')
    check(settings['channel_monitor_mode'] == 'v2', 'V2 must be active before V1 deletion')
    monitors = all_items('channel-monitors')
    check({m['id'] for m in monitors} <= set(portal_state()['monitors'].values()), 'unreviewed V1 monitor found')
    check(not any(m['enabled'] for m in monitors), 'stop V1 schedules before deleting')
    tables = sql_json("SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'channel_monitor%' AND tablename NOT LIKE 'channel_monitor_v2%';")
    check('channel_monitors' in tables and 'channel_monitor_histories' in tables, 'V1 backup tables missing')
    backup = ROOT / 'backups' / 'monitor-v1-before-delete.dump'
    if not backup.exists():
        command = ['docker', 'exec', DB, 'pg_dump', '-U', 'sub2api', '-d', DB_NAME,
                   '-Fc', '-Z1', '--lock-wait-timeout=5s']
        for table in tables:
            command += ['--table', 'public.' + table]
        with backup.open('xb') as stream, (ROOT / 'ops' / 'monitor-v1-backup.stderr').open('wb') as err:
            result = subprocess.run(command, stdout=stream, stderr=err, timeout=120)
        check(result.returncode == 0, 'V1 backup failed; private error log retained')
    listing = run(['docker', 'exec', DB, 'pg_restore', '--list', '/backup/' + backup.name])
    check(all('TABLE DATA public ' + table + ' ' in listing for table in tables), 'V1 backup archive incomplete')
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    users_before, keys_before = user_snapshot(), key_inventory()
    config_before = api('GET', '/api/v1/admin/channel-monitor-v2/config')
    for monitor in monitors:
        api('DELETE', '/api/v1/admin/channel-monitors/' + str(monitor['id']))
    check(not all_items('channel-monitors'), 'V1 monitor definitions remain')
    check(api('GET', '/api/v1/admin/channel-monitor-v2/config') == config_before, 'V2 configuration changed')
    check(user_snapshot() == users_before and key_inventory() == keys_before, 'account/key metadata changed')
    snapshot = api('GET', '/api/v1/admin/channel-monitor-v2/snapshot?range=90m')
    result = {'passed': True, 'deleted_monitor_ids': sorted(m['id'] for m in monitors),
              'remaining_v1_monitors': 0, 'v2_mode': True, 'v2_configuration_unchanged': True,
              'account_settings_unchanged': True, 'api_keys_unchanged': True,
              'backup': str(backup), 'backup_bytes': backup.stat().st_size, 'backup_sha256': digest,
              'v2_data_through': snapshot['coverage']['data_through'],
              'v2_ttft_samples': snapshot['metrics']['ttft']['sample_count']}
    saved_state = json.loads(STATE.read_text())
    saved_state['legacy_monitors_deleted'] = True
    STATE.write_text(json.dumps(saved_state, indent=2))
    record('customer_monitor_v1_deleted', result)


def validate_runtime_customers(users, keys, rows, keep, original_keys):
    """Check durable policy while allowing ordinary customer account activity."""
    user_ids = set(keep['users'].values())
    by_user, by_key = {u['id']: u for u in users}, {k['id']: k for k in keys}
    original = {k['id']: k for k in original_keys}
    check(set(by_user) == user_ids | {1}, 'customer/admin inventory differs')
    check(by_user[1]['role'] == 'admin', 'administrator role changed')
    group_by_user = {}
    surviving_originals = 0
    for row in rows:
        uid, kid = keep['users'][row['api_key_id']], int(row['api_key_id'])
        user, key = by_user[uid], by_key[kid]
        group_by_user[uid] = keep['groups'][row['resource_group']]
        check(user['role'] == 'user' and user['status'] == 'active'
              and user['email'] == row['login_email'], 'customer identity or role differs')
        check(user['concurrency'] == 3 and user['restrict_public_groups'],
              'customer concurrency or public-group restriction differs')
        check(user['balance'] > 0, 'customer wallet needs administrator funding')
        check(key['user_id'] == uid, 'original customer key ownership differs')
        if not key['deleted']:
            check(key['key_digest'] == original[kid]['key_digest'],
                  'a surviving original customer key value differs')
            surviving_originals += 1
    # Customers may create, rename, disable or delete their own keys. Check the
    # current authorization boundary, not equality with an old metadata snapshot.
    for key in keys:
        if key['user_id'] in user_ids and not key['deleted']:
            check(key['group_id'] == group_by_user[key['user_id']],
                  'customer key is outside its assigned resource group')
    check(all(by_key[kid]['deleted'] for kid in [55, 79, 90]),
          'a user-confirmed deleted key was restored')
    return {'customers': len(user_ids), 'surviving_original_customer_keys': surviving_originals,
            'current_customer_keys': sum(k['user_id'] in user_ids and not k['deleted'] for k in keys),
            'low_balance_users': sum(by_user[uid]['balance'] < 10000 for uid in user_ids)}


def volume_fields_visible(value):
    fields = {'success_requests', 'error_requests', 'request_count', 'input_tokens',
              'output_tokens', 'cache_creation_tokens', 'cache_read_tokens', 'token_count',
              'cache_rate_numerator', 'cache_rate_denominator', 'sample_count', 'rpm', 'tpm'}
    if isinstance(value, dict):
        return any((key in fields and item not in (None, 0)) or volume_fields_visible(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(volume_fields_visible(item) for item in value)
    return False


def normalize_sessions(value, group_names):
    check(isinstance(value, dict) and set(value) == set(group_names),
          'session group coverage differs')
    result = {}
    for group, token in value.items():
        check(isinstance(token, str), 'invalid customer session format')
        token = token.strip()
        check(len(token) <= 16384 and re.fullmatch(
            r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token) is not None,
            'invalid customer session format')
        result[group] = token
    return result


def verify(initial_logins=False, sessions=None):
    check(STATE.exists(), 'V2 configuration must complete before verification')
    keep = migration()
    gids = set(keep['groups'].values())
    settings = api('GET', '/api/v1/admin/settings')
    check(settings['channel_monitor_enabled'] and settings['channel_monitor_mode'] == 'v2', 'V2 is not active')
    check(settings['channel_monitor_hide_user_ranking'] and settings['channel_monitor_hide_throughput'], 'customer privacy flags changed')
    config = api('GET', '/api/v1/admin/channel-monitor-v2/config')
    check(config['enabled'] and config['refresh_interval_seconds'] == 300, 'V2 aggregation configuration differs')
    check(set(config['group_ids']) == gids, 'V2 group scope differs')
    check({p['platform'] for p in config['platforms'] if p['enabled']} == {'openai', 'deepseek'}, 'unexpected monitored platform')
    check(not all_items('channel-monitors'), 'a deleted V1 monitor was recreated')
    rows = roster()
    user_ids = set(keep['users'].values())
    users = user_snapshot()
    original = json.loads((ROOT / 'ops' / 'migration-baseline.json').read_text())
    customer_summary = validate_runtime_customers(users, key_inventory(), rows, keep, original['keys'])
    ids = ','.join(str(uid) for uid in sorted(user_ids))
    quotas = sql_json("SELECT json_agg(t) FROM (SELECT user_id,platform,daily_limit_usd,weekly_limit_usd,monthly_limit_usd FROM user_platform_quotas WHERE deleted_at IS NULL AND user_id IN ({})) t;".format(ids)) or []
    gpt = [q for q in quotas if q['platform'] == 'openai']
    check(len(gpt) == 74 and {q['user_id'] for q in gpt} == user_ids
          and all(q['weekly_limit_usd'] == 300 and q['daily_limit_usd'] is None
                  and q['monthly_limit_usd'] is None for q in gpt), 'personal GPT quota policy differs')
    check(not any(q['platform'] != 'openai' and any(q[k] is not None for k in
                  ['daily_limit_usd', 'weekly_limit_usd', 'monthly_limit_usd']) for q in quotas),
          'another personal platform has an amount limit')
    portal_before = certified_history()
    cutoff = portal_before['usage_max_id']
    check(equal_totals(portal_before['usage_totals'], usage_totals(cutoff)),
          'previously verified historical usage changed')
    history_owners = {int(r['api_key_id']): int(keep['users'][r['api_key_id']]) for r in rows}
    history_owners.update({int(r['key_id']): int(r['user_id']) for r in keep.get('history_mapping', [])})
    owner_values = ','.join('({},{})'.format(k, u) for k, u in sorted(history_owners.items()))
    wrong_owners = sql_json("SELECT count(*) FROM usage_logs l JOIN (VALUES {}) AS m(key_id,user_id) ON m.key_id=l.api_key_id WHERE l.id<={} AND l.user_id IS DISTINCT FROM m.user_id;".format(owner_values, int(cutoff)))
    check(wrong_owners == 0, 'historical customer usage belongs to an unexpected user')
    allowed = sql_json('SELECT coalesce(json_agg(t),\'[]\') FROM (SELECT user_id,group_id FROM user_allowed_groups WHERE user_id IN ({}) ORDER BY user_id,group_id) t;'.format(','.join(str(uid) for uid in sorted(user_ids))))
    expected = {(keep['users'][r['api_key_id']], keep['groups'][r['resource_group']]) for r in rows}
    check(len(allowed) == 74 and {(g['user_id'], g['group_id']) for g in allowed} == expected, 'customer group grants differ')
    samples = []
    # Normal runtime checks never assume customers kept their initial passwords.
    # Optional API verification accepts real sessions, or explicit initial-login
    # testing during first delivery. It never resets passwords or provisions users.
    tokens = {}
    if sessions:
        session_file = Path(sessions)
        stat = session_file.stat()
        check(stat.st_uid == os.geteuid() and stat.st_mode & 0o077 == 0,
              'session file must be private and owned by this operator')
        tokens = normalize_sessions(json.loads(session_file.read_text()), keep['groups'])
    for group_name, gid in (keep['groups'].items() if initial_logins or tokens else []):
        row = next(r for r in rows if r['resource_group'] == group_name)
        token = (login(row['login_email'], customer_password(row['login_email']))
                 if initial_logins else tokens[group_name])
        profile = native('GET', '/api/v1/user/profile', token=token)
        group_users = {keep['users'][r['api_key_id']] for r in rows if r['resource_group'] == group_name}
        check(profile['id'] in group_users and profile['role'] == 'user', 'session is not a customer of the required group')
        prefix = '/api/v1/channel-monitor-v2/'
        dimensions = native('GET', prefix + 'dimensions?range=90m', token=token)
        check({g['id'] for g in dimensions['groups']} == {gid}, 'customer can see another group dimension')
        check({p['value'] for p in dimensions['platforms']} == {'openai', 'deepseek'}, 'customer platform list differs')
        matrix = native('GET', prefix + 'matrix?range=90m&group_by=platform_group', token=token)
        # Composite groups may have no matrix row for a platform with no traffic.
        # The configured model catalog still includes both DeepSeek models.
        check({m['group_id'] for m in matrix['items']} <= {gid}, 'customer matrix is outside their group')
        check({m['platform'] for m in matrix['items']} <= {'openai', 'deepseek'}, 'unexpected customer matrix platform')
        models = native('GET', prefix + 'models?range=90m', token=token)
        check({'deepseek-flash', 'deepseek-v4-pro'} <= {m['model'] for m in models['items'] if m['platform'] == 'deepseek'},
              'DeepSeek models missing from customer catalog')
        snapshot = native('GET', prefix + 'snapshot?range=90m', token=token)
        ranking = native('GET', prefix + 'users?range=90m', token=token)
        errors = native('GET', prefix + 'errors?range=90m', token=token)
        check(not ranking['items'], 'customer ranking is visible')
        check(all(e.get('count', 0) == 0 and not e.get('details') for e in errors['items']),
              'customer error details or volume are visible')
        check(not any(volume_fields_visible(v) for v in [dimensions, snapshot, models, matrix]),
              'customer monitoring exposes volume fields')
        check(not snapshot['config'].get('group_ids') and not snapshot['config'].get('updated_by'),
              'customer snapshot exposes operator configuration')
        other = next(g for g in gids if g != gid)
        denied = native('GET', prefix + 'matrix?range=90m&group_by=platform_group&group_id=' + str(other), token=token)
        check(not denied['items'], 'forged group ID exposes another group matrix')
        denied = native('GET', prefix + 'snapshot?range=90m&group_id=' + str(other), token=token)
        check(all(denied['metrics'][metric][field] is None for metric in ['ttft', 'duration']
                  for field in ['p50_ms', 'p90_ms', 'p95_ms', 'avg_ms']),
              'forged group ID exposes another group latency')
        legacy = native('GET', '/api/v1/channel-monitors', token=token)
        check(not legacy['items'], 'old global monitor list still visible')
        samples.append({'group': group_name, 'visible_group_ids': [gid], 'platforms': ['openai', 'deepseek'],
                        'forged_group_returns_empty': True,
                        'ttft_p50_ms': snapshot['metrics']['ttft']['p50_ms'],
                        'duration_p50_ms': snapshot['metrics']['duration']['p50_ms']})
    admin_dimensions = api('GET', '/api/v1/admin/channel-monitor-v2/dimensions?range=90m')
    check({g['id'] for g in admin_dimensions['groups']} == gids, 'admin cannot see all eight groups')
    snapshot = api('GET', '/api/v1/admin/channel-monitor-v2/snapshot?range=90m')
    ready = snapshot['metrics']['ttft']['sample_count'] > 0 and snapshot['metrics']['duration']['sample_count'] > 0
    record('customer_monitor_v2_runtime', {'passed': True, 'mode': 'v2', 'samples': samples, 'admin_groups': len(gids),
        'verification_scope': 'configuration_history_and_customer_api' if samples else 'configuration_and_history',
        'customer_api_verified': bool(samples), 'customer_configuration': customer_summary,
        'legacy_probes_deleted': True, 'personal_quota_policy_verified': True,
        'historical_usage_totals_unchanged_through_id': cutoff,
        'historical_usage_ownership_verified_through_id': cutoff,
        'real_request_latency_available': ready, 'coverage': snapshot['coverage'],
        'admin_ttft_samples': snapshot['metrics']['ttft']['sample_count'],
        'admin_ttft_p50_ms': snapshot['metrics']['ttft']['p50_ms'],
        'admin_duration_samples': snapshot['metrics']['duration']['sample_count']})


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['configure', 'verify', 'delete_legacy'])
    sampling = parser.add_mutually_exclusive_group()
    sampling.add_argument('--initial-logins', action='store_true', help='Explicit first-delivery login test only; never reset changed passwords')
    sampling.add_argument('--sessions', help='Private JSON file mapping all eight group names to existing customer bearer sessions')
    args = parser.parse_args()
    if args.phase != 'verify' and (args.initial_logins or args.sessions):
        parser.error('session options apply only to verify')
    guard(runtime=args.phase == 'verify')
    if args.phase == 'verify':
        verify(initial_logins=args.initial_logins, sessions=args.sessions)
    else:
        globals()[args.phase]()


if __name__ == '__main__':
    main()
