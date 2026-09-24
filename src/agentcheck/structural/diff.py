"""Before/after comparison of public symbols (plan v2, decisions 3 and 4).

Signals: a public signature changed, a public symbol removed, a file that no longer parses. A
symbol that disappears from one file and appears with the same signature in another file of the
same turn was moved, not removed.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import PurePosixPath

from agentcheck.findings import Finding
from agentcheck.structural import python, typescript
from agentcheck.structural.model import Parsed, Symbol

_SIG_CHARS = 60


def language(path: str) -> str | None:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in (".py", ".pyi"):
        return "python"
    if suffix in typescript.TS_EXTENSIONS:
        return "typescript"
    if suffix in typescript.TSX_EXTENSIONS:
        return "tsx"
    return None


@lru_cache(maxsize=512)  # symbols and imports both parse the same files
def parse(path: str, source: bytes) -> Parsed:
    lang = language(path)
    if lang == "python":
        return python.extract(source)
    return typescript.extract(source, tsx=lang == "tsx")


_DATA_DIRS = ("fixtures", "testdata", "__fixtures__", "__snapshots__")


def is_data_path(path: str) -> bool:
    """Sample code kept as data, often broken on purpose: no structural signal applies.

    Found by running agentcheck on itself: its own test fixtures gave six "syntax broken".
    """
    return any(part in _DATA_DIRS for part in PurePosixPath(path).parts[:-1])


def _is_private_module(path: str) -> bool:
    p = PurePosixPath(path)
    return language(path) == "python" and p.stem.startswith("_") and p.stem != "__init__"


def _short_pair(old: str | None, new: str | None) -> tuple[str, str]:
    """Both signatures cut to fit, around where they start to differ.

    Cutting both at the start hides the change when it's at the end: two long signatures differing
    in their last parameter would print as the same prefix.
    """
    old, new = old or "", new or ""
    if max(len(old), len(new)) <= _SIG_CHARS:
        return old, new
    first_diff = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
    start = max(0, first_diff - 15)

    def cut(sig: str) -> str:
        piece = sig[start : start + _SIG_CHARS]
        return ("…" if start > 0 else "") + piece + ("…" if start + _SIG_CHARS < len(sig) else "")

    return cut(old), cut(new)


def analyze(
    changes: list[tuple[str, str]] | list[list[str]],
    before: dict[str, bytes | None],
    after: dict[str, bytes | None],
    is_test_path: Callable[[str], bool],
) -> list[Finding]:
    findings: list[Finding] = []
    removed: list[tuple[str, Symbol]] = []
    added: dict[str, list[tuple[str, Symbol]]] = {}

    for _status, path in changes:
        if language(path) is None or is_data_path(path):
            continue
        old_src, new_src = before.get(path), after.get(path)
        old = parse(path, old_src) if old_src is not None else None
        new = parse(path, new_src) if new_src is not None else None

        if new is not None and not new.ok:
            # Broken now and fine (or absent) before: the agent broke it. Broken before too: not news.
            if old is None or old.ok:
                findings.append(
                    Finding("syntax_broken", "high", path, f"Syntax broken: {path} no longer parses (line {new.error_line})")
                )
            continue  # a half-parsed tree would report every function as removed
        if old is not None and not old.ok:
            continue  # nothing reliable to compare against
        if is_test_path(path) or _is_private_module(path):
            continue

        old_public = old.public if old else {}
        new_public = new.public if new else {}
        for name, sym in old_public.items():
            if name not in new_public:
                removed.append((path, sym))
            elif sym.signature is not None and new_public[name].signature != sym.signature:
                was, now = _short_pair(sym.signature, new_public[name].signature)
                findings.append(
                    Finding(
                        "signature_changed",
                        "high",
                        path,
                        f"Signature changed: {path}::{name} now {now}, was {was}",
                        name,
                    )
                )
        for name, sym in new_public.items():
            if name not in old_public:
                added.setdefault(name, []).append((path, sym))

    removed_names = {(path, sym.name) for path, sym in removed if sym.kind == "class"}
    for path, sym in removed:
        # A removed class is one finding, not one per method.
        owner = sym.name.split(".")[0]
        if sym.kind == "method" and (path, owner) in removed_names:
            continue
        # Same name, same signature, another file of this turn: moved.
        if any(p != path and s.signature == sym.signature for p, s in added.get(sym.name, [])):
            continue
        gone = "file deleted" if after.get(path) is None else "no longer defined"
        findings.append(Finding("removed", "high", path, f"Removed: {path}::{sym.name} ({gone})", sym.name))
    return findings
