# Project status — starting point

> Updated: **2026-09-24**

Where we are today, what's missing and what's blocked. No history: that's in
[devlog.md](devlog.md).

**The rule that keeps this document short: when a line of "What's missing" becomes done, it is
deleted.** Not moved to a list of done things, not annotated "✅ solved on…": deleted, because the
history is already in the devlog and the [registry](registry.md) keeps it anyway. Under 200 lines.

## Where we are

**Documentation only, no code.** Step 0 is closed: the spec ([PROJECT.md](../PROJECT.md)), the way
of working ([CLAUDE.md](../CLAUDE.md)), the verified behaviour of Claude Code hooks
([knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md)) and the first ADR.

**[Plan v1](plan-v1-every-turn-leaves-a-trace.md) is open** — Phase 0, Steps 1–3: hook into
Claude Code and leave, for every turn, a log with the correct diff. Next is **Step 1**.

## What's missing

- **Phase 0**, the whole of plan v1.
- Phases 1–5 of PROJECT.md §9, each still to be turned into a plan.
- **The four open questions** of PROJECT.md §12. The one about how to show the report is answered
  (`systemMessage`); "every turn or only above `low`" gets decided with the first real report, in
  Phase 1.

## What's blocked, and by what

- **Step 1 is blocked by the toolchain.** On 2026-09-24 this machine had **no Python and no `uv`**
  (`python` resolves only to the Microsoft Store alias), and no WSL. `uv` can install Python itself,
  so installing `uv` unblocks both.
