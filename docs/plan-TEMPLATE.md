# agentcheck — Plan vN: "the change, not the area"

> Copy this file to `docs/plan-vN-<slug>.md` and delete the lines in italics, which are
> instructions. The title says **what changes** for the developer using agentcheck, not which part
> of the code gets touched: _"every turn leaves a trace"_, not _"collector refactor"_.

> Entry point of the project: [STATUS.md](STATUS.md). **Where this plan comes from:** a phase of
> [PROJECT.md](../PROJECT.md) §9 / real use on a repo / a cold read of the code. Written on <date>.
>
> **Occupies Steps \<A\>–\<B\>**, one per session. The numbers are taken from
> [registry.md](registry.md) and written there **now**, not when the plan is done.
>
> **Every measurement and reference below was read in the code or the docs**, not inferred.

## Context

_One to three problems, numbered, two lines each. More than three means two plans._

1. **The problem in bold.** What happens today to the developer, and why it's a problem.
2. …

## What already exists (decision 0)

_Mandatory, and written first — by reading the code and the official docs, before deciding
anything else._

**Decision.** _What the code, git or Claude Code already offers, and therefore isn't rewritten._

**Why.** _With files and lines, or the docs section. If PROJECT.md or a comment in the code says
something false, quote it and say that this plan corrects it._

---

## The decisions

### 1 · An affirmative sentence, not a topic title

_"The baseline is never overwritten", not "Baseline management"._

**Decision.** What is done, in one sentence.

**Why.** The reason, with a reference to real code or docs.

**Constraint.** What must remain true afterwards.

### 2 · …

---

## Step \<A\> — "the title"

| File                        | What                                   |
| --------------------------- | -------------------------------------- |
| `src/agentcheck/module.py`  | **new** — what it's for (decision N)   |
| `tests/test_module.py`      | what it pins down                      |

**Already exists and isn't rewritten:** _functions reused, with the module they come from._

### The point not to forget

_The defect that would look like it works. If there isn't one, delete the section — don't fill it
with generalities._

### Definition of done

_A gesture, in order, with the expected outcome: "open Claude Code in a real repo → ask it to edit a
file → `.agentcheck/logs/…` contains that file with status M". **Never "tests pass".** If a
criterion can't be performed by hand, it isn't a criterion._

---

## Step \<B\> — …

---

## What this plan decided NOT to do

_Mandatory, so it doesn't disappear. Each item with its reason:_

- **Postponed:** _what, and the condition that would reopen it._
- **Not touched:** _what, and where the decision was already made (an ADR, PROJECT.md, a previous
  plan)._

## Summary

| Step  | What | Risk |
| ----- | ---- | ---- |
| \<A\> |      |      |

Starting baseline: **N tests green**.
