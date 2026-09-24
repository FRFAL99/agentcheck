"""Step 7: Stop runs the analysis in a child process and returns the report (plan v2, decision 7)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentcheck import hooks

from conftest import FIXTURES, git
from test_hooks import errors, hook_input, ready  # noqa: F401 — `ready` is a fixture
from test_stop import start, turns
from test_turn_start import prompt


def stop_output(repo: Path) -> str:
    payload = json.loads(hook_input("stop", repo))
    payload["prompt_id"] = "p-1"
    return hooks.run_hook("Stop", json.dumps(payload, ensure_ascii=False))


def analyses(repo: Path) -> list[dict]:
    path = repo / ".agentcheck" / "sessions" / "sess-1.analysis.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


@pytest.fixture
def api_repo(ready):
    """`ready`, plus api/invoices.py committed, a session started and a prompt submitted."""
    shutil.copytree(FIXTURES / "run" / "step7" / "before", ready, dirs_exist_ok=True)
    git(ready, "add", ".")
    git(ready, "commit", "-qm", "api")
    start(ready)
    prompt(ready, "p-1")
    return ready


def agent_changes_the_signature(repo: Path) -> None:
    shutil.copytree(FIXTURES / "run" / "step7" / "after", repo, dirs_exist_ok=True)


def test_a_turn_with_findings_ends_with_a_report(api_repo):
    agent_changes_the_signature(api_repo)

    out = stop_output(api_repo)

    message = json.loads(out)["systemMessage"].split("\n")
    assert message[0] == "agentcheck · turn 1 · risk MEDIUM"  # 3 + 2: one high, one medium
    assert message[1].startswith("! Signature changed: api/invoices.py::create_invoice now")
    assert message[2] == "! Code changed, no tests touched: api/invoices.py"
    (entry,) = analyses(api_repo)
    assert entry["risk"] == "medium" and entry["score"] == 5
    assert entry["reported"] is True
    assert [f["kind"] for f in entry["findings"]] == ["signature_changed", "no_tests"]
    assert errors(api_repo) == ""


def test_a_turn_that_changed_nothing_is_silent(api_repo):
    assert stop_output(api_repo) == ""
    assert analyses(api_repo)[0]["reported"] is False


def test_a_clean_turn_is_one_line(api_repo):
    (api_repo / "README.md").write_text("docs\n", encoding="utf-8")

    out = stop_output(api_repo)

    assert json.loads(out) == {"systemMessage": "agentcheck · turn 1 · all good (1 file)"}


def test_the_turn_is_recorded_before_the_analysis_runs(api_repo, monkeypatch):
    # The child dies like tree-sitter 0.26.0 did: no report, no failed hook, the turn on record.
    monkeypatch.setattr(hooks, "ANALYSIS_COMMAND", [sys.executable, "-c", "import os; os._exit(3221225477 % 256)"])
    agent_changes_the_signature(api_repo)

    out = stop_output(api_repo)

    assert out == ""
    assert turns(api_repo)[0]["changed_this_turn"] == [["M", "api/invoices.py"]]
    assert "analysis failed, no report for this turn: exit code" in errors(api_repo)
    assert "failed" in analyses(api_repo)[0]


def test_a_hanging_analysis_times_out(api_repo, monkeypatch):
    monkeypatch.setattr(hooks, "ANALYSIS_COMMAND", [sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(hooks, "ANALYSIS_TIMEOUT_S", 1)
    agent_changes_the_signature(api_repo)

    assert stop_output(api_repo) == ""
    assert "timed out" in errors(api_repo)


def test_unreadable_analysis_output(api_repo, monkeypatch):
    monkeypatch.setattr(hooks, "ANALYSIS_COMMAND", [sys.executable, "-c", "print('not json')"])
    agent_changes_the_signature(api_repo)

    assert stop_output(api_repo) == ""
    assert "unreadable output" in errors(api_repo)


def test_a_broken_config_falls_back_to_the_defaults(api_repo):
    (api_repo / ".agentcheck" / "config.toml").write_text("[report\n", encoding="utf-8")
    agent_changes_the_signature(api_repo)

    out = stop_output(api_repo)

    assert json.loads(out)["systemMessage"].startswith("agentcheck · turn 1 · risk MEDIUM")
    assert "not valid TOML" in errors(api_repo)


def test_max_lines_from_the_config(api_repo):
    (api_repo / ".agentcheck" / "config.toml").write_text("[report]\nmax_lines = 2\n", encoding="utf-8")
    agent_changes_the_signature(api_repo)

    lines = json.loads(stop_output(api_repo))["systemMessage"].split("\n")

    assert len(lines) == 2 and lines[1] == "… and 2 more"


def test_stdout_is_exactly_one_json_object_in_a_real_process(api_repo, tmp_path):
    # What Claude Code reads: the stdout of `agentcheck hook stop`, spawned from elsewhere, on a
    # Windows console encoding. Anything besides the object and the report is lost.
    agent_changes_the_signature(api_repo)
    payload = json.loads(hook_input("stop", api_repo))
    payload["prompt_id"] = "p-1"

    proc = subprocess.run(
        [sys.executable, "-m", "agentcheck", "hook", "stop"],
        input=json.dumps(payload).encode("utf-8"),
        cwd=tmp_path,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    text = proc.stdout.decode("utf-8").strip()
    assert text.startswith("{") and text.endswith("}")
    assert json.loads(text)["systemMessage"].startswith("agentcheck · turn 1 · risk MEDIUM")
