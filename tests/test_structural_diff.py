"""Step 5: signature changed, removed, moved, syntax broken — on before/after fixture pairs."""

from pathlib import Path

import pytest

from agentcheck.structural.diff import analyze

from conftest import FIXTURES

CASES = FIXTURES / "structural"


def load(case: str):
    """(changes, before, after) for a fixture case, as `analyze` receives them from git."""
    sides = {}
    for side in ("before", "after"):
        root = CASES / case / side
        sides[side] = (
            {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            if root.exists()
            else {}
        )
    before, after = sides["before"], sides["after"]
    changes = []
    for path in sorted(set(before) | set(after)):
        if path not in before:
            changes.append(("A", path))
        elif path not in after:
            changes.append(("D", path))
        elif before[path] != after[path]:
            changes.append(("M", path))
    return changes, before, after


def findings_of(case: str) -> list[tuple[str, str | None]]:
    changes, before, after = load(case)
    return sorted((f.kind, f.symbol or f.file) for f in analyze(changes, before, after))


EXPECTED = [
    # ---- python
    ("py-signature-changed", [("signature_changed", "create_invoice")]),
    ("py-return-type-changed", [("signature_changed", "total")]),
    ("py-body-only", []),
    ("py-removed", [("removed", "gone")]),
    ("py-file-deleted", [("removed", "gone")]),
    ("py-moved", []),
    ("py-moved-and-changed", [("removed", "helper")]),
    ("py-private-ignored", []),
    ("py-private-module", []),
    ("py-test-file-ignored", []),
    ("py-all-literal", []),
    ("py-all-dynamic", [("removed", "b")]),
    ("py-methods", [("removed", "Invoice.id"), ("signature_changed", "Invoice.__init__")]),
    ("py-class-removed", [("removed", "Invoice")]),
    ("py-decorated-and-nested", [("signature_changed", "cached")]),
    ("py-syntax-broken", [("syntax_broken", "lib.py")]),
    ("py-new-file-broken", [("syntax_broken", "lib.py")]),
    ("py-broken-before-and-after", []),
    ("py-fixture-data-ignored", []),
    # ---- typescript / javascript
    ("ts-signature-changed", [("signature_changed", "createInvoice")]),
    ("ts-arrow-changed", [("signature_changed", "total")]),
    ("ts-not-exported-ignored", []),
    ("ts-overload-added", [("signature_changed", "over")]),
    ("ts-class-methods", [("signature_changed", "Api.get")]),
    ("ts-export-clause", [("removed", "renamed"), ("signature_changed", "a")]),
    ("ts-default-class", [("signature_changed", "default.get")]),
    ("ts-syntax-broken", [("syntax_broken", "src/f.ts")]),
    ("js-jsx-in-js", []),
    ("ts-test-file-ignored", []),
]


@pytest.mark.parametrize("case, expected", EXPECTED)
def test_case(case, expected):
    assert findings_of(case) == expected


def test_every_fixture_case_is_tested():
    assert {p.name for p in CASES.iterdir() if p.is_dir()} == {case for case, _ in EXPECTED}


def test_messages_read_well():
    changes, before, after = load("py-signature-changed")
    (finding,) = analyze(changes, before, after)

    assert finding.severity == "high"
    assert finding.message == (
        "Signature changed: api/invoices.py::create_invoice now "
        "(customer: str, amount: float, currency: str) -> dict, was (customer: str, amount: float) -> dict"
    )


def test_syntax_message_has_the_line():
    changes, before, after = load("py-syntax-broken")
    (finding,) = analyze(changes, before, after)

    assert finding.message == "Syntax broken: lib.py no longer parses (line 1)"


def test_removed_says_whether_the_file_is_gone():
    changes, before, after = load("py-file-deleted")
    (finding,) = analyze(changes, before, after)

    assert finding.message == "Removed: lib.py::gone (file deleted)"
