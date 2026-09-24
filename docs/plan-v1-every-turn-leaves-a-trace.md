# agentcheck — Plan v1: "every turn leaves a trace"

> Entry point of the project: [STATUS.md](STATUS.md). **Where this plan comes from:** Phase 0 of
> [PROJECT.md](../PROJECT.md) §9, and the official hooks reference read on 2026-09-24 — summarised in
> [knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md). Written on 2026-09-24.
>
> **Occupies Steps 1–3**, one per session. Allocated in [registry.md](registry.md).
>
> **Every reference below was read in the docs or tried in a scratch repo**, not inferred. There is
> no code yet: decision 0 is about what Claude Code and git already provide.

## Context

1. **Nothing observes the agent.** A turn ends and the only record of what changed is whatever
   `git status` shows now — mixed with what was already dirty before the session started.
2. **The later phases have nothing to stand on.** The structural diff (Phase 1) and claim
   verification (Phase 2) both need, for every turn, a reliable "before" and "after" and the
   agent's words. Phase 0 exists to produce exactly those, and nothing more.

## What already exists (decision 0)

**Decision.** Claude Code already hands us the agent's final words, a safe per-event trigger, a
loop guard, and a channel to the user. Git already hands us snapshots that don't touch anything.
Phase 0 writes glue, not machinery.

**Why.**

- **The final message arrives in the Stop input** as `last_assistant_message`. The transcript file
  is written asynchronously and _"may not yet include the current turn's most recent messages when
  a hook fires"_ (hooks reference, "Common input fields"). PROJECT.md §4.4 said to read the final
  messages from the transcript: **this plan corrects it** — the log records both, and Phase 2 reads
  the field first.
- **SessionStart fires on `startup`, `resume`, `clear`, `compact` and `fork`**, not once per
  session. PROJECT.md §4.2 implicitly assumed "once": re-saving the baseline on `compact` would
  silently reset the diff halfway through a session. See decision 1.
- **A Stop hook's plain stdout goes to the debug log only.** The user sees a `systemMessage` in a
  JSON object on stdout. On SessionStart, plain stdout goes **into Claude's context** — so the
  session-start hook must print nothing at all.
- **`git write-tree` on a temporary index** produces a snapshot including untracked, non-ignored
  files, without touching `.git/index`, refs or the stash. Tried in a scratch repo on 2026-09-24:
  index byte-identical before and after, no new refs, no stash entries, `.gitignore`d files
  excluded, `git diff-tree` between two snapshots correct. See
  [ADR 0001](adr/0001-never-touch-the-users-git-state.md) and decision 2.
- **The installed CLI reports `2.1.23`**, the reference documents fields up to v2.1.257. Which
  fields really arrive is settled by decision 4, not assumed.

---

## The decisions

### 1 · The baseline is written once per session id and never overwritten

**Decision.** `hook session-start` writes `.agentcheck/sessions/<session_id>.json` only if it
doesn't exist. On `resume`/`compact` the existing file is left alone; the event is still logged.

**Why.** `compact` and `resume` keep the same session and must keep its starting point. `clear` and
`fork` arrive with a new `session_id` — they get a new baseline naturally, with no special case on
`source`.

**Constraint.** A Stop for a session with no baseline file (agentcheck installed mid-session, or
SessionStart failed) **does not invent one**: it logs "no baseline for this session" and stops.
A baseline taken at Stop would make the diff of that turn empty and look like a clean turn.

### 2 · A snapshot is a git tree built through a temporary index

**Decision.** `snapshot(repo) -> tree_id`: copy `.git/index` to `.agentcheck/tmp/index-<pid>`, run
`git add -A -- . ':!.agentcheck'` and `git write-tree` with `GIT_INDEX_FILE` pointing at the copy,
delete the copy. The baseline stores `head` (`git rev-parse HEAD`, or none on an unborn branch) and
`tree`. Every Stop stores its own `tree`.

