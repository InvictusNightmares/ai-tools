#!/usr/bin/env python3
"""Remove only certified migration copies and the retired A runtime after acceptance."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import time

from cutover_merge import ROOT, OPS, CONTAINER, SOURCE_NETWORK, check, guard, run, sql, value
from cutover_control import state, inspect

OLD = Path('/opt/sub2api-deploy')
OLD_VOLUME = 'a00b5e0fb568f11e81ae8cd0615857dd8e7c145b20672b8b4c63f527fdc0c801'
OLD_CONTAINERS = ('sub2api', 'sub2api-proxy', 'sub2api-postgres', 'sub2api-redis')
OLD_RUNTIME = ('data', 'postgres_data', 'redis_data', 'gateway', '.env', 'docker-compose.yml')
BACKUPS = (
    'full.list', 'candidate.list', 'manifest.json', 'customer-portal-before-manifest.json',
    'candidate-before-customer-portal.dump', 'production-before-candidate.dump',
    'monitor-v1-before-delete.dump', 'production-config.tar.gz',
    'daily-users-before-20261009T093039Z.json', 'daily-users-before-20261009T093039Z.dump',
    'cutover-final-a.dump', 'cutover-final-b.dump', 'cutover-final-b-redis.rdb',
)
PRIVATE_OPS = (
    'customer-portal-before.json', 'native-features-before.json', 'monitor-v2-before.json',
    'compose-before-public-preview.json', 'compose-before-http-only.json',
    'customer-concurrency-before-20261009T081751Z.json', 'acceptance-state.json',
    'acceptance-error.bin', 'websocket-error.json', 'sql-error.log',
    'backups/runtime-repair-20261009T092938Z',
)
PRIVATE_CUTOVER = (
    'source-reader.json', 'compose-before.json', 'nginx-before.conf',
    'rehearsal-recovery-before.json', 'rehearsal-merge.sql', 'final-merge.sql',
    'quota-acceptance-restored.json', 'merge-error.log',
)
AUDIT_TABLES = (
    'activation_accounts_before', 'activation_quotas_before', 'b_certificates', 'b_only_original',
    'b_raw_boundary', 'build_state', 'excluded_qa', 'source_map',
)


def write_private(path, data):
    temporary = path.with_name('.' + path.name + '.tmp')
    safe_path(temporary, path.parent)
    with temporary.open('w') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))
    directory = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def containers():
    ids = run(['docker', 'ps', '-aq']).split()
    return json.loads(run(['docker', 'inspect'] + ids)) if ids else []


def safe_path(path, parent):
    check(parent.resolve() == parent and parent.is_dir(), 'cleanup parent differs')
    check(not path.is_symlink() and path.resolve() == path, 'cleanup path is redirected')
    check(str(path).startswith(str(parent) + '/'), 'cleanup target outside exact parent')


def remove(path, parent):
    if not path.exists():
        return
    safe_path(path, parent)
    mounts = run(['findmnt', '-rn', '-o', 'TARGET']).splitlines()
    check(not any(m == str(path) or m.startswith(str(path) + '/') for m in mounts),
          'cleanup target contains a host mount')
    if path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def healthy():
    for name in ('sub2api-next', 'sub2api-next-proxy', CONTAINER, 'sub2api-next-redis'):
        item = inspect(name)
        check(item['State']['Running'] and item['State'].get('Health', {}).get('Status') == 'healthy',
              'new runtime is not healthy: ' + name)
        check(not any(m['Source'] == str(OLD) or m['Source'].startswith(str(OLD) + '/')
                      or m.get('Name') == OLD_VOLUME for m in item['Mounts']),
              'new runtime still depends on old files')
    config = json.loads((ROOT / 'compose.json').read_text())
    check(config['services']['app']['environment']['DATABASE_DBNAME'] == 'sub2api_next', 'new DB differs')
    check(config['services']['app']['environment']['TOKEN_REFRESH_ENABLED'] == 'true', 'OAuth refresh disabled')
    check('http://app:8080' in (ROOT / 'gateway' / 'nginx.conf').read_text(), 'formal upstream differs')


def export_audit():
    target = OPS / 'evidence'
    target.mkdir(exist_ok=True)
    queries = {
        'source-map.csv': 'SELECT source_table,source_id,target_id,source_hash FROM cutover_audit.source_map ORDER BY source_table,source_id',
        'b-certificates.csv': 'SELECT table_name,certificate FROM cutover_audit.b_certificates ORDER BY table_name',
        'b-retained-history.csv': 'SELECT id,facts_hash FROM cutover_audit.b_only_original ORDER BY id',
        'excluded-qa-ids.csv': 'SELECT id,user_id,api_key_id FROM cutover_audit.excluded_qa ORDER BY id',
        'build-state.csv': 'SELECT name,complete FROM cutover_audit.build_state ORDER BY name',
        'b-raw-boundary.csv': 'SELECT created_at FROM cutover_audit.b_raw_boundary',
    }
    result = {}
    for name, query in queries.items():
        payload = sql('sub2api_next', 'COPY (' + query + ') TO STDOUT WITH CSV HEADER') + '\n'
        file = target / name
        safe_path(file, target)
        write_private(file, payload)
        expected = hashlib.sha256(payload.encode()).hexdigest()
        check(sha(file) == expected, 'audit export readback differs')
        result[name] = {'bytes': file.stat().st_size, 'sha256': expected}
    return result


def main():
    os.umask(0o077)
    guard()
    lock = (OPS / 'cleanup.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    x = state()
    check(x['stage'] in ('open', 'cleanup_started', 'cleaned'), 'service must be accepted and open')
    accepted = json.loads((OPS / 'final-acceptance.json').read_text())
    opened = json.loads((OPS / 'public-entry-check.json').read_text())
    check(accepted.get('passed') is True and accepted.get('freeze_id') == x['freeze_id'], 'acceptance missing')
    check(opened.get('passed') is True and opened.get('freeze_id') == x['freeze_id'], 'open entry check missing')
    healthy()
    report_path = OPS / 'cleanup.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {
        'freeze_id': x['freeze_id'], 'started_epoch': int(time.time()), 'steps': []}
    check(report['freeze_id'] == x['freeze_id'], 'cleanup belongs to another freeze')
    if x['stage'] == 'cleaned':
        check(report.get('completed') is True, 'completed cleanup receipt missing')
        print(json.dumps({'cleanup_completed': True, 'already_completed': True}), flush=True)
        return

    def record(step, **data):
        report.update(data)
        if step not in report['steps']:
            report['steps'].append(step)
        write_private(report_path, json.dumps(report, indent=2))
        print(json.dumps({'cleanup_step': step}), flush=True)

    if x['stage'] == 'open':
        check(not (OPS / 'quota-acceptance-before.json').exists(), 'quota restoration is pending')
        restored = json.loads((OPS / 'quota-acceptance-restored.json').read_text())
        check(restored.get('_freeze_id') == x['freeze_id'], 'quota restoration belongs to another freeze')
        inventory = containers()
        by_name = {c['Name'].lstrip('/'): c for c in inventory}
        check(all(n in by_name for n in OLD_CONTAINERS), 'old runtime inventory differs')
        check(not by_name['sub2api']['State']['Running'] and not by_name['sub2api-proxy']['State']['Running'],
              'retired app or formal proxy is running')
        check(any(m.get('Name') == OLD_VOLUME and m['Destination'] == '/var/lib/postgresql'
                  for m in by_name['sub2api-postgres']['Mounts']), 'old PostgreSQL volume differs')
        consumers = {c['Name'].lstrip('/') for c in inventory if any(
            m.get('Name') == OLD_VOLUME or m['Source'] == str(OLD) or m['Source'].startswith(str(OLD) + '/')
            for m in c['Mounts'])}
        check(consumers.issubset(set(OLD_CONTAINERS)), 'unrelated container depends on retired data')
        backup_names = {p.name for p in (ROOT / 'backups').iterdir()}
        check(backup_names == set(BACKUPS), 'backup inventory differs; inspect before cleanup')
        for side in ('a', 'b'):
            path = ROOT / 'backups' / ('cutover-final-' + side + '.dump')
            receipt = json.loads((OPS / ('final-' + side + '-dump.json')).read_text())
            check(receipt['freeze_id'] == x['freeze_id'] and sha(path) == receipt['sha256'], 'archive hash differs')
        record('inventory_certified', old_container_ids={n: by_name[n]['Id'] for n in OLD_CONTAINERS},
               old_image_id=by_name['sub2api']['Image'], backup_files=sorted(backup_names))
        x['stage'] = 'cleanup_started'
        write_private(OPS / 'control.json', json.dumps(x, indent=2))

    if 'audit_exported' not in report['steps']:
        record('audit_exported', evidence=export_audit())
    if 'temporary_databases_removed' not in report['steps']:
        check(sql('postgres', "SELECT count(*) FROM pg_stat_activity WHERE datname='cutover_previous'") == '0',
              'previous database has active sessions')
        if sql('postgres', "SELECT count(*) FROM pg_database WHERE datname='cutover_previous'") == '1':
            sql('postgres', 'DROP DATABASE cutover_previous')
        check(sql('postgres', "SELECT count(*) FROM pg_database WHERE datname IN('cutover_final','cutover_rehearsal')") == '0',
              'unexpected staging database remains')
        if sql('sub2api_next', "SELECT count(*) FROM pg_namespace WHERE nspname='cutover_audit'") == '1':
            audit_tables = value('sub2api_next', "SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='cutover_audit'")
            check(audit_tables == sorted(AUDIT_TABLES), 'audit table inventory differs')
            check(sql('sub2api_next', "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='cutover_audit' AND c.relkind NOT IN('r','i')") == '0', 'unexpected audit object')
            sql('sub2api_next', 'BEGIN; DROP TABLE ' + ','.join('cutover_audit.' + t for t in AUDIT_TABLES)
                + ' RESTRICT; DROP SCHEMA cutover_audit RESTRICT; COMMIT;')
        record('temporary_databases_removed')
    if 'retired_containers_removed' not in report['steps']:
        by_name = {c['Name'].lstrip('/'): c for c in containers()}
        for name in OLD_CONTAINERS:
            if name not in by_name:
                continue
            check(by_name[name]['Id'] == report['old_container_ids'][name], 'retired container identity changed')
            if by_name[name]['State']['Running']:
                check(name in ('sub2api-postgres', 'sub2api-redis'), 'old app restarted')
                run(['docker', 'stop', '--time', '60', name])
            run(['docker', 'rm', name])
        record('retired_containers_removed')
    if 'retired_data_removed' not in report['steps']:
        remaining = containers()
        check(not any(m.get('Name') == OLD_VOLUME or m['Source'] == str(OLD) or m['Source'].startswith(str(OLD) + '/')
                      for c in remaining for m in c['Mounts']), 'old files still mounted')
        volumes = run(['docker', 'volume', 'ls', '-q']).splitlines()
        if OLD_VOLUME in volumes:
            run(['docker', 'volume', 'rm', OLD_VOLUME])
        for name in OLD_RUNTIME:
            remove(OLD / name, OLD)
        network_names = run(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines()
        if SOURCE_NETWORK in network_names:
            net = json.loads(run(['docker', 'network', 'inspect', SOURCE_NETWORK]))[0]
            check(not net.get('Containers'), 'old network still has consumers')
            run(['docker', 'network', 'rm', SOURCE_NETWORK])
        record('retired_data_removed', preserved_unrelated_old_root_entries=sorted(p.name for p in OLD.iterdir()))
    if 'migration_backups_removed' not in report['steps']:
        for name in BACKUPS:
            remove(ROOT / 'backups' / name, ROOT / 'backups')
        for name in PRIVATE_OPS:
            remove(ROOT / 'ops' / name, ROOT / 'ops')
        for name in PRIVATE_CUTOVER:
            remove(OPS / name, OPS)
        check(not list((ROOT / 'backups').iterdir()), 'a migration backup remains')
        for side in ('a', 'b'):
            path = OPS / ('final-' + side + '-dump.json')
            receipt = json.loads(path.read_text())
            receipt['archive_removed_after_verified_acceptance'] = True
            write_private(path, json.dumps(receipt, indent=2))
        record('migration_backups_removed')
    healthy()
    check(not set(OLD_CONTAINERS).intersection(c['Name'].lstrip('/') for c in containers()), 'old container remains')
    check(sql('sub2api_next', "SELECT count(*) FROM pg_namespace WHERE nspname IN('cutover_audit','source_a','source_b','source_a_facts')") == '0',
          'temporary schema remains')
    x.pop('gate_secret', None)
    x.update(stage='cleaned', cleaned_at_epoch=int(time.time()))
    record('cleanup_completed', completed=True, free_gib=round(shutil.disk_usage(str(ROOT)).free / 1024**3, 2))
    write_private(OPS / 'control.json', json.dumps(x, indent=2))


if __name__ == '__main__':
    main()
