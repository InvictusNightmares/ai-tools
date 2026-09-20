# stage10 preflight audit runtime check

- stage10 SHA-256: `d51b321a1a9c33f69fe51e10a9fd8a61ea0d53d9fa9868b394621ab00457cf73`
- GPU full regression: gofmt, test, vet, race, static auto-server build; `verify_exit=0`.
- On temporary Auto `127.0.0.1:8092` with real Guard `127.0.0.1:8011`, a redacted credential sample returned HTTP 403 (`preflight_blocked`), with audit action `preflight_blocked` and reason `secret_input_not_allowed`; no upstream call.
- On temporary Auto `127.0.0.1:8093` with an unreachable Guard endpoint, a safe sample returned HTTP 503 (`preflight_unavailable`), with audit action `preflight_unavailable` and reason `guard_transport_error`; no routing or upstream call.
- Temporary processes were stopped and ports released. Production Nginx 4000/4001, Guard 8011, and regional services were not changed.
