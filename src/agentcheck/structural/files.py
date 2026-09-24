"""File-level signals: sensitive paths, many files, code without tests, tests removed or disabled."""

from __future__ import annotations

import re
from collections.abc import Callable

from agentcheck.findings import Finding
from agentcheck.structural.globs import matches

_STATUS = {"A": "added", "M": "modified", "D": "deleted", "T": "type changed"}

# Counted line by line, anchored after indentation: a commented-out `# def test_x(` or
# `// it.skip(` doesn't count, on purpose.
_PY_TEST = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+test\w*[ \t]*\(", re.M)
_PY_DISABLED = re.compile(
    r"^[ \t]*(?:@pytest\.mark\.(?:skip|skipif|xfail)\b|@unittest\.skip\w*\b|pytest\.skip\(|self\.skipTest\()",
    re.M,
)
# `it.only(`, `xit(`, `test.skip(` are still tests: focusing one is not removing the others.
_JS_TEST = re.compile(r"^[ \t]*[xf]?(?:it|test)(?:\.(?:skip|only|todo|concurrent))*[ \t]*\(", re.M)
_JS_DISABLED = re.compile(
    r"^[ \t]*(?:(?:it|test|describe)\.(?:skip|only|todo)\b|x(?:it|test|describe)[ \t]*\(|f(?:it|describe)[ \t]*\()",
    re.M,
)


def sensitive(changes: list[tuple[str, str]], patterns: list[str]) -> list[Finding]:
    return [
        Finding("sensitive_file", "high", path, f"Sensitive file touched: {path} ({_STATUS.get(status, status)})")
        for status, path in changes
        if matches(path, patterns)
    ]


def many_files(changes: list[tuple[str, str]], threshold: int) -> list[Finding]:
    if len(changes) <= threshold:
        return []
    return [Finding("many_files", "low", "", f"Many files touched: {len(changes)} (threshold {threshold})")]


def code_without_tests(
    changes: list[tuple[str, str]],
    is_code: Callable[[str], bool],
    is_test: Callable[[str], bool],
) -> list[Finding]:
    """One finding when code was added or modified and no test file changed in the same turn."""
    if any(is_test(path) for _status, path in changes):
        return []
    code = [path for status, path in changes if status in ("A", "M") and is_code(path) and not is_test(path)]
    if not code:
        return []
    more = f" and {len(code) - 1} more" if len(code) > 1 else ""
    return [Finding("no_tests", "medium", code[0], f"Code changed, no tests touched: {code[0]}{more}")]


def _markers(path: str, source: bytes) -> tuple[int, int]:
    """(test count, disabled/focused marker count) for a test file."""
    text = source.decode("utf-8", errors="replace")
    if path.endswith((".py", ".pyi")):
        return len(_PY_TEST.findall(text)), len(_PY_DISABLED.findall(text))
    return len(_JS_TEST.findall(text)), len(_JS_DISABLED.findall(text))


def tests_removed_or_disabled(
    changes: list[tuple[str, str]],
    before: dict[str, bytes | None],
    after: dict[str, bytes | None],
    is_test: Callable[[str], bool],
    is_code: Callable[[str], bool],
) -> list[Finding]:
    findings = []
    for status, path in changes:
        if not (is_test(path) and is_code(path)):
            continue
        old, new = before.get(path), after.get(path)
        if old is not None and new is None:
            findings.append(Finding("tests_removed", "high", path, f"Test file deleted: {path}"))
            continue
        old_tests, old_disabled = _markers(path, old) if old is not None else (0, 0)
        new_tests, new_disabled = _markers(path, new) if new is not None else (0, 0)
        if new_tests < old_tests:
            findings.append(
                Finding("tests_removed", "high", path, f"Tests removed: {path} ({old_tests} -> {new_tests})")
            )
        if new_disabled > old_disabled:
            added = new_disabled - old_disabled
            findings.append(
                Finding("tests_disabled", "high", path, f"Tests disabled or focused: {path} (+{added} skip/xfail/only)")
            )
    return findings
