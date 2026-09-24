# Devlog

Chronological record of progress. Entries in reverse chronological order (newest at the top).

---

## 2026-09-24 — Step 4: the developer's edits are no longer the agent's

A third hook, `agentcheck hook user-prompt-submit`, snapshots the tree into
`sessions/<id>.turn-start.json` when a prompt is submitted. Stop consumes it: `changed_this_turn`
now runs from the prompt to the Stop, and what changed between the previous Stop and the prompt goes
in a new field, `changed_between_turns`. The record also carries `prompt_id` and the first 200
characters of the prompt — Phase 2 will want to know what was asked.

**Pairing.** On 2.1.281 the turn-start and the Stop carry the same `prompt_id`; a mismatch discards
the turn-start, with a note. 2.1.23 sends no `prompt_id`, and the latest turn-start is taken.

**The interrupted turn** — the point the plan said not to forget. Stop doesn't fire when the user
presses Esc, so the turn-start file stays; the next prompt finds it and flags
`previous_turn_interrupted`. The interrupted turn's edits land in `changed_between_turns`, whose
author the record doesn't assert.

**Repos set up before today** have no UserPromptSubmit hook: Stop falls back to the Phase 0
behaviour and says so, `"turn_start": "previous_stop"`. Running `agentcheck init` again adds only
the missing hook — tested.

### What deviated from the plan

- Nothing in the design. The baseline and gc checks were pulled into two helpers, `_load_baseline`
  and `_diff`, now that three places need them.
- The real-process test covers all three hook commands, and each now runs after a real baseline.

### Verification

`uv run pytest`: **60 passed**. Definition of done with real Claude Code 2.1.281: edit `app.py` →
write `HAND_EDIT.md` by hand → create `notes.md`. Turn 2: `changed_this_turn` = `A notes.md`,
`changed_between_turns` = `A HAND_EDIT.md`. Stop took 725–792 ms.

---

## 2026-09-24 — Step 3: every turn leaves a trace, and Phase 0 is done

Stop now appends one record per turn to `.agentcheck/sessions/<id>.turns.jsonl`: turn number,
snapshot tree, `changed_since_start` against the baseline, `changed_this_turn` against the previous
turn, `last_assistant_message` (or `null`), `stop_hook_active`, and `transcript_at_stop`. A turn
where the agent only talks is recorded with an empty `changed_this_turn`, not skipped.

**No baseline, no invented one.** A Stop for a session with no baseline file writes nothing and
leaves a line in `logs/agentcheck.log`. A baseline whose tree was pruned by `git gc` gets the same
treatment; a pruned *previous-turn* tree only makes `changed_this_turn` `null`, the rest of the
record stays.

### Checked with the real thing

`claude -p` plus `--resume` in scratch repos, `--permission-mode acceptEdits`:

- **2.1.281** (extension), three turns — edit `app.py`, create `notes.md`, answer a question.
  `changed_this_turn`: `M app.py`, `A notes.md`, empty. `changed_since_start` accumulated both.
- **2.1.23** (terminal), two turns. No `last_assistant_message`, as Step 2 found.
- **The transcript was not behind in any of the five turns**: its last main-thread assistant text
  at Stop time was the final message every time. The docs' warning stands, the records keep
  measuring — see [knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md).
- A Stop took **295–890 ms**, all of it snapshot, diffs and transcript read.

### What deviated from the plan

- **"Type of the last transcript entry" was useless as a measure**: a real transcript ends with
  metadata (`last-prompt`, `cost-state`, `ai-title`), not messages. Recorded instead: line count,
  uuid and text of the last main-thread assistant entry with text, and — when the field exists —
  whether it matches `last_assistant_message`. Subagent entries (`isSidechain`) are skipped.
- That measurement lives in a new `collector.py`, the module PROJECT.md §6 already names for "hook
  input, git, transcript", rather than in `hooks.py`.
- **Found by the 2.1.23 run, by accident:** turn 2 listed `r1.json` as changed — the output file of
  the command running the test, written *between* turns. agentcheck can't tell the agent's edits
  from the developer's. Not fixed here: it's the first decision for plan v2 (a snapshot on
  `UserPromptSubmit`), recorded in STATUS.

### Verification

`uv run pytest`: **50 passed**. Definition of done with real Claude Code on both versions: see
above. Plan v1 closed, three steps of three.

---

## 2026-09-24 — Step 2: the baseline holds, and the terminal's claude is a different, older one

SessionStart now saves `.agentcheck/sessions/<session_id>.json` — `head` and a snapshot `tree` —
once, and never again for that id. Every hook invocation is appended verbatim to
`.agentcheck/logs/hooks.jsonl` before anything else runs; any failure lands in
`.agentcheck/logs/errors.log` and the hook still exits 0 with nothing on stdout.

**The snapshot does what the scratch test of Step 0 promised**, now under test: the user's index
hash, `git status` and refs identical before and after; untracked in, ignored out; no temporary
index left behind; an unborn branch with no `.git/index` works and leaves none. Two mutations were
run to prove the tests bite — removing the overwrite guard failed three tests, pointing
`GIT_INDEX_FILE` at the real index failed two.

**A repo where `init` never ran is left alone**: no `.agentcheck/` means the hook writes nothing,
not even the raw log. A `session_id` that isn't a plain slug is refused before it becomes a path —
the same guard `obsidian-dev-agent` puts on project names.

### Checked with the real thing

`claude -p` in a scratch repo, then `--resume`, then `/compact`, with both binaries on this machine.

- **The VS Code extension runs 2.1.281, the terminal 2.1.23.** Found only because the first run
  used the terminal one and the log didn't match the docs.
- **2.1.23 sends no `last_assistant_message`** on Stop, and `/compact` in `-p` mode fired no hook.
  2.1.281 sends everything the docs list, and fires `SessionStart` with `source: compact`.
