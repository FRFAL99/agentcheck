"""The text the developer sees at the end of a turn (plan v2, decision 7).

Three cases: findings → a report of at most `max_lines` lines; files changed and no findings → one
line; nothing changed → nothing. Claude Code prefixes every line with "Stop says: ", so lines are
short and start with a plain marker, not with alignment.
"""

from __future__ import annotations

from agentcheck import risk
from agentcheck.findings import SEVERITIES, Finding


def _order(finding: Finding) -> tuple[int, str]:
    return SEVERITIES.index(finding.severity) if finding.severity in SEVERITIES else len(SEVERITIES), finding.file


def render(turn: int, findings: list[Finding], files_changed: int, max_lines: int = 8) -> str | None:
    if not findings:
        if files_changed == 0:
            return None
        plural = "file" if files_changed == 1 else "files"
        return f"agentcheck · turn {turn} · all good ({files_changed} {plural})"

    header = f"agentcheck · turn {turn} · risk {risk.level(findings).upper()}"
    ordered = sorted(findings, key=_order)
    body_lines = max(1, max_lines - 1)
    if len(ordered) > body_lines:
        shown = ordered[: body_lines - 1]
        rest = len(ordered) - len(shown)
        lines = [f"! {f.message}" for f in shown] + [f"… and {rest} more"]
    else:
        lines = [f"! {f.message}" for f in ordered]
    return "\n".join([header, *lines])
