package service

// Custom releases are prepared outside the serving process. Never fall back to
// official binaries: those would remove both collection and this update guard.
import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const policyUpdateRoot = "/app/data/policy-updates"
const policyReleaseRoot = "/app/policy-releases"

var policyVersionRE = regexp.MustCompile(`^(\d+)\.(\d+)\.(\d+)\+policy-log\.(\d+)$`)
var policyHashRE = regexp.MustCompile(`^[a-f0-9]{64}$`)
var policyCommitRE = regexp.MustCompile(`^[a-f0-9]{40}$`)

type policyRelease struct {
	Version        string   `json:"version"`
	SHA256         string   `json:"sha256"`
	Size           int64    `json:"size"`
	PublishedAt    string   `json:"published_at"`
	UpstreamCommit string   `json:"upstream_commit"`
	PatchSHA256    string   `json:"patch_sha256"`
	Features       []string `json:"features"`
}

type policyCatalog struct {
	Schema    int             `json:"schema"`
	CheckedAt string          `json:"checked_at"`
	Status    string          `json:"status"`
	Message   string          `json:"message"`
	Releases  []policyRelease `json:"releases"`
}

func (s *UpdateService) isPolicyBuild() bool {
	return strings.Contains(s.currentVersion, "+policy-log.")
}

func policyVersion(v string) [4]int {
	var result [4]int
	match := policyVersionRE.FindStringSubmatch(v)
	if match != nil {
		for i := range result {
			result[i], _ = strconv.Atoi(match[i+1])
		}
	}
	return result
}

func comparePolicyVersions(a, b string) int {
	x, y := policyVersion(a), policyVersion(b)
	for i := range x {
		if x[i] < y[i] {
			return -1
		}
		if x[i] > y[i] {
			return 1
		}
	}
	return 0
}

func readPolicyCatalog(root string) (*policyCatalog, error) {
	f, err := os.Open(filepath.Join(root, "catalog.json"))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var c policyCatalog
	if err := json.NewDecoder(io.LimitReader(f, 1024*1024)).Decode(&c); err != nil {
		return nil, err
	}
	if c.Schema != 1 || len(c.Releases) > 20 {
		return nil, fmt.Errorf("无效的定制发布目录")
	}
	seen := map[string]bool{}
	for _, r := range c.Releases {
		features := map[string]bool{}
		for _, feature := range r.Features {
			features[feature] = true
		}
		if !policyVersionRE.MatchString(r.Version) || !policyHashRE.MatchString(r.SHA256) ||
			!policyHashRE.MatchString(r.PatchSHA256) || !policyCommitRE.MatchString(r.UpstreamCommit) ||
			r.Size <= 0 || r.Size > maxDownloadSize || seen[r.Version] ||
			!features["policy-requests-v1"] || !features["policy-update-v1"] {
			return nil, fmt.Errorf("定制发布未通过完整性检查")
		}
		seen[r.Version] = true
	}
	sort.Slice(c.Releases, func(i, j int) bool { return comparePolicyVersions(c.Releases[i].Version, c.Releases[j].Version) > 0 })
	return &c, nil
}

func (s *UpdateService) checkPolicyUpdate() (*UpdateInfo, error) {
	info := &UpdateInfo{CurrentVersion: s.currentVersion, LatestVersion: s.currentVersion, BuildType: s.buildType}
	if policyRestartPending() {
		info.NeedRestart = true
		info.Warning = "定制程序已安装，请重启服务完成更新。"
		return info, nil
	}
	c, err := readPolicyCatalog(policyReleaseRoot)
	if err != nil {
		info.Warning = "定制升级目录暂不可用；已禁止下载会覆盖异常记录功能的官方程序。"
		return info, nil
	}
	info.Warning = c.Message
	checked, err := time.Parse(time.RFC3339, c.CheckedAt)
	if err != nil || time.Since(checked) > 3*time.Hour {
		info.Warning = "定制构建检查已超过 3 小时未更新，请检查构建任务。" + c.Message
	}
	if len(c.Releases) > 0 {
		r := c.Releases[0]
		info.LatestVersion = r.Version
		info.HasUpdate = comparePolicyVersions(s.currentVersion, r.Version) < 0
		info.ReleaseInfo = &ReleaseInfo{Name: r.Version, Body: "已保留异常记录采集、管理页面及定制升级通道，并通过自动验证。", PublishedAt: r.PublishedAt, HTMLURL: "https://github.com/Wei-Shaw/sub2api/commit/" + r.UpstreamCommit}
	}
	return info, nil
}

func (s *UpdateService) policyRollbackVersions() ([]RollbackVersion, error) {
	c, err := readPolicyCatalog(policyReleaseRoot)
	if err != nil {
		return nil, fmt.Errorf("定制历史版本目录不可用: %w", err)
	}
	result := make([]RollbackVersion, 0)
	for _, r := range c.Releases {
		if comparePolicyVersions(r.Version, s.currentVersion) < 0 {
			result = append(result, RollbackVersion{Version: r.Version, PublishedAt: r.PublishedAt})
			if len(result) == maxRollbackVersions {
				break
			}
		}
	}
	return result, nil
}