**Why.** It replaces PROJECT.md §4.2's `git stash create` + separate untracked list with one
representation: start and end are the same kind of object, the diff is one
`git diff-tree -r --name-status`, and untracked files come for free. Copying the real index (rather
than `read-tree HEAD`) keeps git's stat cache, so unchanged files aren't re-hashed.

**Constraint.** `sha1(.git/index)` is identical before and after a snapshot — a test asserts it.
The index file is per-process, so two overlapping hooks can't corrupt each other's.

### 3 · `init` makes `.agentcheck/` invisible to git without touching the user's `.gitignore`

**Decision.** `agentcheck init` creates `.agentcheck/.gitignore` containing `*`, and **merges** the
two hook entries into `.claude/settings.json`.

**Why.** Without it, `.agentcheck/` shows as `??` in every `git status` of the user's repo — tried
in the scratch repo. A self-ignoring folder is the one pattern that needs no edit to a file the
user owns. The `':!.agentcheck'` pathspec in decision 2 stays as a second guard.

**Constraint.** `init` is idempotent: run twice, `settings.json` has each hook once. Existing keys
and existing hooks in `settings.json` are preserved. If `settings.json` isn't valid JSON, `init`
stops and says so — it never rewrites a file it couldn't read.

### 4 · The raw hook input is logged verbatim

**Decision.** Every hook invocation appends its raw stdin (one JSON line) to
`.agentcheck/logs/hooks.jsonl` before doing anything else.

**Why.** It is the ground truth for decision 0's last point: which fields the installed Claude Code
actually sends. The knowledge file is corrected from this log, not the other way round.

**Constraint.** The raw log is written even when parsing fails — that's the case it exists for.

### 5 · A hook resolves the repo from the input, and always exits 0

