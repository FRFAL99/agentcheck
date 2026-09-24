# agentcheck — Plan v2: "the turn ends with a verdict"

> Entry point of the project: [STATUS.md](STATUS.md). **Where this plan comes from:** Phase 1 of
> [PROJECT.md](../PROJECT.md) §9, plus the limitation found by the real run of Step 3. Written on
> 2026-09-24.
>
> **Occupies Steps 4–7**, one per session. Allocated in [registry.md](registry.md).
>
> **Every reference below was read in the code or the docs, or tried** — the three experiments of
> decision 0 were run on 2026-09-24 with Claude Code 2.1.281 and tree-sitter 0.26.

## Context

1. **The record lists files, not what they mean.** `changed_this_turn` says `M api/invoices.py`; it
   doesn't say that `create_invoice` gained a required parameter, or that a test got `.skip`.
2. **Nothing reaches the developer.** Everything agentcheck knows sits in a JSONL file nobody opens
   while working.
3. **"This turn" includes the developer's own edits.** Seen for real in Step 3: a file written
   between two turns was listed as the agent's. Any finding built on the per-turn diff would blame
   the agent for the developer's work.

## What already exists (decision 0)

**Decision.** Every turn already has two snapshots, and git already stores the full content of both
sides — the "before" and "after" of every file are one `git cat-file` away, without touching the
working tree. Claude Code already offers the hook that marks the true start of a turn and the
channel to the developer. Phase 1 adds analysis, not plumbing.

**Why.**

- **Before/after contents are already in the object store.** `hooks.stop` (`src/agentcheck/hooks.py`
  lines 107–152) snapshots a tree per turn, and `gitstate.diff` (`gitstate.py` line 83) lists what
  differs. The blobs behind those trees are what tree-sitter parses: `git cat-file --batch`, one
  process per turn. No file is read from disk, so a file the agent is still writing can't be read
  half-done.
- **`UserPromptSubmit` marks the start of a turn** — tried in a scratch repo: it fires on 2.1.281
  with `prompt` and `prompt_id`, and Stop carries the **same `prompt_id`**, so start and end pair
  exactly. The docs add two constraints: it **blocks Claude until it returns** (30 s timeout), and
  its plain stdout **goes into Claude's context**. A snapshot takes ~0.3 s, and the hook prints
  nothing. PROJECT.md §4.1 configures only SessionStart and Stop: **this plan corrects it.**
- **`systemMessage` reaches the developer** — tried: a Stop hook printing
  `{"systemMessage": "..."}` produced a `system/informational` message in the stream, with **every
  line prefixed `Stop says:`**. It is also stored in the transcript as a `hook_system_message`
  attachment. Oddity seen there: `·` was stored as `Â·` (double-encoded); the stream had it right.
  Checked by eye in VS Code in Step 7.
- **tree-sitter needs no toolchain on Windows** — tried with `uv run --with`: `tree-sitter` 0.26.0,
  `tree-sitter-python` 0.25.0, `tree-sitter-typescript` 0.23.2, all wheels. The 0.25+ API is
  `Query(lang, src)` + `QueryCursor(q).captures(node)` → dict of capture name → nodes (not in source
  order). Parsing 94 KB of Python: 39 ms. The dependencies are the ones PROJECT.md §5 already lists.
- **PROJECT.md §4.3's "import of a non-existent module" is not decidable in general**: whether
  `import requests` resolves depends on an environment agentcheck doesn't see. This plan narrows it
  to imports that point inside the repo (decision 5).
- **PROJECT.md §12 asks whether to report every turn.** Decision 7 answers it.

---

## The decisions

### 1 · A turn starts when the prompt is submitted, not when the previous one stopped

