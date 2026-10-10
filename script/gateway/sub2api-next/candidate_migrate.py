#!/usr/bin/env python3
"""Configure and reconcile the private candidate through official APIs and scoped SQL."""
import argparse
import csv
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from candidate_ops import ROOT, DB, DB_NAME, candidate_sql, compose, event, require_space
from customer_passwords import customer_password

# After production cutover, administration uses the existing local gateway.
BASE = 'http://127.0.0.1:8080'
POOLS = {'ecube-A': (51, 198), 'ecube-B': (67, 387), 'dpad-A': (47, 72),
         'dpad-B': (68, 450), 'dpad-C': (74, 9), 'dpad-D': (75, 135),
         'wcan-A': (53, 261), 'wcan-B': (54, 324)}
COPY_GROUP_FIELDS = ['long_context_pricing_enabled', 'model_pricing', 'allow_image_generation',
                     'allow_batch_image_generation', 'image_rate_independent', 'image_rate_multiplier',
                     'batch_image_discount_multiplier', 'batch_image_hold_multiplier',
                     'image_price_1k', 'image_price_2k', 'image_price_4k', 'web_search_price_per_call',
                     'search_price_per_1k', 'allow_messages_dispatch', 'allow_live', 'model_allowlist',
                     'messages_dispatch_model_config', 'default_mapped_model']


def sql_json(sql):
    raw = candidate_sql(sql).strip()
    return json.loads(raw) if raw else None


