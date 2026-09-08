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
		VALUES ('policy-upgrade-fixture', '{"enabled":false,"models":["fixture-model"]}')`)
	require.NoError(t, err)
	var before string
	require.NoError(t, db.QueryRowContext(ctx, `SELECT models_list_config::text FROM groups WHERE name='policy-upgrade-fixture'`).Scan(&before))
	require.NoError(t, ApplyMigrations(ctx, db))
	require.NoError(t, ApplyMigrations(ctx, db), "restart must not rerun or corrupt migrations")
	var after string
	require.NoError(t, db.QueryRowContext(ctx, `SELECT models_list_config::text FROM groups WHERE name='policy-upgrade-fixture'`).Scan(&after))
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
	// The 0.2.0 migration set can still run and its group column remains readable.
	require.NoError(t, applyMigrationsFS(ctx, db, base))
}