**Decision.** `agentcheck hook user-prompt-submit` snapshots the tree into
`.agentcheck/sessions/<id>.turn-start.json` (with `prompt_id` and the prompt's first 200
characters). Stop diffs **turn start → now** for `changed_this_turn`, and records separately
`changed_between_turns` (previous Stop → turn start): the developer's edits. `init` adds the third
hook; re-running it on an existing repo adds just that one.

**Why.** It's the only point where the developer's edits and the agent's separate. `prompt_id`
pairs start and Stop on 2.1.281; on 2.1.23, which sends no `prompt_id`, the latest turn-start of the
session is used.

**Constraint.** No turn-start file (a repo initialised before this step, or a missed hook) → today's
behaviour, previous Stop → now, and the record says `"turn_start": "previous_stop"`. Nothing
printed on UserPromptSubmit, ever.

### 2 · Findings come from this turn's diff only

**Decision.** Signals are computed on `changed_this_turn`, with the before side at turn start and
the after side at Stop. `changed_since_start` stays in the record but produces no findings.

**Why.** It's what the developer is being asked to trust right now, and it's the only diff free of
their own edits (decision 1). A signal computed since the session start would repeat, every turn,
what was already reported.

**Constraint.** "Code changed without tests" is judged per turn: code in turn 1 and tests in turn 2
flags turn 1. That's correct as a statement about turn 1; recurring patterns are Phase 4.

### 3 · "Public" has one definition per language, and it's written down

**Decision.**

- **Python**: module-level functions and classes whose name doesn't start with `_`, and the
  non-underscore methods of those classes — **plus dunders** (`__init__` is how a class is
  called; added in Step 5). If the module assigns a literal `__all__`, the
  module-level set is exactly `__all__`. Files whose module name starts with `_` (except
  `__init__.py`) and test files are not API.
- **TypeScript/JavaScript**: `export`ed functions, `export`ed `const` arrow functions, `export`ed
  classes and their methods not marked `private`/`#`, and `export default`.

A signature is the parameter list plus the return annotation, whitespace collapsed.

**Why.** "Public signature changed" is the highest-weight signal in PROJECT.md §4.3; without a
written definition it can't be tested or explained.

**Constraint.** A symbol removed from one file and added with the same signature in another file of
the same turn is **moved**, not removed: no finding.

### 4 · A file that parsed before — or didn't exist — and doesn't parse after is a finding

**Decision.** New signal, not in PROJECT.md §4.3: **syntax broken**, weight high. For such a file no
symbol-level signal is computed — a half-parsed tree would report every function as removed.

**Why.** It's the cheapest, most certain signal tree-sitter gives (`root_node.has_error`), and the
one an agent's "done!" most often hides. `.js`/`.jsx` with JSX go through the TSX grammar; `.ts`
through the TypeScript one, so JSX in a `.js` file doesn't count as broken.

### 5 · "Import of a non-existent module" means inside the repo

**Decision.** Flagged only for imports **added in this turn** that point inside the repo and don't
resolve in the after-tree: Python relative imports, and absolute imports whose top-level package is
a directory or module of the repo; TS/JS relative specifiers (`./`, `../`) tried with
`.ts .tsx .js .jsx .mjs .cjs .d.ts` and `/index.*`.

**Why.** Third-party resolution depends on an environment agentcheck doesn't see (decision 0). A
wrong local import is exactly the hallucination this signal was meant for.

### 6 · The risk score is a sum, and the report shows the terms

**Decision.** Weights: high 3, medium 2, low 1. Level: **low** under 3, **medium** 3–5, **high** 6
or more — one high signal is medium, two are high. Every finding carries its weight; the report's
order is severity, then file.

**Why.** PROJECT.md §4.5: "no opaque models". A sum is explainable by listing it.

### 7 · Report when there is something to say, one line when it's fine, silence when nothing changed

**Decision.** At Stop: findings → a report of at most `max_lines` (default 8) in `systemMessage`;
files changed and no findings → one line, `agentcheck · turn 4 · all good (3 files)`; nothing
changed and no findings → no output. Findings are also stored in the turn record.

