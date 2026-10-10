#!/usr/bin/env python3
"""Prepare the isolated US West candidate. Never starts or changes production."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
import time

ROOT = Path('/opt/sub2api-next')
PRODUCTION = Path('/opt/sub2api-deploy')
DB = 'sub2api-next-postgres'
DB_NAME = 'sub2api_next'
APP_IMAGE = 'ghcr.io/wei-shaw/sub2api:0.2.15'
OMIT_DATA = {'ops_system_logs', 'ops_error_logs', 'ops_system_metrics',
             'ops_metrics_hourly', 'ops_metrics_daily'}
GIB = 1024 ** 3


def event(phase, **values):
    result = dict(phase=phase, time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **values)
    (ROOT / 'ops' / 'progress.json').write_text(json.dumps(result))
    print(json.dumps(result), flush=True)


def run(args, timeout=120, stdin=None):
    p = subprocess.run(args, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('command failed: {} (exit {}): {}'.format(args[0], p.returncode, p.stderr[-1000:]))
    return p.stdout


def require_space(gib):
    free = shutil.disk_usage(str(ROOT)).free
    if free < gib * GIB:
        raise RuntimeError('insufficient free disk: {} bytes, require {} GiB'.format(free, gib))
    return free


def compose(*args):
    return run(['docker', 'compose', '-p', 'sub2api-next', '-f', str(ROOT / 'compose.json')] + list(args), timeout=180)


def candidate_sql(sql):
    # Fixed container/database targets; caller cannot substitute the production DB.
    p = subprocess.run(['docker', 'exec', '-i', DB, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
                        '-U', 'sub2api', '-d', DB_NAME, '-At'], timeout=1800, input=sql,
                       universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        (ROOT / 'ops' / 'sql-error.log').write_text(p.stderr)
        raise RuntimeError('candidate SQL failed; details saved in private sql-error.log')
    return p.stdout


def snapshot():
    backup = ROOT / 'backups' / 'production-before-candidate.dump'
    if backup.exists():
        raise RuntimeError('backup already exists; refusing to overwrite')
    require_space(12)
    with tarfile.open(str(ROOT / 'backups' / 'production-config.tar.gz'), 'w:gz') as tf:
        for relative in ['.env', 'docker-compose.yml', 'docker-compose.local.yml',
                         'data/config.yaml', 'gateway/nginx.conf', 'gateway/all-hours-api-keys.conf']:
            path = PRODUCTION / relative
            if path.is_file():
                tf.add(str(path), arcname=relative, recursive=False)
    event('backup_running')
    stderr_path = ROOT / 'ops' / 'backup.stderr'
    with backup.open('xb') as out, stderr_path.open('wb') as err:
        p = subprocess.Popen(['docker', 'exec', 'sub2api-postgres', 'nice', '-n', '10',
                              'pg_dump', '-U', 'sub2api', '-d', 'sub2api', '-Fc', '-Z1',
                              '--lock-wait-timeout=5s'], stdout=out, stderr=err)
        while p.poll() is None:
            if shutil.disk_usage(str(ROOT)).free < 9 * GIB:
                p.terminate()
                p.wait(timeout=30)
                raise RuntimeError('backup stopped at disk reserve; partial backup retained')
            time.sleep(3)
        if p.returncode:
            raise RuntimeError('backup failed; inspect private backup.stderr')
    # Read the archive directory using the matching PostgreSQL 18 client.
    listing = run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '0.5',
                   '-v', str(ROOT / 'backups') + ':/backup:ro', 'postgres:18-alpine',
                   'pg_restore', '--list', '/backup/' + backup.name])
    (ROOT / 'backups' / 'full.list').write_text(listing)
    filtered = []
    omitted = []
    for line in listing.splitlines():
        parts = line.split()
        skip = len(parts) > 6 and parts[3:5] == ['TABLE', 'DATA'] and parts[5] == 'public' and parts[6] in OMIT_DATA
        if skip:
            omitted.append(parts[6])
        else:
            filtered.append(line)
    if set(omitted) != OMIT_DATA:
        raise RuntimeError('archive telemetry table set differs from reviewed scope')
    (ROOT / 'backups' / 'candidate.list').write_text('\n'.join(filtered) + '\n')
    digest = hashlib.sha256()
    with backup.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    manifest = dict(bytes=backup.stat().st_size, sha256=digest.hexdigest(), omitted_candidate_data=sorted(omitted))
    (ROOT / 'backups' / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    event('backup_verified', **manifest)


def provision():
    if not (ROOT / 'backups' / 'manifest.json').exists():
        raise RuntimeError('verified backup required')
    if (ROOT / 'compose.json').exists():
        raise RuntimeError('candidate configuration exists; inspect before retrying')
    require_space(10)
    event('pulling_official_image')
    run(['docker', 'pull', APP_IMAGE], timeout=600)
    image = json.loads(run(['docker', 'image', 'inspect', APP_IMAGE]))[0]
    version = image['Config'].get('Labels', {}).get('org.opencontainers.image.version')
    if version not in ('0.2.15', 'v0.2.15'):
        raise RuntimeError('official image version label mismatch')
    pinned_app = next(d for d in image['RepoDigests'] if d.startswith('ghcr.io/wei-shaw/sub2api@'))
    current = json.loads(run(['docker', 'inspect', 'sub2api', 'sub2api-postgres', 'sub2api-redis']))
    pg_uid = int(run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'id', current[1]['Image'], '-u', 'postgres']).strip())
    pg_gid = int(run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'id', current[1]['Image'], '-g', 'postgres']).strip())
    os.chown(str(ROOT / 'postgres_data'), pg_uid, pg_gid)
    old_env = dict(item.split('=', 1) for item in current[0]['Config']['Env'])
    db_pass, redis_pass = secrets.token_hex(24), secrets.token_hex(24)
    environment = {
        'AUTO_SETUP': 'true', 'RUN_MODE': 'standard', 'SERVER_HOST': '0.0.0.0',
        'SERVER_PORT': '8080', 'SERVER_MODE': 'release', 'TZ': 'Asia/Shanghai',
        'DATABASE_HOST': 'postgres', 'DATABASE_PORT': '5432', 'DATABASE_USER': 'sub2api',
        'DATABASE_PASSWORD': db_pass, 'DATABASE_DBNAME': DB_NAME, 'DATABASE_SSLMODE': 'disable',
        'DATABASE_MAX_OPEN_CONNS': '15', 'DATABASE_MAX_IDLE_CONNS': '3',
        'REDIS_HOST': 'redis', 'REDIS_PORT': '6379', 'REDIS_PASSWORD': redis_pass,
        'REDIS_DB': '0', 'REDIS_POOL_SIZE': '32', 'REDIS_MIN_IDLE_CONNS': '2',
        'JWT_SECRET': secrets.token_hex(32), 'JWT_EXPIRE_HOUR': '24',
        'TOTP_ENCRYPTION_KEY': old_env.get('TOTP_ENCRYPTION_KEY', ''),
        'TOKEN_REFRESH_ENABLED': 'false', 'OPS_ENABLED': 'false',
        'DASHBOARD_AGGREGATION_ENABLED': 'false', 'USAGE_CLEANUP_ENABLED': 'false',
        'SETUP_MIGRATION_TIMEOUT_SECONDS': '1800', 'GOMEMLIMIT': '480MiB',
        'SECURITY_URL_ALLOWLIST_ENABLED': 'false',
        'SECURITY_URL_ALLOWLIST_ALLOW_INSECURE_HTTP': 'true',
        'SECURITY_URL_ALLOWLIST_ALLOW_PRIVATE_HOSTS': 'true',
    }
    # Preserve known gateway compatibility knobs; no old program or custom mounts.
    environment.update({k: v for k, v in old_env.items() if k.startswith('GATEWAY_')})
    # Official v0.2.15 does not recheck standard-mode personal quota on later WS turns.
    environment.update({'GATEWAY_OPENAI_WS_ENABLED': 'false',
                        'GATEWAY_OPENAI_WS_FORCE_HTTP': 'true',
                        'GATEWAY_OPENAI_WS_MODE_ROUTER_V2_ENABLED': 'false'})
    common = {'restart': 'unless-stopped', 'networks': ['candidate'],
              'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}}
    services = {
        'postgres': dict(common, image=current[1]['Image'], container_name=DB,
            mem_limit='768m', cpus=0.75,
            environment={'POSTGRES_USER': 'sub2api', 'POSTGRES_PASSWORD': db_pass,
                         'POSTGRES_DB': DB_NAME, 'PGDATA': '/var/lib/postgresql/data', 'TZ': 'Asia/Shanghai'},
            volumes=[str(ROOT / 'postgres_data') + ':/var/lib/postgresql:Z',
                     str(ROOT / 'backups') + ':/backup:ro'],
            command=['postgres', '-c', 'shared_buffers=128MB', '-c', 'work_mem=8MB',
                     '-c', 'maintenance_work_mem=128MB', '-c', 'max_connections=30',
                     '-c', 'max_wal_size=512MB'],
            healthcheck={'test': ['CMD-SHELL', 'pg_isready -U sub2api -d ' + DB_NAME],
                         'interval': '10s', 'timeout': '5s', 'retries': 10}),
        'redis': dict(common, image=current[2]['Image'], container_name='sub2api-next-redis',
            mem_limit='128m', cpus=0.15, environment={'REDISCLI_AUTH': redis_pass},
            volumes=[str(ROOT / 'redis_data') + ':/data:Z'],
            command=['redis-server', '--requirepass', redis_pass, '--appendonly', 'yes',
                     '--maxmemory', '96mb', '--maxmemory-policy', 'allkeys-lru'],
            healthcheck={'test': ['CMD', 'redis-cli', 'ping'], 'interval': '10s', 'timeout': '5s', 'retries': 10}),
        'app': dict(common, image=pinned_app, container_name='sub2api-next',
            mem_limit='640m', cpus=0.5, security_opt=['no-new-privileges:true'],
            ports=['127.0.0.1:18080:8080'], volumes=[str(ROOT / 'data') + ':/app/data:Z'],
            environment=environment,
            depends_on={'postgres': {'condition': 'service_healthy'}, 'redis': {'condition': 'service_healthy'}},
            healthcheck={'test': ['CMD', 'curl', '-fsS', 'http://127.0.0.1:8080/health'],
                         'interval': '15s', 'timeout': '5s', 'retries': 6, 'start_period': '30m'}),
    }
    (ROOT / 'compose.json').write_text(json.dumps({'services': services, 'networks': {'candidate': {}}}, indent=2))
    (ROOT / 'ops' / 'image.json').write_text(json.dumps({'image': pinned_app, 'version': version, 'id': image['Id']}))
    (ROOT / 'ops' / 'admin-api-key').write_text('ak_' + secrets.token_hex(32))
    compose('config', '--quiet')
    compose('up', '-d', 'postgres', 'redis')
    event('candidate_datastores_started', image=pinned_app, version=version, free_bytes=require_space(9))


def restore():
    require_space(9)
    count = candidate_sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public';").strip()
    if count != '0':
        raise RuntimeError('candidate database is not empty; refusing to overwrite')
    event('restore_running')
    with (ROOT / 'ops' / 'restore.stdout').open('wb') as out, (ROOT / 'ops' / 'restore.stderr').open('wb') as err:
        p = subprocess.Popen(['docker', 'exec', DB, 'pg_restore', '-U', 'sub2api', '-d', DB_NAME,
                              '--exit-on-error', '--no-owner', '--no-privileges',
                              '--use-list=/backup/candidate.list', '/backup/production-before-candidate.dump'],
                             stdout=out, stderr=err)
        while p.poll() is None:
            if shutil.disk_usage(str(ROOT)).free < 5 * GIB:
                p.terminate()
                p.wait(timeout=30)
                compose('stop', 'postgres')
                raise RuntimeError('restore stopped at disk reserve; candidate database retained')
            time.sleep(3)
        if p.returncode:
            raise RuntimeError('restore failed; inspect private restore.stderr')
    event('restored_before_app_start', db_bytes=int(candidate_sql('SELECT pg_database_size(current_database());').strip()),
          free_bytes=require_space(5))


def isolate():
    running = run(['docker', 'ps', '--format', '{{.Names}}']).splitlines()
    if 'sub2api-next' in running:
        raise RuntimeError('candidate app must be stopped before isolation')
    if candidate_sql('SELECT current_database();').strip() != DB_NAME:
        raise RuntimeError('candidate database identity mismatch')
    batch_tables = candidate_sql("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'batch_image_%';").splitlines()
    jobs = 0
    for table in batch_tables:
        if not table.replace('_', '').isalnum():
            raise RuntimeError('unexpected batch table identifier')
        jobs += int(candidate_sql('SELECT count(*) FROM "{}";'.format(table)).strip())
    if jobs:
        raise RuntimeError('batch image records exist in snapshot; inspect their states before starting candidate')
    admin_key = (ROOT / 'ops' / 'admin-api-key').read_text().strip()
    if not admin_key.startswith('ak_') or not all(c in '0123456789abcdef' for c in admin_key[3:]):
        raise RuntimeError('unexpected candidate admin key format')
    sql = """BEGIN;
