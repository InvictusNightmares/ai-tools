#!/usr/bin/env python3
"""Configure the user-approved customer portal on 18080 only."""
import argparse
import hashlib
import json
import os
import subprocess
import time

from candidate_ops import ROOT, DB, DB_NAME, candidate_sql, require_space, event, run
from candidate_migrate import api, all_items, key_inventory, usage_totals, equal_totals, sql_json, POOLS, roster
from candidate_accept import login, native, request, check, record
from customer_passwords import customer_password

STATE = ROOT / 'ops' / 'customer-portal-state.json'
BASELINE = ROOT / 'ops' / 'customer-portal-before.json'
MANIFEST = ROOT / 'backups' / 'customer-portal-before-manifest.json'
OLD_GROUPS = {3, 7, 9, 72, 135, 198, 261, 324, 387, 450, 513, 576, 639, 704}
OLD_USERS = {3, 4, 79}
CHANNEL_NAME = 'GPT / DeepSeek'


def migration():
    return json.loads((ROOT / 'ops' / 'migration-state.json').read_text())


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {'monitors': {}}


def save(value):
    STATE.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def guard(runtime=False):
    check(candidate_sql('SELECT current_database();').strip() == DB_NAME, 'wrong database')
    services = json.loads((ROOT / 'compose.json').read_text())['services']
    config = services['app']
    check(config['container_name'] == 'sub2api-next', 'wrong instance')
    if runtime:
        check(not config.get('ports'), 'production app must have no published ports')
        gateway = services.get('gateway', {})
        check(gateway.get('container_name') == 'sub2api-next-proxy'
              and gateway.get('ports') == ['0.0.0.0:8080:8080'], 'wrong production gateway')
    else:
        check(config.get('ports') == ['0.0.0.0:18080:8080'], 'preview mutation is unavailable after cutover')
    check(config['environment']['DATABASE_DBNAME'] == DB_NAME, 'wrong app database')
    require_space(5)


def require_backup():
    check(MANIFEST.exists() and BASELINE.exists(), 'verified candidate backup required')


def backup():
    check(not MANIFEST.exists(), 'portal backup already exists; inspect before repeating')
    require_space(6)
    users, groups, channels = all_items('users'), all_items('groups'), all_items('channels')
    keep = migration()
    check({u['id'] for u in users} == set(keep['users'].values()) | OLD_USERS | {1}, 'user inventory changed')
    check({g['id'] for g in groups} == set(keep['groups'].values()) | OLD_GROUPS, 'group inventory changed')
    check(len(channels) == 1 and channels[0]['id'] == 1 and channels[0]['name'] == 'Codex', 'channel inventory changed')
    usage_max_id = int(candidate_sql('SELECT coalesce(max(id),0) FROM usage_logs;').strip())
    BASELINE.write_text(json.dumps({'users': users, 'groups': groups,
        'channels': [api('GET', '/api/v1/admin/channels/1')], 'keys': key_inventory(),
        'usage_max_id': usage_max_id, 'usage_totals': usage_totals(usage_max_id),
        'settings': api('GET', '/api/v1/admin/settings')}, ensure_ascii=False, indent=2))
    path = ROOT / 'backups' / 'candidate-before-customer-portal.dump'
    event('portal_backup_started')
    with path.open('xb') as out, (ROOT / 'ops' / 'portal-backup.stderr').open('wb') as err:
        result = subprocess.run(['docker', 'exec', DB, 'nice', '-n', '10', 'pg_dump',
                                 '-U', 'sub2api', '-d', DB_NAME, '-Fc', '-Z1', '--lock-wait-timeout=5s'],
                                stdout=out, stderr=err, timeout=900)
    check(result.returncode == 0, 'candidate backup failed; private log retained')
    listing = run(['docker', 'exec', DB, 'pg_restore', '--list', '/backup/' + path.name])
    check('TABLE DATA public users ' in listing and 'TABLE DATA public usage_logs ' in listing, 'backup archive incomplete')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    result = {'file': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest(),
              'database': DB_NAME, 'verified_archive': True}
    MANIFEST.write_text(json.dumps(result, indent=2))
    event('portal_backup_verified', **result)


