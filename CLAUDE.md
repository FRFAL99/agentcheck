# agentcheck — how work is done in this repo

**Read [PROJECT.md](PROJECT.md) before starting, and follow the phases in order.** It is the product
spec: what the tool is, the design principles, the stack, and section 13 — the rules for working
here. Do not anticipate features from a later phase.

Python 3.11+ managed with `uv`, CLI with `typer`. One-person project: **code, comments,
documentation and commit messages are in English.**

## Read these first

| You want to know…                                   | Read                                                    |
| --------------------------------------------------- | ------------------------------------------------------- |
| what the tool is and why                            | `PROJECT.md`                                            |
| where we are **today**                              | `docs/STATUS.md`                                        |
| what number a step has, and whether it's closed     | `docs/registry.md`                                      |
| **how something works**, now                        | `docs/knowledge/`                                       |
| how Claude Code hooks really behave                 | `docs/knowledge/claude-code-hooks.md`                   |
| what was **decided** and why, for the work in progress | the plan `docs/plan-vN-*.md`                         |
| an irreversible architectural choice                | `docs/adr/`                                             |

`docs/devlog.md` is newest-first. Once it grows, grep it instead of reading it whole:
`grep -n '^## ' docs/devlog.md` is its index.

## Verification

```bash
uv run pytest                        # full test suite
uv run agentcheck --help             # the CLI still starts
```

Nothing else is wired yet. A linter or formatter is a new dependency: PROJECT.md §13 says ask first.

**After adding a dependency, run `uv tool install --editable . --reinstall`.** The editable tool
follows the source but not new dependencies: the `agentcheck` the hooks call would miss them.

## Rules that are not negotiable

1. **agentcheck never modifies the user's repo.** Not files, not the index, not refs, not the
   stash. The one exception is `agentcheck init`, run by hand, which writes `.claude/settings.json`
   and `.agentcheck/`. See [ADR 0001](docs/adr/0001-never-touch-the-users-git-state.md).
2. **A hook never breaks the user's session.** Every hook entry point catches everything, logs to
   `.agentcheck/logs/`, and exits 0. Exit 2 blocks Claude: only the opt-in send-back mode may
   produce a block, and only through JSON `decision: "block"`.
3. **A hook never trusts its process cwd.** Claude Code spawns it from a directory we don't choose —
   the same lesson as `obsidian-dev-agent`'s MCP server. The repo is resolved from the `cwd` field
   of the hook input.
4. **`structural/` never imports `claims.py`.** The deterministic report must exist without the LLM.
5. **Hook facts come from the docs, then from the raw stdin log** — never from memory. Update
   `docs/knowledge/claude-code-hooks.md` when they turn out different.

## Step numbering

Global and continuous, from 0 up.

1. **Never renumber.** A retired number stays burned.
2. **A number is assigned by writing a plan**, which declares it at the top: "occupies Steps 1–3".
   It is written into `docs/registry.md` at that moment, not when the plan is done.
3. **Off-plan work doesn't take a number**: it's a devlog entry with the date only.
4. **"What's the next number" has one source**: the "Next free number" line in `docs/registry.md`.

Each phase of PROJECT.md §9 becomes one plan when it starts. A new plan starts from
`docs/plan-TEMPLATE.md` — or run `/new-plan`.

## End-of-step ritual

Run `/end-step`, or by hand:

1. `uv run pytest` — stop at the first red, and say so
2. `docs/registry.md`: the step's row goes to ✅
3. `docs/devlog.md`: new entry **at the top**, `## YYYY-MM-DD — Step N: <title>`, closed by
   `### Verification` with the real test count
4. `docs/STATUS.md`: **only if where we are changes**. What became done is **deleted** from "What's
   missing" — the history is already in the devlog. STATUS stays under 200 lines.
5. A new pitfall → `docs/knowledge/pitfalls.md`, not only in the devlog
6. Commit `Step N: <lowercase English sentence>` — **ask before committing**

## Where to write what

| What changes…                           | Write in                                                 |
| --------------------------------------- | -------------------------------------------------------- |
| where we are today                      | `docs/STATUS.md` — and delete what is no longer open     |
| the state of a step                     | `docs/registry.md`                                       |
| how today went                          | `docs/devlog.md`, at the top                             |
| how something works, now                | `docs/knowledge/`                                        |
| a decision of the work in progress      | the plan `docs/plan-vN-*.md`                             |
| an irreversible architectural choice    | `docs/adr/`                                              |
| what the product is                     | `PROJECT.md` — rarely, and saying which plan changed it  |

If an Obsidian vault keeps a parallel devlog of this project (via `obsidian-dev-agent`), it is
**decoupled on purpose**: when the two diverge, **`docs/devlog.md` is the source of truth**.
