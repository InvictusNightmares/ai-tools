"""GPU-side read-only exact-ID acceptance accounting; never fills unknown tokens.
Each scope declares a usage glob, identity secret and authorized numeric Key files.
Only those keys' event IDs are queried. Output contains no prompt, Key or session.
"""
import argparse,collections,datetime,glob,hashlib,hmac,json,os,pathlib,shlex,sys
import usage_sync

def quote(x):return "'"+str(x).replace("'","''")+"'"
def confirmed_partial(event, bill, audits):
 """An observed prefix is not the final bill; require matching terminal proof."""
 if event.get('success') or not event.get('usage_reported'):
  return False
 matches=[a for a in audits if a.get('request_id')==event.get('request_id')
          and a.get('upstream_client_request_id')==event.get('upstream_client_request_id')
          and a.get('region')==event.get('region') and a.get('api_key_id')==event.get('api_key_id')
          and a.get('stage') in ('request_canceled','client_delivery_failed')
          and a.get('response_complete') is False]
 if len(matches)!=1 or not event.get('upstream_client_request_id'):
  return False
 read=int(bill.get('cache_read_tokens') or 0);write=int(bill.get('cache_creation_tokens') or 0)
 maximum_in=sum(int(bill.get(k) or 0) for k in ('input_tokens','image_input_tokens'))+read+write
 maximum_out=sum(int(bill.get(k) or 0) for k in ('output_tokens','image_output_tokens'))
 return (0<=event.get('input_tokens',-1)<=maximum_in
         and 0<=event.get('output_tokens',-1)<=maximum_out
         and 0<=event.get('cache_hit_tokens',-1)<=read)


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();os.umask(0o077)
 config=json.loads(pathlib.Path(args.config).read_text());since=datetime.datetime.fromisoformat(config['since']);assert since.tzinfo is not None
 output=pathlib.Path(args.output)
 if output.exists():raise ValueError('new_evidence_path_required')
 all_results=[]
 for scope in config['scopes']:
  region=scope['region'];assert region in ('tokyo','us');secret=pathlib.Path(scope['secret_file']).read_text().strip();keys={}
  for spec in scope['keys']:
   ident=spec['id'];assert type(ident) is int and ident>0;token=pathlib.Path(spec['token_file']).read_text().strip();value='sub2api-identity-v1\x00'+region+'\x00'+token;hashed='key-hmac-v1:'+hmac.new(secret.encode(),value.encode(),hashlib.sha256).hexdigest();keys[hashed]=ident
  events=[]
  for name in sorted(glob.glob(scope['usage_glob'])):
   if name.endswith('.lock'):continue
   for line in pathlib.Path(name).read_text().splitlines():
    e=json.loads(line)
    if e.get('region')==region and e.get('api_key_id') in keys and datetime.datetime.fromisoformat(e['at'].replace('Z','+00:00'))>=since:events.append(e)
  attempts=[e for e in events if e.get('attempt')];ids=sorted({'client:'+e['upstream_client_request_id'] for e in attempts if e.get('upstream_client_request_id')});bills=[]
  command=shlex.join(['docker','exec','-i','sub2api-postgres','psql','-X','-q','-v','ON_ERROR_STOP=1','-U','sub2api','-d','sub2api','-At'])
  columns='id,api_key_id,request_id,upstream_request_id,model,requested_model,upstream_model,upstream_response_model,requested_reasoning_effort,reasoning_effort,input_tokens,output_tokens,cache_read_tokens,cache_creation_tokens,image_count,image_input_tokens,image_output_tokens,input_cost,output_cost,cache_read_cost,cache_creation_cost,image_input_cost,image_output_cost,total_cost,actual_cost,duration_ms,first_token_ms,user_agent'
  for start in range(0,len(ids),100):
   values=','.join(quote(v) for v in ids[start:start+100]);key_ids=','.join(str(v) for v in sorted(set(keys.values())))
   sql="SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT "+columns+' FROM usage_logs WHERE api_key_id IN ('+key_ids+') AND created_at>='+quote(since.isoformat())+'::timestamptz AND (request_id IN ('+values+') OR upstream_request_id IN ('+values+')))x;'
   bills.extend(json.loads(usage_sync.ssh(region,command,sql)))
  bills=list({b['id']:b for b in bills}.values());rows=[];mismatches=[];unknown=[];missing=[];partial=[]
  audits=[]
  for name in sorted(glob.glob(scope.get('audit_glob',''))):
   if name.endswith(('.lock','.gz')) or not pathlib.Path(name).is_file():continue
   for line in pathlib.Path(name).read_text().splitlines():
    if line.strip():audits.append(json.loads(line))
  for e in attempts:
   correlation='client:'+e.get('upstream_client_request_id','');key_id=keys[e['api_key_id']];matches=[b for b in bills if b['api_key_id']==key_id and correlation in (b['request_id'],b['upstream_request_id'])]
   row={k:e.get(k) for k in ('request_id','upstream_client_request_id','purpose','effective_model','success','usage_reported','http_status','error_type','input_tokens','output_tokens','cache_hit_tokens')};row['api_key_id']=key_id
   if len(matches)!=1:
    row['billing_match']='missing' if not matches else 'ambiguous';missing.append(row)
    row['requires_investigation']=bool(e.get('success') and e.get('usage_reported')) or len(matches)>1
   else:
    b=matches[0];row['billing_match']='exact_client_id_and_key';row['bill']={k:v for k,v in b.items() if k not in ('request_id','upstream_request_id')}
    if e.get('usage_reported'):
     read=int(b.get('cache_read_tokens') or 0);write=int(b.get('cache_creation_tokens') or 0);text_in=int(b.get('input_tokens') or 0);text_out=int(b.get('output_tokens') or 0);image_in=int(b.get('image_input_tokens') or 0);image_out=int(b.get('image_output_tokens') or 0)
     # Preserve both billing layouts. A separate image column is not added twice.
     input_candidates={text_in,text_in+read+write,text_in+image_in,text_in+read+write+image_in}
     output_candidates={text_out,text_out+image_out}
     row['gateway_input_matches_text_total']=e.get('input_tokens') in {text_in,text_in+read+write}
     row['gateway_input_matches_text_plus_image_total']=bool(image_in) and e.get('input_tokens') in {text_in+image_in,text_in+read+write+image_in}
     row['gateway_output_matches_text_total']=e.get('output_tokens')==text_out
     row['gateway_output_matches_text_plus_image_total']=bool(image_out) and e.get('output_tokens')==text_out+image_out
     row['token_match']=e.get('input_tokens') in input_candidates and e.get('output_tokens') in output_candidates and e.get('cache_hit_tokens')==read
     row['image_columns_present']=bool(image_in or image_out)
     if not row['token_match']:
      row['confirmed_partial_usage']=confirmed_partial(e,b,audits)
      if row['confirmed_partial_usage']:
       row['gateway_values_are_final']=False
       partial.append(row)
      else:mismatches.append(row)
    else:
     row['gateway_tokens_unknown']=True;row['provider_bill_available']=True;unknown.append(row)
   rows.append(row)
  duplicate_ids=[i for i,n in collections.Counter(e.get('upstream_client_request_id') for e in attempts if e.get('upstream_client_request_id')).items() if n>1]
  result=dict(label=scope['label'],region=region,since=since.isoformat(),events=len(events),attempts=len(attempts),purpose_counts=dict(collections.Counter(e.get('purpose') for e in attempts)),response_cache_hits=sum(bool(e.get('response_cache_hit')) for e in events),classification_cache_hits=sum(bool(e.get('classification_cache_hit')) for e in events),exact_matches=sum(r['billing_match']=='exact_client_id_and_key' for r in rows),token_mismatches=len(mismatches),confirmed_partial_usage_with_final_bill=len(partial),known_success_missing=sum(r['requires_investigation'] for r in missing),gateway_unknown_with_provider_bill=len(unknown),duplicate_attempt_ids=duplicate_ids,rows=rows)
  result['known_usage_reconciled']=any(e.get('usage_reported') for e in attempts) and not mismatches and not any(r['requires_investigation'] for r in missing) and not duplicate_ids
  cache_savings=[]
  for b in bills:
   uncached=int(b.get('input_tokens') or 0);cached=int(b.get('cache_read_tokens') or 0)
   if uncached>0 and cached>0 and float(b.get('input_cost') or 0)>0:
    equivalent=cached*float(b['input_cost'])/uncached;charged=float(b.get('cache_read_cost') or 0)
    cache_savings.append(dict(bill_id=b['id'],model=b['model'],cached_tokens=cached,reported_cache_cost=charged,conditional_uncached_cost=equivalent,conditional_saving=equivalent-charged,assumption='same per-token uncached input price within this bill; excludes other price tiers and account multipliers'))
  result['conditional_cache_cost_observations']=cache_savings
  all_results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
 output.write_text(json.dumps(dict(scope='read-only exact client request ID and numeric Key reconciliation; unknown gateway usage stays unknown; confirmed cancellation prefixes are not final totals',results=all_results),indent=2))

if __name__=='__main__':main()
