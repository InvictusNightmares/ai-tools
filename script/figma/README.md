# Figma Anthropic adapter

This directory contains the Anthropic-compatible adapter used by Claude Code.
It forwards text and tool-use requests to Figma Make and supports base64
JPEG/PNG/GIF/WebP images and PDFs. Word, Excel, ZIP, video, and URL-based
attachment sources are rejected before any upstream request.

## Prepare safe runtime templates

Image and PDF requests need runtime metadata copied from a real Figma Make
request plus the matching Foundry sync request. Never deploy a raw cURL
capture: it can contain cookies, authorization headers, historical chats,
binary references, prompts, signed download URLs, and project source.

Create the capture from a new synthetic Figma Make project with no private
content. The preparer retains at most ten non-binary project files by default.
If an audited synthetic Figma starter contains more, pass the exact reviewed
limit with `--max-project-files`; the hard limit is 64. Never raise this for
an existing private project.

First copy the matching `figmake` request and generate the request runtime
template plus an optional environment fragment:

```sh
python3 prepare-request-template.py \
  --clipboard \
  --allow-sensitive-input \
  --max-project-files "$REVIEWED_PROJECT_FILE_COUNT" \
  --foundry-origin-host "$CAPTURED_FIGMA_SITE_HOST" \
  --output "$TEMPLATE_OUTPUT" \
  --env-output "$TEMPLATE_ENV_OUTPUT" \
  --runtime-template-path "$RUNTIME_TEMPLATE_PATH"
```

Then copy the matching `/api/cortex/foundry/sync` request and generate a
separate source-only sync template:

```sh
python3 prepare-foundry-sync-template.py \
  --clipboard \
  --allow-sensitive-input \
  --output "$FOUNDRY_SYNC_TEMPLATE_OUTPUT"
```

Without `--clipboard`, the tool reads JSON or cURL from standard input.
Authentication headers are rejected by default. The explicit
`--allow-sensitive-input` option is only for a local sanitization step; Cookie,
Authorization, API-key, and CSRF headers are never written.

The generated files have mode `0600`. Each JSON file is marked with its
runtime-template format so the adapter rejects raw cURL or unprocessed JSON at
startup and again before an attachment request. The request template contains
the reviewed synthetic project snapshot and Foundry workload metadata. The
Foundry sync template contains only reviewed source entries; captured
`src/imports` binaries and their expiring signed download URLs are removed.

At request time the adapter uploads the current attachment, lists its new
Figma-signed download URL, adds a dynamic `src/imports/...` entry to an
in-memory copy of the source-only sync template, syncs the Foundry sandbox, and
then calls the model. Signed URLs are never persisted.

The request template contains only:

- a sanitized `body` with one empty user message, no chat history, no old
  binary files, and no old attachment prompt;
- adapter-allowlisted runtime headers;
- non-secret runtime `config` when it can be derived from the capture.

`--attachment-runtime-only` removes the project and workload snapshot. Keep it
for isolated request-shape diagnostics only; it is not sufficient for the
full Foundry-backed image/PDF flow.

The environment fragment points `FIGMA_REQUEST_TEMPLATE_FILE` at
`--runtime-template-path` and includes any derived Figma user, file, thread, and
attachment GUID values. Set that option to the final server path; otherwise the
tool writes the local `--output` path, which is unsuitable after copying the
template to another host.
Review key names and file counts, but do not print either the raw capture or
credential files into logs. Keep the Figma cookie in the separately protected
cookie file.

## Pre-deployment checks

Run all offline tests before copying files:

```sh
python3 -m unittest \
  test_anthropic_adapter.py \
  test_prepare_request_template.py \
  test_prepare_foundry_sync_template.py \
  test_merge_adapter_env.py \
  test_registration_sql.py \
  test_smoke_test.py
```

Confirm the deployment environment has non-empty adapter authentication and
Figma runtime values, and that the template and cookie files are both mode
`0600`. Do not source or print the environment file during validation.

The production unit runs as the dedicated `figma-adapter` system user. Keep
the application directory owned by `root:figma-adapter` with mode `0750`;
install source files as root-owned `0644`, and install the environment, Cookie,
and both sanitized templates as `figma-adapter:figma-adapter` with mode `0600`.
Create the non-login system user before installing the unit. Do not grant that
user access to the old raw cURL capture.

## Canary deployment

