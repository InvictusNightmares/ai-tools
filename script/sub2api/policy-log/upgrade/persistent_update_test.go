package service

// This test is injected only into the isolated Linux build workspace. It runs
// from the same persistent executable path used in production, never on a node.
import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestPolicyUpdatePersistentExecutableFlow(t *testing.T) {
	if os.Getenv("POLICY_UPDATER_INTEGRATION") != "isolated-builder" {
		t.Skip("isolated build container only")
	}
	exe, err := os.Executable()
	require.NoError(t, err)
	require.Equal(t, filepath.Join(policyUpdateRoot, "runtime", "sub2api"), exe)
	old, err := os.ReadFile(exe)
	require.NoError(t, err)
	body, err := os.ReadFile("/src/sub2api")
	require.NoError(t, err)
	hash := sha256.Sum256(body)
	r := policyRelease{Version: "99.0.0+policy-log.6", SHA256: hex.EncodeToString(hash[:]), Size: int64(len(body)), UpstreamCommit: strings.Repeat("a", 40), PatchSHA256: strings.Repeat("b", 64), Features: []string{"policy-requests-v1", "policy-update-v1"}}
	dir := filepath.Join(policyReleaseRoot, "releases", r.SHA256)
	if os.Getenv("POLICY_UPDATER_READONLY") != "1" {
		require.NoError(t, os.MkdirAll(dir, 0755))
		require.NoError(t, os.WriteFile(filepath.Join(dir, "sub2api"), body, 0755))
		catalog, err := json.Marshal(policyCatalog{Schema: 1, CheckedAt: time.Now().UTC().Format(time.RFC3339), Status: "ready", Releases: []policyRelease{r}})
		require.NoError(t, err)
		require.NoError(t, os.WriteFile(filepath.Join(policyReleaseRoot, "catalog.json"), catalog, 0644))
	} else {
		require.Equal(t, 1000, os.Getuid())
		require.Error(t, os.WriteFile(filepath.Join(policyReleaseRoot, "must-not-be-writable"), []byte("probe"), 0644))
	}
	s := NewUpdateService(nil, nil, "0.2.0+policy-log.6", "release")
	info, err := s.CheckUpdate(context.Background(), true)
	require.NoError(t, err)
	require.True(t, info.HasUpdate)
	require.NoError(t, s.PerformUpdate(context.Background()))
	installed, err := os.ReadFile(exe)
	require.NoError(t, err)
	require.Equal(t, body, installed)
	backup, err := os.ReadFile(exe + ".backup")
	require.NoError(t, err)
	require.Equal(t, old, backup)
	info, err = s.CheckUpdate(context.Background(), true)
	require.NoError(t, err)
	require.True(t, info.NeedRestart)
	require.False(t, info.HasUpdate)
	// Repeating update after a lost response must not replace the backup again.
	require.NoError(t, s.PerformUpdate(context.Background()))
	backup, err = os.ReadFile(exe + ".backup")
	require.NoError(t, err)
	require.Equal(t, old, backup)
	require.Error(t, s.RollbackToVersion(context.Background(), "0.1.0+policy-log.6"))
}
