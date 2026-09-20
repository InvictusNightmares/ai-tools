# stage12 real response-cache check

- Tokyo test Key was used only in a remote process environment and is not stored here.
- Temporary Auto used `127.0.0.1:8092`, Guard `127.0.0.1:8011`, Tokyo upstream `106.14.254.110:9881`, and API key group marker `test`.
- Two identical requests returned HTTP 200 with `deepseek-flash`.
- Usage events: first `attempt=true`, `response_cache_hit=false`, input 14/output 43; second `attempt=false`, `response_cache_hit=true`, input/output 0. This proves the replay did not make a second provider attempt or duplicate provider token accounting.
- Both requests produced audit and usage events. Temporary process was stopped and no production Nginx or Guard service was changed.