- **With both, the baseline survived**: one file per session, byte-identical after `resume` (with a
  file added in between) and after `compact`.

The table of what each version sends is now in
[knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md).

### What deviated from the plan

- **`last_assistant_message` turned out optional**, which decision 0 had assumed away. Step 3 now
  also records the transcript's state at Stop time, to measure the lag instead of guessing it.
- The first `/compact` attempt never reached Claude: Git Bash had rewritten it into a Windows path.
- `init.py` now reuses `gitstate.repo_root` instead of its own `git rev-parse`.
- Hook stdin is read as bytes and decoded as UTF-8: on Windows `sys.stdin` would be cp1252, and the
  fixture's Italian message with `—` and `✓` is there to catch it.

### Verification

`uv run pytest`: **35 passed**. Definition of done with real Claude Code (2.1.281 and 2.1.23):
baseline written at startup, unchanged after resume and compact, `hooks.jsonl` with every event,
`errors.log` absent.

---

## 2026-09-24 — Step 1: `init` wires the hooks, and a check mark crashed it on Windows

`agentcheck init` merges the SessionStart and Stop hooks into `.claude/settings.json` and creates a
self-ignoring `.agentcheck/`. The two hook commands exist as stubs that read stdin and print
nothing — on SessionStart, anything printed would go into Claude's context.

**The merge never loses what's there.** Another tool's `Stop` hook stays: ours is appended as a
separate matcher group. Invalid JSON, or a `hooks.Stop` that isn't a list, stops init **before any
write** — including `.agentcheck/`, so a refused init leaves the repo exactly as it was. Run twice,
nothing changes: the second run doesn't even rewrite the file.

**Run from a subdirectory, it finds the repo root** with `git rev-parse --show-toplevel`, so
`.claude/` never lands inside `src/`.

### What deviated from the plan

- **The first real run crashed** with `UnicodeEncodeError` on `✓`: the definition of done was run
  with stdout piped, and on Windows a piped stdout is cp1252. All twelve tests were green, because
  `CliRunner` writes UTF-8. The CLI now reconfigures stdout and stderr to UTF-8 with
  `errors="replace"`, and a thirteenth test spawns a real process with `PYTHONIOENCODING=cp1252`.
  It matters beyond init: the report of PROJECT.md §4.7 is made of `✗ ! ✓`.
- **Python couldn't be downloaded**: `uv python install` failed with `invalid peer certificate:
  UnknownIssuer` — something on this machine intercepts TLS, and uv by default trusts only its
  bundled roots. `system-certs = true` in uv's user config fixed it; the PowerShell installer had
  worked because it uses the Windows store.
- `requires-python` is `>=3.11` as the spec says; development runs on 3.12.14, installed by uv.
- Added `src/agentcheck/__main__.py`, not in the plan, so the subprocess test can run
  `python -m agentcheck`.

### Verification

`uv run pytest`: **13 passed**. Definition of done in a scratch repo: `init` twice → one hook of
each kind in `settings.json`, second run reports "already configured", `git status` lists
`.claude/` and the repo's own file but not `.agentcheck/`.

---

## 2026-09-24 — Step 0: repo and documentation, and the hooks read before writing a line

**Done**

- `PROJECT.md`: the spec, translated to English, with notes where the hooks reference corrects it.
- `CLAUDE.md` as the index of how to work here, modelled on JuTrack's: step numbering, end-of-step
  ritual, where to write what.
- `docs/`: `STATUS.md`, `registry.md`, this devlog, `plan-TEMPLATE.md`, `knowledge/`, `adr/`.
- `.claude/commands/`: `/new-plan` and `/end-step`.
- [Plan v1](plan-v1-every-turn-leaves-a-trace.md) written for Phase 0: Steps 1–3 allocated.

**Verified, not assumed**

The spec said to check the hooks against the official documentation before implementing. Doing it
first changed four things:

- **A Stop hook's plain stdout is invisible.** It goes to the debug log only. The report has to be a
  `systemMessage` in a JSON object — which also answers one of PROJECT.md's open questions.
- **The transcript can be behind.** It is written asynchronously and may not contain the current
  turn at Stop time. The final message comes in the Stop input as `last_assistant_message`.
- **SessionStart is not "once per session".** It fires on `resume`, `compact`, `clear` and `fork`
  too. Saving the baseline on each would have reset the diff at every compaction, silently.
- **On SessionStart, stdout talks to Claude**, not to the user: the hook must print nothing.

**The snapshot, tried in a scratch repo**

PROJECT.md proposed `git stash create` plus a separate list of untracked files. Tried instead: copy
the index, `git add -A` into the copy through `GIT_INDEX_FILE`, `git write-tree`. The user's index
was byte-identical afterwards, no refs, no stash entries; untracked files were in, ignored ones
out; `git diff-tree` between two snapshots gave the right `M`/`A`/`D`. Adopted — ADR 0001,
decision 2 of plan v1.

Same test, a side effect: `.agentcheck/` showed as `??` in the user's `git status`. A
`.agentcheck/.gitignore` containing `*` removes it from both status and snapshot, without editing
the user's `.gitignore`.

**From obsidian-dev-agent:** a process spawned by Claude Code doesn't get a cwd you chose — the MCP
server there had to anchor `.env` and `sys.path` to its own file. Here the equivalent is resolving
the repo from the hook input's `cwd`: rule 3 of CLAUDE.md.

**Toolchain**

No Python and no `uv` on this machine, no WSL. The installed Claude Code CLI reports `2.1.23`,
while the reference documents fields up to v2.1.257 — the raw stdin log of Step 2 settles which
ones really arrive.

### Verification

No code, no tests. `git init` done; nothing committed yet.
