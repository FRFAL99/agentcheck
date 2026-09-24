# Step registry

One row per step, from 0 up. It is the only place to look to know **what number a step has, which
plan it belongs to and whether it's closed**. How it went is in [devlog.md](devlog.md); where we are
now is in [STATUS.md](STATUS.md).

## Next free number: **8**

## The rules

1. **A number is never renumbered.** A retired number stays burned.
2. **A number is assigned by writing a plan**, which declares it at the top: "occupies Steps 1–3".
   It is written here at that moment, not when the plan is done.
3. **Off-plan work doesn't take a number.** It is a devlog entry with the date only.

Status: ✅ closed · 🟡 partly · ⬜ not done.

## The table

| N | Title                                      | Plan  | Status | Devlog     |
| - | ------------------------------------------ | ----- | ------ | ---------- |
| 0 | Repo and documentation                     | setup | ✅      | 2026-09-24 |
| 1 | The skeleton and `init`                    | v1    | ✅      | 2026-09-24 |
| 2 | The session remembers where it started     | v1    | ✅      | 2026-09-24 |
| 3 | Every turn leaves a trace                  | v1    | ✅      | 2026-09-24 |
| 4 | The developer's edits are not the agent's  | v2    | ⬜      |            |
| 5 | agentcheck knows what a public function is | v2    | ⬜      |            |
| 6 | The file-level signals                     | v2    | ⬜      |            |
| 7 | The verdict reaches the developer          | v2    | ⬜      |            |

## Plans

- **[v1](plan-v1-every-turn-leaves-a-trace.md)** — Phase 0 of PROJECT.md. Opened and **closed**
  2026-09-24, Steps 1–3, three of three.
- **[v2](plan-v2-the-turn-ends-with-a-verdict.md)** — Phase 1 of PROJECT.md. Opened 2026-09-24,
  occupies Steps 4–7.
