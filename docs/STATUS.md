# Project status — starting point

> Updated: **2026-09-24**

Where we are today, what's missing and what's blocked. No history: that's in
[devlog.md](devlog.md).

**The rule that keeps this document short: when a line of "What's missing" becomes done, it is
deleted.** Not moved to a list of done things, not annotated "✅ solved on…": deleted, because the
history is already in the devlog and the [registry](registry.md) keeps it anyway. Under 200 lines.

## Where we are

**Steps 0 and 1 are closed.** `agentcheck init` wires the hooks into a repo; the hooks themselves
are still stubs that read their input and print nothing. **13 tests green.** Step 0 gave the spec
([PROJECT.md](../PROJECT.md)), the way of working ([CLAUDE.md](../CLAUDE.md)), the verified
behaviour of Claude Code hooks
([knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md)) and the first ADR.

On this machine agentcheck is installed with `uv tool install --editable .`, so the `agentcheck`
on PATH follows the source.

**[Plan v1](plan-v1-every-turn-leaves-a-trace.md) is open** — Phase 0, Steps 1–3: hook into
Claude Code and leave, for every turn, a log with the correct diff. Next is **Step 2**: the baseline.

## What's missing

- **Steps 2 and 3** of plan v1: the baseline, then the per-turn diff checked in a real session.
- Phases 1–5 of PROJECT.md §9, each still to be turned into a plan.
- **The four open questions** of PROJECT.md §12. The one about how to show the report is answered
  (`systemMessage`); "every turn or only above `low`" gets decided with the first real report, in
  Phase 1.

## What's blocked, and by what

Nothing.
