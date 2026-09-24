# Project status — starting point

> Updated: **2026-09-24**

Where we are today, what's missing and what's blocked. No history: that's in
[devlog.md](devlog.md).

**The rule that keeps this document short: when a line of "What's missing" becomes done, it is
deleted.** Not moved to a list of done things, not annotated "✅ solved on…": deleted, because the
history is already in the devlog and the [registry](registry.md) keeps it anyway. Under 200 lines.

## Where we are

**Steps 0–2 are closed.** `agentcheck init` wires the hooks into a repo; SessionStart saves a
baseline snapshot once per session; Stop only logs its raw input so far. **35 tests green.**
Step 0 gave the spec ([PROJECT.md](../PROJECT.md)), the way of working ([CLAUDE.md](../CLAUDE.md)), the verified
behaviour of Claude Code hooks ([knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md)) and the first ADR.

On this machine agentcheck is installed with `uv tool install --editable .`, so the `agentcheck`
on PATH follows the source. The repo is on GitHub, private:
https://github.com/FRFAL99/agentcheck.

**[Plan v1](plan-v1-every-turn-leaves-a-trace.md) is open** — Phase 0, Steps 1–3: hook into
Claude Code and leave, for every turn, a log with the correct diff. Next is **Step 3**: the per-turn diff.

## What's missing

- **Step 3** of plan v1: the per-turn diff, checked in a real session.
- **The terminal `claude` is 2.1.23**, the VS Code extension 2.1.281: the old one sends no
  `last_assistant_message` and fires no hook on `/compact` in `-p` mode. Updating it
  (`claude update`) is the user's call; agentcheck has to work with both anyway.
- Phases 1–5 of PROJECT.md §9, each still to be turned into a plan.
- **The four open questions** of PROJECT.md §12. The one about how to show the report is answered
  (`systemMessage`); "every turn or only above `low`" gets decided with the first real report, in
  Phase 1.

## What's blocked, and by what

Nothing.
