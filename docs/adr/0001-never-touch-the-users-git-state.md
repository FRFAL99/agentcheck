# ADR 0001 — agentcheck never touches the user's git state

- **Date:** 2026-09-24
- **Status:** Accepted

## Context

agentcheck runs inside someone else's repo, on every turn of an agent, without being asked each
time. It needs two things from git: a snapshot of the working tree at the start of the session, and
one at the end of every turn, including untracked files.

The obvious commands to get them all have side effects the user would notice or suffer:

- `git stash` / `git stash push` moves the user's changes out of the working tree.
- `git add` stages files in the user's index: the next `git commit` would include things the user
  didn't choose.
- A branch, tag or ref under `refs/` shows up in `git log --all`, in IDEs, and gets pushed by
  `git push --mirror`.

`git stash create` is safe, but it ignores untracked files — the new files an agent creates are
exactly the ones that matter most.

## Decision

agentcheck **never writes** to the user's working tree, index (`.git/index`), refs, reflog or
stash. Snapshots are built through a **temporary index file** (`GIT_INDEX_FILE` pointing inside
`.agentcheck/`), seeded from a copy of the real index, and turned into a tree with
`git write-tree`. The tree id is stored in `.agentcheck/`, not in a ref.

The only writes into `.git/` are the blob and tree objects that `git add` and `git write-tree`
create in the object store. They are content-addressed, invisible to every porcelain command, and
unreferenced objects are removed by `git gc` after the prune window.

`agentcheck init`, run by hand, is the one command allowed to write user files: `.claude/settings.json`
(merged, never overwritten) and `.agentcheck/`.

## Consequences

**Positive**

- Running agentcheck, or uninstalling it, can't change what the user's next commit contains.
- Start and end snapshots are the same kind of object, so the diff is one `git diff-tree`.
- Untracked, non-ignored files are included for free, because `git add -A` on the temporary index
  honours `.gitignore`.

**Negative**

- Unreferenced objects accumulate until `git gc`. At the scale of one developer's sessions, this is
  noise in the object store, not a size problem.
- Because snapshots aren't referenced, a `git gc --prune=now` run by the user during a session can
  delete a baseline. The snapshot's tree id then no longer resolves: agentcheck must detect it and
  say so, not crash.

## Reversibility

Reversible: the snapshots live only in `.agentcheck/`. If the object growth ever matters, a single
ref under a private namespace (`refs/agentcheck/…`) would keep baselines alive — that would be a
new ADR, because it is a visible write.
