# Devlog

Chronological record of progress. Entries in reverse chronological order (newest at the top).

---

## 2026-09-24 — Step 7: the verdict reaches the developer — checked headless, VS Code still to see

Stop now does what Phase 1 was for. After writing the turn record — first, so nothing below can
lose it — it runs the analysis of Steps 5–6 on the turn's own diff (prompt → Stop) **in a child
process**, `agentcheck analyze-turn`, with a 30 s timeout. The result goes to
`sessions/<id>.analysis.jsonl`; the report goes to stdout as the one JSON object Claude Code reads:
`{"systemMessage": "..."}`.

- `risk.py`: weights 3/2/1, **medium** from 3, **high** from 6 — one high signal is medium.
- `report.py`: findings → header `agentcheck · turn N · risk LEVEL` and one `! message` per finding,
  by severity then file, within `max_lines` (`… and N more`); files changed and nothing found →
  `agentcheck · turn N · all good (3 files)`; nothing changed → no output.
- A child that crashes, hangs or prints garbage costs **that turn's report and nothing else**: a
  line in `errors.log`, a `failed` entry in the analysis file, exit 0, empty stdout. Tested with a
  child that exits like the tree-sitter crash did, one that sleeps past the timeout, one that prints
  non-JSON. A broken `config.toml` falls back to the defaults and says so.

### Checked with the real thing

Claude Code 2.1.281, `claude -p … --output-format stream-json`, in a scratch repo:

- "add a required parameter `currency` to `create_invoice`, don't touch the tests" →
  `Stop says: agentcheck · turn 1 · risk MEDIUM`, then the signature change with old and new, then
  `Code changed, no tests touched: api/invoices.py`. Exactly the plan's definition of done.
- A question with no edit → `all good (1 file)` instead of silence — and the one file was
  **`s2.jsonl`, the output of the command running the test**, written inside the repo while the
  turn ran. agentcheck was right that it changed; nothing from hooks can tell who changed it.
- Stop took **~0.8 s to record plus ~0.75 s to analyse**, well inside the 2 s of PROJECT.md §3.

### What deviated from the plan

- The analysis result lives in its own file, `analysis.jsonl`, rather than inside the turn record:
  the record is written before the analysis runs and is never rewritten.
- `run_hook` now returns what the handler returns; only Stop returns anything.

### Verification

`uv run pytest`: **161 passed**. Headless definition of done: above. **Still open:** the look of the
report in VS Code, by the developer — `·` rendering (the transcript stores it double-encoded) and
whether the lines read well after `Stop says: `.

---

## 2026-09-24 — Step 6: the file-level signals, and a tree-sitter that crashed the process

`structural/turn.py` now runs every deterministic signal on a turn, each family isolated — an
exception drops that family into `errors` and the others still report:

- **sensitive file** (high) — `.env*`, `**/migrations/**`, `.github/workflows/**` by default;
- **new dependency** (medium) — names, not lines: `pyproject.toml` (PEP 621, dependency groups,
  Poetry), `requirements*.txt`, `package.json`; reordering or bumping versions reports nothing;
- **code changed, no tests touched** (medium) — one finding per turn;
- **tests removed or disabled** (high) — a deleted test file, fewer `def test_` / `it(` / `test(`,
  more `skip`/`xfail`/`.only`/`xit`; commented-out lines don't count;
- **import not found** (high) — only imports added this turn that point inside the repo: Python
  relative imports and absolute ones whose top package is at the root or under `src/`; TS/JS
  relative specifiers, with `./x.js` resolving to `x.ts`. Gitignored generated modules
  (`_version.py`) are checked on disk before being called missing;
- **many files** (low).

`config.py` loads `.agentcheck/config.toml` over the defaults of PROJECT.md §8; `globs.py` gives
`**` the same meaning on every Python version. `agentcheck run` uses all of it.

### A crash that no try/except catches

