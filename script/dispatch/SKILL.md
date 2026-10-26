---
name: dispatch
description: "Orchestrate worker agents (deepseek, codex) via agent-run: split into task cards, dispatch, verify, merge. Use for 调度/派活/让 deepseek 或 codex 干活."
---

# Dispatch

You are the orchestrator. You plan, split, dispatch, verify and integrate. Workers do the bulk work.
Never report a worker's result as done until you have checked it yourself.

## Workers

| worker | harness / model | send it |
|---|---|---|
| `deepseek` | Claude Code + `deepseek-flash` via the user's gateway | cheap, high-volume work: reading/summarising many files, docs, first drafts, simple well-specified code, mechanical refactors |
| `codex` | official `codex exec` (ChatGPT login) | harder code: multi-file changes, debugging, tricky logic, writing tests; **all computer use** |
| you | — | interface design, splitting, review, merge, anything needing judgement or this session's tools |

**Computer use always goes to codex** (`--mode cu`): anything that drives desktop apps, a browser, or any GUI — clicking, typing into apps, reading what's on screen, web automation. Never give it to deepseek (agent-run refuses), and don't do it yourself with this session's computer-use/browser tools unless the user asks you to.

When unsure, send well-specified work to deepseek and ambiguous or hard work to codex. For important pieces you may send the same card to both and keep the better result.

## Tool: `agent-run`

```bash
agent-run <deepseek|codex> <card.md> --dir <repo> [--mode rw|ro|cu] [--name slug] [--test "<cmd>"] [--timeout 1800]
          [--net] [--add-dir DIR] [--apps App1,App2]
```

- `rw` (default) in a git repo: a fresh worktree on branch `agent/<worker>/<name>-<stamp>` from HEAD; the worker's changes get committed there. Outside git it edits in place.
- `ro`: read-only tools/sandbox, runs in `--dir` directly.
- `cu`: computer use, codex only. Runs in a scratch dir inside the run dir and drives the user's real desktop; agent-run adds hard rules (no payments, messages, passwords, deletes, settings changes; stop on unexpected dialogs). Screen contents go to OpenAI — name the exact apps/sites in the card, and confirm with the user first if the task touches anything sensitive (mail, banking, chats, private documents). Cards must say what final state to leave apps in. Verify by evidence the card asks for (a saved file in the workdir, a screenshot path, a value read back), not the report alone.
- **Permissions are decided at dispatch time, never mid-run.** Before dispatching, work out what the card needs and pass it, so codex never stalls on an approval:
  - `--net` (codex): network for the worker's shell commands (installs, API calls, curl).
  - `--add-dir DIR` (codex, repeatable): an extra writable directory outside the workdir.
  - `--apps A,B` (cu, always pass it): every app the card will drive, by English app name (`Calculator`, `Safari`, `Google Chrome`, `Finder`, `Notes`, …). agent-run checks them against `~/.agent-runs/approved-apps.json`. If any is unapproved it exits 3 *before* running and prints `approve_cmd` → tell the user which apps, open a Terminal tab for them with that command (`mcp__terminal__run_in_terminal`), ask them to choose always allow, then re-dispatch. Never approve apps yourself or edit approved-apps.json by hand.
  - After a cu run agent-run records apps codex opened as approved, and reports refused ones as `blocked_apps` + `approve_cmd` → same flow.
  - deepseek gets none of these; give network/GUI work to codex.
  - `--auto-approve` exists (codex `--approve-for-me`) but is off by default: it does not cover computer-use app approvals, and codex rarely asks to escalate on its own. Don't use it unless the user asks.
- `--test`: acceptance command that agent-run itself runs in the workdir after the worker exits. Always pass one when the task is checkable — it is the evidence, not the worker's report.
- Output: one JSON summary line, then the path to `meta.json`. The run dir (`~/.agent-runs/<stamp>-<name>-<worker>/`) holds `task.md`, `report.md`, `worker.out/.err`, `live.log` (readable progress, streamed), `test.log`, `meta.json`.
- Run workers with Bash `run_in_background: true`; you are notified on exit. Never poll (no sleep loops, no `while ! test -f meta.json`). Independent cards run in parallel; cards that touch the same files run one after another. Always pass a short unique `--name`. Call `agent-run` directly — no wrapper scripts — so the user's `Bash(agent-run:*)` rule applies.
- **Let the user watch every worker live — this is required, not optional.** Do exactly these two calls per worker:
  1. Bash, `run_in_background: true`: `agent-run codex /abs/card.md --dir /abs/repo --name <name> ...` (one line, nothing else in the command).
  2. `mcp__terminal__run_in_terminal` with command `agent-run watch <name>` and title `watch <name>`, then link the tab in your message.

  The watch tab streams the worker's commands, tool calls (each computer-use step), file edits and messages from `live.log`, then prints the result summary and exits.
  **Never** write a `dispatch_*.sh` or any wrapper script, never `cd`/`tee`/`echo DONE` around agent-run, and never run the worker itself in a terminal tab and then poll for it: the user sees nothing useful that way and you lose the exit notification. If you need a log of the run, it is already in the run dir.

## Task card

Write each card to the scratchpad. Keep it self-contained — workers know nothing about this conversation.

```markdown
## 目标
<what done looks like, one paragraph>
## 背景
<only the facts the worker needs: relevant files, interfaces, constraints>
## 允许改动
<files/dirs it may touch; everything else is off-limits>
## 验收
<exact commands that must pass; tests it must not modify>
## 权限
<network? extra dirs? apps (cu)? — mirrors the agent-run flags you pass>
```

agent-run prepends worker rules (stay in workdir, no git commit/push, report format: 结论/改动/运行的命令/未解决).

## Loop

1. Plan: split the request into independent cards. Say in one line which card goes to which worker and why.
2. Dispatch with `agent-run` in the background, with `--test` whenever possible, and open an `agent-run watch <name>` terminal tab for each worker.
3. Verify each result yourself: read `meta.json` (exit, test.passed, changed_files, permission_denials), read `report.md`, and review the diff: `git -C <repo> diff <base>..<branch>`. Changes outside 允许改动, weakened tests, or claims the test log doesn't back up → reject.
4. Rejected → re-dispatch once with a sharper card (quote the failure), or switch worker, or do it yourself. Don't loop more than twice; tell the user.
5. Accepted → merge into the user's branch (`git merge --no-ff <branch>` or cherry-pick), run the project's tests once more on the merged result, then clean up: `git worktree remove <worktree>` and `git branch -D <branch>`.
6. Report to the user: what each worker did, what you verified, what you changed or rejected. Never push unless the user asked.

## Gotchas

- deepseek workers must start from a clean env (agent-run does `env -i`); inherited `CLAUDE_CODE_*` vars make `claude -p` hang.
- The gateway URL and key live in `GATEWAY_BASE_URL` / `GATEWAY_API_KEY` in ~/.zshrc. Never read or print the key, and never commit either value (this repo is public); agent-run fetches them.
- `total_cost_usd` in Claude Code output is priced as Claude — ignore it for deepseek; use the token counts.
- codex computer-use app approval can only be granted by the user in the interactive codex CLI in a terminal; approving in the Codex/ChatGPT desktop app did not carry over to `codex exec`, and `--approve-for-me` does not cover it. Never try to bypass it.
- Without `--net`, codex `workspace-write` and the deepseek sandbox block network (curl fails with "Could not resolve host").
