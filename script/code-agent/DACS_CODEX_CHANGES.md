# DACS Codex Changes

This document summarizes the local changes made while debugging Codex startup inside DACS.

## Problem

Running Codex inside DACS fails with permission errors around Codex runtime temp files:

```text
WARNING: failed to clean up stale arg0 temp dirs: Operation not permitted (os error 1)
WARNING: proceeding, even though we could not update PATH: Operation not permitted (os error 1)
Error loading configuration: Operation not permitted (os error 1)
```

The failing path changed during testing, but the root issue remained that Codex tries to write under:

```text
$CODEX_HOME/tmp/arg0/codex-arg0...
```

DACS allows very limited writes. A probe from inside DACS showed only this path is writable:

```text
/var/folders/2v/4svhn1f54qs9vz4rf_75spgh0000gn/T/
```

Most user and meili directories failed write checks inside DACS.

## Created Files

### `/Users/invictus/bin/codex-dacs`

Purpose: initial wrapper to run Codex with a different `CODEX_HOME`.

Current behavior:

```text
1. Tries to find a writable CODEX_HOME candidate.
2. Copies config/auth files into that home.
3. Runs `codex`.
```

Current status:

```text
Not the preferred path anymore.
```

Reason:

```text
DACS rejected all non-TMPDIR writable candidates, and copying config files also hit Operation not permitted.
```

### `/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex`

Purpose: PATH shadow wrapper, also called the "replacement" or "stub" approach.

DACS has this directory early in `PATH`:

```text
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin
```

So running this in DACS:

```bash
codex
```

should resolve to:

```text
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex
```

Current wrapper strategy:

```text
1. Directly runs the native Codex binary instead of the npm launcher.
2. Uses `exec -a codex` so argv[0] appears as `codex`.
3. Sets `CODEX_HOME` to a fresh per-process directory under `$TMPDIR`.
4. Reads `OPENAI_API_KEY` from `~/.codex/auth.json` into the environment.
5. Passes Codex config through `-c` command-line overrides instead of copying config.toml.
```

Native Codex binary used:

```text
/usr/local/lib/node_modules/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/codex/codex
```

Vendor path added to `PATH`:

```text
/usr/local/lib/node_modules/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/path
```

Current config passed with `-c`:

```text
model_provider = "aether"
model = "gpt-5.4"
model_reasoning_effort = "high"
network_access = "enabled"
disable_response_storage = true

[model_providers.aether]
name = "OpenAI"
base_url = "https://niffler.org/v1"
wire_api = "responses"
requires_openai_auth = true
```

Current status:

```text
Preferred active experiment.
```

Run inside DACS:

```bash
codex
```

or explicitly:

```bash
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex
```

### `/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/dacs-writable-probe`

Purpose: probe which directories are writable from inside DACS.

Run inside DACS:

```bash
dacs-writable-probe
```

Observed DACS result:

```text
OK    /var/folders/2v/4svhn1f54qs9vz4rf_75spgh0000gn/T/
FAIL  /Users/invictus
FAIL  /tmp
FAIL  /private/tmp
FAIL  /Users/invictus/meili
FAIL  /Users/invictus/meili/zhangcheng
FAIL  /Users/invictus/meili/zhangcheng/6
FAIL  /Users/invictus/meili/zhangcheng/98/短期外发
FAIL  /Users/invictus/meili/zhangcheng/98/长期外发
FAIL  /Users/invictus/meili/zhangcheng/Applications
FAIL  /Users/invictus/meili/zhangcheng/Applications/.globalBase
FAIL  /Users/invictus/meili/zhangcheng/Applications/.globalBase/var
FAIL  /Users/invictus/meili/secure/zhangcheng/104
FAIL  /Users/invictus/meili/secure/zhangcheng/110
```

## Important Findings

### Codex always writes `tmp/arg0`

Even when bypassing the npm launcher and directly invoking the native binary, Codex still tries to create:

```text
$CODEX_HOME/tmp/arg0/codex-arg0...
```

So the issue is inside the native Codex runtime behavior, not only the npm wrapper.

### Fixed `CODEX_HOME` under meili does not work in DACS

These failed inside DACS:

```text
/Users/invictus/meili/zhangcheng/.codex-dacs-home
/Users/invictus/meili/zhangcheng/Applications/.globalBase/var/codex-home
```

### Fixed `$TMPDIR/codex-home` also failed

This failed earlier:

```text
/var/folders/2v/4svhn1f54qs9vz4rf_75spgh0000gn/T/codex-home/config.toml
```

The wrapper was changed to use a fresh per-process temp home instead:

```text
$TMPDIR/codex-home-dacs-$$
```

### Copying config files inside DACS failed

This failed inside DACS:

```text
cp: .../config.toml: Operation not permitted
```

The current wrapper avoids copying config and instead passes config through `-c` arguments.

## Modified Files Outside This Repo

These files are outside `/Users/invictus/Github/ai-tools`:

```text
/Users/invictus/bin/codex-dacs
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/dacs-writable-probe
```

## Verification Commands

Run outside DACS:

```bash
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex --version
```

Expected:

```text
codex-cli 0.125.0
```

Run inside DACS:

```bash
which codex
```

Expected:

```text
/Users/invictus/meili/zhangcheng/Applications/.globalBase/usr/bin/codex
```

Run inside DACS:

```bash
codex
```

If it still fails, capture the full error and check whether it references:

```text
$TMPDIR/codex-home-dacs-<pid>/tmp/arg0
```

## Current Next Step

Test the latest no-copy wrapper inside DACS:

```bash
codex
```

The latest wrapper no longer copies `config.toml` or `auth.json`. If DACS still blocks Codex, the remaining blocker is likely Codex native runtime writing to `$CODEX_HOME/tmp/arg0` even under the only DACS-writable path.