**Why.** Answers PROJECT.md §12. A turn where the agent only talked has nothing to check yet —
claims are Phase 2 — and a line on every turn would be the noise §3 rules out. One line on a turn
that changed files is the proof agentcheck is running.

**Constraint.** Lines are written to be read after `Stop says: `: short, no leading symbols that
depend on alignment. Stdout carries only the JSON object — nothing else, or Claude Code parses it
as plain text and the message is lost.

---

## Step 4 — "the developer's edits are not the agent's"

| File                         | What                                                                  |
| ---------------------------- | --------------------------------------------------------------------- |
| `src/agentcheck/hooks.py`    | `user_prompt_submit` handler; Stop uses the turn start (decision 1)   |
| `src/agentcheck/init.py`     | third hook, `agentcheck hook user-prompt-submit`                      |
| `src/agentcheck/cli.py`      | the new hook command                                                  |
| `tests/fixtures/hooks/`      | `user-prompt-submit.json`, and a 2.1.23-shaped one without `prompt_id` |
| `tests/test_hooks.py`, `tests/test_stop.py`, `tests/test_init.py` | between-turns edits separated; fallback; init adds the third hook once |

**Already exists and isn't rewritten:** `gitstate.snapshot`, `gitstate.diff`, the `run_hook`
envelope, the baseline logic.

### The point not to forget

**Stop doesn't fire on a user interrupt.** An interrupted turn leaves its turn-start file
unconsumed, and the next prompt overwrites it: the interrupted turn's edits then land in the next
turn's `changed_between_turns`, labelled as the developer's. When a turn-start is found unconsumed,
the record says `"previous_turn_interrupted": true`, and those changes are "author unknown", not
"developer".

### Definition of done

In a real repo with Claude Code: ask for an edit → edit a different file by hand → ask for another
edit. The second record has the hand edit in `changed_between_turns` and only the agent's file in
`changed_this_turn`.

---

## Step 5 — "agentcheck knows what a public function is"

| File                                   | What                                                          |
| -------------------------------------- | ------------------------------------------------------------- |
| `pyproject.toml`                       | `tree-sitter`, `tree-sitter-python`, `tree-sitter-typescript` |
| `src/agentcheck/gitstate.py`           | `read_blobs(repo, tree, paths)` via one `git cat-file --batch` |
| `src/agentcheck/structural/python.py`  | **new** — public symbols, signatures, imports, test markers   |
| `src/agentcheck/structural/typescript.py` | **new** — the same for TS/JS                               |
| `src/agentcheck/structural/diff.py`    | **new** — signature changed, removed, moved, syntax broken (decisions 3, 4) |
| `tests/fixtures/structural/`           | before/after file pairs, one per signal                       |

### The point not to forget

`__all__` built dynamically (`__all__ = [...] + other.__all__`) isn't a literal: fall back to the
underscore rule rather than treating the module as exporting nothing — which would hide every
removal.

### Definition of done

In a scratch repo: `agentcheck run --from <tree> --to <tree>` — a debug entry point, PROJECT.md §7 —
on a pair where `create_invoice` gained a required parameter, a public function was deleted, one
moved to another file, and a file got a syntax error, prints exactly three findings and no "removed"
for the moved one.

---

## Step 6 — "the file-level signals"

| File                                    | What                                                          |
| --------------------------------------- | ------------------------------------------------------------- |
| `src/agentcheck/config.py`              | **new** — defaults of PROJECT.md §8, overridden by `.agentcheck/config.toml` (`tomllib`) |
| `src/agentcheck/structural/files.py`    | **new** — sensitive paths, many files, code without tests, tests removed or disabled |
| `src/agentcheck/structural/deps.py`     | **new** — new dependency: names added in `requirements*.txt`, `pyproject.toml`, `package.json` |
| `src/agentcheck/structural/imports.py`  | **new** — unresolved in-repo imports (decision 5)             |
| `tests/fixtures/structural/`            | one case per signal, plus a manifest edited without adding a package |

