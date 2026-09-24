"""Step 7: the risk score and the report text (plan v2, decisions 6 and 7)."""

import pytest

from agentcheck import report, risk
from agentcheck.findings import Finding


def f(severity: str, message: str = "x", file: str = "a.py") -> Finding:
    return Finding("kind", severity, file, message)


@pytest.mark.parametrize(
    "severities, expected",
    [
        ([], None),
        (["low"], "low"),
        (["medium"], "low"),
        (["low", "low", "low"], "medium"),
        (["high"], "medium"),  # one high signal is medium
        (["high", "medium"], "medium"),
        (["high", "high"], "high"),  # two are high
        (["medium", "medium", "medium"], "high"),
    ],
)
def test_risk_levels(severities, expected):
    assert risk.level([f(s) for s in severities]) == expected


def test_score_is_the_sum_of_the_weights():
    assert risk.score([f("high"), f("medium"), f("low")]) == 6


def test_nothing_changed_nothing_said():
    assert report.render(3, [], files_changed=0) is None


def test_files_changed_and_nothing_found_is_one_line():
    assert report.render(3, [], files_changed=1) == "agentcheck · turn 3 · all good (1 file)"
    assert report.render(3, [], files_changed=4) == "agentcheck · turn 3 · all good (4 files)"


def test_report_orders_by_severity_then_file():
    findings = [
        f("low", "Many files touched: 20 (threshold 15)", ""),
        f("medium", "New dependency: x in pyproject.toml", "pyproject.toml"),
        f("high", "Removed: b.py::g (no longer defined)", "b.py"),
        f("high", "Signature changed: a.py::f now (a, b), was (a)", "a.py"),
    ]

    assert report.render(4, findings, files_changed=20).split("\n") == [
        "agentcheck · turn 4 · risk HIGH",
        "! Signature changed: a.py::f now (a, b), was (a)",
        "! Removed: b.py::g (no longer defined)",
        "! New dependency: x in pyproject.toml",
        "! Many files touched: 20 (threshold 15)",
    ]


def test_report_fits_in_max_lines():
    findings = [f("high", f"finding {i}", f"f{i}.py") for i in range(10)]

    lines = report.render(1, findings, files_changed=10, max_lines=5).split("\n")

    assert len(lines) == 5
    assert lines[0] == "agentcheck · turn 1 · risk HIGH"
    assert lines[1:4] == ["! finding 0", "! finding 1", "! finding 2"]
    assert lines[4] == "… and 7 more"


def test_exactly_max_lines_needs_no_ellipsis():
    findings = [f("high", f"finding {i}", f"f{i}.py") for i in range(4)]

    lines = report.render(1, findings, files_changed=4, max_lines=5).split("\n")

    assert len(lines) == 5 and not lines[-1].startswith("…")
