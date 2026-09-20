#!/usr/bin/env python3
"""Summarize every round and pooled samples, never substitute one for the other."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def percentile(values):
    ordered=sorted(values)
    return ordered[(95*len(ordered)+99)//100-1]


def summarize(root):
    rows=[json.loads(line) for line in (root/'results.jsonl').read_text().splitlines()]
    status=json.loads((root/'on/status.json').read_text())
    groups=defaultdict(dict)
    pooled=defaultdict(lambda:defaultdict(list))
    expected_captured=expected_written=0
    for row in rows:
        key=(row['mode'],row['payload_bytes'],row['round'])
        if row['candidate'] in groups[key]:raise ValueError('duplicate_case')
        groups[key][row['candidate']]=row
        pooled[key[:2]][row['candidate']].append(row)
        if row['candidate']=='on':
            count=row['count']+32 # The fixture always sends 32 warm-up exchanges.
            expected_captured+=count
            expected_written+=count*(17 if row['mode']=='ws' else 1)
    comparisons=[]
    for key,cases in sorted(groups.items()):
        if set(cases)!={'nginx','off','on'}:raise ValueError('incomplete_case_set')
        entry={'mode':key[0],'payload_bytes':key[1],'round':key[2]}
        for field in ('first','total'):
            before=percentile(cases['off'][field+'_ms'])
            after=percentile(cases['on'][field+'_ms'])
            entry[field+'_overhead_percent']=(after/before-1)*100
        entry['within_5_percent']=all(entry[k]<=5 for k in ('first_overhead_percent','total_overhead_percent'))
        comparisons.append(entry)
    merged=[]
    for key,cases in sorted(pooled.items()):
        entry={'mode':key[0],'payload_bytes':key[1],'routes':{}}
        for name,items in cases.items():
            entry['routes'][name]={
                'samples':sum(r['count'] for r in items),
                'first_p95_ms':percentile([v for r in items for v in r['first_ms']]),
                'total_p95_ms':percentile([v for r in items for v in r['total_ms']]),
                'peak_rss_bytes':max(r['peak_rss_bytes'] for r in items),
                'cpu_s_including_warmup':sum(r['cpu_s_including_warmup'] for r in items)}
        for metric in ('first','total'):
            on=entry['routes']['on'][metric+'_p95_ms']
            entry[metric+'_capture_overhead_percent']=(on/entry['routes']['off'][metric+'_p95_ms']-1)*100
            entry[metric+'_whole_path_overhead_percent']=(on/entry['routes']['nginx'][metric+'_p95_ms']-1)*100
        merged.append(entry)
    counters=('dropped','truncated','projection_errors','write_errors','queued_bytes','queue_items','active_requests')
    complete=status.get('captured')==expected_captured and status.get('written')==expected_written and all(status.get(k)==0 for k in counters)
    return {'version':status['version'],'cases':len(rows),'measured_requests':sum(r['count'] for r in rows),
        'body_correct':all(r['ok']==r['count'] and not r['errors'] for r in rows),
        'capture_complete':complete,'expected_captured':expected_captured,'expected_written':expected_written,
        'capture_counters':{k:status.get(k) for k in (*counters,'captured','written','stored_bytes')},
        'every_round_within_5_percent':all(r['within_5_percent'] for r in comparisons),
        'rounds':comparisons,'pooled':merged,'percentile_method':'nearest_rank',
        'limitations':['Only synthetic loopback workload; not production acceptance.','Whole-path overhead is reported separately from capture on/off.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence_dir',type=Path)
    args=parser.parse_args()
    result=summarize(args.evidence_dir)
    print(json.dumps(result,indent=2)+'\n',end='')


if __name__=='__main__':main()
