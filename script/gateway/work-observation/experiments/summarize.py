#!/usr/bin/env python3
"""Summarize synthetic trials; this is not full capture acceptance."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median


def summarize(path):
    groups=defaultdict(list)
    for line in Path(path).read_text().splitlines():
        r=json.loads(line)
        key=(r['mode'],r['payload_bytes'],r['delay_ms'],r['concurrency'],r.get('offered_rps',0))
        groups[(key,r['candidate'])].append(r)
    result=[]
    for (case,candidate),rows in sorted(groups.items()):
        base=groups[(case,'nginx')]
        p95=median(r['first_p95_ms'] for r in rows)
        total=median(r['total_p95_ms'] for r in rows)
        first_base=median(r['first_p95_ms'] for r in base)
        total_base=median(r['total_p95_ms'] for r in base)
        result.append({'mode':case[0],'payload_bytes':case[1],'delay_ms':case[2],
            'concurrency':case[3],'offered_rps':case[4],'candidate':candidate,'rounds':len(rows),
            'measured_requests':sum(r['count'] for r in rows),'ok':sum(r['ok'] for r in rows),
            'first_p95_ms_median':p95,'total_p95_ms_median':total,
            'first_vs_nginx_percent':100*(p95/first_base-1) if first_base else None,
            'total_vs_nginx_percent':100*(total/total_base-1) if total_base else None,
            'rps_median':median(r['rps'] for r in rows),
            'cpu_ms_per_exchange_including_warmup':1000*sum(r['cpu_s_including_warmup'] for r in rows)/sum(r['count']+32 for r in rows),
            'peak_rss_mib':max(r['peak_rss_bytes'] for r in rows)/(1024*1024),
            'round_first_p95_ms':[r['first_p95_ms'] for r in rows],
            'round_total_p95_ms':[r['total_p95_ms'] for r in rows]})
    return {'scope':'synthetic_transport_and_bounded_hash_queue_only',
            'full_capture_acceptance':False,'rows':result}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path');args=p.parse_args()
    print(json.dumps(summarize(args.path),indent=2))
