import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentcheck.cli import app
from agentcheck.init import HOOK_COMMANDS, InitError, run_init

from conftest import FIXTURES, git


def settings_of(repo: Path) -> dict:
    return json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))


def commands(settings: dict, event: str) -> list[str]:
    return [h["command"] for g in settings["hooks"][event] for h in g["hooks"]]


def test_creates_settings_with_both_hooks(repo):
    result = run_init(repo)

    settings = settings_of(repo)
    assert commands(settings, "SessionStart") == [HOOK_COMMANDS["SessionStart"]]
    assert commands(settings, "Stop") == [HOOK_COMMANDS["Stop"]]
    assert result.settings_created
    assert result.hooks_added == ["SessionStart", "Stop"]


def test_is_idempotent(repo):
    run_init(repo)
    before = (repo / ".claude" / "settings.json").read_bytes()

    result = run_init(repo)

    assert result.hooks_added == []
    assert result.hooks_present == ["SessionStart", "Stop"]
    assert (repo / ".claude" / "settings.json").read_bytes() == before


def test_keeps_existing_keys_and_hooks(repo):
    (repo / ".claude").mkdir()
    shutil.copy(FIXTURES / "settings" / "with-other-stop-hook.json", repo / ".claude" / "settings.json")

    run_init(repo)

    settings = settings_of(repo)
    assert settings["permissions"] == {"allow": ["Bash(npm test)"]}
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "./check.sh"
    # The other tool's Stop hook stays, ours is appended as a separate group.
    assert commands(settings, "Stop") == ["notify-send done", HOOK_COMMANDS["Stop"]]


def test_refuses_invalid_json_and_writes_nothing(repo):
    (repo / ".claude").mkdir()
    shutil.copy(FIXTURES / "settings" / "invalid.json", repo / ".claude" / "settings.json")
    before = (repo / ".claude" / "settings.json").read_bytes()

    with pytest.raises(InitError, match="not valid JSON"):
        run_init(repo)

    assert (repo / ".claude" / "settings.json").read_bytes() == before
    assert not (repo / ".agentcheck").exists()


def test_refuses_hooks_event_that_is_not_a_list(repo):
    (repo / ".claude").mkdir()
    original = {"hooks": {"SessionStart": [], "Stop": {"command": "x"}}}
    (repo / ".claude" / "settings.json").write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(InitError, match="hooks.Stop"):
        run_init(repo)

    assert settings_of(repo) == original


def test_agentcheck_dir_is_invisible_to_git(repo):
    (repo / "a.txt").write_text("a\n", encoding="utf-8")

    run_init(repo)
    (repo / ".agentcheck" / "logs" / "something.log").write_text("x\n", encoding="utf-8")

    status = git(repo, "status", "--porcelain", "--untracked-files=all")
    assert ".agentcheck" not in status
    assert "a.txt" in status


def test_works_from_a_subdirectory(repo):
    sub = repo / "src" / "pkg"
    sub.mkdir(parents=True)

    result = run_init(sub)

    assert result.repo.resolve() == repo.resolve()
    assert (repo / ".claude" / "settings.json").exists()
    assert not (sub / ".claude").exists()


def test_not_a_git_repo(tmp_path):
    with pytest.raises(InitError, match="not inside a git repository"):
        run_init(tmp_path)


def test_cli_init(repo, monkeypatch):
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert "SessionStart, Stop hook added" in result.output


def test_cli_init_outside_a_repo_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 1
    assert "not inside a git repository" in result.output


def test_cli_init_survives_a_cp1252_stdout(repo):
    # CliRunner writes UTF-8 and can't see this: a real process with a Windows piped stdout can.
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}

    proc = subprocess.run(
        [sys.executable, "-m", "agentcheck", "init"], cwd=repo, env=env, capture_output=True
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert "✓" in proc.stdout.decode("utf-8")
