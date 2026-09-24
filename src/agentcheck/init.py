"""`agentcheck init`: wire the hooks into a repo (plan v1, decisions 3 and 6).

The one command allowed to write user files (ADR 0001): it merges two hook entries into
`.claude/settings.json` and creates `.agentcheck/`. It never rewrites a file it couldn't read.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from agentcheck.gitstate import AGENTCHECK_DIR, repo_root

SETTINGS_PATH = Path(".claude") / "settings.json"

# A bare command, not an interpreter path: settings.json stays identical across machines and
# committable. It relies on `agentcheck` being on PATH (decision 6).
HOOK_COMMANDS = {
    "SessionStart": "agentcheck hook session-start",
    "UserPromptSubmit": "agentcheck hook user-prompt-submit",
    "Stop": "agentcheck hook stop",
}


class InitError(Exception):
    """Something the user must fix before init can go on. Nothing has been written."""


@dataclass
class InitResult:
    repo: Path
    hooks_added: list[str] = field(default_factory=list)
    hooks_present: list[str] = field(default_factory=list)
    settings_created: bool = False
    on_path: bool = True


def find_repo_root(start: Path) -> Path:
    root = repo_root(start)
    if root is None:
        raise InitError(f"{start} is not inside a git repository.")
    return root


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InitError(f"{path} is not valid JSON ({exc}). Fix it and run init again.") from exc
    if not isinstance(settings, dict):
        raise InitError(f"{path} is not a JSON object. Fix it and run init again.")
    return settings


def _has_command(groups: list, command: str) -> bool:
    for group in groups:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks") or []:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False


def merge_hooks(settings: dict) -> tuple[list[str], list[str]]:
    """Add our hooks to `settings` in place. Returns (events added, events already present).

    Existing matcher groups for the same event — the user's or another tool's — are kept: ours is
    appended as a new group, never replacing the array.
    """
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InitError('"hooks" in settings.json is not an object. Fix it and run init again.')

    # Validate everything before touching anything, so a refusal leaves `settings` unchanged.
    for event in HOOK_COMMANDS:
        if event in hooks and not isinstance(hooks[event], list):
            raise InitError(f'"hooks.{event}" in settings.json is not a list. Fix it and run init again.')

    added, present = [], []
    for event, command in HOOK_COMMANDS.items():
        groups = hooks.setdefault(event, [])
        if _has_command(groups, command):
            present.append(event)
            continue
        groups.append({"hooks": [{"type": "command", "command": command}]})
        added.append(event)
    return added, present


def _ensure_agentcheck_dir(repo: Path) -> None:
    root = repo / AGENTCHECK_DIR
    for sub in ("logs", "sessions", "tmp"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    # Self-ignoring folder: invisible to `git status` and to snapshots, without editing the user's
    # own .gitignore (decision 3).
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")


def run_init(start: Path) -> InitResult:
    repo = find_repo_root(start)
    settings_file = repo / SETTINGS_PATH

    settings = _load_settings(settings_file)
    created = not settings_file.exists()
    added, present = merge_hooks(settings)

    if added:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    _ensure_agentcheck_dir(repo)

    return InitResult(
        repo=repo,
        hooks_added=added,
        hooks_present=present,
        settings_created=created and bool(added),
        on_path=shutil.which("agentcheck") is not None,
    )
