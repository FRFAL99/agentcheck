# Claude Code hooks — what is verified

How the hooks that agentcheck relies on actually behave. **Read from the official reference**
(`https://code.claude.com/docs/en/hooks`) on **2026-09-24**, not recalled from memory. The Claude
Code CLI installed on this machine reported `2.1.23` that day, while the reference documents fields
up to v2.1.257: **which fields really arrive is settled by the raw stdin log of plan v1, not by this
page.** When the two disagree, the log wins and this page is corrected.

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