def configure():
    require_backup()
    keep, current = migration(), state()
    settings = {
        'backend_mode_enabled': False, 'registration_enabled': False,
        'payment_enabled': False, 'payment_balance_disabled': True,
        'purchase_subscription_enabled': False, 'purchase_subscription_url': '',
        'balance_low_notify_recharge_url': '',
        'available_channels_enabled': True, 'model_plaza_enabled': True,
        'model_plaza_require_auth': True, 'allow_user_view_error_requests': True,
        'model_plaza_description': '查看可使用的模型与计费标准。账户额度由管理员分配，无需充值。GPT 每人每周 300 美元，DeepSeek 不设个人平台金额限额。',
        'channel_monitor_enabled': True,
        'channel_monitor_default_interval_seconds': 300,
        'channel_monitor_hide_user_ranking': True,
        'channel_monitor_hide_throughput': True, 'channel_monitor_show_quota': False,
    }
    api('PUT', '/api/v1/admin/settings', settings)
    model_sets = []
    for aid, _ in POOLS.values():
        mapping = sql_json("SELECT credentials->'model_mapping' FROM accounts WHERE id={};".format(aid))
        check(isinstance(mapping, dict) and mapping, 'upstream model catalog missing')
        model_sets.append(set(mapping))
    # Show the common customer-facing catalog; do not advertise internal aliases.
    models = sorted(set.intersection(*model_sets) - {'gpt-reserve', 'codex-auto-review'})
    check('gpt-5.6-luna' in models and 'gpt-image-2.5-flare' in models, 'unexpected common GPT catalog')
    model_mapping = {'openai': {m: m for m in models},
                     'deepseek': {m: m for m in ['deepseek-flash', 'deepseek-v4-pro']}}
    payload = {'name': CHANNEL_NAME, 'description': 'GPT 与 DeepSeek 统一接入；可使用的资源组由管理员分配。',
               'group_ids': sorted(keep['groups'].values()), 'model_mapping': model_mapping,
               'model_pricing': [], 'billing_model_source': 'upstream', 'restrict_models': False,
               'apply_pricing_to_account_stats': False}
    channels = all_items('channels')
    found = next((c for c in channels if c['name'] == CHANNEL_NAME), None)
    if found:
        check(found['id'] == current.get('channel_id'), 'unexpected existing customer channel')
        channel = api('PUT', '/api/v1/admin/channels/' + str(found['id']), payload)
    else:
        channel = api('POST', '/api/v1/admin/channels', payload)
    current.update(channel_id=channel['id'], gpt_catalog=models, deepseek_catalog=list(model_mapping['deepseek']))
    save(current)
    check(channel['model_pricing'] == [], 'channel must retain existing global pricing')
    if any(c['id'] == 1 for c in channels):
        api('DELETE', '/api/v1/admin/channels/1')
    event('customer_channel_configured', channel_id=channel['id'], channel_name=CHANNEL_NAME,
          groups=len(keep['groups']), gpt_models=len(models), deepseek_models=2,
          payments=False, customer_channels=True, model_plaza=True)


def cleanup():
    require_backup()
    keep = migration()
    check(state().get('channel_id'), 'customer channel must be configured first')
    users, groups = all_items('users'), all_items('groups')
    old_users = {u['id'] for u in users} - set(keep['users'].values()) - {1}
    old_groups = {g['id'] for g in groups} - set(keep['groups'].values())
    check(old_users <= OLD_USERS and old_groups <= OLD_GROUPS, 'unreviewed user or group appeared')
    # Preserve the existing technical GPT key's upstream when the legacy group goes away.
    api('PUT', '/api/v1/admin/api-keys/90', {'group_id': keep['groups']['wcan-B']})
    # The excluded Claude key has no supported resource in this customer portal.
    # Keep its value and history, but detach it from the retiring Claude group.
    api('PUT', '/api/v1/admin/api-keys/79', {'group_id': 0})
    for uid in sorted(old_users):
        api('DELETE', '/api/v1/admin/users/' + str(uid))
    for gid in sorted(old_groups):
        api('DELETE', '/api/v1/admin/groups/' + str(gid))
    event('customer_legacy_cleanup', deleted_users=sorted(old_users), deleted_groups=sorted(old_groups),
          customer_users_retained=74, groups_retained=8, technical_key_group='wcan-B', claude_key_detached=True)


def monitors():
    require_backup()
    check(api('GET', '/api/v1/admin/settings')['channel_monitor_mode'] == 'v1',
          'V1 monitors are retired in the current V2 setup; do not recreate them')
    current = state()
    existing = {m['name']: m for m in all_items('channel-monitors')}
    definitions = []
    for name, (aid, _) in POOLS.items():
        definitions.append({'name': name + ' GPT 账号状态', 'provider': 'openai', 'api_mode': 'responses',
            'primary_model': '账号状态（非模型请求探测）', 'extra_models': [], 'group_name': name,
            'enabled': True, 'interval_seconds': 300, 'jitter_seconds': 30,
            'check_mode': 'quota', 'account_id': aid})
    for aid, label in zip(migration()['deepseek_accounts'], ['DeepSeek Flash', 'DeepSeek V4 Pro']):
        credentials = sql_json('SELECT credentials FROM accounts WHERE id={};'.format(aid))
        public_model, upstream_model = next(iter(credentials['model_mapping'].items()))
        check(public_model in ('deepseek-flash', 'deepseek-v4-pro'), 'unexpected DeepSeek monitor model')
        definitions.append({'name': label + ' 请求探针', 'provider': 'deepseek', 'api_mode': 'chat_completions',
            'endpoint': credentials['base_url'], 'api_key': credentials['api_key'],
            'primary_model': public_model, 'extra_models': [], 'group_name': '共享 DeepSeek',
            'enabled': True, 'interval_seconds': 300, 'jitter_seconds': 30, 'check_mode': 'probe',
            'body_override_mode': 'replace', 'body_override': {'model': upstream_model,
                'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}],
                'max_tokens': 64, 'stream': False, 'thinking': {'type': 'disabled'}}})
    for payload in definitions:
        name = payload['name']
        if name in existing:
            check(existing[name]['id'] == current['monitors'].get(name), 'unexpected existing monitor')
            monitor = api('PUT', '/api/v1/admin/channel-monitors/' + str(existing[name]['id']), payload)
        else:
            monitor = api('POST', '/api/v1/admin/channel-monitors', payload)
        current['monitors'][name] = monitor['id']
        save(current)
        event('customer_monitor_configured', name=name, monitor_id=monitor['id'], check_mode=payload['check_mode'], interval_seconds=300)


