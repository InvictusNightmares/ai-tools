\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
    IF (
        SELECT count(*)
        FROM public.groups
        WHERE name = '研发Claude'
          AND status = 'active'
    ) <> 1 THEN
        RAISE EXCEPTION
            'required active group 研发Claude must exist exactly once';
    END IF;
END
$$;

INSERT INTO public.accounts (
    name,
    platform,
    type,
    credentials,
    extra,
    concurrency,
    priority,
    status,
    schedulable,
    created_at,
    updated_at,
    auto_pause_on_expired,
    rate_multiplier,
    quota_dimension
)
SELECT
    'Figma Claude 4.8',
    'anthropic',
    'apikey',
    '{}'::jsonb,
    '{}'::jsonb,
    1,
    0,
    'active',
    true,
    now(),
    now(),
    true,
    1,
    'global'
WHERE NOT EXISTS (
    SELECT 1
    FROM public.accounts
    WHERE name = 'Figma Claude 4.8'
      AND deleted_at IS NULL
);

DO $$
BEGIN
    IF (
        SELECT count(*)
        FROM public.accounts
        WHERE name = 'Figma Claude 4.8'
          AND deleted_at IS NULL
    ) <> 1 THEN
        RAISE EXCEPTION
            'required account Figma Claude 4.8 must exist exactly once';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.accounts
        WHERE name = 'Figma Claude 4.8'
          AND deleted_at IS NULL
          AND (
              jsonb_typeof(credentials) <> 'object'
              OR (
                  credentials ? 'model_mapping'
                  AND jsonb_typeof(credentials->'model_mapping') <> 'object'
              )
          )
    ) THEN
        RAISE EXCEPTION 'model_mapping must be a JSON object';
    END IF;
END
$$;

UPDATE public.accounts
SET platform = 'anthropic',
    type = 'apikey',
    credentials = COALESCE(credentials, '{}'::jsonb)
        || jsonb_build_object(
            'api_key', :'adapter_key',
            'base_url', 'http://172.18.0.1:18090',
            'model_mapping',
                COALESCE(credentials->'model_mapping', '{}'::jsonb)
                || jsonb_build_object(
                    'claude-4.8', 'anthropic-claude-4.8-opus',
                    'claude-opus-4-8', 'anthropic-claude-4.8-opus',
                    'claude-opus-5', 'anthropic-claude-4.8-opus',
                    'claude-opus-5[1m]', 'anthropic-claude-4.8-opus',
                    'anthropic-claude-4.8-opus',
                        'anthropic-claude-4.8-opus'
                )
        ),
    concurrency = 1,
    priority = 0,
    status = 'active',
    schedulable = true,
    error_message = NULL,
    rate_limit_reset_at = NULL,
    overload_until = NULL,
    temp_unschedulable_until = NULL,
    temp_unschedulable_reason = NULL,
    updated_at = now(),
    auto_pause_on_expired = true,
    rate_multiplier = 1,
    quota_dimension = 'global'
WHERE name = 'Figma Claude 4.8'
  AND deleted_at IS NULL;

INSERT INTO public.account_groups (account_id, group_id, priority, created_at)
SELECT account.id, account_group.id, 0, now()
FROM public.accounts AS account
JOIN public.groups AS account_group
  ON account_group.name = '研发Claude'
 AND account_group.status = 'active'
WHERE account.name = 'Figma Claude 4.8'
  AND account.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM public.account_groups AS existing
      WHERE existing.account_id = account.id
        AND existing.group_id = account_group.id
  );

INSERT INTO public.scheduler_outbox (
    event_type,
    account_id,
    group_id,
    payload
)
SELECT
    'account_changed',
    account.id,
    NULL,
    jsonb_build_object('group_ids', jsonb_build_array(account_group.id))
FROM public.accounts AS account
JOIN public.groups AS account_group
  ON account_group.name = '研发Claude'
 AND account_group.status = 'active'
WHERE account.name = 'Figma Claude 4.8'
  AND account.deleted_at IS NULL;

COMMIT;

SELECT
    account.id,
    account.name,
    account.status,
    account.schedulable,
    account.credentials->>'base_url' AS base_url,
    account.credentials->'model_mapping' AS model_mapping,
    account_group.name AS group_name
FROM public.accounts AS account
LEFT JOIN public.account_groups AS membership
  ON membership.account_id = account.id
LEFT JOIN public.groups AS account_group
  ON account_group.id = membership.group_id
WHERE account.name = 'Figma Claude 4.8'
  AND account.deleted_at IS NULL;
