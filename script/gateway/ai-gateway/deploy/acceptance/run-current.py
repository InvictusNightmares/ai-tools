#!/usr/bin/env python3
"""Choose operations code from the same immutable release as the regional API."""
import json
import os
from pathlib import Path
import sys

if len(sys.argv) not in (2,3) or sys.argv[1] not in ('tokyo','us') or (len(sys.argv)==3 and sys.argv[2]!='usage'):
    raise SystemExit('known region required')
region=sys.argv[1]
root=Path('/data/ai-gateway/acceptance-'+region)
release=json.loads((root/'current-release.json').read_text())
code=Path(release['path']).resolve()
if not code.is_relative_to('/data/ai-gateway/releases'):
    raise SystemExit('invalid immutable release path')
config=json.loads((root/'ops/config.json').read_text())
args=[sys.executable,str(code/'tools/gateway_ops.py'),'--region',region,'--root',str(root),'--apply-log-maintenance']
if len(sys.argv)==3:
    # A rollback to the earlier combined job continues exporting via health.
    metadata=json.loads((code/'release.json').read_text())
    if metadata.get('operations_contract')!='independent-usage-health-v1':raise SystemExit(0)
    args=[sys.executable,str(code/'tools/gateway_ops.py'),'--region',region,'--root',str(root),'--usage-only']
retention=config.get('retention_days')
if retention is not None:
    if retention not in (30,90):raise SystemExit('unsupported retention policy')
    args+=['--retention-days',str(retention)]
os.execv(sys.executable,args)
