#!/usr/bin/env python3
"""Inspect or repair completed-day active-user aggregates on B only."""
import argparse
import hashlib
import json
import os
import subprocess
import time

from candidate_ops import ROOT, DB, DB_NAME, candidate_sql, run
from candidate_migrate import sql_json, usage_totals, equal_totals, certified_history
from candidate_portal import guard
from candidate_accept import check, record

TABLES = ('usage_dashboard_daily_users', 'usage_dashboard_daily')
EXPECTED_SQL = """SELECT DISTINCT
 (created_at AT TIME ZONE 'Asia/Shanghai')::date AS bucket_date,user_id
 FROM usage_logs
 WHERE created_at < date_trunc('day',now() AT TIME ZONE 'Asia/Shanghai')
                    AT TIME ZONE 'Asia/Shanghai'"""


def inspect():
    return sql_json("""WITH expected AS (%s), actual AS (
 SELECT bucket_date,user_id FROM usage_dashboard_daily_users
 WHERE bucket_date < (now() AT TIME ZONE 'Asia/Shanghai')::date),
 missing AS (SELECT * FROM expected EXCEPT SELECT * FROM actual),
 extra AS (SELECT * FROM actual EXCEPT SELECT * FROM expected)
 SELECT json_build_object(
 'missing_memberships',(SELECT count(*) FROM missing),
 'extra_memberships',(SELECT count(*) FROM extra),
 'aggregate_mismatch_days',(SELECT count(*) FROM usage_dashboard_daily d
 WHERE d.bucket_date < (now() AT TIME ZONE 'Asia/Shanghai')::date
 AND d.active_users<>(SELECT count(*) FROM expected e WHERE e.bucket_date=d.bucket_date)),
 'through_local_date',((now() AT TIME ZONE 'Asia/Shanghai')::date-1)::text)
 """ % EXPECTED_SQL)


def needs_repair(result):
    return any(result[k] for k in
               ['missing_memberships', 'extra_memberships', 'aggregate_mismatch_days'])


