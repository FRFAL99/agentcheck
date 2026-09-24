"""Hook entry points (plan v1, decisions 1, 4 and 5; Step 3).

`run_hook` is the envelope every hook goes through: it resolves the repo from the input, logs the
raw input, runs the handler, and never raises. What it returns is what goes on stdout — in Phase 0,
always nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from agentcheck import collector, gitstate

AGENTCHECK_DIR = gitstate.AGENTCHECK_DIR

# A session id becomes a file name: anything else could escape `sessions/`.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _note(repo: Path, message: str) -> None:
    """Something worth knowing that isn't an error: goes to `logs/agentcheck.log`."""
    _append(repo / AGENTCHECK_DIR / "logs" / "agentcheck.log", f"{_now()} {message}")


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


def turns_path(repo: Path, session_id: str) -> Path:
    return session_path(repo, session_id).with_suffix(".turns.jsonl")


def _last_turn(path: Path) -> dict | None:
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else None


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
    """Append one record per turn: what changed since the session started and in this turn.

    A turn in which the agent only talks is a valid record with an empty `changed_this_turn` —
    Phase 2 needs exactly those ("I fixed it" with nothing changed).
    """
    started = time.perf_counter()
    session_id = payload["session_id"]
    base_file = session_path(repo, session_id)
    if not base_file.exists():
        # Don't invent a baseline now: this turn's diff would be empty and look clean (decision 1).
        _note(repo, f"Stop without a baseline for session {session_id}: turn not recorded")
        return
    base = json.loads(base_file.read_text(encoding="utf-8"))
    if not gitstate.tree_exists(repo, base["tree"]):
        _note(repo, f"baseline tree {base['tree']} of session {session_id} is gone (git gc?): turn not recorded")
        return

    turns = turns_path(repo, session_id)
    previous = _last_turn(turns)
    previous_tree = previous["tree"] if previous else base["tree"]

    tree = gitstate.snapshot(repo)
    this_turn = None
    if gitstate.tree_exists(repo, previous_tree):
        this_turn = [list(c) for c in gitstate.diff(repo, previous_tree, tree)]
    else:
        _note(repo, f"previous turn tree {previous_tree} is gone (git gc?): changed_this_turn unknown")

    final_message = payload.get("last_assistant_message")
    record = {
        "turn": (previous["turn"] + 1) if previous else 1,
        "completed_at": _now(),
        "session_id": session_id,
        "head": gitstate.head(repo),
        "tree": tree,
        "changed_since_start": [list(c) for c in gitstate.diff(repo, base["tree"], tree)],
        "changed_this_turn": this_turn,
        "stop_hook_active": payload.get("stop_hook_active"),
        # None when the Claude Code version doesn't send it (2.1.23 doesn't).
        "last_assistant_message": final_message,
        "transcript_path": payload.get("transcript_path"),
        "transcript_at_stop": collector.transcript_state(payload.get("transcript_path"), final_message),
    }
    record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    _append(turns, json.dumps(record, ensure_ascii=False))


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
