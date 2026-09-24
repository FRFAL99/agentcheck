"""A finding: one thing in a turn that deserves the developer's attention."""

from __future__ import annotations

from dataclasses import asdict, dataclass

SEVERITIES = ("high", "medium", "low")


@dataclass(frozen=True)
class Finding:
    kind: str  # e.g. "signature_changed", "removed", "syntax_broken"
    severity: str  # one of SEVERITIES
    file: str
    message: str  # one line, readable after Claude Code's "Stop says: " prefix
    symbol: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