**Decision.** The repo root is `git -C <input.cwd> rev-parse --show-toplevel`, never the process
cwd. The whole hook body runs inside one `try/except` that logs the traceback to
`.agentcheck/logs/errors.log` (or stderr, if even the repo can't be found) and exits 0. In Phase 0,
stdout stays empty.

**Why.** Claude Code spawns the hook from a directory we don't control, and after entering a
worktree `cwd` and `CLAUDE_PROJECT_DIR` differ — the repo that changed is the one at `cwd`. The
same lesson as `obsidian-dev-agent`'s MCP server, which had to fix its own `sys.path` and `.env`
lookup for the same reason. Exit 2 would block Claude; any other non-zero exit shows the user a
"hook error".

**Constraint.** Not a git repo → log one line and exit 0, silently.

### 6 · The hook command is `agentcheck`, installed as a uv tool

**Decision.** `init` writes `"command": "agentcheck hook stop"` (and `session-start`). During
development agentcheck is installed with `uv tool install --editable .`, which puts an
`agentcheck.exe` on PATH that follows the source.

**Why.** On Windows, hooks run in Git Bash by default, which has the user's PATH. A bare command
keeps `settings.json` identical across machines and committable; a hard-coded interpreter path
would not be.

**Constraint.** If `agentcheck` isn't on PATH, Claude Code shows a hook error — the one failure
agentcheck can't catch itself. `init` checks `shutil.which("agentcheck")` and warns.

---

## Step 1 — "the skeleton and `init`"

| File                          | What                                                             |
| ----------------------------- | ---------------------------------------------------------------- |
| `pyproject.toml`              | **new** — uv project, `typer` + `rich`, `pytest` dev, `agentcheck` script entry |
| `src/agentcheck/cli.py`       | **new** — `typer` app: `init`, `hook session-start`, `hook stop` (stubs) |
| `src/agentcheck/init.py`      | **new** — settings merge and `.agentcheck/` layout (decisions 3, 6) |
| `tests/test_init.py`          | idempotence, key preservation, invalid JSON refused, `.agentcheck/.gitignore` |
| `README.md`                   | **new** — three lines: what it is, install, `agentcheck init`    |

`tree-sitter` and `anthropic` are **not** added yet: Phase 1 and Phase 2.

### The point not to forget

`.claude/settings.json` may already hold hooks for `Stop` from the user or another tool. The merge
appends a matcher group; it never replaces the `Stop` array.

### Definition of done

In a scratch repo: `agentcheck init` → `.claude/settings.json` has both hooks → run `init` again →
still one of each → `git status` doesn't list `.agentcheck/`.

---

## Step 2 — "the session remembers where it started"

| File                           | What                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| `src/agentcheck/gitstate.py`   | **new** — `repo_root(cwd)`, `snapshot(repo)`, `diff(tree_a, tree_b)` (decision 2) |
| `src/agentcheck/hooks.py`      | **new** — input parsing, raw log, error envelope (decisions 4, 5), `session_start` (decision 1) |
| `tests/fixtures/`              | hook inputs as JSON files, one per `source`                 |
| `tests/test_gitstate.py`       | against a real temporary git repo: index hash unchanged, untracked in, ignored out, unborn branch |
| `tests/test_hooks.py`          | baseline written once; `compact` doesn't overwrite; not-a-repo exits 0 |

### The point not to forget

**An unborn branch** (a repo with no commits yet) has no `HEAD` and may have no `.git/index`. The
snapshot must work from an empty index; `head` is stored as `null`.

### Definition of done

Open Claude Code in a real repo → `.agentcheck/sessions/<id>.json` exists with `head` and `tree` →
`/compact` → the file's `tree` hasn't changed → `.agentcheck/logs/hooks.jsonl` has both events.

---

## Step 3 — "every turn leaves a trace"

| File                          | What                                                         |
| ----------------------------- | ------------------------------------------------------------ |
| `src/agentcheck/hooks.py`     | `stop`: snapshot, diff vs baseline and vs previous turn, write the turn log |
| `tests/test_hooks.py`         | turn numbering, diff vs previous turn, no-baseline case      |

Each Stop appends one record to `.agentcheck/sessions/<id>.turns.jsonl`: turn number, time, tree,
`changed_since_start` and `changed_this_turn` (name-status lists), `transcript_path`,
`last_assistant_message` (or `null` if the field is absent), `stop_hook_active`.

### The point not to forget

A turn in which the agent only talks changes nothing: `changed_this_turn` is empty, and that is a
valid record — not an error, not skipped. Phase 2 will need precisely those turns ("I fixed it"
with an empty diff).

### Definition of done

In a real repo, with Claude Code: ask for an edit to one file → ask for a new file → ask a question
with no edit. `turns.jsonl` has three records; the first lists `M file`, the second `A newfile` in
`changed_this_turn` and both in `changed_since_start`, the third an empty `changed_this_turn`. Then
compare `hooks.jsonl` with [knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md) and
correct whatever the installed version does differently.

---

## What this plan decided NOT to do

- **Postponed: any output to the user.** `systemMessage` is how the report will reach them, but
  there is no report before Phase 1. Printing "turn logged" would be noise, which PROJECT.md §3
  rules out.
- **Postponed: SQLite.** Phase 0 writes JSON files; the `sessions`/`turns` tables arrive with
  Phase 4. The JSON records are shaped like those tables so the migration is a read, not a redesign.
- **Postponed: `SessionEnd`.** Its `systemMessage` is discarded and its budget is 1.5 s: it can't
  report, only tidy up. Reopen if `.agentcheck/tmp/` ever accumulates leftovers.
- **Not touched: the send-back mode.** Phase 3, PROJECT.md §4.8.
- **Not touched: `async: true` on the Stop hook.** It would stop a slow analysis from delaying the
  turn, but an async hook's output can't reach the user. Decide in Phase 1, when there's an analysis
  to time.

## Summary

| Step | What                                      | Risk                                                |
| ---- | ----------------------------------------- | --------------------------------------------------- |
| 1    | Skeleton, CLI, `init`                     | Low                                                 |
| 2    | Baseline snapshot on SessionStart         | Medium: the temporary-index trick on Windows paths  |
| 3    | Per-turn diff on Stop, checked for real   | Medium: fields the installed version may not send   |

Starting baseline: **0 tests** — no code yet.
