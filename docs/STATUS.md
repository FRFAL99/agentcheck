# Project status — starting point

> Updated: **2026-09-24**

Where we are today, what's missing and what's blocked. No history: that's in
[devlog.md](devlog.md).

**The rule that keeps this document short: when a line of "What's missing" becomes done, it is
deleted.** Not moved to a list of done things, not annotated "✅ solved on…": deleted, because the
history is already in the devlog and the [registry](registry.md) keeps it anyway. Under 200 lines.

## Where we are

**Phase 0 is done — [plan v1](plan-v1-every-turn-leaves-a-trace.md) closed, Steps 0–3.** In a repo
where `agentcheck init` ran, every Claude Code session gets a baseline, and every turn appends a
record to `.agentcheck/sessions/<id>.turns.jsonl`: what changed since the session started, what
changed in this turn, what the agent said, and the state of the transcript at that moment.
Checked with real Claude Code on both versions of this machine. Nothing is shown to the user yet.
**50 tests green.**
Step 0 gave the spec ([PROJECT.md](../PROJECT.md)), the way of working ([CLAUDE.md](../CLAUDE.md)), the verified
behaviour of Claude Code hooks ([knowledge/claude-code-hooks.md](knowledge/claude-code-hooks.md)) and the first ADR.

On this machine agentcheck is installed with `uv tool install --editable .`, so the `agentcheck`
on PATH follows the source. The repo is on GitHub, private:
https://github.com/FRFAL99/agentcheck.

**[Plan v2](plan-v2-the-turn-ends-with-a-verdict.md) is open** — Phase 1, Steps 4–7: the turn
starts at the prompt, symbols and file-level signals, a risk score, and the first report shown
to the developer. Next is **Step 4**.

## What's missing

- **Plan v2**, all four steps.
- **"This turn" includes the user's own edits between turns** — seen for real on 2026-09-24.
  Step 4 fixes it with a snapshot on `UserPromptSubmit`.
- **The terminal `claude` is 2.1.23**, the VS Code extension 2.1.281: the old one sends no
  `last_assistant_message` and fires no hook on `/compact` in `-p` mode. Updating it
  (`claude update`) is the user's call; agentcheck has to work with both anyway.
- Phases 2–5 of PROJECT.md §9, each still to be turned into a plan.
- **The four open questions** of PROJECT.md §12. The one about how to show the report is answered
  (`systemMessage`); "every turn or only above `low`" gets decided with the first real report, in
  Phase 1.

## What's blocked, and by what

Nothing.
