"""Hook entry points (plan v1, decisions 1, 4 and 5).

`run_hook` is the envelope every hook goes through: it resolves the repo from the input, logs the
raw input, runs the handler, and never raises. What it returns is what goes on stdout — in Phase 0,
always nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from agentcheck import gitstate

AGENTCHECK_DIR = gitstate.AGENTCHECK_DIR

# A session id becomes a file name: anything else could escape `sessions/`.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _locate_repo(payload: dict | None) -> Path | None:
    """The repo the hook is about: the input's `cwd` first, never the process cwd alone.

    The fallbacks only matter when the input couldn't be parsed, so the raw log still lands
    somewhere useful.
    """
    candidates = []
    if payload and isinstance(payload.get("cwd"), str):
        candidates.append(payload["cwd"])
    else:
        candidates += [os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()]
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            root = gitstate.repo_root(Path(candidate))
            if root is not None:
                return root
    return None


def session_path(repo: Path, session_id: str) -> Path:
    if not _SAFE_ID.match(session_id):
        raise ValueError(f"unsafe session_id: {session_id!r}")
    return repo / AGENTCHECK_DIR / "sessions" / f"{session_id}.json"


def session_start(payload: dict, repo: Path) -> None:
    """Write the baseline once per session id (decision 1).

    `resume` and `compact` keep their session id and must keep their starting point; `clear` and
    `fork` arrive with a new id and get a new baseline without any special case on `source`.
    """
    path = session_path(repo, payload["session_id"])
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "session_id": payload["session_id"],
            "started_at": _now(),
            "source": payload.get("source"),
            "cwd": payload.get("cwd"),
            "transcript_path": payload.get("transcript_path"),
            "head": gitstate.head(repo),
            "tree": gitstate.snapshot(repo),
        },
    )


def stop(payload: dict, repo: Path) -> None:
    """Stub until Step 3: the raw input is already logged by the envelope."""


HANDLERS = {"SessionStart": session_start, "Stop": stop}


def run_hook(event: str, raw: str) -> str:
    """Run one hook invocation. Never raises; returns what goes on stdout."""
    repo = None
    try:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                payload = None
        except json.JSONDecodeError:
            payload = None

        repo = _locate_repo(payload)
        # Not a git repo, or a repo where `agentcheck init` never ran: stay silent, write nothing.
        if repo is None or not (repo / AGENTCHECK_DIR).is_dir():
            return ""

        logs = repo / AGENTCHECK_DIR / "logs"
        logs.mkdir(exist_ok=True)
        # Verbatim, before anything can fail: it's the ground truth of what Claude Code sends.
        _append(logs / "hooks.jsonl", json.dumps({"received_at": _now(), "event": event, "raw": raw}))

        if payload is None:
            raise ValueError("hook input is not a JSON object")
        HANDLERS[event](payload, repo)
    except Exception:
        _report_error(repo, event)
    return ""


def _report_error(repo: Path | None, event: str) -> None:
    text = f"--- {_now()} {event}\n{traceback.format_exc()}"
    try:
        if repo is not None and (repo / AGENTCHECK_DIR).is_dir():
            logs = repo / AGENTCHECK_DIR / "logs"
            logs.mkdir(exist_ok=True)
            with (logs / "errors.log").open("a", encoding="utf-8") as f:
                f.write(text)
            return
    except OSError:
        pass
    # stderr of a hook that exits 0 goes to Claude Code's debug log only.
    print(text, file=sys.stderr)
