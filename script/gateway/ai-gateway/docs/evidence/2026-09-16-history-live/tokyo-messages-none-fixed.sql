BEGIN READ ONLY;
SET LOCAL statement_timeout='15s';
SET LOCAL TIME ZONE 'Asia/Shanghai';
SELECT json_build_object('snapshot_at',now(),'api_key_id',141,'row',row_to_json(t)) FROM (
 SELECT created_at,request_id,model,requested_reasoning_effort,reasoning_effort,inbound_endpoint,input_tokens,output_tokens
 FROM usage_logs WHERE api_key_id=141 AND created_at >= '2026-09-16 09:54:00+08' AND model='deepseek-flash' AND inbound_endpoint='/v1/messages' ORDER BY created_at
) t;
COMMIT;