Running `agentcheck run` on this repo ended in a **segmentation fault**. Traced line by line: the
process died on `while stack:` in `_imports` — i.e. when Python freed the previous tree-sitter
`Node`. The same file parsed with **tree-sitter 0.25.2 went fine; 0.26.0 crashed every time**, and
on the Python standard library it crashed within 200 files while 0.25.2 went through all 1094.
Pinned `<0.26`. Stress run on JuTrack after the pin: 6000 TS/JS/Python files, no crash; its 384
own TS/JS files all parse (the 152 that don't are Flow and friends in `node_modules`).

In a hook this would have been a "hook error" on every turn. So Step 7 gets a new point not to
forget, written into the plan: the analysis runs in a **child process** with a timeout, after the
turn record is written.

### What deviated from the plan

- **Fixture directories are data for every signal**, not only the symbol ones of Step 5: a
  fixture's `.env.example` was about to be a "sensitive file".
- **`it.only(` wasn't counted as a test** in the first version, so focusing a test looked like
  "Tests removed (2 -> 1)" — the fixture caught it.
- The default test and migration globs match at any depth (`**/tests/**`, `**/migrations/**`);
  PROJECT.md §8's `tests/**` would miss every package-level `tests/` of a monorepo.
- Signature messages are now cut **where the two versions differ**: the self-run showed two
  truncated signatures printing identically when the change was the last parameter.

### Verification

`uv run pytest`: **138 passed**. Definition of done in a scratch repo, one turn adding
`python-dateutil`, touching `.env.example`, skipping a test and importing `.nonexistent`:
exactly those four. Reordering the dependencies alone: nothing. On agentcheck itself, Step 5 → now:
the three real API changes of this step (`analyze`'s new parameter, `is_test_path` and
`analyze_trees` gone) plus "many files", in 2.7 s for 47 files.

---

## 2026-09-24 — Step 5: agentcheck knows what a public function is, and ran on itself

Two tree-sitter extractors, `structural/python.py` and `structural/typescript.py`, return the public
symbols of one version of a file with their signatures; `structural/diff.py` compares before and
after — read from the snapshots' blobs with one `git cat-file --batch`, never from disk — and
produces three kinds of finding, all high: **signature changed**, **removed**, **syntax broken**.
`agentcheck run --from <ref> [--to <ref>]` runs it by hand.

**What "public" turned out to need, case by case** — 29 fixture pairs, one per case: `__all__` as a
literal list restricts; built dynamically, the underscore rule applies instead (the point the plan
said not to forget). Decorated definitions count; nested ones and those under `if TYPE_CHECKING:`
don't. In TS: overloads are joined into one signature, so adding one is a change; `export { a as b }`
re-exports under the alias; `export default class X` is `default`, so renaming `X` changes nothing
for importers; `private` and `#` methods are ignored. A removed class is one finding, not one per
method. **Moved** — same name and signature, another file of the same turn — is no finding; moved
*and* changed is reported as removed.

Two mutations again: dropping the moved check and dropping the private-method check each failed
exactly the case written for it.

### Ran on agentcheck itself — and it said six false things

`agentcheck run --from 6d0086d` on this repo: **six "syntax broken", all on test fixtures broken on
purpose.** Files under `fixtures/`, `testdata/`, `__fixtures__/`, `__snapshots__/` are data, not
code: no structural signal applies to them now. Re-run: 112 files changed, 0 findings, 2.4 s for
the whole repo history of the day — a turn's diff is a fraction of that.

### The trap that would have broken every session

The first `agentcheck run` from the installed tool crashed: `No module named 'tree_sitter'`.
**`uv tool install --editable` follows the source, not new dependencies** — and since `cli.py`
imported the analysis at the top, *every hook* would have crashed the same way, in every repo with
agentcheck installed, as a "hook error" in Claude Code. Two fixes: the CLI imports the analysis only
inside `run`, and a test runs a hook with `tree_sitter` made unimportable — it failed with the old
import, passes now. The tool was reinstalled, and CLAUDE.md says to after every dependency change.

### What deviated from the plan

- **Python dunders are public** (`__init__` is how a class is called) — decision 3 amended.
- **A new file that doesn't parse is "syntax broken" too**, not only a file that parsed before —
  decision 4 amended. A file broken before and after is still not news.
- **Imports and test markers** — listed for Step 5's extractors — move to Step 6 with the signals
  that use them.
- The data directories above, found by the self-run.
- `pyproject.toml`: pytest no longer recurses into `fixtures/`, which holds files named `test_*.py`.

### Verification

`uv run pytest`: **97 passed**. Definition of done in a scratch repo: `agentcheck run --from HEAD`
over `create_invoice` gaining `currency`, `void_invoice` deleted, `format_money` moved to another
file and `report.py` broken → exactly three findings, nothing about `format_money`.

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
