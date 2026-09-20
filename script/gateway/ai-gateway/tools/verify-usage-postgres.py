#!/usr/bin/env python3
"""Verify exporter on session-local temporary PostgreSQL tables, leaving no DB objects."""
import argparse
import json
from pathlib import Path
import tempfile

from usage_ledger import Ledger
import usage_sync


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--region',choices=tuple(usage_sync.HOSTS),required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gateway-usage-sql-') as directory:
        root=Path(directory);ledger=Ledger(root/'fixture.sqlite');spool=root/'usage.jsonl'
        base=dict(at='2026-09-16T00:00:00Z',region=args.region,api_key_id='key-hmac-v1:synthetic',request_id='fixture',purpose='business',
                  effective_model='gpt-5.6-luna',attempt=True,success=True,usage_reported=True,input_tokens=10,cache_hit_tokens=6,cache_miss_tokens=4,output_tokens=2)
        rows=[base,dict(base,at='2026-09-16T00:00:01Z',success=False),
              dict(base,at='2026-09-16T00:00:02Z',request_id='cache',attempt=False,response_cache_hit=True,input_tokens=0,cache_hit_tokens=0,cache_miss_tokens=0,output_tokens=0),
              dict(base,at='2026-09-16T00:00:03Z',purpose='security',effective_model='qwen3guard-gen-8b'),
              dict(base,at='2026-09-16T00:00:04Z',purpose='security_check',effective_model='qwen3guard-gen-8b',attempt=False,success=False,decision='unavailable',input_tokens=0,cache_hit_tokens=0,cache_miss_tokens=0,output_tokens=0)]
        spool.write_text(''.join(json.dumps(row)+'\n' for row in rows));ledger.ingest(spool)
        scripts=[];real=usage_sync.psql
        try:
            usage_sync.psql=lambda region,script: scripts.append(script)
            usage_sync.export_batch(args.region,ledger,[dict(region=args.region,key_hash=base['api_key_id'],api_key_id=777)])
        finally:
            usage_sync.psql=real;ledger.close()
        schema=Path(__file__).with_name('usage_schema.sql').read_text().replace('BEGIN;','').replace('COMMIT;','').replace('CREATE TABLE IF NOT EXISTS','CREATE TEMP TABLE')
        # Execute the exact same committed batch twice to test lost-ACK replay.
        script=schema+'\n'+scripts[0]+'\n'+scripts[0]+'''
          SELECT json_build_object('business',(SELECT row_to_json(x) FROM (SELECT requests,events,attempts,input_tokens,output_tokens,failures,response_cache_hits,api_key_id FROM model_usage_daily)x),
            'security_unavailable',(SELECT sum(unavailable) FROM security_model_usage_daily),'events',(SELECT count(*) FROM gateway_usage_events));
        '''
        raw=real(args.region,script,'postgres')
        result=next(json.loads(line) for line in reversed(raw.splitlines()) if line.startswith('{'))
        expected=dict(requests=2,events=3,attempts=2,input_tokens=20,output_tokens=4,failures=1,response_cache_hits=1,api_key_id=777)
        passed=result==dict(business=expected,security_unavailable=1,events=5)
        print(json.dumps({'region':args.region,'passed':passed,'session_local_tables_only':True,'result':result}))
        if not passed:raise SystemExit(1)


if __name__=='__main__':main()