def repair():
    before = inspect()
    if not needs_repair(before):
        print(json.dumps({'passed': True, 'changed': False, 'inspection': before}), flush=True)
        return
    # Make a private backup of exactly the two derived tables, before any write.
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    backup = ROOT / 'backups' / ('daily-users-before-' + stamp + '.dump')
    command = ['docker', 'exec', DB, 'pg_dump', '-U', 'sub2api', '-d', DB_NAME,
               '-Fc', '-Z1', '--lock-wait-timeout=5s']
    for table in TABLES:
        command += ['--table', 'public.' + table]
    with backup.open('xb') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, timeout=120)
    check(result.returncode == 0, 'derived-table backup failed; no repair performed')
    listing = run(['docker', 'exec', DB, 'pg_restore', '--list', '/backup/' + backup.name])
    check(all('TABLE DATA public ' + table + ' ' in listing for table in TABLES),
          'backup archive incomplete; no repair performed')
    # Use the already reconciled immutable history boundary, not in-flight calls.
    portal_before = certified_history()
    cutoff = portal_before['usage_max_id']
    historical = usage_totals(cutoff)
    check(equal_totals(portal_before['usage_totals'], historical),
          'certified history differs; no derived-table repair performed')
    manifest = dict(backup=str(backup), bytes=backup.stat().st_size,
                    sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
                    cutoff_id=cutoff, usage_totals=historical, before=before)
    manifest_path = backup.with_suffix('.json')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    # Lock derived tables only. Current requests can continue writing usage_logs.
    # Exclude today's buckets, and never update cost, token or request totals.
    changed = sql_json("""BEGIN;
 SET LOCAL lock_timeout='5s';
 SET LOCAL statement_timeout='60s';
 LOCK TABLE usage_dashboard_daily_users,usage_dashboard_daily IN SHARE ROW EXCLUSIVE MODE;
 CREATE TEMP TABLE expected_daily_users ON COMMIT DROP AS %s;
 CREATE UNIQUE INDEX ON expected_daily_users(bucket_date,user_id);
 CREATE TEMP TABLE protected_daily_rows ON COMMIT DROP AS
 SELECT bucket_date,to_jsonb(d)-'active_users' AS fields FROM usage_dashboard_daily d;
 CREATE TEMP TABLE unchanged_today ON COMMIT DROP AS
 SELECT * FROM usage_dashboard_daily_users
 WHERE bucket_date >= (now() AT TIME ZONE 'Asia/Shanghai')::date;
 CREATE TEMP TABLE repair_counts(label text,n bigint) ON COMMIT DROP;
 WITH removed AS (
 DELETE FROM usage_dashboard_daily_users d
 WHERE d.bucket_date < (now() AT TIME ZONE 'Asia/Shanghai')::date
 AND NOT EXISTS(SELECT 1 FROM expected_daily_users e
                WHERE e.bucket_date=d.bucket_date AND e.user_id=d.user_id)
 RETURNING 1) INSERT INTO repair_counts SELECT 'removed_memberships',count(*) FROM removed;
 WITH added AS (
 INSERT INTO usage_dashboard_daily_users(bucket_date,user_id)
 SELECT bucket_date,user_id FROM expected_daily_users ON CONFLICT DO NOTHING
 RETURNING 1) INSERT INTO repair_counts SELECT 'added_memberships',count(*) FROM added;
 WITH updated AS (
 UPDATE usage_dashboard_daily d
 SET active_users=(SELECT count(*) FROM expected_daily_users e WHERE e.bucket_date=d.bucket_date)
 WHERE d.bucket_date < (now() AT TIME ZONE 'Asia/Shanghai')::date
 AND d.active_users IS DISTINCT FROM
     (SELECT count(*) FROM expected_daily_users e WHERE e.bucket_date=d.bucket_date)
 RETURNING 1) INSERT INTO repair_counts SELECT 'updated_days',count(*) FROM updated;
 DO $audit$
 BEGIN
  IF EXISTS(SELECT 1 FROM protected_daily_rows p FULL JOIN usage_dashboard_daily d USING(bucket_date)
            WHERE p.fields IS DISTINCT FROM to_jsonb(d)-'active_users') THEN
   RAISE EXCEPTION 'non-active-user aggregate fields changed';
  END IF;
  IF EXISTS((SELECT * FROM unchanged_today EXCEPT SELECT * FROM usage_dashboard_daily_users)
            UNION ALL
            (SELECT * FROM usage_dashboard_daily_users
             WHERE bucket_date >= (now() AT TIME ZONE 'Asia/Shanghai')::date
             EXCEPT SELECT * FROM unchanged_today)) THEN
   RAISE EXCEPTION 'current-day memberships changed';
  END IF;
 END $audit$;
 SELECT json_object_agg(label,n) FROM repair_counts;
 COMMIT;
 """ % EXPECTED_SQL)
    after = inspect()
    check(not needs_repair(after), 'completed-day repair verification failed; backup retained')
    history_ok = equal_totals(historical, usage_totals(cutoff))
    check(history_ok, 'bounded usage totals changed; investigate without restoring live ledgers')
    record('daily_active_users_repair', dict(passed=True, before=before, after=after,
        changed=changed, backup=str(backup), backup_sha256=manifest['sha256'],
        usage_cutoff_id=cutoff, bounded_history_unchanged=history_ok,
        cost_token_request_aggregates_unchanged=True, current_day_untouched=True))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['inspect', 'repair'])
    args = parser.parse_args()
    guard()
    config = json.loads((ROOT / 'compose.json').read_text())
    check(config['services']['app']['environment'].get('TZ') == 'Asia/Shanghai',
          'candidate timezone differs from approved repair scope')
    if args.phase == 'inspect':
        print(json.dumps(inspect()), flush=True)
    else:
        repair()


if __name__ == '__main__':
    main()
