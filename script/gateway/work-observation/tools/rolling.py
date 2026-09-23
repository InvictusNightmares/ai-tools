#!/usr/bin/env python3
"""Bounded local analysis and optional offline replay ticks.

Read final immutable records directly, verify their digest, and keep only
metadata and evidence references in a private analysis DB.  When explicitly
configured, ``semantic.py`` may call private offline Guard/Auto preview
endpoints; it never executes production tools or changes production routing.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time

import analyze
import health
import semantic

MAX_RECORD = 256 << 20
PREFIX = re.compile(r'^\s*\{"sha256":"([a-f0-9]{64})","event":')
DEFAULT_INGEST_INTERVAL_SECONDS = 300
MAX_INGEST_INTERVAL_SECONDS = 24 * 60 * 60


def _run_id(now):
    """Stable human-facing batch id; contains no source or account data."""
    return now.astimezone(timezone.utc).strftime('%Y%m%d-%H%M%S')


def _record_run(root, result):
    """Append bounded body-free metadata for the standalone review page.

    The rolling worker's existing ``tick.json`` is intentionally a latest
    snapshot.  This small JSONL ledger lets an operator see each analysis
    tick without opening the source store or copying request/response text.
    A write failure never changes the analysis result or forwarding path.
    """
    path = root / 'runs.jsonl'
    allowed = ('run_id', 'at', 'status', 'reason', 'scanned', 'review_jobs_added', 'review_pending',
               'review_deferred', 'semantic_review', 'semantic_reviewed', 'semantic_processed',
               'semantic_complete', 'semantic_unavailable', 'semantic_failed',
               'semantic_pending', 'semantic_deferred', 'semantic_guard_reused', 'semantic_auto_reused',
               'invalid_sources', 'body_copies_created')
    row = {key: result[key] for key in allowed if key in result}
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('a', encoding='utf-8') as stream:
            os.chmod(path, 0o600)
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        # Keep the ledger bounded even if a timer is left running for months.
        if path.stat().st_size > 2 << 20:
            lines = path.read_text(encoding='utf-8').splitlines()[-1000:]
            temporary = path.with_suffix('.tmp')
            temporary.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
    except (OSError, ValueError, TypeError):
        return False
    return True


def read_record(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD:
            raise ValueError('unsupported_record_size_or_type')
        raw = stream.read(MAX_RECORD + 1)
    if len(raw) > MAX_RECORD:
        raise ValueError('oversized_record')
    text = raw.decode('utf-8')
    match = PREFIX.match(text)
    if not match:
        raise ValueError('invalid_record_envelope')
    event, end = json.JSONDecoder().raw_decode(text, match.end())
    if text[end:].strip() != '}':
        raise ValueError('invalid_record_envelope')
    digest = hashlib.sha256(text[match.end():end].encode()).hexdigest()
    if digest != match.group(1):
        raise ValueError('record_checksum_mismatch')
    if event.get('content_policy') != 'literal_text_attachment_metadata':
        raise ValueError('unsupported_content_policy')
    return event, digest


def setup(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS sources (
            path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
            sha TEXT NOT NULL, region TEXT NOT NULL, event_id TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_failures (
            path TEXT PRIMARY KEY, reason TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_jobs (
            region TEXT NOT NULL, event_id TEXT NOT NULL, source_path TEXT NOT NULL,
            sha TEXT NOT NULL, at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            scope TEXT NOT NULL DEFAULT 'event_requires_context',
            PRIMARY KEY(region,event_id)
        );
        CREATE TABLE IF NOT EXISTS ticks (name TEXT PRIMARY KEY, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scan_cursors (
            root TEXT PRIMARY KEY, day TEXT NOT NULL, position INTEGER NOT NULL
        );
    ''')
    semantic.ensure_schema(db)


def records(root, cursor=('', 0)):
    """Only collector partitions; never recursively follow an arbitrary symlink."""
    events = root / 'events'
    if events.is_symlink():
        raise ValueError('symlink_store_refused')
    with os.scandir(events) as entries:
        days=sorted((d for d in entries if re.fullmatch(r'\d{4}-\d{2}-\d{2}',d.name)),key=lambda d:d.name)
        for day in days:
            if day.name < cursor[0]:continue
            if not day.is_dir(follow_symlinks=False):
                raise ValueError('invalid_partition')
            with os.scandir(day.path) as entries:
                for position,entry in enumerate(entries,1):
                    if day.name==cursor[0] and position<=cursor[1]:continue
                    if entry.name.endswith('.json'):
                        yield Path(entry.path), entry.stat(follow_symlinks=False), (day.name,position)


def ingest_batch(db, stores, now, max_events=1000, seconds=20, review_limit=10000):
    result = Counter()
    deadline = time.monotonic() + seconds
    cutoff = (now - timedelta(days=30)).isoformat()
    pending = db.execute("""SELECT COUNT(*) FROM review_jobs j JOIN events e
        ON e.region=j.region AND e.id=j.event_id
        WHERE j.state='pending' AND e.kind='http_exchange'""").fetchone()[0]
    # Rotate the first store to avoid one busy region starving the other.
    order = list(stores)
    last = db.execute("SELECT at FROM ticks WHERE name='store_rotation'").fetchone()
    rotate = int(last[0]) if last else 0
    order = order[rotate % len(order):] + order[:rotate % len(order)]
    db.execute("INSERT OR REPLACE INTO ticks VALUES ('store_rotation',?)", (str(rotate + 1),))
    for store in order:
        root = Path(store['store_dir'])
        cursor=db.execute('SELECT day,position FROM scan_cursors WHERE root=?',(str(root),)).fetchone() or ('',0)
        try:
            for path, info, position in records(root, cursor):
                if time.monotonic() >= deadline or result['read'] >= max_events:
                    result['budget_exhausted'] += 1
                    return dict(result)
                # Resume directory traversal as well as ingestion after a budget
                # boundary. Otherwise a large known prefix can starve new files.
                # Directory offsets are hints only: restart a complete sweep at
                # EOF, so insertions/deletions/reordering are eventually revisited.
                db.execute('INSERT OR REPLACE INTO scan_cursors VALUES (?,?,?)',(str(root),*position))
                result['scanned'] += 1
                previous = db.execute('SELECT size,mtime_ns,sha FROM sources WHERE path=?', (str(path),)).fetchone()
                if previous and previous[0] == info.st_size and previous[1] == info.st_mtime_ns:
                    continue
                result['read'] += 1
                try:
                    event, digest = read_record(path)
                    if event.get('region') != store['region'] or event.get('ingress') != store['ingress']:
                        raise ValueError('configured_ingress_mismatch')
                    if previous and previous[2] != digest:
                        raise ValueError('immutable_record_changed')
                    at = analyze.utc(event['at'])
                    if at <= cutoff:
                        result['expired_skipped'] += 1
                        continue
                    # Same transaction for the metadata row and cursor. A crash
                    # can safely replay the source without skipping an event.
                    result['inserted_or_enriched'] += analyze.ingest(db, event)
                    db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?)',
                               (str(path), info.st_size, info.st_mtime_ns, digest, event['region'], event['id'], at))
                    db.execute('DELETE FROM source_failures WHERE path=?', (str(path),))
                    # A websocket message is a transport fragment, not a
                    # complete task.  Queue only completed HTTP exchanges for
                    # semantic replay; the raw websocket records remain in
                    # the evidence store and continue to count in reports.
                    if event['kind'] == 'http_exchange':
                        if pending < review_limit:
                            cursor = db.execute('INSERT OR IGNORE INTO review_jobs(region,event_id,source_path,sha,at) VALUES (?,?,?,?,?)',
                                                (event['region'], event['id'], str(path), digest, at))
                            pending += cursor.rowcount
                            result['review_jobs_added'] += cursor.rowcount
                        else:
                            result['review_queue_deferred'] += 1
                except (OSError, ValueError, KeyError, TypeError):
                    # Do not include parse errors: they can quote original bodies.
                    result['invalid_records'] += 1
                    db.execute('INSERT OR REPLACE INTO source_failures VALUES (?,?,?)',
                               (str(path), 'record_validation_failed', now.isoformat()))
                if result['read'] % 50 == 0:
                    db.commit()
            db.execute('DELETE FROM scan_cursors WHERE root=?',(str(root),))
            result['sweeps_completed'] += 1
        except (OSError, ValueError):
            result['stores_unavailable'] += 1
    return dict(result)


def replenish_review_queue(db, limit):
    pending = db.execute("SELECT COUNT(*) FROM review_jobs WHERE state='pending'").fetchone()[0]
    available = max(0, limit - pending)
    if available:
        db.execute('''INSERT OR IGNORE INTO review_jobs(region,event_id,source_path,sha,at)
            SELECT s.region,s.event_id,s.path,s.sha,s.at FROM sources s
            JOIN events e ON e.region=s.region AND e.id=s.event_id
            LEFT JOIN review_jobs j ON j.region=s.region AND j.event_id=s.event_id
            WHERE j.event_id IS NULL AND e.kind='http_exchange' ORDER BY s.at LIMIT ?''', (available,))


def prune(db, now):
    cutoff = (now - timedelta(days=30)).isoformat()
    counts = {}
    for table in ('events', 'sources', 'source_failures', 'review_jobs'):
        counts[table] = db.execute(f'DELETE FROM {table} WHERE at<=?', (cutoff,)).rowcount
    counts['semantic_reviews'] = db.execute("DELETE FROM semantic_reviews WHERE reviewed_at IS NOT NULL AND reviewed_at<=?", (cutoff,)).rowcount
    return counts


def due(db, name, now, interval, force):
    row = db.execute('SELECT at FROM ticks WHERE name=?', (name,)).fetchone()
    return force or not row or now - datetime.fromisoformat(row[0]) >= interval


def mark(db, name, now):
    db.execute('INSERT OR REPLACE INTO ticks VALUES (?,?)', (name, now.isoformat()))


def tick(config, now=None, force=False):
    now = now or datetime.now(timezone.utc)
    os.umask(0o077)
    root = Path(config['analysis_dir'])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise ValueError('symlink_analysis_root_refused')
    with (root / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'already_running'}
        state_path = root / 'health-state.json'
        try:
            previous = json.loads(state_path.read_text())
        except (OSError, ValueError):
            previous = {}
        health_reports, health_state = [], {}
        for store in config['stores']:
            name = store['region'] + '/' + store['ingress']
            try:
                current = json.loads(Path(store['status_file']).read_text())
                report = health.evaluate(current, previous.get(name), now, shutil.disk_usage(store['store_dir']).free)
                health_state[name] = {k: current[k] for k in ('started_at', *health.COUNTERS) if k in current}
            except (OSError, ValueError, TypeError):
                report = {'status': 'degraded', 'issues': [{'reason': 'status_unavailable'}], 'complete_capture_claim': False}
            report['region'], report['ingress'] = store['region'], store['ingress']
            health_reports.append(report)
        health.atomic_json(state_path, health_state)
        health.atomic_json(root / 'health.json', {'at': now.isoformat(), 'stores': health_reports})
        # Dedicated bounded analysis allocation, separate from collector buffers.
        analysis_bytes = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
        if analysis_bytes >= config['analysis_bytes'] or shutil.disk_usage(root).free < 64 << 20:
            result = {'run_id': _run_id(now), 'at': now.isoformat(), 'status': 'degraded', 'reason': 'analysis_capacity_exhausted', 'complete_analysis_claim': False}
            health.atomic_json(root / 'tick.json', result)
            _record_run(root, result)
            return result
        db = analyze.connect(root / 'index.sqlite')
        try:
            setup(db)
            result = {'run_id': _run_id(now), 'at': now.isoformat(), 'plane': 'actual', 'status': 'ok', 'body_copies_created': 0}
            result['pruned'] = prune(db, now)
            # The collector is continuous.  Index each new bounded slice on
            # the same five-minute timer as the semantic worker instead of
            # waiting for the old hourly catch-up window.  The scan cursor
            # and ingest budget still make this safe when a store is busy.
            ingest_interval = timedelta(seconds=config.get('ingest_interval_seconds', DEFAULT_INGEST_INTERVAL_SECONDS))
            if due(db, 'ingest', now, ingest_interval, force):
                result['incremental'] = ingest_batch(db, config['stores'], now, config['max_events'], config['max_seconds'], config['review_queue_limit'])
                replenish_review_queue(db, config['review_queue_limit'])
                # Continue budget-limited catch-up on the next five-minute
                # tick.  A failed store must remain due so we do not silently
                # advance the cursor and claim that the queue is current.
                if not result['incremental'].get('budget_exhausted') and not result['incremental'].get('stores_unavailable'):
                    mark(db, 'ingest', now)
                result['recent'] = analyze.report(db, now, 1)
                health.atomic_json(root / 'incremental.json', result['recent'])
                # Flatten only body-free counters into the run ledger/UI.
                result['scanned'] = result['incremental'].get('scanned', 0)
                result['review_jobs_added'] = result['incremental'].get('review_jobs_added', 0)
            # Keep the hourly report as a compatibility/reporting cadence. It
            # no longer controls ingestion, so a slow or skipped report cannot
            # delay new samples reaching the bounded semantic queue.
            if due(db, 'hourly_report', now, timedelta(hours=1), force):
                hourly = result.get('recent') or analyze.report(db, now, 1)
                health.atomic_json(root / 'hourly.json', hourly)
                mark(db, 'hourly_report', now)
            # Semantic replay is deliberately after ingestion and before the
            # daily report. It has its own bounded queue and can only call the
            # explicitly configured private Guard/Auto route-preview services.
            semantic_result = semantic.run(db, config.get('semantic', {}), now)
            if due(db, 'daily', now, timedelta(days=1), force):
                health.atomic_json(root / 'daily.json', {'at': now.isoformat(),
                    'recent': analyze.report(db, now, 24), 'rolling': analyze.report(db, now, 720),
                    'semantic_review': semantic_result['status'],
                    'semantic_reviewed': semantic_result.get('complete', 0),
                    'semantic_pending': semantic_result.get('pending', 0),
                    'semantic_auth_error': semantic_result.get('auth_error'),
                    'task_type_coverage': 'unknown'})
                mark(db, 'daily', now)
            result['review_pending'] = db.execute("""SELECT COUNT(*) FROM review_jobs j JOIN events e
                ON e.region=j.region AND e.id=j.event_id
                WHERE j.state='pending' AND e.kind='http_exchange'""").fetchone()[0]
            result['review_deferred'] = db.execute('''SELECT COUNT(*) FROM sources s JOIN events e ON e.region=s.region AND e.id=s.event_id
                LEFT JOIN review_jobs j ON j.region=s.region AND j.event_id=s.event_id WHERE j.event_id IS NULL AND e.kind='http_exchange' ''').fetchone()[0]
            result['invalid_sources'] = db.execute('SELECT COUNT(*) FROM source_failures').fetchone()[0]
            result['semantic_review'] = semantic_result['status']
            result['semantic_reviewed'] = semantic_result.get('complete', 0)
            result['semantic_processed'] = semantic_result.get('processed', 0)
            result['semantic_complete'] = semantic_result.get('complete', 0)
            result['semantic_unavailable'] = semantic_result.get('unavailable', 0)
            result['semantic_failed'] = semantic_result.get('failed', 0)
            result['semantic_pending'] = semantic_result.get('pending', 0)
            result['semantic_deferred'] = semantic_result.get('deferred', 0)
            result['semantic_guard_reused'] = semantic_result.get('guard_reused', 0)
            result['semantic_auto_reused'] = semantic_result.get('auto_reused', 0)
            if semantic_result.get('auth_error'):
                result['semantic_auth_error'] = semantic_result['auth_error']
            if semantic_result.get('failed') or semantic_result.get('deferred'):
                result['status'] = 'degraded'
            result['complete_analysis_claim'] = False
            if result['invalid_sources'] or result['review_deferred'] or any(r['status'] != 'ok' for r in health_reports):
                result['status'] = 'degraded'
            db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            health.atomic_json(root / 'tick.json', result)
            _record_run(root, result)
            return result
        finally:
            db.close()


def read_config(path):
    config = json.loads(Path(path).read_text())
    defaults = {'max_events': 1000, 'max_seconds': 20, 'review_queue_limit': 10000, 'analysis_bytes': 2 << 30}
    for key, value in defaults.items():
        config.setdefault(key, value)
        if type(config[key]) is not int or not 1 <= config[key] <= value:
            raise ValueError('invalid_analysis_limit')
    config.setdefault('ingest_interval_seconds', DEFAULT_INGEST_INTERVAL_SECONDS)
    if (type(config['ingest_interval_seconds']) is not int or
            not 1 <= config['ingest_interval_seconds'] <= MAX_INGEST_INTERVAL_SECONDS):
        raise ValueError('invalid_ingest_interval')
    semantic_config = config.setdefault('semantic', {})
    if not isinstance(semantic_config, dict):
        raise ValueError('invalid_semantic_config')
    semantic_config.setdefault('enabled', False)
    semantic_config.setdefault('timeout_seconds', 3)
    semantic_config.setdefault('max_jobs', 20)
    semantic_config.setdefault('max_workers', semantic.DEFAULT_MAX_WORKERS)
    semantic_config.setdefault('max_attempts', semantic.DEFAULT_MAX_ATTEMPTS)
    semantic_config.setdefault('stage_reuse_ttl_seconds', semantic.DEFAULT_STAGE_REUSE_TTL_SECONDS)
    if type(semantic_config['enabled']) is not bool:
        raise ValueError('invalid_semantic_enabled')
    if type(semantic_config['max_jobs']) is not int or not 1 <= semantic_config['max_jobs'] <= 1000:
        raise ValueError('invalid_semantic_limit')
    if type(semantic_config['max_workers']) is not int or not 1 <= semantic_config['max_workers'] <= semantic.MAX_WORKERS:
        raise ValueError('invalid_semantic_workers')
    if type(semantic_config['max_attempts']) is not int or not 1 <= semantic_config['max_attempts'] <= semantic.MAX_ATTEMPTS:
        raise ValueError('invalid_max_attempts')
    if (type(semantic_config['stage_reuse_ttl_seconds']) is not int or
            not 0 <= semantic_config['stage_reuse_ttl_seconds'] <= semantic.MAX_STAGE_REUSE_TTL_SECONDS):
        raise ValueError('invalid_stage_reuse_ttl')
    if type(semantic_config['timeout_seconds']) not in (int, float) or not 0.1 <= semantic_config['timeout_seconds'] <= 30:
        raise ValueError('invalid_semantic_timeout')
    if semantic_config['enabled']:
        # Validate before a timer starts. This prevents a typo from sending
        # captured employee text to a public endpoint. Regional mappings are
        # mandatory when present so a US event can never fall back to Tokyo.
        region_configs = semantic_config.get('regions')
        if region_configs is not None:
            if not isinstance(region_configs, dict) or not region_configs:
                raise ValueError('invalid_semantic_regions')
            base = {key: value for key, value in semantic_config.items() if key != 'regions'}
            for region, override in region_configs.items():
                if not isinstance(region, str) or not isinstance(override, dict):
                    raise ValueError('invalid_semantic_region_config')
                resolved = dict(base)
                resolved.update(override)
                if not resolved.get('guard_url') or not resolved.get('auto_url'):
                    raise ValueError('semantic_region_endpoints_required')
                if (type(resolved.get('stage_reuse_ttl_seconds')) is not int or
                        not 0 <= resolved['stage_reuse_ttl_seconds'] <= semantic.MAX_STAGE_REUSE_TTL_SECONDS):
                    raise ValueError('invalid_stage_reuse_ttl')
                semantic._local_url(resolved['guard_url'])
                semantic._local_url(resolved['auto_url'])
                for role in ('guard', 'auto'):
                    auth_file = resolved.get(role + '_auth_file', '')
                    if auth_file and not Path(auth_file).is_absolute():
                        raise ValueError('semantic_auth_file_must_be_absolute')
                    if resolved.get(role + '_auth_header', 'Authorization') not in ('Authorization', 'X-API-Key'):
                        raise ValueError('semantic_auth_header_invalid')
        else:
            if not semantic_config.get('guard_url') or not semantic_config.get('auto_url'):
                raise ValueError('semantic_endpoints_required')
            semantic._local_url(semantic_config['guard_url'])
            semantic._local_url(semantic_config['auto_url'])
            for role in ('guard', 'auto'):
                auth_file = semantic_config.get(role + '_auth_file', '')
                if auth_file and not Path(auth_file).is_absolute():
                    raise ValueError('semantic_auth_file_must_be_absolute')
                if semantic_config.get(role + '_auth_header', 'Authorization') not in ('Authorization', 'X-API-Key'):
                    raise ValueError('semantic_auth_header_invalid')
    if not config.get('stores') or not Path(config['analysis_dir']).is_absolute():
        raise ValueError('invalid_analysis_paths')
    paths = [Path(config['analysis_dir']).resolve()]
    names = set()
    for store in config['stores']:
        if not Path(store['store_dir']).is_absolute() or not Path(store['status_file']).is_absolute():
            raise ValueError('absolute_store_paths_required')
        name = (store['region'], store['ingress'])
        if name in names:
            raise ValueError('duplicate_store_identity')
        names.add(name)
        paths.append(Path(store['store_dir']).resolve())
    for i, path in enumerate(paths):
        if any(path == other or path in other.parents or other in path.parents for other in paths[i+1:]):
            raise ValueError('overlapping_analysis_store_paths')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--force', action='store_true', help='run due analysis immediately within the same resource bounds')
    args = parser.parse_args()
    try:
        result = tick(read_config(args.config), force=args.force)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        # Generic stderr is intentional: no malformed source text leaks to logs.
        raise SystemExit('rolling_analysis_failed; inspect restricted state')
    print(json.dumps({k: result[k] for k in ('at', 'status', 'reason', 'review_pending', 'review_deferred', 'complete_analysis_claim') if k in result}))


if __name__ == '__main__':
    main()
