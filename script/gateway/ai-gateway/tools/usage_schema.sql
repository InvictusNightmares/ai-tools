-- Isolated gateway_usage database only. Never run this against sub2api.
BEGIN;
CREATE TABLE IF NOT EXISTS gateway_usage_schema(version integer PRIMARY KEY CHECK(version=1));
INSERT INTO gateway_usage_schema VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gateway_key_mapping(
  region text NOT NULL, key_hash text NOT NULL, api_key_id bigint NOT NULL CHECK(api_key_id>0),
  PRIMARY KEY(region,key_hash)
);
CREATE TABLE IF NOT EXISTS gateway_usage_events(
  event_id text PRIMARY KEY CHECK(length(event_id)=64),
  payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
  imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS gateway_usage_bucket ON gateway_usage_events(
  (payload->>'date'), (payload->>'region'), (payload->>'api_key_id'),
  (payload->>'purpose'), (payload->>'effective_model'), (payload->>'effective_reasoning_effort')
);
CREATE TABLE IF NOT EXISTS model_usage_daily(
  date date NOT NULL, region text NOT NULL, api_key_hash text NOT NULL, api_key_id bigint,
  purpose text NOT NULL, effective_model text NOT NULL, effective_reasoning_effort text NOT NULL,
  requests bigint NOT NULL, events bigint NOT NULL, attempts bigint NOT NULL,
  successes bigint NOT NULL, failures bigint NOT NULL,
  input_tokens bigint NOT NULL, cache_hit_tokens bigint NOT NULL,
  cache_miss_tokens bigint NOT NULL, output_tokens bigint NOT NULL,
  response_cache_hits bigint NOT NULL, classification_cache_hits bigint NOT NULL,
  unknown_usage_attempts bigint NOT NULL, unavailable bigint NOT NULL, upgrades bigint NOT NULL, downgrades bigint NOT NULL,
  PRIMARY KEY(date,region,api_key_hash,purpose,effective_model,effective_reasoning_effort)
);
CREATE TABLE IF NOT EXISTS security_model_usage_daily(LIKE model_usage_daily INCLUDING ALL);
COMMIT;
