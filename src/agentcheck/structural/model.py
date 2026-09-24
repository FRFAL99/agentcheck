"""What an extractor returns for one version of one file."""

from __future__ import annotations

from dataclasses import dataclass, field

from tree_sitter import Node


@dataclass(frozen=True)
class Symbol:
    name: str  # qualified within the file: "create_invoice", "Invoice.total"
    kind: str  # "function", "class", "method"
    signature: str | None  # parameters + return annotation, whitespace collapsed; None for classes
    line: int  # 1-based


@dataclass
class Parsed:
    ok: bool  # False when the tree has syntax errors
    error_line: int | None = None  # first error, 1-based
    public: dict[str, Symbol] = field(default_factory=dict)


def collapse(text: bytes | str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return " ".join(text.split())


def first_error_line(node: Node) -> int | None:
    """Line of the first ERROR or MISSING node, depth first."""
    if node.type == "ERROR" or node.is_missing:
        return node.start_point.row + 1
    if not node.has_error:
        return None
    for child in node.children:
        line = first_error_line(child)
        if line is not None:
            return line
    return node.start_point.row + 1
