#!/usr/bin/env python3
"""Replay metadata-only spools into a durable, idempotent regional ledger.

The ledger is operational accounting, not a replacement for Sub2API billing.
Only the explicit allowlist below is stored; arbitrary JSON fields are rejected.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3

COUNTERS = ('input_tokens', 'cache_hit_tokens', 'cache_miss_tokens', 'output_tokens')
FLAGS = ('attempt', 'success', 'response_cache_hit', 'classification_cache_hit', 'upgrade', 'downgrade', 'usage_reported')
STRINGS = ('request_id', 'region', 'api_key_id', 'effective_model', 'effective_reasoning_effort',
           'response_model', 'response_id', 'upstream_request_id', 'upstream_client_request_id', 'error_type', 'decision', 'rule_version', 'model_version')
PURPOSES = ('business', 'classification', 'action_review', 'image', 'security', 'security_check')


def normalized(raw):
    source = json.loads(raw)
    if not isinstance(source, dict):
        raise ValueError('usage event must be an object')
    event = {key: str(source.get(key) or '') for key in STRINGS}
    if any(len(value) > 512 for value in event.values()):
        raise ValueError('usage identifier exceeds limit')
    if not all(event[key] for key in ('region', 'api_key_id', 'effective_model')):
        raise ValueError('usage identity is missing')
    event['purpose'] = source.get('purpose') or 'business'
    if event['purpose'] not in PURPOSES:
        raise ValueError('unknown usage purpose')
    at = datetime.datetime.fromisoformat(source['at'].replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('usage timestamp needs a timezone')
    event['at'] = at.astimezone(datetime.timezone.utc).isoformat()
    event['date'] = at.astimezone(datetime.timezone.utc).date().isoformat()
    for key in COUNTERS:
        value = source.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError('invalid token counter')
        event[key] = value
    for key in FLAGS:
        value = source.get(key, False)
        if not isinstance(value, bool):
            raise ValueError('invalid usage flag')
        event[key] = value
    status = source.get('http_status', 0)
    if not isinstance(status, int) or status < 0 or status > 599:
        raise ValueError('invalid HTTP status')
    event['http_status'] = status
    for key in ('latency_ms','queue_wait_ms'):
        value=source.get(key,0)
        if not isinstance(value,int) or value<0:
            raise ValueError('invalid latency')
        event[key]=value
    # Explicitly retain known tokens even if the final transport failed.
    if not event['attempt'] and any(event[key] for key in COUNTERS):
        raise ValueError('cache replay cannot add provider tokens')
    # Hash the original line, including Go's nanosecond timestamp; Python's
    # microsecond timestamp conversion must not merge distinct chunk attempts.
    event['event_id'] = hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest()
    return event


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError('ledger symlink rejected')
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        os.chmod(self.path, 0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS ledger_meta(version INTEGER NOT NULL);
          INSERT INTO ledger_meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM ledger_meta);
          CREATE TABLE IF NOT EXISTS events(
            event_id TEXT PRIMARY KEY, date TEXT NOT NULL, region TEXT NOT NULL,
            key_hash TEXT NOT NULL, purpose TEXT NOT NULL, model TEXT NOT NULL,
            effort TEXT NOT NULL, request_id TEXT NOT NULL, payload TEXT NOT NULL,
            exported INTEGER NOT NULL DEFAULT 0);
          CREATE INDEX IF NOT EXISTS event_bucket ON events(date,region,key_hash,purpose,model,effort);
          CREATE TABLE IF NOT EXISTS spool_offsets(
            file_id TEXT PRIMARY KEY, byte_offset INTEGER NOT NULL, prefix_hash TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS key_mapping(
            region TEXT NOT NULL,key_hash TEXT NOT NULL,api_key_id INTEGER NOT NULL,
            PRIMARY KEY(region,key_hash));
        ''')
        if self.db.execute('SELECT version FROM ledger_meta').fetchall() != [(1,)]:
            raise ValueError('unsupported ledger schema')

    def ingest(self, path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('regular spool file required')
        inserted, read = 0, 0
        with path.open('rb') as stream, self.db:
            info = os.fstat(stream.fileno())
            file_id = str(info.st_dev) + ':' + str(info.st_ino)
            saved = self.db.execute('SELECT byte_offset,prefix_hash FROM spool_offsets WHERE file_id=?', (file_id,)).fetchone()
            offset = saved[0] if saved else 0
            # Track a fixed prefix only after a complete first record exists.
            first = stream.readline(1 << 20)
            if not first.endswith(b'\n'):
                if len(first) >= 1 << 20:
                    raise ValueError('spool line exceeds limit')
                return {'read': 0, 'inserted': 0, 'partial_tail': bool(first)}
            prefix = hashlib.sha256(first).hexdigest()
            if saved and (info.st_size < offset or saved[1] != prefix):
                raise ValueError('spool was truncated or inode reused; inspect before replay')
            stream.seek(offset)
            partial = False
            while True:
                raw = stream.readline(1 << 20)
                if not raw:
                    break
                if not raw.endswith(b'\n'):
                    if len(raw) >= 1 << 20:
                        raise ValueError('spool line exceeds limit')
                    partial = True
                    break
                event = normalized(raw)
                cursor = self.db.execute('INSERT OR IGNORE INTO events(event_id,date,region,key_hash,purpose,model,effort,request_id,payload) VALUES(?,?,?,?,?,?,?,?,?)',
                    (event['event_id'], event['date'], event['region'], event['api_key_id'], event['purpose'], event['effective_model'],
                     event['effective_reasoning_effort'], event['request_id'], json.dumps(event, separators=(',', ':'))))
                inserted += cursor.rowcount
                read += 1
                offset = stream.tell()
            self.db.execute('INSERT INTO spool_offsets VALUES(?,?,?) ON CONFLICT(file_id) DO UPDATE SET byte_offset=excluded.byte_offset,prefix_hash=excluded.prefix_hash',
                            (file_id, offset, prefix))
        return {'read': read, 'inserted': inserted, 'partial_tail': partial}

    def map_keys(self, mapping):
        with self.db:
            for row in mapping:
                if not isinstance(row['api_key_id'], int) or row['api_key_id'] <= 0 or not row['key_hash'].startswith('key-hmac-v1:'):
                    raise ValueError('invalid numeric Key mapping')
                existing = self.db.execute('SELECT api_key_id FROM key_mapping WHERE region=? AND key_hash=?', (row['region'],row['key_hash'])).fetchone()
                if existing and existing[0] != row['api_key_id']:
                    raise ValueError('numeric Key mapping conflict')
                self.db.execute('INSERT INTO key_mapping VALUES(?,?,?) ON CONFLICT(region,key_hash) DO UPDATE SET api_key_id=excluded.api_key_id',
                                (row['region'], row['key_hash'], row['api_key_id']))

    def daily(self):
        buckets = {}
        for (raw, numeric) in self.db.execute('SELECT e.payload,k.api_key_id FROM events e LEFT JOIN key_mapping k ON e.region=k.region AND e.key_hash=k.key_hash ORDER BY e.date,e.event_id'):
            event = json.loads(raw)
            key = tuple(event[k] for k in ('date', 'region', 'api_key_id', 'purpose', 'effective_model', 'effective_reasoning_effort'))
            if key not in buckets:
                buckets[key] = dict(zip(('date', 'region', 'api_key_hash', 'purpose', 'effective_model', 'effective_reasoning_effort'), key),
                                    api_key_id=numeric, requests=0, events=0, attempts=0, successes=0, failures=0,
                                    response_cache_hits=0, classification_cache_hits=0, upgrades=0, downgrades=0, unknown_usage_attempts=0, unavailable=0,
                                    **{k: 0 for k in COUNTERS}, _requests=set())
            row = buckets[key]
            row['_requests'].add(event['request_id'] or event['event_id'])
            row['events'] += 1
            row['unavailable'] += int(event['decision']=='unavailable')
            row['unknown_usage_attempts'] += int(event['attempt'] and not event['usage_reported'])
            for source, dest in [('attempt','attempts'),('success','successes'),('response_cache_hit','response_cache_hits'),
                                 ('classification_cache_hit','classification_cache_hits'),('upgrade','upgrades'),('downgrade','downgrades')]:
                row[dest] += int(event[source])
            row['failures'] += int(not event['success'])
            for counter in COUNTERS:
                row[counter] += event[counter]
        for row in buckets.values():
            row['requests'] = len(row.pop('_requests'))
        return list(buckets.values())

    def close(self):
        self.db.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--spool', type=Path, action='append', default=[])
    parser.add_argument('--key-map', type=Path)
    parser.add_argument('--daily', action='store_true')
    args = parser.parse_args()
    ledger = Ledger(args.database)
    try:
        if args.key_map:
            if args.key_map.stat().st_mode & 0o077:
                parser.error('Key mapping must be private')
            ledger.map_keys(json.loads(args.key_map.read_text()))
        imported = [ledger.ingest(path) for path in args.spool]
        print(json.dumps({'imported': imported, **({'daily': ledger.daily()} if args.daily else {})}))
    finally:
        ledger.close()


if __name__ == '__main__':
    main()