def api(method, path, payload=None):
    if not path.startswith('/api/v1/admin/'):
        raise ValueError('only candidate admin routes are allowed')
    key = (ROOT / 'ops' / 'admin-api-key').read_text().strip()
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE + path, data=body, method=method,
                                     headers={'x-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # Native API responses may contain account secrets: keep error details private.
        (ROOT / 'ops' / 'api-error.json').write_bytes(exc.read())
        raise RuntimeError('candidate API {} {} returned {}; private api-error.json saved'.format(method, path, exc.code))
    if result.get('code', 0) != 0:
        raise RuntimeError('candidate API returned an unsuccessful response')
    return result.get('data', result)


def all_items(resource):
    result, page = [], 1
    while True:
        data = api('GET', '/api/v1/admin/{}?page={}&page_size=100'.format(resource, page))
        items = data if isinstance(data, list) else data.get('items', [])
        result.extend(items)
        if isinstance(data, list) or len(result) >= data.get('total', len(result)) or not items:
            return result
        page += 1


def roster():
    with (ROOT / 'ops' / 'allocation.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 74 or len({r['api_key_id'] for r in rows}) != 74 or len({r['login_email'] for r in rows}) != 74:
        raise RuntimeError('expected 74 unique personal keys and logins')
    for row in rows:
        if (row['resource_group'] not in POOLS or int(row['gpt_account_id']) != POOLS[row['resource_group']][0]
                or row['gpt_weekly_limit_usd'] != '300' or row['deepseek_limit'] != 'unlimited'
                or not row['login_email'].endswith('@cpirhzl.com') or not row['api_key_id'].isdigit()):
            raise RuntimeError('roster differs from approved scope')
        local_part = row['login_email'].split('@')[0]
        if not local_part.isalpha() or local_part != local_part.lower():
            raise RuntimeError('invalid account naming rule')
    if {55, 79, 90}.intersection(int(r['api_key_id']) for r in rows):
        raise RuntimeError('excluded key found in personal roster')
    return rows


def key_inventory():
    return sql_json("""SELECT coalesce(json_agg(t),'[]') FROM
      (SELECT id,name,user_id,group_id,status,deleted_at IS NOT NULL AS deleted,
              md5(key) AS key_digest FROM api_keys ORDER BY id) t;""")


def usage_totals(max_id=None):
    # Strings preserve exact DECIMAL totals through JSON round trips.
    if max_id is not None and (type(max_id) is not int or max_id < 0):
        raise ValueError('usage cutoff must be a non-negative integer')
    condition = '' if max_id is None else 'WHERE id <= {}'.format(max_id)
    return sql_json("""SELECT json_agg(t) FROM
      (SELECT api_key_id,count(*) AS requests,sum(input_tokens)::text AS input_tokens,
       sum(output_tokens)::text AS output_tokens,sum(cache_creation_tokens)::text AS cache_creation_tokens,
       sum(cache_read_tokens)::text AS cache_read_tokens,sum(total_cost)::text AS total_cost,
       sum(actual_cost)::text AS actual_cost FROM usage_logs {} GROUP BY api_key_id ORDER BY api_key_id) t;""".format(condition))


def certified_history():
    """The production cutover replaces the preview-only history boundary."""
    production = ROOT / 'ops' / 'production-history-baseline.json'
    path = production if production.exists() else ROOT / 'ops' / 'customer-portal-before.json'
    result = json.loads(path.read_text())
    if type(result.get('usage_max_id')) is not int or not isinstance(result.get('usage_totals'), list):
        raise RuntimeError('invalid certified history baseline')
    return result


def archive_usage_totals():
    fields = ['input_tokens', 'output_tokens', 'cache_creation_tokens', 'cache_read_tokens', 'total_cost', 'actual_cost']
    totals, columns = {}, None
    with (ROOT / 'ops' / 'archive-read.stderr').open('wb') as err:
        process = subprocess.Popen(['docker', 'exec', DB, 'pg_restore', '--data-only', '--table=usage_logs',
                                    '--file=-', '/backup/production-before-candidate.dump'],
                                   stdout=subprocess.PIPE, stderr=err, universal_newlines=True, bufsize=1)
        for line in process.stdout:
            if line.startswith('COPY public.usage_logs ('):
                columns = [c.strip().strip('"') for c in line.split('(', 1)[1].split(')', 1)[0].split(',')]
                continue
            if columns is None:
                continue
            if line.rstrip('\n') == '\\.':
                columns = None
                continue
            values = line.rstrip('\n').split('\t')
            if len(values) != len(columns):
                process.terminate()
                raise RuntimeError('unexpected COPY row shape in backup')
            row = dict(zip(columns, values))
            key_id = int(row['api_key_id'])
            if key_id not in totals:
                totals[key_id] = dict(api_key_id=key_id, requests=0, **{f: Decimal(0) for f in fields})
            total = totals[key_id]
            total['requests'] += 1
            for field in fields:
                total[field] += Decimal(0) if row[field] == '\\N' else Decimal(row[field])
        if process.wait(timeout=60):
            raise RuntimeError('could not read usage data from verified backup')
    if not totals:
        raise RuntimeError('backup contains no readable usage data')
    return [{k: str(v) if isinstance(v, Decimal) else v for k, v in totals[key].items()} for key in sorted(totals)]


def equal_totals(left, right):
    def normalize(items):
        return {row['api_key_id']: {key: Decimal(str(value or 0)) for key, value in row.items() if key != 'api_key_id'}
                for row in items}
    return normalize(left) == normalize(right)


def inventory():
    rows = roster()
    keys = key_inventory()
    personal_names = {r['person_name'] for r in rows}
    extra = [{k: item[k] for k in ['id', 'name', 'deleted', 'group_id']} for item in keys
             if item['deleted'] and item['name'] in personal_names]
    path = ROOT / 'ops' / 'migration-baseline.json'
    if not path.exists():
        expected = archive_usage_totals()
        actual = usage_totals()
        if not equal_totals(expected, actual):
            (ROOT / 'ops' / 'usage-mismatch.json').write_text(json.dumps({'backup': expected, 'candidate': actual}))
            raise RuntimeError('candidate usage totals differ from the consistent backup')
        candidate = {'keys': keys, 'usage_totals': expected, 'source': 'verified full production backup'}
        path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2))
        event('restored_usage_verified', requests=sum(r['requests'] for r in actual), key_count=len(actual))
    print(json.dumps({'key_rows': len(keys), 'same_name_deleted_keys': extra,
                      'accounts': sql_json("SELECT json_agg(t) FROM (SELECT id,platform,type,status,schedulable,array(SELECT jsonb_object_keys(credentials)) AS credential_fields FROM accounts WHERE deleted_at IS NULL ORDER BY id) t;"),
                      'groups': sql_json("SELECT json_agg(t) FROM (SELECT id,name,platform FROM groups WHERE deleted_at IS NULL ORDER BY id) t;")}, ensure_ascii=False), flush=True)


