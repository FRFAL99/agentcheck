"""The risk of a turn: a sum of weights, explainable by listing it (plan v2, decision 6)."""

from __future__ import annotations

from agentcheck.findings import Finding

WEIGHTS = {"high": 3, "medium": 2, "low": 1}


def score(findings: list[Finding]) -> int:
    return sum(WEIGHTS.get(f.severity, 0) for f in findings)


def level(findings: list[Finding]) -> str | None:
    """None with no findings; then low under 3, medium 3-5, high 6 or more.

    One high signal is medium, two are high.
    """
    if not findings:
        return None
    total = score(findings)
    if total >= 6:
        return "high"
    if total >= 3:
        return "medium"
    return "low"
