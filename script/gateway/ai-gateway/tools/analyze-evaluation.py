#!/usr/bin/env python3
"""Summarize frozen classifier trials without selecting or relabeling samples."""
import argparse, collections, hashlib, json, math, pathlib, statistics, sys
p=argparse.ArgumentParser();p.add_argument('--cases',required=True);p.add_argument('--results',nargs='+',required=True);p.add_argument('--out',required=True);p.add_argument('--split',help='explicit subset; otherwise require all fixture cases');a=p.parse_args()
fixture=json.loads(pathlib.Path(a.cases).read_text());index={x['id']:x for x in fixture['cases']};all_reports=[]
if len(index)!=len(fixture['cases']):p.error('duplicate fixture IDs')
expected_cases={k:v for k,v in index.items() if a.split is None or v['split']==a.split}
if not expected_cases:p.error('fixture split not found')
expected={(ident,lang) for ident in expected_cases for lang in ('zh','en','mixed')}
for path in a.results:
 rows=[json.loads(x) for x in pathlib.Path(path).read_text().splitlines() if x.strip()]
 if not rows:p.error('empty results')
 if len({(r['primary'],r['reviewer']) for r in rows})!=1:p.error('different candidates in one trial')
 seen=set()
 for r in rows:
  key=(r['case_id'],r['language'])
  if key not in expected or key in seen:p.error('unknown or duplicate sample')
  case=index[r['case_id']]
  if r['split']!=case['split'] or ('protocol' in case and r.get('protocol')!=case['protocol']):p.error('result disagrees with fixture split/protocol')
  seen.add(key)
 report={'file':pathlib.Path(path).name,'sha256':hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest(),'primary':rows[0]['primary'],'reviewer':rows[0]['reviewer'],'requests':len(rows),'expected_requests':len(expected),'complete':seen==expected,'missing_samples':[dict(case_id=c,language=l) for c,l in sorted(expected-seen)],'successes':sum(x['ok'] for x in rows),'business_calls':sum(bool(x.get('business_upstream_called')) for x in rows),'splits':{}}
 for split in dict.fromkeys(c['split'] for c in expected_cases.values()):
  cases={k:v for k,v in expected_cases.items() if v['split']==split}
  selected=[r for r in rows if index[r['case_id']]['split']==split]
  groups=collections.defaultdict(list)
  for r in selected:groups[r['case_id']].append(r)
  consistent=0;differences=[]
  for ident in cases:
   items=groups[ident]
   sig={((x['classification'].get('Assessment') or {}).get('complexity'),x['classification'].get('EffectiveReasoningEffort')) for x in items}
   passed=len(items)==3 and all(x['ok'] for x in items) and len(sig)==1 and None not in next(iter(sig))
   consistent+=passed
   if not passed:differences.append({'case_id':ident,'variants':[{k:x[k] for k in ['language','ok']}|{'complexity':(x['classification'].get('Assessment') or {}).get('complexity'),'effort':x['classification'].get('EffectiveReasoningEffort')} for x in items]})
  langs={}
  for lang in ('zh','en','mixed'):
   r=[x for x in selected if x['language']==lang];lat=sorted(x['latency_ms'] for x in r)
   high_low=sum(index[x['case_id']]['reviewer_complexity'] in ('complex','exceptional') and (x['classification'].get('Assessment') or {}).get('complexity')=='simple' for x in r)
   labels=sum(x['ok'] and index[x['case_id']]['expected_task'] in (x['classification'].get('Assessment') or {}).get('task_labels',[]) for x in r)
   matches=sum(x['ok'] and index[x['case_id']]['reviewer_complexity']==(x['classification'].get('Assessment') or {}).get('complexity') for x in r)
   boundaries=[x for x in r if 'expected_new_task' in index[x['case_id']]]
   langs[lang]={'requests':len(r),'successes':sum(x['ok'] for x in r),'median_ms':statistics.median(lat) if lat else None,'p95_ms':lat[math.ceil(.95*len(lat))-1] if lat else None,'high_complexity_to_simple':high_low,'expected_task_in_labels':labels,'assigned_complexity_matches':matches,'task_boundary_checks':len(boundaries),'task_boundary_matches':sum(x['ok'] and index[x['case_id']]['expected_new_task']==(x['classification'].get('Assessment') or {}).get('new_task') for x in boundaries),'efforts':dict(collections.Counter(x['classification'].get('EffectiveReasoningEffort') for x in r if x['ok']))}
  events=[e for r in selected for e in r['classification_calls']]
  report['splits'][split]={'groups':len(cases),'consistent_groups':consistent,'consistency_percent':round(100*consistent/len(cases),2),'differences':differences,'languages':langs,'classifier_attempts':len(events),'input_tokens':sum(e.get('input_tokens',0) for e in events),'output_tokens':sum(e.get('output_tokens',0) for e in events),'prompt_cache_hit_tokens':sum(e.get('cache_hit_tokens',0) for e in events)}
 all_reports.append(report)
pathlib.Path(a.out).write_text(json.dumps({'scope':'classifier_only_not_guard_auto_business_acceptance','label_authority':'implementer_assigned_not_independent_human_adjudication','consistency_definition':'same_complexity_and_target_effort_in_all_three_languages','fixture_sha256':hashlib.sha256(pathlib.Path(a.cases).read_bytes()).hexdigest(),'trials':all_reports},ensure_ascii=False,indent=2)+'\n')
for r in all_reports:
 print(r['primary'],r['reviewer'],'requests',r['requests'],'success',r['successes'],'complete',r['complete'])
 for split,h in r['splits'].items():print(split,str(h['consistent_groups'])+'/'+str(h['groups']),h['consistency_percent'])
sys.exit(0 if all(r['complete'] for r in all_reports) else 1)
