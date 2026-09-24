# Claude Code hooks — what is verified

How the hooks that agentcheck relies on actually behave. **Read from the official reference**
(`https://code.claude.com/docs/en/hooks`) on **2026-09-24**, then **checked against the raw stdin
log** (`.agentcheck/logs/hooks.jsonl`) of real headless sessions the same day. When the two
disagree, the log wins and this page is corrected.

## What each version really sends — from the log, 2026-09-24

**Two versions live on this machine**: the VS Code extension bundles **2.1.281**
(`~/.vscode/extensions/anthropic.claude-code-2.1.281-win32-x64/resources/native-binary/claude.exe`),
while the `claude` on PATH in a terminal is **2.1.23**. The same repo gets different inputs
depending on where the session was started.

| Event                  | 2.1.281 (extension)                                                                                                                             | 2.1.23 (terminal)                                                  |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| SessionStart `startup` | `cwd`, `source`, `transcript_path`, `scratchpad_dir`                                                                                            | `cwd`, `source`, `transcript_path`                                 |
| SessionStart `resume`  | same, plus `seconds_since_last_response`, `context_tokens`, `prompt_cache_likely_expired`, `estimated_cache_write_usd`                          | `cwd`, `source`, `transcript_path` — same `session_id`             |
| SessionStart `compact` | `cwd`, `source`, `transcript_path`, `model`, `prompt_id`                                                                                        | **not fired** — `/compact` in `-p` mode invoked no hook at all     |
| Stop                   | `last_assistant_message`, `stop_hook_active`, `permission_mode`, `effort`, `prompt_id`, `background_tasks`, `session_crons`, `transcript_path` | **no `last_assistant_message`**, `stop_hook_active`, `permission_mode`, `transcript_path` |

Consequence: **`last_assistant_message` is optional.** Whatever reads the agent's words must fall
back to the transcript when the field is absent — and the transcript is the thing the docs say may
lag. Step 3 measures whether it does.

`resume` keeps the `session_id` in both versions.

## Input (JSON on stdin)

Common to every event: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and — not on all
events — `permission_mode`, `effort`, `prompt_id`, `scratchpad_dir`. Inside a subagent: `agent_id`,
`agent_type`.

- **`cwd` is the directory when the hook fires**, and after Claude enters a worktree it points to
  the worktree root, while `${CLAUDE_PROJECT_DIR}` stays at the original project root. The repo to
  diff is the one containing `cwd`.
- **`transcript_path` is written asynchronously** and _"may not yet include the current turn's
  most recent messages when a hook fires."_ For the final text of the turn, use
  `last_assistant_message`.

**SessionStart** adds `source`: `startup` · `resume` · `clear` · `compact` · `fork`, and optionally
`model`, `agent_type`, `session_title`. The matcher filters on the same values.

**Stop** adds:

- `stop_hook_active` — `true` when Claude is _already_ continuing because a Stop hook blocked.
- `last_assistant_message` — the text of Claude's final response.
- `background_tasks`, `session_crons` — work still in flight; lets a hook tell "done" from "paused".

Stop **does not fire on a user interrupt**; an API error fires `StopFailure` instead.

**SessionEnd** adds `reason`: `clear` · `resume` · `logout` · `prompt_input_exit` · `other`.

## Output

| Channel                         | Where it goes on `Stop`                                    |
| ------------------------------- | ---------------------------------------------------------- |
| plain stdout, exit 0            | **debug log only** — neither the user nor Claude sees it   |
| stderr, exit 0                  | debug log only                                             |
| JSON `systemMessage`, exit 0    | **shown to the user** as a warning message                 |
| JSON `decision: "block"` + `reason` | Claude keeps going, `reason` is its instruction        |
| JSON `hookSpecificOutput.additionalContext` | Claude keeps going, labelled "Stop hook feedback", no error notice |
| exit 2                          | blocks; stderr becomes the reason                          |
| exit 1 or any other             | non-blocking error, a `hook error` notice in the transcript |

On **SessionStart**, instead, plain stdout **is added to Claude's context**. A session-start hook
that prints a friendly "baseline saved" line is talking to Claude, not to the user: print nothing.

- stdout is parsed as JSON only if it starts with `{` and ends with `}`, and must contain **only**
  that object. A shell profile that prints on startup breaks it.
- `systemMessage`, `additionalContext` and plain stdout are each capped at **10,000 characters**.
- `decision` and `reason` are **top-level** fields for Stop, not inside `hookSpecificOutput`.
- Loop protection is built in: besides `stop_hook_active`, Claude Code **ends the turn by itself
  after 8 consecutive blocks.** Our own "at most one send-back per turn" rule is stricter and stays.
- **SessionEnd** discards `systemMessage` and has a default budget of **1.5 seconds** shared across
  all SessionEnd hooks.

## Execution

- Default timeout for a `command` hook: **600 s**. `async: true` runs it in the background without
  blocking (and then its output can't block or reach the user).
- Environment: the parent's environment, plus `CLAUDE_PROJECT_DIR`. `CLAUDE_ENV_FILE` only on
  SessionStart. No `CLAUDE_MODEL`.
- **Windows:** commands run in **Git Bash** when it is installed, otherwise PowerShell; `"shell":
  "powershell"` forces it. The exec form (`args` set) needs a real `.exe` — `.cmd`/`.bat` shims
  don't run.
- SessionStart runs in the background at launch, but Claude's first response waits for it: a slow
  session-start hook delays the first answer.

## Config location

`.claude/settings.json` (project, committed), `.claude/settings.local.json` (project, gitignored),
`~/.claude/settings.json` (user). `"disableAllHooks": true` turns them all off.
