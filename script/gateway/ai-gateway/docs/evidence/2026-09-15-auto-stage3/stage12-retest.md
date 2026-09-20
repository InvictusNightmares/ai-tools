# stage12 retest after Tokyo test Key update

- The user updated the Tokyo `test` Key to allow GPT models. The Key was used only in a remote process environment and is not stored here.
- Temporary Auto used `127.0.0.1:8092`, Guard `127.0.0.1:8011`, and Tokyo upstream `106.14.254.110:9881`.
- Four sequential requests shared one session. Metadata-only results:
  - cases 1-3: HTTP 200, `deepseek-flash` (the three-turn upgrade cooldown);
  - case 4: HTTP 200, `gpt-5.6-luna`, `finish=stop`, prompt/completion usage present, audit action `upgrade` and reason `quality_upgrade`.
- This confirms the previous case-4 503 was caused by the test Key's then-current GPT permission, not the Auto route or Guard order.
- Temporary process was stopped; production Nginx 4000/4001 and Guard were unchanged.
