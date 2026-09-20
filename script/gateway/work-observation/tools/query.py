#!/usr/bin/env python3
"""Read-only administrator metadata query. Bodies remain in restricted records."""
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from analyze import utc

FILTERS = {'region', 'ingress', 'key_hash', 'session_hash', 'agent_hash', 'connection_id', 'upstream_request_id', 'client', 'outcome', 'id'}
FIELDS = '''region,id,at,ingress,client,kind,protocol,model,requested_model,reported_model,outcome,status,
    first_ms,total_ms,input_tokens,output_tokens,billed_cost,billing_matched,
    key_hash,session_hash,agent_hash,connection_id,direction,upstream_request_id,response_id,association,missing_count,quality,version'''


def query(path, filters, since=None, limit=50):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not 1 <= limit <= 100:
        raise ValueError('invalid_query_path_or_limit')
    if not filters.get('region') or any(key not in FILTERS for key in filters):
        raise ValueError('region_required_and_only_known_filters_allowed')
    clauses, values = [], []
    for key, value in filters.items():
        if value is not None:
            clauses.append(key + '=?')
            values.append(value)
    if since:
        clauses.append('at>=?')
        values.append(utc(since))
    db = sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in db.execute('SELECT ' + FIELDS + ' FROM events WHERE ' +
                ' AND '.join(clauses) + ' ORDER BY at DESC,id LIMIT ?', (*values, limit + 1))]
        return {'plane': 'actual', 'region': filters['region'], 'events': rows[:limit],
                'has_more': len(rows) > limit, 'contains_bodies': False}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    for key in sorted(FILTERS):
        parser.add_argument('--' + key.replace('_', '-'), required=key == 'region')
    parser.add_argument('--since')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    try:
        result = query(args.db, {key: getattr(args, key) for key in FILTERS}, args.since, args.limit)
    except (OSError, ValueError, sqlite3.Error):
        raise SystemExit('metadata_query_failed')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