def verify():
    require_backup()
    check(api('GET', '/api/v1/admin/settings')['channel_monitor_mode'] == 'v1',
          'this is the historical V1 acceptance phase; use candidate_monitor_v2.py verify for V2')
    current, keep = state(), migration()
    users, groups, channels = all_items('users'), all_items('groups'), all_items('channels')
    check({u['id'] for u in users} == set(keep['users'].values()) | {1}, 'old or missing users remain')
    check({g['id'] for g in groups} == set(keep['groups'].values()), 'old or missing groups remain')
    check(len(channels) == 1 and channels[0]['id'] == current['channel_id'], 'unexpected channel set')
    baseline = json.loads(BASELINE.read_text())
    keys = {k['id']: k for k in key_inventory()}
    originals = {k['id']: k for k in baseline['keys']}
    for row in roster():
        kid = int(row['api_key_id'])
        check(keys[kid] == originals[kid], 'customer key changed during portal cleanup')
    # Later smoke calls must not make the preserved historical snapshot fail reconciliation.
    check(equal_totals(baseline['usage_totals'], usage_totals(baseline.get('usage_max_id'))),
          'historical usage changed during portal cleanup')
    sample_results = []
    for group_name in POOLS:
        row = next(r for r in roster() if r['resource_group'] == group_name)
        token = login(row['login_email'], customer_password(row['login_email']))
        available = native('GET', '/api/v1/channels/available', token=token)
        plaza = native('GET', '/api/v1/model-plaza', token=token)
        monitors_view = native('GET', '/api/v1/channel-monitors', token=token)['items']
        gid = keep['groups'][group_name]
        check(len(available) == 1 and available[0]['name'] == CHANNEL_NAME, 'customer channel missing')
        visible = {g['id'] for p in available[0]['platforms'] for g in p['groups']}
        check(visible == {gid}, 'customer sees a different resource group')
        check({p['platform'] for p in available[0]['platforms']} == {'openai', 'deepseek'}, 'model platform missing')
        check({g['id'] for g in plaza['groups']} == {gid}, 'model plaza group visibility mismatch')
        check(len(monitors_view) == 10, 'customer monitor list incomplete')
        check(all('endpoint' not in m and 'api_key' not in m and 'latest_quota' not in m for m in monitors_view), 'monitor internals exposed')
        model_count = sum(len(p['supported_models']) for p in available[0]['platforms'])
        check(model_count == len(current['gpt_catalog']) + 2, 'customer model count mismatch')
        sample_results.append({'group': group_name, 'models': model_count, 'monitors': len(monitors_view)})
    settings = api('GET', '/api/v1/admin/settings')
    check(not settings['payment_enabled'] and settings['payment_balance_disabled'] and not settings['purchase_subscription_enabled'], 'customer payment still enabled')
    check(request('GET', '/api/v1/model-plaza')[0] == 401, 'model plaza should require customer login')
    monitoring = all_items('channel-monitors')
    statuses = [{k: m.get(k) for k in ['id', 'name', 'check_mode', 'primary_model', 'primary_status', 'last_checked_at']} for m in monitoring]
    check(len(statuses) == 10 and all(m['last_checked_at'] for m in statuses), 'first monitor cycle incomplete')
    record('customer_portal', {'passed': True, 'customers': 74, 'administrators': 1, 'groups': 8,
        'channel_id': current['channel_id'], 'channel_name': CHANNEL_NAME, 'model_count': len(current['gpt_catalog'])+2,
        'customer_view_samples': sample_results, 'monitors': statuses,
        'customer_keys_unchanged': True, 'historical_usage_unchanged': True,
        'payments_enabled': False, 'probe_interval_seconds': 300})


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['backup', 'configure', 'cleanup', 'monitors', 'verify'])
    args = parser.parse_args()
    guard()
    globals()[args.phase]()


if __name__ == '__main__':
    main()