def configure():
    rows = roster()
    if not (ROOT / 'ops' / 'migration-baseline.json').exists():
        raise RuntimeError('inventory and baseline are required before configuration')
    users = {u['email']: u for u in all_items('users')}
    # Validate supplied credentials before any mutations; existing users keep
    # their current passwords and do not require a password file.
    new_passwords = {row['login_email']: customer_password(row['login_email'])
                     for row in rows if row['login_email'] not in users}
    state_path = ROOT / 'ops' / 'migration-state.json'
    state = {'groups': {}, 'users': {}, 'deepseek_accounts': []}
    if state_path.exists():
        state = json.loads(state_path.read_text())
    def save():
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    groups = {g['name']: g for g in all_items('groups')}
    old_groups = {}
    for name, (account_id, old_group_id) in POOLS.items():
        old = api('GET', '/api/v1/admin/groups/{}'.format(old_group_id))
        old_groups[name] = old
        if name not in groups:
            payload = {k: old[k] for k in COPY_GROUP_FIELDS if k in old and old[k] is not None}
            payload.update(name=name, description='West personal accounts 2026-10-09', platform='composite',
                           rate_multiplier=1, is_exclusive=True, subscription_type='standard',
                           require_oauth_only=False, require_privacy_set=False,
                           daily_limit_usd=None, weekly_limit_usd=None, monthly_limit_usd=None)
            groups[name] = api('POST', '/api/v1/admin/groups', payload)
        group = groups[name]
        if group['platform'] != 'composite' or group['subscription_type'] != 'standard':
            raise RuntimeError('existing named group conflicts with candidate plan')
        gid = int(group['id'])
        state['groups'][name] = gid
        save()
        existing = api('GET', '/api/v1/admin/groups/{}/composite-routes'.format(gid))
        existing_models = {r['public_model'] for r in existing}
        routes = [('gpt-', 'prefix', 'openai'), ('codex-', 'prefix', 'openai'),
                  ('deepseek-flash', 'exact', 'deepseek'), ('deepseek-v4-pro', 'exact', 'deepseek')]
        for model, match_type, platform in routes:
            if model not in existing_models:
                api('POST', '/api/v1/admin/groups/{}/composite-routes'.format(gid),
                    dict(public_model=model, match_type=match_type, target_platform=platform,
                         endpoint='any', priority=0, enabled=True))
        account = api('GET', '/api/v1/admin/accounts/{}'.format(account_id))
        old_ids = account.get('group_ids') or [g['id'] for g in account.get('groups', [])]
        api('PUT', '/api/v1/admin/accounts/{}'.format(account_id),
            {'group_ids': sorted(set(old_ids + [gid])), 'confirm_mixed_channel_risk': True})
        event('resource_group_configured', group=name, group_id=gid, gpt_account_id=account_id)
    accounts = {a['name']: a for a in all_items('accounts')}
    state['deepseek_accounts'] = []
    for source_id, name in [(60, 'deepseek-native'), (70, 'aliyun-deepseek-native')]:
        # Admin GET intentionally redacts api_key; read only B's restored source row.
        source_credentials = sql_json('SELECT credentials FROM accounts WHERE id={};'.format(source_id))
        if not source_credentials.get('api_key'):
            raise RuntimeError('restored DeepSeek source has no API credential')
        if name not in accounts:
            source = api('GET', '/api/v1/admin/accounts/{}'.format(source_id))
            payload = {k: source[k] for k in ['credentials', 'extra', 'proxy_id', 'concurrency', 'priority',
                                             'rate_multiplier', 'load_factor'] if k in source and source[k] is not None}
            payload.update(name=name, notes='Candidate copy of account {}'.format(source_id), platform='deepseek',
                           type='apikey', group_ids=list(state['groups'].values()),
                           upstream_billing_probe_enabled=False, confirm_mixed_channel_risk=True)
            payload['credentials'] = source_credentials
            accounts[name] = api('POST', '/api/v1/admin/accounts', payload)
        if accounts[name]['platform'] != 'deepseek':
            raise RuntimeError('existing DeepSeek candidate account has wrong platform')
        api('PUT', '/api/v1/admin/accounts/{}'.format(accounts[name]['id']), {'credentials': source_credentials})
        state['deepseek_accounts'].append(int(accounts[name]['id']))
        save()
    # Keep existing channel pricing available on the corresponding new groups.
    for channel in all_items('channels'):
        original_ids = channel.get('group_ids', [])
        appended = [state['groups'][name] for name, (_, old_id) in POOLS.items() if old_id in original_ids]
        if appended:
            channel = api('GET', '/api/v1/admin/channels/{}'.format(channel['id']))
            pricing = channel.get('model_pricing', [])
            deepseek_prices = []
            for price in pricing:
                models = [m for m in price.get('models', []) if m.startswith('deepseek-')]
                if price.get('platform') == 'openai' and models:
                    copy = dict(price, platform='deepseek', models=models)
                    if not any(p.get('platform') == 'deepseek' and p.get('models') == models for p in pricing):
                        deepseek_prices.append(copy)
            mapping = dict(channel.get('model_mapping') or {})
            ds_mapping = {k: v for k, v in mapping.get('openai', {}).items() if k.startswith('deepseek-')}
            if ds_mapping:
                mapping['deepseek'] = dict(mapping.get('deepseek', {}), **ds_mapping)
            update = {'group_ids': sorted(set(original_ids + appended))}
            if deepseek_prices:
                update['model_pricing'] = pricing + deepseek_prices
            if ds_mapping:
                update['model_mapping'] = mapping
            api('PUT', '/api/v1/admin/channels/{}'.format(channel['id']), update)
    for index, row in enumerate(rows, 1):
        email, group_id = row['login_email'], state['groups'][row['resource_group']]
        if email not in users:
            payload = {'email': email, 'password': new_passwords[email], 'username': row['person_name'],
                       'notes': '开发组：{}；资源组：{}'.format(row['development_group'], row['resource_group']),
                       'role': 'user', 'balance': 100000, 'concurrency': 3, 'rpm_limit': 0,
                       'allowed_groups': [group_id], 'restrict_public_groups': True}
            users[email] = api('POST', '/api/v1/admin/users', payload)
        user = users[email]
        if user['role'] != 'user' or user['username'] != row['person_name']:
            raise RuntimeError('existing personal login conflicts with roster')
        uid = int(user['id'])
        state['users'][row['api_key_id']] = uid
        save()
        api('PUT', '/api/v1/admin/users/{}/platform-quotas'.format(uid),
            {'quotas': [{'platform': 'openai', 'daily_limit_usd': None, 'weekly_limit_usd': 300, 'monthly_limit_usd': None}]})
        if index % 10 == 0 or index == 74:
            event('personal_users_configured', count=index)
    state['configuration_complete'] = True
    save()


