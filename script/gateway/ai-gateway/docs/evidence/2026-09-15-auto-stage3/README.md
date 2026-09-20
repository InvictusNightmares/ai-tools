# Auto stage3 GPU regression and temporary chain check

- Archive: `/tmp/auto-gateway-stage9.VMeN7R.tgz`
- SHA-256: `9b43e3a4f001b589d620c2d4e225046a25a288a8a92629f5e8090acf1b3422c9`
- Host: `qiyuan-gpu`
- Regression: `gofmt`, full `go test`, `go vet`, race detector, and static `auto-preview`/`auto-server` builds all passed (`verify_exit=0`).
- Temporary chain: Auto bound only to `127.0.0.1:8092`, Guard `127.0.0.1:8011`, Tokyo upstream `106.14.254.110:9881`; existing Nginx `4000/4001` was untouched.
- Safe allow sample reached the real Tokyo front and returned `401 INVALID_API_KEY` for a deliberately fake token. Audit and usage spools each received one redacted event; route selected `deepseek-flash` with generated effort `none`.
- Credential sample was stopped by Guard with HTTP `403`, `preflight_blocked`, and `secret_input_not_allowed`; it did not call the upstream. stage10 re-verified the new blocked/unavailable audit rows; see `stage10-runtime.md`.
- Temporary Auto was stopped and port `8092` confirmed free. No production process, Nginx configuration, Guard container, or regional traffic was changed.
