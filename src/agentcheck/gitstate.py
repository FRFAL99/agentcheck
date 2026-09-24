"""Read-only access to the user's git state (ADR 0001, plan v1 decision 2).

Nothing here writes to the working tree, the index, refs or the stash. Snapshots are git trees
built through a temporary copy of the index; the only writes are objects in the object store.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

AGENTCHECK_DIR = ".agentcheck"


class GitError(Exception):
    pass


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    # Judged by exit code only: on Windows `git add` prints CRLF warnings on stderr.
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def repo_root(cwd: Path) -> Path | None:
    """The top level of the repo containing `cwd`, or None if it isn't in one."""
    try:
        return Path(_git(cwd, "rev-parse", "--show-toplevel").strip())
    except (GitError, OSError):
        return None


def head(repo: Path) -> str | None:
    """The commit HEAD points to, or None on an unborn branch."""
    try:
        return _git(repo, "rev-parse", "--verify", "-q", "HEAD").strip() or None
    except GitError:
        return None


def snapshot(repo: Path) -> str:
    """Tree id of the working tree as `git add -A` would see it, untracked files included.

    The user's index is copied, never used: `git add` runs against the copy through
    GIT_INDEX_FILE. Copying (rather than starting from HEAD) keeps git's stat cache, so unchanged
    files aren't re-hashed.
    """
    real_index = repo / _git(repo, "rev-parse", "--git-path", "index").strip()
    tmp_dir = repo / AGENTCHECK_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    # Per-process name: two overlapping hooks never share an index file.
    tmp_index = tmp_dir / f"index-{os.getpid()}"
    try:
        if real_index.exists():
            shutil.copyfile(real_index, tmp_index)
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index.resolve())}
        # The pathspec is a second guard: `.agentcheck/.gitignore` already hides the folder.
        _git(repo, "add", "-A", "--", ".", f":!{AGENTCHECK_DIR}", env=env)
        return _git(repo, "write-tree", env=env).strip()
    finally:
        tmp_index.unlink(missing_ok=True)


def tree_exists(repo: Path, tree: str) -> bool:
    """False when a snapshot's objects are gone, e.g. after a `git gc --prune=now`."""
    try:
        return _git(repo, "cat-file", "-t", tree).strip() == "tree"
    except GitError:
        return False


def read_blobs(repo: Path, tree: str, paths: list[str]) -> dict[str, bytes | None]:
    """Contents of `paths` in `tree` (None where absent), from the object store in one process.

    Never reads the working tree: a file the agent is still writing can't be caught half-done.
    """
    if not paths:
        return {}
    request = "".join(f"{tree}:{p}\n" for p in paths).encode("utf-8")
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"], input=request, capture_output=True
    )
    if proc.returncode != 0:
        raise GitError(f"git cat-file --batch failed ({proc.returncode}): {proc.stderr.decode(errors='replace')}")
    out, pos, blobs = proc.stdout, 0, {}
    for path in paths:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if header[-1] == b"missing" or header[1] != b"blob":
            blobs[path] = None
            continue
        size = int(header[2])
        blobs[path] = out[pos : pos + size]
        pos += size + 1  # the content is followed by a newline
    return blobs


def list_files(repo: Path, tree: str) -> list[str]:
    """Every file path in `tree`."""
    out = _git(repo, "ls-tree", "-r", "-z", "--name-only", tree)
    return [p for p in out.split("\0") if p]


def diff(repo: Path, old_tree: str, new_tree: str) -> list[tuple[str, str]]:
    """(status, path) pairs between two trees: A added, M modified, D deleted, T type changed.

    Renames are reported as a deletion plus an addition: detecting them is a guess, and Phase 1
    compares symbols, not file names.
    """
    out = _git(repo, "diff-tree", "-r", "-z", "--no-renames", "--name-status", old_tree, new_tree)
    parts = [p for p in out.split("\0") if p]
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]
