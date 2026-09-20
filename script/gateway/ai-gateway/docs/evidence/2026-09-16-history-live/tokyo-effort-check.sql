BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL TIME ZONE 'Asia/Shanghai';
SELECT json_build_object('kind','daily_effort','snapshot_at',now(),'api_key_id',141,'rows',coalesce(json_agg(t),'[]'::json)) FROM (
 SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date AS local_day, model, upstream_model, upstream_response_model, requested_reasoning_effort, reasoning_effort, count(*) AS requests, sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens
 FROM public.usage_logs WHERE api_key_id=141 AND created_at >= '2026-09-15 00:00:00+08'::timestamptz
 GROUP BY 1,2,3,4,5,6 ORDER BY 1,2,5,6
) t;
SELECT json_build_object('kind','recent_requests','api_key_id',141,'rows',coalesce(json_agg(t),'[]'::json)) FROM (
 SELECT created_at,request_id,requested_model,model,upstream_model,upstream_response_model,requested_reasoning_effort,reasoning_effort,inbound_endpoint,input_tokens,output_tokens
 FROM public.usage_logs WHERE api_key_id=141 AND created_at >= '2026-09-16 00:00:00+08'::timestamptz ORDER BY created_at DESC LIMIT 30
) t;
SELECT json_build_object('kind','error_counts','api_key_id',141,'rows',coalesce(json_agg(t),'[]'::json)) FROM (
 SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date AS local_day, model, status_code, count(*) AS requests
 FROM public.ops_error_logs WHERE api_key_id=141 AND created_at >= '2026-09-15 00:00:00+08'::timestamptz GROUP BY 1,2,3 ORDER BY 1,2,3
) t;
COMMIT;
