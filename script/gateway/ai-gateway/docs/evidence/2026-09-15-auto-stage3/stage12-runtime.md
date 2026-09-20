# stage12 real session switching check

- Tokyo test Key was used only in a remote process environment; it is not included here.
- Temporary Auto bound to `127.0.0.1:8092`, Guard to `127.0.0.1:8011`, and Tokyo upstream to `106.14.254.110:9881`.
- Four sequential requests shared one session ID and used safe prompts. Results (metadata only):
  - case 1: HTTP 200, `deepseek-flash`, prompt 10, completion 16;
  - case 2: HTTP 200, `deepseek-flash`, prompt 57, completion 6604;
  - case 3: HTTP 200, `deepseek-flash`, prompt 33, completion 3812;
  - case 4: route audit selected `gpt-5.6-luna` with generated effort `low`, action `upgrade`, reason `quality_upgrade`, but the real upstream returned HTTP 503.
- The first three turns demonstrate the configured three-turn upgrade cooldown; the fourth demonstrates that turn persistence now permits an upgrade. The 503 is an upstream/provider model mapping or account availability issue, not a Guard block and not a routing failure.
- Temporary process was stopped and port 8092 released. Existing Nginx 4000/4001 and production services were not modified.