def transfer():
    rows = roster()
    state_path = ROOT / 'ops' / 'migration-state.json'
    state = json.loads(state_path.read_text())
    if not state.get('configuration_complete') or len(state['users']) != 74:
        raise RuntimeError('all 74 users must be configured first')
    baseline = json.loads((ROOT / 'ops' / 'migration-baseline.json').read_text())
    if not equal_totals(baseline['usage_totals'], usage_totals()):
        raise RuntimeError('usage changed before ownership transfer')
    original = {item['id']: item for item in baseline['keys']}
    current = {item['id']: item for item in key_inventory()}
    if set(original) != set(current) or any(original[k]['key_digest'] != current[k]['key_digest'] for k in original):
        raise RuntimeError('key IDs or secrets changed')
    mapping = []
    for row in rows:
        key_id = int(row['api_key_id'])
        if original[key_id]['deleted'] or original[key_id]['group_id'] != int(row['old_group_id']):
            raise RuntimeError('active key differs from approved source group')
        mapping.append((key_id, state['users'][str(key_id)], state['groups'][row['resource_group']], True))
    # Preserve same-name retired GPT history without reviving retired keys.
    people = {r['person_name']: r for r in rows}
    platform_by_group = {g['id']: g['platform'] for g in sql_json('SELECT json_agg(t) FROM (SELECT id,platform FROM groups) t;')}
    legacy = []
    for key in original.values():
        if key['deleted'] and key['name'] in people and platform_by_group.get(key['group_id']) == 'openai':
            row = people[key['name']]
            uid = state['users'][row['api_key_id']]
            mapping.append((key['id'], uid, key['group_id'], False))
            legacy.append({'key_id': key['id'], 'person_name': key['name'], 'user_id': uid})
    state['history_mapping'] = legacy
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    require_space(7)
    compose('stop', 'app')
    values = ','.join('({},{},{},{})'.format(k, u, g, 'true' if active else 'false') for k, u, g, active in mapping)
    sql = """BEGIN;
SET LOCAL statement_timeout='25min';
SET LOCAL lock_timeout='10s';
CREATE TEMP TABLE personal_migration_map(api_key_id bigint PRIMARY KEY,user_id bigint,group_id bigint,is_current boolean) ON COMMIT DROP;
INSERT INTO personal_migration_map VALUES %s;
UPDATE api_keys k SET user_id=m.user_id,group_id=CASE WHEN m.is_current THEN m.group_id ELSE k.group_id END,updated_at=now()
 FROM personal_migration_map m WHERE k.id=m.api_key_id AND (k.user_id IS DISTINCT FROM m.user_id OR (m.is_current AND k.group_id IS DISTINCT FROM m.group_id));
UPDATE usage_logs l SET user_id=m.user_id FROM personal_migration_map m
 WHERE l.api_key_id=m.api_key_id AND l.user_id IS DISTINCT FROM m.user_id;
TRUNCATE usage_dashboard_hourly_users,usage_dashboard_daily_users;
INSERT INTO usage_dashboard_hourly_users(bucket_start,user_id)
 SELECT DISTINCT date_trunc('hour',created_at AT TIME ZONE 'Asia/Shanghai') AT TIME ZONE 'Asia/Shanghai',user_id FROM usage_logs;
INSERT INTO usage_dashboard_daily_users(bucket_date,user_id)
 SELECT DISTINCT (created_at AT TIME ZONE 'Asia/Shanghai')::date,user_id FROM usage_logs;
UPDATE usage_dashboard_hourly a SET active_users=(SELECT count(*) FROM usage_dashboard_hourly_users u WHERE u.bucket_start=a.bucket_start);
UPDATE usage_dashboard_daily a SET active_users=(SELECT count(*) FROM usage_dashboard_daily_users u WHERE u.bucket_date=a.bucket_date);
COMMIT;
""" % values
    event('personal_history_transfer_running', current_keys=74, retired_history_keys=len(legacy))
    candidate_sql(sql)
    if not equal_totals(baseline['usage_totals'], usage_totals()):
        raise RuntimeError('usage reconciliation failed after transfer; candidate remains stopped')
    state['transfer_complete'] = True
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    compose('start', 'app')
    event('personal_history_transferred', current_keys=74, retired_history=legacy, free_bytes=require_space(5))