func (s *UpdateService) installPolicyUpdate(ctx context.Context, rollback string) error {
	if policyRestartPending() {
		if rollback != "" {
			return fmt.Errorf("已有待重启的定制更新，请先重启服务后再回退")
		}
		return nil
	}
	c, err := readPolicyCatalog(policyReleaseRoot)
	if err != nil {
		return fmt.Errorf("定制发布目录不可用，未替换程序: %w", err)
	}
	var selected *policyRelease
	olderCount := 0
	for i := range c.Releases {
		r := &c.Releases[i]
		if comparePolicyVersions(r.Version, s.currentVersion) < 0 {
			olderCount++
		}
		if rollback == "" && comparePolicyVersions(r.Version, s.currentVersion) > 0 ||
			rollback == r.Version && comparePolicyVersions(r.Version, s.currentVersion) < 0 && olderCount <= maxRollbackVersions {
			selected = r
			break
		}
	}
	if selected == nil {
		if rollback != "" {
			return ErrRollbackVersionNotAllowed
		}
		return ErrNoUpdateAvailable
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	// The compose command starts this persistent file, so replacement survives
	// container recreation. Refuse an incorrectly installed bootstrap binary.
	if exe != filepath.Join(policyUpdateRoot, "runtime", "sub2api") {
		return fmt.Errorf("运行程序不在定制持久目录，升级已停止")
	}
	running, err := os.Stat("/proc/self/exe")
	if err != nil {
		return err
	}
	installed, err := os.Stat(exe)
	if err != nil {
		return err
	}
	if !os.SameFile(running, installed) {
		return fmt.Errorf("程序已替换，请先重启服务后再执行更新或回退")
	}
	return replacePolicyBinary(ctx, policyReleaseRoot, exe, *selected)
}

func policyRestartPending() bool {
	exe, err := os.Executable()
	if err != nil || exe != filepath.Join(policyUpdateRoot, "runtime", "sub2api") {
		return false
	}
	running, err := os.Stat("/proc/self/exe")
	if err != nil {
		return false
	}
	installed, err := os.Stat(exe)
	return err == nil && !os.SameFile(running, installed)
}

func replacePolicyBinary(ctx context.Context, root, exe string, release policyRelease) error {
	source, err := os.Open(filepath.Join(root, "releases", release.SHA256, "sub2api"))
	if err != nil {
		return err
	}
	defer source.Close()
	st, err := source.Stat()
	if err != nil {
		return err
	}
	if !st.Mode().IsRegular() || st.Size() != release.Size {
		return fmt.Errorf("定制程序大小不匹配")
	}
	next, err := os.CreateTemp(filepath.Dir(exe), ".policy-update-")
	if err != nil {
		return err
	}
	defer os.Remove(next.Name())
	defer next.Close()
	hash := sha256.New()
	if _, err = io.Copy(io.MultiWriter(next, hash), io.LimitReader(source, maxDownloadSize+1)); err != nil {
		return err
	}
	if hex.EncodeToString(hash.Sum(nil)) != release.SHA256 {
		return fmt.Errorf("定制程序 SHA256 不匹配，当前程序未改动")
	}
	if err = ctx.Err(); err != nil {
		return err
	}
	if err = next.Chmod(0755); err != nil {
		return err
	}
	if err = next.Sync(); err != nil {
		return err
	}
	if err = next.Close(); err != nil {
		return err
	}
	// Keep the recorder configuration with this activation's immutable metadata.
	runtimeRoot := filepath.Dir(filepath.Dir(exe))
	backupDir := filepath.Join(runtimeRoot, "backups", time.Now().UTC().Format("20060102T150405.000000000"))
	if err = os.MkdirAll(backupDir, 0700); err != nil {
		return err
	}
	config, configErr := os.ReadFile(filepath.Join(filepath.Dir(runtimeRoot), "policy-request-log.json"))
	if configErr != nil && !os.IsNotExist(configErr) {
		return configErr
	}
	if configErr == nil {
		if err = os.WriteFile(filepath.Join(backupDir, "policy-request-log.json"), config, 0600); err != nil {
			return err
		}
	}
	metadata, err := json.Marshal(release)
	if err != nil {
		return err
	}
	if err = os.WriteFile(filepath.Join(backupDir, "target.json"), metadata, 0600); err != nil {
		return err
	}
	// Hard-link the current inode first; there is never a gap at the executable
	// path, even if the process or host dies before the final atomic rename.
	backup := exe + ".backup"
	if err = os.Remove(backup); err != nil && !os.IsNotExist(err) {
		return err
	}
	if err = os.Link(exe, backup); err != nil {
		return err
	}
	if err = os.Rename(next.Name(), exe); err != nil {
		return err
	}
	dir, err := os.Open(filepath.Dir(exe))
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}