**Already exists and isn't rewritten:** the extractors of Step 5 give imports and test markers.

### The point not to forget

**A dependency is a name, not a line.** Reordering `pyproject.toml`, or bumping a version, adds
lines without adding a package: manifests are parsed (`tomllib`, `json`) and compared as sets of
names. And glob patterns like `migrations/**` need a real `**` matcher: `fnmatch` treats `*` as
crossing `/`, `PurePath.match` doesn't do `**` before Python 3.13.

### Definition of done

In a scratch repo, one turn by hand that adds `python-dateutil` to `pyproject.toml`, touches
`.env.example`, adds `@pytest.mark.skip` to a test and imports `from .nonexistent import x`:
`agentcheck run` lists those four and nothing else. Reordering the dependencies alone lists nothing.

---

## Step 7 — "the verdict reaches the developer"

| File                       | What                                                             |
| -------------------------- | ---------------------------------------------------------------- |
| `src/agentcheck/risk.py`   | **new** — the sum and the levels (decision 6)                    |
| `src/agentcheck/report.py` | **new** — the lines, `max_lines`, the three cases of decision 7  |
| `src/agentcheck/hooks.py`  | Stop runs the analysis, stores findings, returns the JSON        |
| `tests/test_report.py`     | ordering, truncation (`… and 3 more`), silence, the one-liner    |

### The point not to forget

**The analysis must fail alone.** An exception in a signal drops that signal — noted in
`errors.log` — and the rest of the report still goes out; an exception anywhere still leaves the
turn record written. The Phase 0 record is the thing Phase 2 will stand on.

**Added after Step 6: an exception is not the only way to fail.** tree-sitter 0.26.0 crashed the
process with an access violation that no `try/except` catches — in a hook that would be a
"hook error" on every turn. The version is pinned below 0.26, but the next native crash or hang
will look the same: **Stop writes the turn record first, then runs the analysis in a child process
with a timeout.** A child that dies or times out is a line in `errors.log` and a turn with no
report — never a failed hook.

### Definition of done

In VS Code, in a real repo: ask Claude to add a required parameter to a public function without
touching the tests → the turn ends with a report, visible in the conversation, whose first line is
`agentcheck · turn N · risk MEDIUM`, and whose lines name the function and the untouched tests,
with `·` and `✓` displayed correctly. Then ask a question with no edit → no message. `elapsed_ms`
in the record under 2000.

---

## What this plan decided NOT to do

- **Postponed: third-party import resolution.** Needs the project's environment. Reopen if unresolved
  in-repo imports prove useful and false third-party ones are seen in real turns.
- **Postponed: TypeScript `interface`/`type` changes.** Exported types are API too, but comparing
  them is a different problem from comparing call signatures. Reopen after dogfooding.
- **Postponed: `.agentcheck/reports/` and `agentcheck last`.** Phase 3, PROJECT.md §9.
- **Postponed: claims.** The prompt text is now captured at turn start, which Phase 2 will want —
  nothing more is done with it here.
- **Not touched: `async: true` on Stop.** An async hook's output can't reach the developer, and
  decision 7 needs it to. Phase 0 measured 0.3–0.9 s: the budget allows synchronous.

## Summary

| Step | What                                         | Risk                                               |
| ---- | -------------------------------------------- | -------------------------------------------------- |
| 4    | Turn start on UserPromptSubmit               | Low: one more snapshot, the same machinery         |
| 5    | Symbol extractors, signature/removed/syntax  | Medium: "public" per language, moved vs removed    |
| 6    | File-level signals and config                | Medium: manifests and globs, easy to make noisy    |
| 7    | Risk, report, systemMessage — for real       | Medium: the first thing the developer sees         |

Starting baseline: **50 tests green**.
