package repository

// Injected only into the isolated builder, never into a serving node. The
// fixture contains no production data and is discarded with its container.
import (
	"context"
	"database/sql"
	"os"
	"testing"
	"time"

	_ "github.com/lib/pq"
	"github.com/stretchr/testify/require"
)

func TestPolicyMigrationUpgradeFrom020(t *testing.T) {
	if os.Getenv("POLICY_MIGRATION_FIXTURE") != "isolated-builder" {
		t.Skip("isolated database only")
	}
	db, err := sql.Open("postgres", "host=127.0.0.1 port=5432 user=postgres dbname=policy_fixture sslmode=disable")
	require.NoError(t, err)
	defer db.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	for attempt := 0; ; attempt++ {
		err = db.PingContext(ctx)
		if err == nil || attempt >= 60 {
			break
		}
		time.Sleep(500 * time.Millisecond)
	}
	require.NoError(t, err)
	base := os.DirFS("/src/migration-base")
	require.NoError(t, applyMigrationsFS(ctx, db, base))
	_, err = db.ExecContext(ctx, `INSERT INTO groups (name, models_list_config)
		VALUES ('policy-upgrade-fixture', '{"enabled":false,"models":["fixture-model"]}'),
		('policy-enabled-fixture', '{"enabled":true,"models":["gpt-5.6-sol","gpt-image-2"]}')`)
	require.NoError(t, err)
	var fixtureUserID int64
	require.NoError(t, db.QueryRowContext(ctx, `INSERT INTO users (email, password_hash)
		VALUES ('policy-migration@example.invalid', 'fixture') RETURNING id`).Scan(&fixtureUserID))
	_, err = db.ExecContext(ctx, `INSERT INTO user_platform_quotas
		(user_id, platform, daily_limit_usd, weekly_limit_usd, deleted_at)
		VALUES ($1, 'openai', NULL, NULL, NULL),
		       ($1, 'anthropic', 0, NULL, NULL),
		       ($1, 'gemini', NULL, 1, NOW())`, fixtureUserID)
	require.NoError(t, err)
	var before string
	require.NoError(t, db.QueryRowContext(ctx, `SELECT models_list_config::text FROM groups WHERE name='policy-upgrade-fixture'`).Scan(&before))
	require.NoError(t, ApplyMigrations(ctx, db))
	require.NoError(t, ApplyMigrations(ctx, db), "restart must not rerun or corrupt migrations")
	var after string
	require.NoError(t, db.QueryRowContext(ctx, `SELECT model_allowlist::text FROM groups WHERE name='policy-upgrade-fixture'`).Scan(&after))
	require.Equal(t, before, after, "existing disabled model-list configuration must be preserved")
	var columns int
	require.NoError(t, db.QueryRowContext(ctx, `SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public' AND
		((table_name='usage_logs' AND column_name='upstream_request_id') OR
		(table_name='channel_model_pricing' AND column_name='max_reasoning_effort_multiplier') OR
		(table_name='groups' AND column_name='codex_models_manifest_config'))`).Scan(&columns))
	require.Equal(t, 3, columns)
	var indexValid bool
	require.NoError(t, db.QueryRowContext(ctx, `SELECT indisvalid FROM pg_index WHERE indexrelid='idx_usage_logs_upstream_request_id'::regclass`).Scan(&indexValid))
	require.True(t, indexValid, "concurrent index must be valid")
	// Enabled allowlists must preserve both text and image access across the rename.
	var enabled bool
	require.NoError(t, db.QueryRowContext(ctx, `SELECT model_allowlist = '{"enabled":true,"models":["gpt-5.6-sol","gpt-image-2"]}'::jsonb FROM groups WHERE name='policy-enabled-fixture'`).Scan(&enabled))
	require.True(t, enabled)
	// Old binaries query the removed column. The updater must forbid binary-only rollback.
	_, err = db.ExecContext(ctx, `SELECT models_list_config FROM groups LIMIT 0`)
	require.ErrorContains(t, err, "models_list_config")
	var minimaxAllowed bool
	require.NoError(t, db.QueryRowContext(ctx, `SELECT position('minimax' IN pg_get_constraintdef(oid)) > 0 FROM pg_constraint WHERE conname='user_platform_quotas_platform_check'`).Scan(&minimaxAllowed))
	require.True(t, minimaxAllowed)
	var upgradedConstraints int
	require.NoError(t, db.QueryRowContext(ctx, `SELECT COUNT(*) FROM pg_constraint WHERE conname IN
		('user_platform_quotas_platform_check', 'composite_model_routes_target_platform_check',
		 'channel_monitors_provider_check', 'channel_monitor_request_templates_provider_check')
		AND position('opencode_go' IN pg_get_constraintdef(oid)) > 0`).Scan(&upgradedConstraints))
	require.Equal(t, 4, upgradedConstraints)
	var applied238 int
	require.NoError(t, db.QueryRowContext(ctx, `SELECT COUNT(*) FROM schema_migrations WHERE filename IN
		('238_opencode_go_platform.sql', '238_purge_unlimited_user_platform_quotas.sql')`).Scan(&applied238))
	require.Equal(t, 2, applied238)
	var unlimited, disabled, softDeleted int
	require.NoError(t, db.QueryRowContext(ctx, `SELECT
		COUNT(*) FILTER (WHERE platform='openai'),
		COUNT(*) FILTER (WHERE platform='anthropic' AND daily_limit_usd=0),
		COUNT(*) FILTER (WHERE platform='gemini' AND weekly_limit_usd=1 AND deleted_at IS NOT NULL)
		FROM user_platform_quotas WHERE user_id=$1`, fixtureUserID).Scan(&unlimited, &disabled, &softDeleted))
	require.Zero(t, unlimited, "only rows with all three limits NULL are purged")
	require.Equal(t, 1, disabled, "an explicit zero limit remains")
	require.Equal(t, 1, softDeleted, "historical rows with a limit remain")
}
