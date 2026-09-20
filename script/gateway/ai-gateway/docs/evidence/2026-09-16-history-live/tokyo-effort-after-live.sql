BEGIN READ ONLY;
SET LOCAL statement_timeout='15s';
SET LOCAL TIME ZONE 'Asia/Shanghai';
SELECT json_build_object('kind','snapshot','at',now(),'api_key_id',141);
SELECT json_build_object('kind','summary','row',row_to_json(t)) FROM (
 SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date AS local_day,model,requested_reasoning_effort,reasoning_effort,count(*) AS requests
 FROM usage_logs WHERE api_key_id=141 AND created_at >= '2026-09-15 00:00:00+08' GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
) t;
SELECT json_build_object('kind','recent_high','row',row_to_json(t)) FROM (
 SELECT created_at,request_id,model,requested_reasoning_effort,reasoning_effort,inbound_endpoint,input_tokens,output_tokens
 FROM usage_logs WHERE api_key_id=141 AND created_at >= '2026-09-16 09:22:00+08' AND (reasoning_effort IN ('medium','high','xhigh','max') OR requested_reasoning_effort IN ('high','xhigh','max')) ORDER BY created_at DESC LIMIT 24
) t;
COMMIT;
