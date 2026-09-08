#!/usr/bin/env python3
"""Build verified policy releases on the existing GPU host's CPU, then stage via SSH.

Never activates a production binary. The existing admin update + restart buttons
perform activation. Merge conflicts, schema changes and failed checks keep the
last verified release available, with an explicit status in the admin UI.
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.error
import uuid

REPO = "Wei-Shaw/sub2api"
DEFAULT_HOME = Path("/data/sub2api-policy-build")
FEATURES = ["policy-requests-v1", "policy-update-v1"]
NODES = ("qiyuan-us", "qiyuan-tokyo")
NODE_ROOT = "/opt/sub2api-deploy/policy-releases"
REVISION = 7
NODE_IMAGE = "node:24-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e"
GO_IMAGE = "golang:1.27.1-bookworm@sha256:648f440f42a0958804efb24df176f806f9d353b41f1c0627f666428e40310f6b"
POSTGRES_IMAGE = "postgres:18-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2"
MIGRATION_BASE_COMMIT = "aa236488351eb71e120fc2b6fb32e36b0374c918"
MIGRATION_BASE_SHA256 = "0535674a97117289b871efccbb012835f2135631622b70133f187cecccc4825d"


class CompatibilityError(RuntimeError):
    def __init__(self, detail, public_reason):
        super().__init__(detail)
        self.public_reason = public_reason


def latest_official_release():
    try:
        return fetch(f"https://api.github.com/repos/{REPO}/releases/latest")
    except urllib.error.HTTPError as error:
        if error.code not in (403, 429):
            raise
    # Only the official /latest redirect is a stable-release fallback. The
    # Atom feed also contains unpublished tags and must not select upgrades.
    request = urllib.request.Request(f"https://github.com/{REPO}/releases/latest",
                                     headers={"User-Agent": "sub2api-policy-builder"})
    with urllib.request.urlopen(request, timeout=120) as response:
        url = response.geturl()
    match = re.fullmatch(r"https://github\.com/Wei-Shaw/sub2api/releases/tag/(v\d+\.\d+\.\d+)", url)
    if not match:
        raise RuntimeError("Official stable release redirect is invalid")
    return {"tag_name": match[1], "draft": False, "prerelease": False}


def official_tag_commit(tag):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise RuntimeError("Invalid official tag")
    try:
        commit = fetch(f"https://api.github.com/repos/{REPO}/commits/{tag}")["sha"]
        if not re.fullmatch("[a-f0-9]{40}", commit):
            raise RuntimeError("Invalid official commit")
        return commit
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        pass
    ref = "refs/tags/" + tag
    result = run(["git", "ls-remote", f"https://github.com/{REPO}.git", ref, ref + "^{}"],
                 capture_output=True, text=True, timeout=120)
    refs = {}
    for line in result.stdout.splitlines():
        sha, name = line.split()
        if re.fullmatch("[a-f0-9]{40}", sha):
            refs[name] = sha
    commit = refs.get(ref + "^{}", refs.get(ref))
    if not commit:
        raise RuntimeError("Official tag could not be resolved")
    return commit


def failure_message(release, error):
    tag = (release or {}).get("tag_name", "")
    prefix = f"已发现官方 {tag}；" if re.fullmatch(r"v\d+\.\d+\.\d+", tag) else "官方版本检查未完成；"
    reason = error.public_reason if isinstance(error, CompatibilityError) else "定制构建或分发失败，请检查构建任务"
    return prefix + reason + "。当前服务和已验证版本保持可用。"


def run(args, **kwargs):
    shown = args[:-1] + ["<stage verified release>"] if args[0] == "ssh" else args
    print("+", " ".join(str(a) for a in shown), flush=True)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".pending")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def fetch(url, path=None):
    request = urllib.request.Request(url, headers={"User-Agent": "sub2api-policy-builder"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if path:
            temporary = Path(str(path) + ".pending")
            with temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            os.replace(temporary, path)
        else:
            return json.load(response)


def extract(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        for member in tar:
            parts = Path(member.name).parts
            if ".." in parts or Path(member.name).is_absolute():
                raise RuntimeError("Unsafe upstream archive path")
            if member.isdir():
                continue
            if not member.isfile() or len(parts) < 2:
                raise RuntimeError("Upstream archive contains an unsupported entry")
            dest = target.joinpath(*parts[1:])
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            dest.chmod(member.mode & 0o777)


def merge_custom(base, custom, target):
    """True base/current/upstream text merge; never overwrite a conflict."""
    for current in sorted(custom.rglob("*")):
        if not current.is_file():
            continue
        rel = current.relative_to(custom)
        original, newer = base / rel, target / rel
        if not original.exists():
            if newer.exists() and newer.read_bytes() != current.read_bytes():
                raise CompatibilityError(f"New custom file collides with upstream: {rel}", "定制功能与官方源码冲突，等待适配")
            newer.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, newer)
        elif not newer.exists():
            raise CompatibilityError(f"Upstream removed custom integration: {rel}", "官方调整了定制功能的接入位置，等待适配")
        else:
            result = subprocess.run(["git", "merge-file", "-p", str(current), str(original), str(newer)], capture_output=True)
            if result.returncode:
                raise CompatibilityError(f"Custom merge conflict: {rel}", "定制功能与官方源码冲突，等待适配")
            newer.write_bytes(result.stdout)


def migration_fingerprint(root):
    # A new or altered migration needs compatibility review before automatic
    # binary rollback can be promised. Includes non-SQL migration runners.
    paths = list((root / "backend/migrations").rglob("*"))
    paths.append(root / "backend/internal/repository/migrations_runner.go")
    return {str(p.relative_to(root)): digest(p) for p in paths
            if p.is_file() and not p.name.endswith("_test.go")}


def validate_bundle(bundle):
    meta = json.loads((bundle / "upstream.json").read_text())
    if digest(bundle / "policy-log.patch") != meta["patch_sha256"]:
        raise RuntimeError("Policy patch checksum mismatch")
    if not re.fullmatch("[a-f0-9]{40}", meta["upstream_commit"]):
        raise RuntimeError("Invalid pinned upstream commit")
    return meta


def container(home, image, root, workdir, command, cache_kind):
    cache = home / "cache" / cache_kind
    cache.mkdir(parents=True, exist_ok=True)
    name = "sub2api-policy-build-" + uuid.uuid4().hex
    try:
        run(["docker", "run", "--rm", "--name", name, "--label", "com.qiyuan.sub2api-policy-build=true", "--cpus=8", "--memory=12g", "--pids-limit=1024",
         "--cap-drop=ALL", "--security-opt=no-new-privileges", "--mount", f"type=bind,src={root},dst=/src",
         "--mount", f"type=bind,src={cache},dst=/cache", "-w", f"/src/{workdir}",
             image, "sh", "-ec", command], timeout=3600)
    finally:
        # Killing a timed-out Docker CLI alone does not stop its container.
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


def compile_release(home, root, version, commit, bundle):
    shutil.copy2(bundle / "upgrade/persistent_update_test.go", root / "backend/internal/service/policy_upgrade_flow_test.go")
    shutil.copy2(bundle / "upgrade/migration_upgrade_test.go", root / "backend/internal/repository/policy_migration_upgrade_test.go")
    base_archive = home / "archives" / (MIGRATION_BASE_COMMIT + ".tar.gz")
    if not base_archive.exists():
        fetch(f"https://codeload.github.com/{REPO}/tar.gz/{MIGRATION_BASE_COMMIT}", base_archive)
    if digest(base_archive) != MIGRATION_BASE_SHA256:
        raise RuntimeError("Migration fixture archive checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="migration-base-", dir=home) as tmp:
        extract(base_archive, Path(tmp))
        shutil.copytree(Path(tmp) / "backend/migrations", root / "migration-base")
    container(home, NODE_IMAGE, root, "frontend",
              "export COREPACK_HOME=/cache/corepack; corepack enable; corepack prepare pnpm@9.12.3 --activate; "
              "pnpm config set store-dir /cache/pnpm; pnpm install --frozen-lockfile; "
              "pnpm exec vitest run src/views/admin/__tests__/PolicyRequestsView.spec.ts src/components/common/__tests__/VersionBadge.policy.spec.ts; pnpm run build", "node")
    container(home, GO_IMAGE, root, "backend",
              "export GOPATH=/cache/gopath GOCACHE=/cache/gobuild GOMAXPROCS=8 GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct; "
              "go test -race ./internal/requestcontent; "
              "go test -race -tags unit ./internal/service -run '^(TestPolicy|TestUpdateService)'; "
              "go test -race ./internal/handler -run '^(TestPolicyRequestRecorder|TestClearCyberPolicy|TestOpenAIResponsesWebSocket.*Cyber)'; "
              "go test -race ./internal/handler/admin -run '^TestPolicyRequests'; "
              "go test -race ./migrations; "
              f"CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -tags embed -trimpath "
              f"-ldflags='-s -w -X main.Version={version} -X main.Commit={commit}-policy-log.{REVISION} "
              f"-X main.Date={now()} -X main.BuildType=release' -o /src/sub2api ./cmd/server; "
              f"/src/sub2api -version 2>&1 | grep -F '{version}'; "
              "go test -c -tags unit -o /src/policy-updater-test ./internal/service; "
              "go test -c -tags unit -o /src/policy-migration-test ./internal/repository", "go")
    verify_user_update_flow(root)
    verify_migration_upgrade(root)


def verify_migration_upgrade(root):
    name = "sub2api-policy-migration-" + uuid.uuid4().hex
    client = name + "-test"
    try:
        run(["docker", "run", "-d", "--name", name, "--network", "none",
             "--memory=2g", "--cpus=2", "--pids-limit=256",
             "--tmpfs", "/var/lib/postgresql:rw", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
             "-e", "POSTGRES_DB=policy_fixture", POSTGRES_IMAGE], timeout=300)
        run(["docker", "run", "--rm", "--name", client, "--network", "container:" + name,
             "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
             "--memory=2g", "--pids-limit=128",
             "--mount", f"type=bind,src={root},dst=/src,readonly",
             "-e", "POLICY_MIGRATION_FIXTURE=isolated-builder",
             "--entrypoint", "/src/policy-migration-test", GO_IMAGE,
             "-test.v", "-test.run", "^TestPolicyMigrationUpgradeFrom020$"], timeout=180)
    finally:
        for item in (client, name):
            subprocess.run(["docker", "rm", "-f", "-v", item], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)


def verify_user_update_flow(root):
    fixture = root / "update-flow"
    data, releases = fixture / "data", fixture / "releases"
    runtime = data / "policy-updates/runtime"
    runtime.mkdir(parents=True)
    test_binary = runtime / "sub2api"
    shutil.copy2(root / "policy-updater-test", test_binary)
    for path in [data, data / "policy-updates", runtime, test_binary]:
        os.chown(path, 1000, 1000)
    sha = digest(root / "sub2api")
    dest = releases / "releases" / sha
    dest.mkdir(parents=True)
    shutil.copy2(root / "sub2api", dest / "sub2api")
    atomic_json(releases / "catalog.json", {"schema":1,"checked_at":now(),"status":"ready","releases":[{
        "version":"99.0.0+policy-log.6","sha256":sha,"size":(root / "sub2api").stat().st_size,
        "upstream_commit":"a"*40,"patch_sha256":"b"*64,"features":FEATURES}]})
    name = "sub2api-policy-flow-" + uuid.uuid4().hex
    try:
        run(["docker","run","--rm","--name",name,"--user","1000:1000","--network","none","--read-only",
             "--cap-drop=ALL","--security-opt=no-new-privileges","--memory=2g","--pids-limit=128",
             "--mount",f"type=bind,src={data},dst=/app/data",
             "--mount",f"type=bind,src={releases},dst=/app/policy-releases,readonly",
             "--mount",f"type=bind,src={root / 'sub2api'},dst=/src/sub2api,readonly",
             "-e","POLICY_UPDATER_INTEGRATION=isolated-builder","-e","POLICY_UPDATER_READONLY=1",
             "--entrypoint","/app/data/policy-updates/runtime/sub2api",GO_IMAGE,
             "-test.v","-test.run","^TestPolicyUpdatePersistentExecutableFlow$"],timeout=180)
    finally:
        subprocess.run(["docker","rm","-f",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)


def verify_cached_update_flow(home, bundle, meta, record, result_dir):
    # Adding a validation gate does not change the already built application.
    # Restore its exact sources and exercise the existing binary, without
    # rebuilding or silently replacing an immutable release version.
    archives = home / "archives"
    base_archive = archives / (meta["upstream_commit"] + ".tar.gz")
    if digest(base_archive) != meta["upstream_archive_sha256"]:
        raise RuntimeError("Pinned upstream archive checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="verify-", dir=home) as tmp:
        root, base = Path(tmp) / "target", Path(tmp) / "base"
        extract(base_archive, base)
        extract(archives / (record["upstream_commit"] + ".tar.gz"), root)
        merge_custom(base, bundle / "source", root)
        shutil.copy2(result_dir / "sub2api", root / "sub2api")
        shutil.copy2(bundle / "upgrade/persistent_update_test.go", root / "backend/internal/service/policy_upgrade_flow_test.go")
        container(home, GO_IMAGE, root, "backend",
                  "export GOPATH=/cache/gopath GOCACHE=/cache/gobuild GOMAXPROCS=8 GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct; "
                  "go test -c -tags unit -o /src/policy-updater-test ./internal/service", "go")
        verify_user_update_flow(root)
    record["persistent_update_verified"] = True
    atomic_json(result_dir / "release.json", record)


def prepare(home, bundle, release):
    meta = validate_bundle(bundle)
    tag = release["tag_name"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or release.get("prerelease") or release.get("draft"):
        raise RuntimeError("Only official stable semantic versions are accepted")
    version = tag[1:] + f"+policy-log.{REVISION}"
    result_dir = home / "releases" / version
    if (result_dir / "release.json").exists():
        record = json.loads((result_dir / "release.json").read_text())
        # This immutable artifact already passed source/commit, checksum, build
        # and update-flow verification. A transient GitHub outage must not
        # prevent its first delivery or hourly catalog refresh.
        if (record["version"] != version or record["patch_sha256"] != meta["patch_sha256"] or
                not re.fullmatch("[a-f0-9]{40}", record["upstream_commit"]) or
                (tag[1:] == meta["upstream_version"] and record["upstream_commit"] != meta["upstream_commit"])):
            raise RuntimeError("An existing version changed source; increment policy revision before rebuilding")
        if digest(result_dir / "sub2api") != record["sha256"]:
            raise RuntimeError("Cached binary checksum mismatch")
        if not record.get("persistent_update_verified"):
            verify_cached_update_flow(home, bundle, meta, record, result_dir)
        return record, result_dir
    commit = official_tag_commit(tag)
    archives = home / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    for revision in {meta["upstream_commit"], commit}:
        archive = archives / f"{revision}.tar.gz"
        if not archive.exists():
            fetch(f"https://codeload.github.com/{REPO}/tar.gz/{revision}", archive)
    base_archive = archives / (meta["upstream_commit"] + ".tar.gz")
    if digest(base_archive) != meta["upstream_archive_sha256"]:
        raise RuntimeError("Pinned upstream archive checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="build-", dir=home) as tmp:
        tmp = Path(tmp)
        base, patched, target = tmp / "base", tmp / "patched", tmp / "target"
        extract(base_archive, base)
        shutil.copytree(base, patched)
        run(["git", "apply", "--check", bundle / "policy-log.patch"], cwd=patched)
        run(["git", "apply", bundle / "policy-log.patch"], cwd=patched)
        # Snapshot and executable patch must agree, otherwise refuse stale input.
        for current in (bundle / "source").rglob("*"):
            if current.is_file() and current.read_bytes() != (patched / current.relative_to(bundle / "source")).read_bytes():
                raise RuntimeError("Policy source and patch disagree")
        extract(archives / f"{commit}.tar.gz", target)
        if migration_fingerprint(base) != migration_fingerprint(target):
            raise CompatibilityError("Official migration or runner changed", "数据库结构或迁移流程变化，等待兼容性验证")
        merge_custom(base, bundle / "source", target)
        compile_release(home, target, version, commit, bundle)
        binary = target / "sub2api"
        record = {"version": version, "sha256": digest(binary), "size": binary.stat().st_size,
                  "published_at": now(), "upstream_commit": commit, "patch_sha256": meta["patch_sha256"], "features": FEATURES,
                  "persistent_update_verified": True}
        result_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, result_dir / "sub2api")
        atomic_json(result_dir / "release.json", record)
        return record, result_dir


def stage(home, catalog, binary_dir=None, record=None):
    """Stage immutable content-addressed files, then atomically publish the index.

    The receiver code has no shell interpolation of external version strings and
    never invokes docker, modifies the runtime file or restarts production.
    """
    receiver = r'''
import hashlib,json,os,pathlib,re,sys,tarfile,tempfile
import shutil
root=pathlib.Path("/opt/sub2api-deploy/policy-releases")
root.mkdir(parents=True,exist_ok=True)
root.chmod(0o755)
(root/"releases").mkdir(exist_ok=True)
(root/"releases").chmod(0o755)
if shutil.disk_usage(root).free < 2560*1024*1024:raise RuntimeError("insufficient staging disk space")
with tempfile.TemporaryDirectory(prefix=".incoming-",dir=root) as temp:
 temp=pathlib.Path(temp)
 with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as tar:
  for entry in tar:
   if entry.name not in ("catalog.json","sub2api","release.json") or not entry.isfile(): raise RuntimeError("invalid staged file")
   with tar.extractfile(entry) as src,(temp/entry.name).open("wb") as dst:
    import shutil;shutil.copyfileobj(src,dst)
 if (temp/"sub2api").exists():
  r=json.loads((temp/"release.json").read_text()); h=hashlib.sha256()
  with (temp/"sub2api").open("rb") as f:
   for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
  if h.hexdigest()!=r["sha256"] or (temp/"sub2api").stat().st_size!=r["size"]:raise RuntimeError("checksum mismatch")
  out=root/"releases"/r["sha256"];out.mkdir(parents=True,exist_ok=True)
  out.chmod(0o755)
  (temp/"sub2api").chmod(0o755);os.replace(temp/"sub2api",out/"sub2api")
  (temp/"release.json").chmod(0o644);os.replace(temp/"release.json",out/"release.json")
 catalog=json.loads((temp/"catalog.json").read_text())
 available=[r for r in catalog["releases"] if (root/"releases"/r["sha256"]/"sub2api").is_file()]
 if catalog["status"]=="ready" and catalog["releases"] and catalog["releases"][0] not in available:raise RuntimeError("latest binary not staged")
 catalog["releases"]=available
 (temp/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False))
 (temp/"catalog.json").chmod(0o644);os.replace(temp/"catalog.json",root/"catalog.json")
 if catalog["status"]=="ready":
  keep={r["sha256"] for r in available}
  for old in (root/"releases").glob("*"):
   if re.fullmatch("[a-f0-9]{64}",old.name) and old.name not in keep and old.is_dir() and not old.is_symlink():shutil.rmtree(old)
print("staged",catalog["status"],flush=True)
'''
    import shlex
    with tempfile.TemporaryDirectory(prefix="stage-", dir=home) as temp:
        temp = Path(temp)
        atomic_json(temp / "catalog.json", catalog)
        archive = temp / "stage.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(temp / "catalog.json", arcname="catalog.json")
            if binary_dir:
                tar.add(binary_dir / "sub2api", arcname="sub2api")
                tar.add(binary_dir / "release.json", arcname="release.json")
        failures = []
        for node in NODES:
            try:
                if node == "qiyuan-tokyo" and binary_dir:
                    # Keep bulk data off the unreliable bastion-to-Tokyo upload
                    # path. The encrypted package is fetched from the US node;
                    # secrets, digests and the verifier still travel over SSH.
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("policy_pull_transport", Path(__file__).with_name("pull_transport.py"))
                    transport = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(transport)
                    transport.stage_tokyo(catalog, record, receiver, run)
                    continue
                with archive.open("rb") as stream:
                    run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", node,
                         "python3 -c " + shlex.quote(receiver)], stdin=stream, timeout=1200)
            except Exception as error:
                failures.append(f"{node}: {error}")
        if failures:
            raise RuntimeError("; ".join(failures))


def main():
    def terminate(_signal, _frame):
        raise KeyboardInterrupt("builder terminated")
    signal.signal(signal.SIGTERM, terminate)
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_HOME / "policy-log")
    parser.add_argument("--no-stage", action="store_true", help="Build and verify only")
    args = parser.parse_args()
    home, bundle = args.home.resolve(), args.bundle.resolve()
    home.mkdir(parents=True, exist_ok=True)
    with (home / "build.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        catalog_file = home / "catalog.json"
        catalog = json.loads(catalog_file.read_text()) if catalog_file.exists() else {"schema":1,"releases":[]}
        was_ready = catalog.get("status") == "ready"
        staged_file = home / "staged.json"
        staged = json.loads(staged_file.read_text()) if staged_file.exists() else {}
        release = None
        try:
            release = latest_official_release()
            catalog.update(checked_at=now(), upstream_version=release['tag_name'], status="building", message=f"已发现官方 {release['tag_name']}，正在验证保留异常记录的更新包；当前服务继续运行。")
            atomic_json(catalog_file, catalog)
            if not args.no_stage:
                # A node outage must not block compilation or delivery to the other node.
                with contextlib.suppress(Exception):
                    stage(home, catalog)
            record, result = prepare(home, bundle, release)
            already_staged = was_ready and record in catalog["releases"] and staged.get("sha256") == record["sha256"]
            previous = [r for r in catalog["releases"] if r["version"] != record["version"]]
            catalog.update(checked_at=now(), status="ready", message="", releases=([record] + previous)[:20])
            if not args.no_stage:
                # Retain the verified record even when delivery is interrupted.
                # A later status refresh must not forget a version already
                # delivered to one node or remove its cached binary.
                atomic_json(catalog_file, dict(catalog, status="building", message=f"官方 {release['tag_name']} 已验证，正在分发保留异常记录的更新包。"))
                stage(home, catalog, None if already_staged else result, record)
                atomic_json(staged_file, {"sha256":record["sha256"],"nodes":list(NODES),"at":now()})
            else:
                catalog["status"] = "verified"
            atomic_json(catalog_file, catalog)
            if not args.no_stage:
                keep = {r["version"] for r in catalog["releases"]}
                for old in (home / "releases").glob("*"):
                    if re.fullmatch(r"\d+\.\d+\.\d+\+policy-log\.\d+", old.name) and old.name not in keep and old.is_dir() and not old.is_symlink():
                        shutil.rmtree(old)
            return 0
        except Exception as error:
            # Do not expose raw build logs or paths in the user-facing UI.
            print(f"BUILD FAILED: {error}", file=sys.stderr, flush=True)
            catalog.update(checked_at=now(), status="failed", message=failure_message(release, error))
            atomic_json(catalog_file, catalog)
            if not args.no_stage:
                with contextlib.suppress(Exception):
                    stage(home, catalog)
            return 1


if __name__ == "__main__":
    sys.exit(main())
