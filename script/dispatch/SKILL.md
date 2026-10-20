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
| `codex` | official `codex exec` (ChatGPT login) | harder code: multi-file changes, debugging, tricky logic, writing tests |
| you | — | interface design, splitting, review, merge, anything needing judgement or this session's tools |

When unsure, send well-specified work to deepseek and ambiguous or hard work to codex. For important pieces you may send the same card to both and keep the better result.

## Tool: `agent-run`

```bash
agent-run <deepseek|codex> <card.md> --dir <repo> [--mode rw|ro] [--name slug] [--test "<cmd>"] [--timeout 1800]
```

- `rw` (default) in a git repo: a fresh worktree on branch `agent/<worker>/<name>-<stamp>` from HEAD; the worker's changes get committed there. Outside git it edits in place.
- `ro`: read-only tools/sandbox, runs in `--dir` directly.
- `--test`: acceptance command that agent-run itself runs in the workdir after the worker exits. Always pass one when the task is checkable — it is the evidence, not the worker's report.
- Output: one JSON summary line, then the path to `meta.json`. The run dir (`~/.agent-runs/<stamp>-<name>-<worker>/`) holds `task.md`, `report.md`, `worker.out/.err`, `test.log`, `meta.json`.
- Run workers with Bash `run_in_background: true`; you are notified on exit. Never poll. Independent cards run in parallel; cards that touch the same files run one after another.

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
```

agent-run prepends worker rules (stay in workdir, no git commit/push, report format: 结论/改动/运行的命令/未解决).

## Loop

1. Plan: split the request into independent cards. Say in one line which card goes to which worker and why.
2. Dispatch with `agent-run` in the background, with `--test` whenever possible.
3. Verify each result yourself: read `meta.json` (exit, test.passed, changed_files, permission_denials), read `report.md`, and review the diff: `git -C <repo> diff <base>..<branch>`. Changes outside 允许改动, weakened tests, or claims the test log doesn't back up → reject.
4. Rejected → re-dispatch once with a sharper card (quote the failure), or switch worker, or do it yourself. Don't loop more than twice; tell the user.
5. Accepted → merge into the user's branch (`git merge --no-ff <branch>` or cherry-pick), run the project's tests once more on the merged result, then clean up: `git worktree remove <worktree>` and `git branch -D <branch>`.
6. Report to the user: what each worker did, what you verified, what you changed or rejected. Never push unless the user asked.

## Gotchas

- deepseek workers must start from a clean env (agent-run does `env -i`); inherited `CLAUDE_CODE_*` vars make `claude -p` hang.
- The gateway URL and key live in `GATEWAY_BASE_URL` / `GATEWAY_API_KEY` in ~/.zshrc. Never read or print the key, and never commit either value (this repo is public); agent-run fetches them.
- `total_cost_usd` in Claude Code output is priced as Claude — ignore it for deepseek; use the token counts.
- codex `workspace-write` and the deepseek sandbox both block network for worker shell commands. Tasks needing network (installs, API calls) → tell the user or do that step yourself.
