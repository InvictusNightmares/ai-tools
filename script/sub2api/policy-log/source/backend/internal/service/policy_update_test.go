package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
)

func policyFixture(t *testing.T) (string, string, policyRelease) {
	t.Helper()
	root := t.TempDir()
	body := []byte("new-custom-binary")
	digest := sha256.Sum256(body)
	r := policyRelease{Version: "0.2.1+policy-log.6", SHA256: hex.EncodeToString(digest[:]), Size: int64(len(body)), UpstreamCommit: strings.Repeat("a", 40), PatchSHA256: strings.Repeat("b", 64), Features: []string{"policy-requests-v1", "policy-update-v1"}}
	require.NoError(t, os.MkdirAll(filepath.Join(root, "releases", r.SHA256), 0755))
	require.NoError(t, os.MkdirAll(filepath.Join(root, "runtime"), 0755))
	require.NoError(t, os.WriteFile(filepath.Join(root, "releases", r.SHA256, "sub2api"), body, 0644))
	exe := filepath.Join(root, "runtime", "sub2api")
	require.NoError(t, os.WriteFile(exe, []byte("old-custom-binary"), 0755))
	return root, exe, r
}

func TestPolicyUpdateAtomicInstallAndBackup(t *testing.T) {
	root, exe, r := policyFixture(t)
	require.NoError(t, replacePolicyBinary(context.Background(), root, exe, r))
	b, err := os.ReadFile(exe)
	require.NoError(t, err)
	require.Equal(t, "new-custom-binary", string(b))
	b, err = os.ReadFile(exe + ".backup")
	require.NoError(t, err)
	require.Equal(t, "old-custom-binary", string(b))
}

func TestPolicyUpdateCorruptionAndCancellationLeaveCurrentIntact(t *testing.T) {
	for _, mode := range []string{"checksum", "cancelled", "missing", "size"} {
		t.Run(mode, func(t *testing.T) {
			root, exe, r := policyFixture(t)
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			switch mode {
			case "checksum":
				require.NoError(t, os.WriteFile(filepath.Join(root, "releases", r.SHA256, "sub2api"), []byte("bad-custom-binary"), 0644))
			case "cancelled":
				cancel()
			case "missing":
				require.NoError(t, os.Remove(filepath.Join(root, "releases", r.SHA256, "sub2api")))
			case "size":
				r.Size++
			}
			require.Error(t, replacePolicyBinary(ctx, root, exe, r))
			b, err := os.ReadFile(exe)
			require.NoError(t, err)
			require.Equal(t, "old-custom-binary", string(b))
		})
	}
}

func TestPolicyUpdateCatalogRejectsOfficialAndIncompleteReleases(t *testing.T) {
	for _, mode := range []string{"official", "feature", "hash", "path", "duplicate"} {
		t.Run(mode, func(t *testing.T) {
			root, _, r := policyFixture(t)
			switch mode {
			case "official":
				r.Version = "0.2.1"
			case "feature":
				r.Features = []string{"policy-requests-v1"}
			case "hash":
				r.SHA256 = "bad"
			case "path":
				r.SHA256 = "../../etc/passwd"
			}
			c := policyCatalog{Schema: 1, Releases: []policyRelease{r}}
			if mode == "duplicate" {
				c.Releases = append(c.Releases, r)
			}
			b, err := json.Marshal(c)
			require.NoError(t, err)
			require.NoError(t, os.WriteFile(filepath.Join(root, "catalog.json"), b, 0644))
			_, err = readPolicyCatalog(root)
			require.Error(t, err)
		})
	}
}

func TestPolicyUpdateNeverFallsBackToOfficial(t *testing.T) {
	s := NewUpdateService(nil, nil, "0.2.0+policy-log.6", "release")
	// A nil GitHub client would panic if any native official path were called.
	_, err := s.CheckUpdate(context.Background(), true)
	require.NoError(t, err)
	require.Error(t, s.PerformUpdate(context.Background()))
	require.Error(t, s.Rollback())
	require.Error(t, s.RollbackToVersion(context.Background(), "0.1.999"))
}

func TestPolicyUpdateVersionOrdersRevisionAndOfficialVersion(t *testing.T) {
	require.Positive(t, comparePolicyVersions("0.2.0+policy-log.10", "0.2.0+policy-log.6"))
	require.Positive(t, comparePolicyVersions("0.2.1+policy-log.6", "0.2.0+policy-log.99"))
}
