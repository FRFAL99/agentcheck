---
description: Opens a new work plan, allocating its steps in the registry
---

Open a new plan for agentcheck. The argument, if any, is the topic: $ARGUMENTS

Follow this order, without skipping.

## 1. Read before proposing

- `docs/registry.md` — the next free number and the last plan
- `docs/STATUS.md` — where we are, and above all **what's missing**
- `PROJECT.md` §9 — the next phase, since each phase becomes one plan
- `CLAUDE.md` — the numbering rule

If the user didn't say what the plan is about, propose the next phase of PROJECT.md, or two or three
candidates from "What's missing" in `STATUS.md`, and ask. Don't invent a topic.

## 2. Write decision 0 by reading the code and the docs

**This is the step that isn't skipped, and it's why this command exists.** Before writing a single
decision, read the code the plan would touch — and, for anything about Claude Code or the Anthropic
API, the official docs — and write:

- what **already exists** and mustn't be rewritten, with files and lines;
- what **PROJECT.md or a code comment says that is false**, and that the plan corrects;
- anything you can **try in a scratch repo** instead of assuming — then try it.

## 3. Write the plan

```bash
cp docs/plan-TEMPLATE.md docs/plan-v<N>-<slug>.md
```

The title says **what changes for the developer using agentcheck**, not which part of the code is
touched. One to three problems in the context: more than three means two plans. Every definition of
done is **a gesture**, never "tests pass".

## 4. Allocate the numbers in the registry, now

Add the rows to `docs/registry.md` with status ⬜, the `Plan` column filled in, and **update the
"next free number"**. It's done now, not when the plan is finished: it's the act that assigns the
numbers.

## 5. Close

Show the user the plan and the registry rows. Commit `Write Plan v<N>: <lowercase English
sentence>` — but **ask before committing**.
