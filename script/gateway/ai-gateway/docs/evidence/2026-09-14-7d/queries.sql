
BEGIN READ ONLY;
SET LOCAL statement_timeout = '45s';
SET LOCAL TIME ZONE 'UTC';
WITH u AS MATERIALIZED (
 SELECT *, COALESCE(input_tokens,0)::bigint+COALESCE(cache_read_tokens,0)::bigint+COALESCE(cache_creation_tokens,0)::bigint AS recorded_prompt_tokens,
 COALESCE(NULLIF(upstream_response_model,''),NULLIF(upstream_model,''),NULLIF(model,''),'<unknown>') AS effective_model
 FROM public.usage_logs WHERE created_at >= '2026-09-07T03:16:00Z'::timestamptz AND created_at < '2026-09-14T03:16:00Z'::timestamptz
), d AS (
 SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day, count(*) AS usage_rows,
 count(DISTINCT NULLIF(request_id,'')) AS request_ids, count(DISTINCT api_key_id) AS active_keys,
 sum(input_tokens) AS input_tokens, sum(cache_read_tokens) AS cache_read_tokens,
 sum(cache_creation_tokens) AS cache_creation_tokens, sum(output_tokens) AS output_tokens,
 sum(actual_cost) AS actual_cost FROM u GROUP BY 1
), h AS (
 SELECT date_trunc('hour',created_at) AS hour, count(*) AS usage_rows,
 count(DISTINCT api_key_id) AS active_keys, sum(duration_ms)/3600000.0 AS business_inflight_estimate,
 sum(recorded_prompt_tokens) AS recorded_prompt_tokens FROM u GROUP BY 1
), m AS (
 SELECT date_trunc('minute',created_at) AS minute, count(*) AS n FROM u GROUP BY 1
), s AS (
 SELECT date_trunc('second',created_at) AS second, count(*) AS n FROM u GROUP BY 1
), start_m AS (
 SELECT date_trunc('minute',created_at-COALESCE(duration_ms,0)*interval '1 millisecond') AS minute, count(*) AS n FROM u GROUP BY 1
), models AS (
 SELECT effective_model AS model,count(*) AS usage_rows,sum(input_tokens) AS input_tokens,
 sum(cache_read_tokens) AS cache_read_tokens,sum(cache_creation_tokens) AS cache_creation_tokens,
 sum(output_tokens) AS output_tokens FROM u GROUP BY 1
), ends AS (
 SELECT COALESCE(inbound_endpoint,'<null>') AS endpoint,count(*) AS usage_rows FROM u GROUP BY 1
)
SELECT json_build_object(
 'window_start_utc','2026-09-07T03:16:00Z','window_end_utc','2026-09-14T03:16:00Z','queried_at',CURRENT_TIMESTAMP,
 'totals',(SELECT row_to_json(t) FROM (SELECT count(*) AS usage_rows,count(DISTINCT NULLIF(request_id,'')) AS request_ids,
 count(*) FILTER (WHERE request_id IS NULL OR request_id='') AS missing_request_id,
 count(DISTINCT api_key_id) AS active_keys,
 sum(input_tokens) AS input_tokens,sum(cache_read_tokens) AS cache_read_tokens,
 sum(cache_creation_tokens) AS cache_creation_tokens,sum(output_tokens) AS output_tokens,sum(actual_cost) AS actual_cost,
 min(created_at) AS first_record,max(created_at) AS last_record,
 count(*) FILTER (WHERE duration_ms IS NULL OR duration_ms<=0) AS invalid_duration_rows,
 avg(duration_ms) AS business_duration_avg_ms,
 percentile_cont(ARRAY[0.5,0.95,0.99]) WITHIN GROUP (ORDER BY duration_ms) AS business_duration_ms_quantiles,
 percentile_cont(ARRAY[0.5,0.9,0.95,0.99]) WITHIN GROUP (ORDER BY recorded_prompt_tokens) AS prompt_token_proxy_quantiles,
 max(recorded_prompt_tokens) AS max_prompt_token_proxy,
 count(*) FILTER (WHERE recorded_prompt_tokens>32768) AS over_32k_prompt_proxy,
 sum(recorded_prompt_tokens) AS prompt_token_proxy_sum FROM u) t),
 'daily',(SELECT json_agg(d ORDER BY day) FROM d),
 'hourly',(SELECT json_agg(h ORDER BY hour) FROM h),
 'minute_counts',(SELECT json_agg(m ORDER BY minute) FROM m),
 'start_minute_counts',(SELECT json_agg(start_m ORDER BY minute) FROM start_m),
 'second_peak',(SELECT row_to_json(s) FROM s ORDER BY n DESC,second LIMIT 1),
 'models',(SELECT json_agg(models ORDER BY usage_rows DESC) FROM models),
 'endpoints',(SELECT json_agg(ends ORDER BY usage_rows DESC) FROM ends)
);
SELECT json_build_object('ops_errors', count(*),'error_request_ids',count(DISTINCT NULLIF(request_id,'')))
FROM public.ops_error_logs WHERE created_at >= '2026-09-07T03:16:00Z'::timestamptz AND created_at < '2026-09-14T03:16:00Z'::timestamptz;
ROLLBACK;
