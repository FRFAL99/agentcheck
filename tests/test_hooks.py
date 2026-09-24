import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentcheck import gitstate, hooks
from agentcheck.init import run_init

from conftest import FIXTURES, git


def hook_input(name: str, repo: Path, session_id: str = "sess-1") -> str:
    payload = json.loads((FIXTURES / "hooks" / f"{name}.json").read_text(encoding="utf-8"))
    payload["cwd"] = str(repo)
    payload["session_id"] = session_id
    return json.dumps(payload, ensure_ascii=False)


def baseline(repo: Path, session_id: str = "sess-1") -> dict:
    path = repo / ".agentcheck" / "sessions" / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def raw_log(repo: Path) -> list[dict]:
    path = repo / ".agentcheck" / "logs" / "hooks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def errors(repo: Path) -> str:
    path = repo / ".agentcheck" / "logs" / "errors.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def ready(repo):
    """A repo with one commit, one uncommitted change, and `agentcheck init` done."""
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "a.txt").write_text("dirty before the session\n", encoding="utf-8")
    run_init(repo)
    return repo


def test_startup_writes_the_baseline(ready):
    out = hooks.run_hook("SessionStart", hook_input("session-start-startup", ready))

    assert out == ""
    base = baseline(ready)
    assert base["source"] == "startup"
    assert base["head"] == git(ready, "rev-parse", "HEAD").strip()
    # The snapshot includes the change that was already there: the diff starts from here.
    assert base["tree"] == gitstate.snapshot(ready)
    assert base["tree"] != git(ready, "rev-parse", "HEAD^{tree}").strip()
    assert errors(ready) == ""


@pytest.mark.parametrize("source", ["resume", "compact", "startup"])
def test_the_baseline_is_never_overwritten(ready, source):
    hooks.run_hook("SessionStart", hook_input("session-start-startup", ready))
    first = baseline(ready)
    (ready / "b.txt").write_text("the agent wrote this\n", encoding="utf-8")

    hooks.run_hook("SessionStart", hook_input(f"session-start-{source}", ready))

    assert baseline(ready) == first


def test_a_new_session_id_gets_its_own_baseline(ready):
    hooks.run_hook("SessionStart", hook_input("session-start-startup", ready, "sess-1"))
    (ready / "b.txt").write_text("b\n", encoding="utf-8")

    hooks.run_hook("SessionStart", hook_input("session-start-clear", ready, "sess-2"))

    assert baseline(ready, "sess-1")["tree"] != baseline(ready, "sess-2")["tree"]


def test_every_invocation_is_logged_verbatim(ready):
    start = hook_input("session-start-startup", ready)
    stop = hook_input("stop", ready)

    hooks.run_hook("SessionStart", start)
    hooks.run_hook("Stop", stop)

    log = raw_log(ready)
    assert [e["event"] for e in log] == ["SessionStart", "Stop"]
    assert log[1]["raw"] == stop
    assert "tutto verde ✓" in log[1]["raw"]


def test_unparseable_input_is_still_logged(ready, monkeypatch):
    monkeypatch.chdir(ready)

    out = hooks.run_hook("Stop", "not json {")

    assert out == ""
    assert raw_log(ready)[0]["raw"] == "not json {"
    assert "not a JSON object" in errors(ready)


def test_resolves_the_repo_from_the_input_not_the_process_cwd(ready, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    sub = ready / "src"
    sub.mkdir()
    payload = json.loads(hook_input("session-start-startup", ready))
    payload["cwd"] = str(sub)

    hooks.run_hook("SessionStart", json.dumps(payload))

    assert baseline(ready)["cwd"] == str(sub)


def test_not_a_git_repo_is_silent(tmp_path):
    payload = json.loads(hook_input("session-start-startup", tmp_path))

    assert hooks.run_hook("SessionStart", json.dumps(payload)) == ""
    assert not (tmp_path / ".agentcheck").exists()


def test_a_repo_without_init_is_left_untouched(repo):
    hooks.run_hook("SessionStart", hook_input("session-start-startup", repo))

    assert not (repo / ".agentcheck").exists()


def test_an_unsafe_session_id_writes_nothing_outside_sessions(ready):
    hooks.run_hook("SessionStart", hook_input("session-start-startup", ready, "../../escape"))

    assert list((ready / ".agentcheck" / "sessions").iterdir()) == []
    assert not (ready / "escape.json").exists()
    assert "unsafe session_id" in errors(ready)


def test_a_failure_inside_the_handler_is_logged_not_raised(ready, monkeypatch):
    def boom(repo):
        raise gitstate.GitError("simulated")

    monkeypatch.setattr(gitstate, "snapshot", boom)

    out = hooks.run_hook("SessionStart", hook_input("session-start-startup", ready))

    assert out == ""
    assert "simulated" in errors(ready)
    assert not (ready / ".agentcheck" / "sessions" / "sess-1.json").exists()


@pytest.mark.parametrize("event", ["session-start", "stop"])
def test_cli_hook_in_a_real_process(ready, event, tmp_path):
    # A real process, UTF-8 bytes on stdin, Windows' cp1252 as the default encoding, a cwd that
    # isn't the repo: what Claude Code will do. Exit 0 and nothing on stdout.
    fixture = "session-start-startup" if event == "session-start" else "stop"
    proc = subprocess.run(
        [sys.executable, "-m", "agentcheck", "hook", event],
        input=hook_input(fixture, ready).encode("utf-8"),
        cwd=tmp_path,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout == b""
    assert errors(ready) == ""
    assert raw_log(ready)[-1]["event"] == ("SessionStart" if event == "session-start" else "Stop")