UPDATE accounts SET credentials=credentials-'refresh_token' WHERE type='oauth';
UPDATE scheduled_test_plans SET enabled=false;
UPDATE channel_monitors SET enabled=false;
INSERT INTO settings(key,value,updated_at)
VALUES ('ops_runtime_log_config','{"request_retention_days":0}',now())
ON CONFLICT (key) DO UPDATE SET value=(settings.value::jsonb || excluded.value::jsonb)::text,updated_at=now();
INSERT INTO settings(key,value,updated_at) VALUES
 ('channel_monitor_enabled','false',now()),
 ('ops_monitoring_enabled','false',now()),
 ('ops_realtime_monitoring_enabled','false',now()),
 ('registration_enabled','false',now()),
 ('backend_mode_enabled','false',now()),
 ('email_verify_enabled','false',now()),
 ('backup_schedule','{"enabled":false}',now()),
 ('admin_api_key','%s',now())
ON CONFLICT (key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at;
COMMIT;
""" % admin_key
    candidate_sql(sql)
    remaining = int(candidate_sql("SELECT count(*) FROM accounts WHERE type='oauth' AND credentials ? 'refresh_token';").strip())
    if remaining:
        raise RuntimeError('candidate refresh tokens remain')
    (ROOT / 'ops' / 'isolation.json').write_text(json.dumps({'refresh_tokens': 0, 'background_refresh': False,
                                                          'active_probes': False, 'batch_jobs': jobs}))
    event('candidate_isolated', refresh_tokens=0, batch_jobs=jobs)


def start():
    require_space(5)
    if not (ROOT / 'ops' / 'isolation.json').exists():
        raise RuntimeError('candidate isolation must run first')
    configuration = json.loads((ROOT / 'compose.json').read_text())
    app = configuration['services']['app']
    if app['environment']['DATABASE_DBNAME'] != DB_NAME or app['environment']['TOKEN_REFRESH_ENABLED'] != 'false':
        raise RuntimeError('candidate configuration changed')
    if app['ports'] != ['127.0.0.1:18080:8080']:
        raise RuntimeError('candidate must use the private test entry')
    for service in configuration['services'].values():
        if any(str(PRODUCTION) in mount for mount in service.get('volumes', [])):
            raise RuntimeError('production volume referenced by candidate')
    compose('up', '-d', 'app')
    event('candidate_app_started', free_bytes=require_space(5))


def preview():
    """User-authorized public preview, only after historical migration verification."""
    report = ROOT / 'ops' / 'migration-verification.json'
    if not report.exists() or not json.loads(report.read_text()).get('history_totals_equal_to_backup'):
        raise RuntimeError('verified candidate migration is required before public preview')
    path = ROOT / 'compose.json'
    config = json.loads(path.read_text())
    app = config['services']['app']
    if app['container_name'] != 'sub2api-next' or app['environment']['DATABASE_DBNAME'] != DB_NAME:
        raise RuntimeError('candidate identity mismatch')
    if app.get('ports') not in (['127.0.0.1:18080:8080'], ['0.0.0.0:18080:8080']):
        raise RuntimeError('unexpected candidate port mapping')
    before = ROOT / 'ops' / 'compose-before-public-preview.json'
    if not before.exists():
        before.write_text(path.read_text())
    app['ports'] = ['0.0.0.0:18080:8080']
    path.write_text(json.dumps(config, indent=2))
    compose('up', '-d', '--no-deps', 'app')
    event('public_preview_enabled', port=18080, production_unchanged=True)


def http_only():
    path = ROOT / 'compose.json'
    config = json.loads(path.read_text())
    app = config['services']['app']
    if app['container_name'] != 'sub2api-next' or app['environment']['DATABASE_DBNAME'] != DB_NAME:
        raise RuntimeError('candidate identity mismatch')
    before = ROOT / 'ops' / 'compose-before-http-only.json'
    if not before.exists():
        before.write_text(path.read_text())
    app['environment'].update({'GATEWAY_OPENAI_WS_ENABLED': 'false',
                               'GATEWAY_OPENAI_WS_FORCE_HTTP': 'true',
                               'GATEWAY_OPENAI_WS_MODE_ROUTER_V2_ENABLED': 'false'})
    path.write_text(json.dumps(config, indent=2))
    compose('up', '-d', '--no-deps', 'app')
    event('candidate_http_only', websocket=False, official_binary_unchanged=True)


def native_features():
    """Restore official management services after candidate history reconciliation.

    The user retains HTTP/SSE for the v0.2.15 WS quota limitation. OAuth refresh
    stays isolated until the production instance is frozen for a future cutover.
    """
    require_space(5)
    report = ROOT / 'ops' / 'migration-verification.json'
    if not report.exists() or not json.loads(report.read_text()).get('history_totals_equal_to_backup'):
        raise RuntimeError('verified candidate migration required')
    path = ROOT / 'compose.json'
    config = json.loads(path.read_text())
    app = config['services']['app']
    if (app['container_name'] != 'sub2api-next'
            or app['environment']['DATABASE_DBNAME'] != DB_NAME
            or candidate_sql('SELECT current_database();').strip() != DB_NAME):
        raise RuntimeError('candidate identity mismatch')
    if app['environment'].get('TOKEN_REFRESH_ENABLED') != 'false':
        raise RuntimeError('candidate must remain isolated from production OAuth refresh')
    for service in config['services'].values():
        if any(str(PRODUCTION) in mount for mount in service.get('volumes', [])):
            raise RuntimeError('production volume referenced by candidate')
    pending = int(candidate_sql("SELECT count(*) FROM usage_cleanup_tasks WHERE status IN ('pending','running');").strip())
    probes = int(candidate_sql('SELECT count(*) FROM channel_monitors WHERE enabled;').strip())
    if pending or probes:
        raise RuntimeError('inherited pending cleanup or active probes require inspection')
    names = ['ops_monitoring_enabled', 'ops_realtime_monitoring_enabled', 'channel_monitor_enabled',
             'ops_advanced_settings', 'ops_runtime_log_config', 'ops_email_notification_config']
    rows = json.loads(candidate_sql("SELECT coalesce(json_agg(t),'[]') FROM (SELECT key,value FROM settings WHERE key IN ({})) t;".format(
        ','.join("'" + name + "'" for name in names))))
    settings = {r['key']: r['value'] for r in rows}
    email = json.loads(settings.get('ops_email_notification_config', '{}'))
    if any(email.get(section, {}).get('enabled', False) for section in ['alert', 'report']):
        raise RuntimeError('candidate outbound notification configuration requires inspection')
    backup = ROOT / 'ops' / 'native-features-before.json'
    if not backup.exists():
        backup.write_text(json.dumps({'compose': config, 'settings': rows}, indent=2))
    # Keep request history indefinitely while allowing native monitoring retention.
    candidate_sql("""BEGIN;
INSERT INTO settings(key,value,updated_at) VALUES
 ('ops_monitoring_enabled','true',now()),
 ('ops_realtime_monitoring_enabled','true',now()),
 ('channel_monitor_enabled','true',now())
ON CONFLICT (key) DO UPDATE SET value=excluded.value,updated_at=now();
INSERT INTO settings(key,value,updated_at)
VALUES ('ops_runtime_log_config','{"request_retention_days":0}',now())
ON CONFLICT (key) DO UPDATE SET value=(settings.value::jsonb || excluded.value::jsonb)::text,updated_at=now();
INSERT INTO settings(key,value,updated_at)
VALUES ('ops_advanced_settings','{}',now()) ON CONFLICT (key) DO NOTHING;
UPDATE settings SET value=(value::jsonb || jsonb_build_object(
 'data_retention',coalesce(value::jsonb->'data_retention','{}'::jsonb) || '{"cleanup_enabled":true}'::jsonb,
 'aggregation',coalesce(value::jsonb->'aggregation','{}'::jsonb) || '{"aggregation_enabled":true}'::jsonb,
 'auto_refresh_enabled',true))::text,updated_at=now()
WHERE key='ops_advanced_settings';
COMMIT;""")
    app['environment'].update({'OPS_ENABLED': 'true',
                               'DASHBOARD_AGGREGATION_ENABLED': 'true',
                               'USAGE_CLEANUP_ENABLED': 'true'})
    path.write_text(json.dumps(config, indent=2))
    compose('config', '--quiet')
    compose('up', '-d', '--no-deps', 'app')
    event('candidate_native_features_enabled', monitoring=True, realtime=True,
          dashboard_aggregation=True, usage_cleanup_service=True, channel_monitor=True,
          oauth_refresh=False, gpt_websocket=False, production_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['snapshot', 'provision', 'restore', 'isolate', 'start', 'preview', 'http_only', 'native_features'])
    args = parser.parse_args()
    os.umask(0o077)
    if not PRODUCTION.is_dir() or str(ROOT.resolve()) != '/opt/sub2api-next':
        raise RuntimeError('unexpected host or candidate path')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    for child in ['ops', 'backups', 'data', 'postgres_data', 'redis_data']:
        (ROOT / child).mkdir(mode=0o700, exist_ok=True)
    try:
        globals()[args.phase]()
    except Exception as exc:
        event('failed', operation=args.phase, error=str(exc))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
