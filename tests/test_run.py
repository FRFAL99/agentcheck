"""`agentcheck run`: the analysis by hand, the definition of done of Step 5."""

import shutil

from typer.testing import CliRunner

from agentcheck.cli import app

from conftest import FIXTURES, git

DOD = FIXTURES / "run" / "step5"


def test_run_between_a_commit_and_the_working_tree(repo, monkeypatch):
    shutil.copytree(DOD / "before", repo, dirs_exist_ok=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "before")
    shutil.rmtree(repo / "api")
    shutil.copytree(DOD / "after", repo, dirs_exist_ok=True)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["run", "--from", "HEAD"])

    assert result.exit_code == 0, result.output
    lines = [l for l in result.output.splitlines() if l.startswith("!")]
    assert len(lines) == 3, result.output
    text = " ".join(result.output.split())
    assert "Signature changed: api/invoices.py::create_invoice" in text
    assert "Removed: api/invoices.py::void_invoice" in text
    assert "Syntax broken: api/report.py" in text
    assert "format_money" not in text  # moved from legacy.py to money.py
    assert "[high]" in text


def test_run_outside_a_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["run", "--from", "HEAD"])

    assert result.exit_code == 1