def verify():
    rows = roster()
    state = json.loads((ROOT / 'ops' / 'migration-state.json').read_text())
    if not state.get('transfer_complete'):
        raise RuntimeError('transfer is not complete')
    baseline = json.loads((ROOT / 'ops' / 'migration-baseline.json').read_text())
    current = {item['id']: item for item in key_inventory()}
    original = {item['id']: item for item in baseline['keys']}
    if set(current) != set(original):
        raise RuntimeError('key row count changed')
    for key_id, old in original.items():
        if current[key_id]['key_digest'] != old['key_digest'] or current[key_id]['deleted'] != old['deleted']:
            raise RuntimeError('a key secret or deletion state changed')
    for key_id in [55, 79, 90]:
        if current[key_id] != original[key_id]:
            raise RuntimeError('an excluded key changed')
    for row in rows:
        key_id = int(row['api_key_id'])
        if current[key_id]['user_id'] != state['users'][str(key_id)] or current[key_id]['group_id'] != state['groups'][row['resource_group']]:
            raise RuntimeError('personal ownership or resource group mismatch')
    user_ids = ','.join(str(uid) for uid in sorted(state['users'].values()))
    users = sql_json('SELECT json_agg(t) FROM (SELECT id,email,username,role,status,balance,concurrency,restrict_public_groups FROM users WHERE id IN ({})) t;'.format(user_ids))
    if len(users) != 74 or any(u['role'] != 'user' or u['status'] != 'active' or u['concurrency'] != 3 or not u['restrict_public_groups'] for u in users):
        raise RuntimeError('personal user settings mismatch')
    allowed = sql_json('SELECT json_agg(t) FROM (SELECT user_id,group_id FROM user_allowed_groups WHERE user_id IN ({})) t;'.format(user_ids))
    expected_allowed = {(state['users'][r['api_key_id']], state['groups'][r['resource_group']]) for r in rows}
    if len(allowed) != 74 or {(a['user_id'], a['group_id']) for a in allowed} != expected_allowed:
        raise RuntimeError('personal group permissions mismatch')
    key_ids = ','.join(str(int(r['api_key_id'])) for r in rows)
    wrong_owner_count = int(candidate_sql('SELECT count(*) FROM usage_logs l JOIN api_keys k ON k.id=l.api_key_id WHERE k.id IN ({}) AND l.user_id IS DISTINCT FROM k.user_id;'.format(key_ids)))
    if wrong_owner_count:
        raise RuntimeError('personal historical usage has incorrect ownership')
    quotas = sql_json('SELECT json_agg(t) FROM (SELECT user_id,platform,daily_limit_usd,weekly_limit_usd,monthly_limit_usd,weekly_usage_usd FROM user_platform_quotas WHERE deleted_at IS NULL AND user_id IN ({})) t;'.format(user_ids))
    if len(quotas) != 74 or any(q['platform'] != 'openai' or q['weekly_limit_usd'] != 300 or q['daily_limit_usd'] is not None or q['monthly_limit_usd'] is not None for q in quotas):
        raise RuntimeError('personal platform quota mismatch')
    if any(q['weekly_usage_usd'] != 0 for q in quotas) or any(u['balance'] != 100000 for u in users):
        raise RuntimeError('personal initial balance or first-week usage mismatch')
    actual = usage_totals()
    if not equal_totals(baseline['usage_totals'], actual):
        raise RuntimeError('historical usage totals changed')
    report = {'personal_users': 74, 'active_personal_keys': 74, 'gpt_groups': 8,
              'key_ids_and_secrets_preserved': True, 'history_totals_equal_to_backup': True,
              'historical_requests': sum(r['requests'] for r in actual),
              'retired_history_keys': state.get('history_mapping', []),
              'all_weekly_quotas_300': True, 'deepseek_platform_quotas': 0,
              'initial_weekly_usage_zero': all(q['weekly_usage_usd'] == 0 for q in quotas),
              'initial_balance_100000': all(u['balance'] == 100000 for u in users),
              'exclusions_preserved': [55, 79, 90]}
    (ROOT / 'ops' / 'migration-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['inventory', 'configure', 'transfer', 'verify'])
    args = parser.parse_args()
    if candidate_sql('SELECT current_database();').strip() != DB_NAME:
        raise RuntimeError('candidate database identity mismatch')
    require_space(5)
    globals()[args.phase]()


if __name__ == '__main__':
    main()
