---
description: Runs the end-of-step ritual, stopping at the first red
---

Close the step in progress on agentcheck following the ritual in `CLAUDE.md`. User notes, if any:
$ARGUMENTS

**Stop at the first red and say so.** Don't carry on "it'll get fixed later", and don't report as
done what didn't pass.

## 1. Verification

```bash
uv run pytest
uv run agentcheck --help
```

## 2. The definition of done

Re-read the step's "Definition of done" in its plan. If it is a gesture in a real Claude Code
session, **ask the user to perform it** and report what they saw — don't mark it done on the
strength of the tests.

## 3. `docs/registry.md`

The step's row goes to ✅. If the step wasn't in the table, it's an upstream mistake: the number
should have been allocated when the plan was written. Add it and tell the user.

## 4. `docs/devlog.md`

New entry **at the top** (the file is newest-first), title
`## YYYY-MM-DD — Step N: <lowercase title, with the thesis of what was learned>`, separated from the
next one by `---` and closed by `### Verification` with the test count just seen — the real one,
not copied from the previous entry.

Also tell **what deviated from the plan**: it's the part worth rereading.

## 5. `docs/STATUS.md`, only if needed

Touched **only if where we are changes**. When a line of "What's missing" has become done, it is
**deleted** — not moved to done things, not annotated as solved. STATUS stays under 200 lines.

## 6. A new pitfall

If the step lost time for a reason someone could rediscover, the row goes in
`docs/knowledge/pitfalls.md`, not only in the devlog. If a hook behaved differently from
`docs/knowledge/claude-code-hooks.md`, correct that file.

## 7. Commit

Commit `Step N: <lowercase English sentence>` — **asking the user first**.