Keep the production adapter on its existing port. Start the new adapter as a
separate canary on port `18091` with a separate environment file and the
sanitized JSON template.

Before starting the canary:

1. Record the current service status and health response.
2. Copy the current adapter, service definition, environment file, and runtime
   template into a timestamped directory readable only by the service owner.
3. Copy the new adapter, smoke test, and both sanitized templates into the
   canary directory. Do not copy a raw cURL capture.
4. Merge the generated environment fragment into the canary environment with
   `merge-adapter-env.py`. The helper accepts only reviewed non-secret runtime
   keys, preserves the adapter API key from the base file, and retains the
   existing output file owner/group during an in-place merge:

   ```sh
   python3 merge-adapter-env.py \
     --base "$CANARY_ENV" \
     --overlay "$TEMPLATE_ENV_OUTPUT" \
     --output "$CANARY_ENV" \
     --set FIGMA_ADAPTER_PORT=18091
   ```

   Pass the canary host, Cookie path, template path, and size limits with
   additional `--set NAME=VALUE` arguments, including
   `FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE`. Never place the adapter API key in the
   generated overlay or on a command line.
5. Bind the canary only to the interface required for host and sub2api
   verification.

Run the direct canary smoke test:

```sh
python3 smoke-test.py \
  --origin http://172.18.0.1:18091 \
  --env-file "$CANARY_ENV"
```

The command must pass health, unauthenticated rejection, text generation,
tool-use, synthetic PNG, and synthetic PDF checks. Then send the same text and
tool-use cases through the sub2api canary account using a real Claude Code
client. A model-list response alone is not sufficient.

Prove the Claude Code agent loop with real file tools in a disposable
directory. Use the existing Claude Code user settings; do not place its token
on the command line:

```sh
agent_dir=$(mktemp -d /private/tmp/figma-claude-agent.XXXXXX)
agent_token=$(uuidgen | tr -d '-')
cli_session=$(uuidgen | tr '[:upper:]' '[:lower:]')
printf '%s\n' "$agent_token" > "$agent_dir/input.txt"
(
  cd "$agent_dir" &&
  claude -p --session-id "$cli_session" \
    --model claude-opus-5 --setting-sources user \
    --tools 'Read,Write,Edit' --allowedTools 'Read,Write,Edit' \
    --permission-mode acceptEdits --no-session-persistence \
    --output-format json \
    'Read input.txt; Write output.txt with READ_OK:<value> on line one and EDIT_PENDING on line two; Edit EDIT_PENDING to EDIT_OK; never use Bash; finally reply only AGENT_DONE.'
)
printf 'READ_OK:%s\nEDIT_OK\n' "$agent_token" > "$agent_dir/expected.txt"
cmp -s "$agent_dir/expected.txt" "$agent_dir/output.txt"
```

`cmp` must return zero. Verify the matching session in `usage_logs` used the
canary account, requested `claude-opus-5`, mapped to
`anthropic-claude-4.8-opus`, and identified Claude Code as its user agent.

Before cutover, also retain evidence of one Claude Code request through the
same sub2api path lasting longer than 60 seconds. A recent `usage_logs`
duration is acceptable; record only its request ID and duration, not prompts or
credentials.

## Production cutover

Cut over only after the direct and sub2api canaries pass:

1. Recheck the backup and current production health.
2. Install the new adapter and both sanitized templates without changing the
   cookie.
3. Apply only the reviewed environment-key changes.
4. Restart the adapter service; do not restart PostgreSQL or Redis.
5. Verify `/health`, then run `smoke-test.py` against production.
6. Verify text, tool-use, file read/write, PNG, and PDF behavior from Claude
   Code through sub2api.

Do not remove the canary or backup until the production checks have completed.

## Rollback

If startup, health, authentication, text, tool-use, image, PDF, or Claude Code
agent behavior fails:

1. Stop routing new traffic to the updated adapter.
2. Restore the backed-up adapter, environment file, service definition, and
   prior sanitized template.
3. Reload the service manager only if the unit changed, then restart the old
   adapter.
4. Verify the old `/health` response and a minimal authenticated text request.
5. Restore the previous sub2api account endpoint or model mapping only if it
   was changed during cutover.

Keep the failed canary logs and non-secret smoke output for diagnosis. Never
attach the cookie file, environment file, or raw cURL capture to an issue.
