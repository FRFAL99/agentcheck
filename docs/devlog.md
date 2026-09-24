# Devlog

Chronological record of progress. Entries in reverse chronological order (newest at the top).

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
