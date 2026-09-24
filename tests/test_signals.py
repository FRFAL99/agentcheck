"""Step 6: globs, config, file-level signals, dependencies and in-repo imports."""

import shutil

import pytest

from agentcheck.config import Config, ConfigError, load_config
from agentcheck.findings import Finding
from agentcheck.structural import deps, files, imports
from agentcheck.structural.diff import parse
from agentcheck.structural.globs import matches
from agentcheck.structural.turn import analyze_turn
from agentcheck import gitstate

from conftest import FIXTURES, git

TESTS = Config().tests


def is_test(path):
    return matches(path, TESTS)


def is_code(path):
    return path.endswith((".py", ".ts", ".tsx", ".js"))


def fx(rel: str) -> bytes:
    return (FIXTURES / rel).read_bytes()


def kinds(findings: list[Finding]) -> list[str]:
    return [f.kind for f in findings]


# ---------------------------------------------------------------- globs


@pytest.mark.parametrize(
    "path, pattern, expected",
    [
        (".env", ".env*", True),
        ("config/.env.local", ".env*", True),  # no slash: the name, at any depth
        ("src/environment.py", ".env*", False),
        ("migrations/0001.py", "**/migrations/**", True),
        ("app/billing/migrations/0001.py", "**/migrations/**", True),
        ("tests/unit/test_a.py", "tests/**", True),
        ("pkg/tests/test_a.py", "tests/**", False),  # with a slash: anchored at the root
        ("pkg/tests/test_a.py", "**/tests/**", True),
        ("src/a.test.ts", "**/*.test.*", True),
        ("src/a.ts", "**/*.test.*", False),
        ("a/b/c.pem", "*.pem", True),
        ("x.pem.bak", "*.pem", False),
        ("src/a/b.py", "src/*.py", False),  # `*` doesn't cross `/`
    ],
)
def test_globs(path, pattern, expected):
    assert matches(path, [pattern]) is expected


# ---------------------------------------------------------------- config


def test_config_defaults_without_a_file(tmp_path):
    assert load_config(tmp_path) == Config()


def test_config_overrides_and_ignores_unknown_tables(tmp_path):
    (tmp_path / ".agentcheck").mkdir()
    shutil.copy(FIXTURES / "config" / "valid.toml", tmp_path / ".agentcheck" / "config.toml")

    config = load_config(tmp_path)

    assert config.max_lines == 5
    assert config.many_files_threshold == 30
    assert config.sensitive == ["secrets/**", "*.pem"]
    assert config.tests == Config().tests


@pytest.mark.parametrize("name, message", [("bad-type.toml", "must be a list of strings"), ("bad-toml.toml", "not valid TOML")])
def test_config_errors(tmp_path, name, message):
    (tmp_path / ".agentcheck").mkdir()
    shutil.copy(FIXTURES / "config" / name, tmp_path / ".agentcheck" / "config.toml")

    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path)


# ---------------------------------------------------------------- file-level signals


def test_sensitive_files():
    changes = [("M", ".env.example"), ("A", "app/migrations/0002.py"), ("M", ".github/workflows/ci.yml"), ("M", "src/a.py")]

    found = files.sensitive(changes, Config().sensitive)

    assert [f.file for f in found] == [".env.example", "app/migrations/0002.py", ".github/workflows/ci.yml"]
    assert found[0].message == "Sensitive file touched: .env.example (modified)"


def test_many_files():
    changes = [("M", f"f{i}.py") for i in range(16)]

    assert files.many_files(changes, 15)[0].severity == "low"
    assert files.many_files(changes[:15], 15) == []


def test_code_without_tests():
    found = files.code_without_tests([("M", "src/a.py"), ("A", "src/b.ts"), ("M", "README.md")], is_code, is_test)

    assert [f.message for f in found] == ["Code changed, no tests touched: src/a.py and 1 more"]
    assert files.code_without_tests([("M", "src/a.py"), ("M", "tests/test_a.py")], is_code, is_test) == []
    assert files.code_without_tests([("D", "src/a.py")], is_code, is_test) == []  # deleting isn't writing
    assert files.code_without_tests([("M", "README.md")], is_code, is_test) == []


@pytest.mark.parametrize(
    "before, after, expected",
    [
        ("test_invoice.before.py", "test_invoice.removed.py", ["Tests removed: tests/test_x.py (3 -> 1)"]),
        ("test_invoice.before.py", "test_invoice.skipped.py", ["Tests disabled or focused: tests/test_x.py (+2 skip/xfail/only)"]),
        ("test_invoice.before.py", "test_invoice.before.py", []),
    ],
)
def test_python_tests_removed_or_disabled(before, after, expected):
    path = "tests/test_x.py"
    found = files.tests_removed_or_disabled(
        [("M", path)], {path: fx(f"testfiles/{before}")}, {path: fx(f"testfiles/{after}")}, is_test, is_code
    )
    assert [f.message for f in found] == expected


def test_ts_only_counts_and_commented_lines_dont():
    path = "src/invoice.test.ts"
    found = files.tests_removed_or_disabled(
        [("M", path)],
        {path: fx("testfiles/invoice.before.test.ts")},
        {path: fx("testfiles/invoice.only.test.ts")},
        is_test,
        is_code,
    )
    assert [f.message for f in found] == ["Tests disabled or focused: src/invoice.test.ts (+1 skip/xfail/only)"]


def test_test_file_deleted():
    path = "tests/test_x.py"
    found = files.tests_removed_or_disabled([("D", path)], {path: b"def test_a(): pass\n"}, {path: None}, is_test, is_code)

    assert [f.message for f in found] == ["Test file deleted: tests/test_x.py"]


# ---------------------------------------------------------------- dependencies


@pytest.mark.parametrize(
    "path, fixture, expected",
    [
        ("pyproject.toml", "pyproject.before.toml", {"requests", "typer", "pytest", "ruff"}),
        ("pyproject.toml", "pyproject.poetry.toml", {"requests", "pytest"}),
        ("pyproject.toml", "pyproject.broken.toml", None),
        ("requirements.txt", "requirements.txt", {"requests", "django", "my-package"}),
        ("package.json", "package.before.json", {"react", "vitest"}),
    ],
)
def test_manifest_names(path, fixture, expected):
    assert deps.names(path, fx(f"manifests/{fixture}")) == expected


def test_new_dependency_is_a_name_not_a_line():
    def run(path, old, new):
        return deps.new_dependencies([("M", path)], {path: fx(f"manifests/{old}")}, {path: fx(f"manifests/{new}")})

    assert run("pyproject.toml", "pyproject.before.toml", "pyproject.reordered.toml") == []
    added = run("pyproject.toml", "pyproject.before.toml", "pyproject.added.toml")
    assert [f.message for f in added] == ["New dependency: hypothesis, python-dateutil in pyproject.toml"]
    npm = run("package.json", "package.before.json", "package.added.json")
    assert [f.message for f in npm] == ["New dependency: left-pad, react-dom in package.json"]
    assert run("pyproject.toml", "pyproject.before.toml", "pyproject.broken.toml") == []


def test_a_new_manifest_lists_everything_it_brings():
    path = "web/package.json"
    found = deps.new_dependencies([("A", path)], {path: None}, {path: fx("manifests/package.added.json")})

    assert found[0].message == "New dependency: left-pad, react, react-dom and 1 more in web/package.json"


# ---------------------------------------------------------------- in-repo imports


REPO_FILES = {
    "billing/__init__.py", "billing/invoices.py", "billing/dates.py", "billing/sub/__init__.py",
    "src/core/__init__.py", "src/core/money.py",
    "web/src/app.ts", "web/src/util/index.ts", "web/src/api.ts", "web/src/style.css",
}  # fmt: skip
REPO_DIRS = {"billing/", "billing/sub/", "src/", "src/core/", "web/", "web/src/", "web/src/util/"}


def exists(path):
    return path in REPO_FILES or path in REPO_DIRS


def unresolved(path: str, source: bytes, before: bytes | None = None) -> list[str]:
    found = imports.unresolved_imports(
        [("M", path)],
        {path: parse(path, before) if before is not None else None},
        {path: parse(path, source)},
        exists,
    )
    return [f.message.split(" imports ")[1] for f in found]


def test_python_imports():
    source = b"""import os
import requests
from . import dates
from .dates import parse
from .nonexistent import x
from .sub import y
from ..outside import z
from billing.dates import parse
from billing.ghost import g
import core.money
import core.nothing
def f():
    from .lazy_missing import w
"""
    assert unresolved("billing/invoices.py", source) == [
        ".nonexistent", "..outside", "billing.ghost", "core.nothing", ".lazy_missing",
    ]  # fmt: skip


def test_only_imports_added_in_this_turn():
    old = b"from .nonexistent import x\n"
    new = b"from .nonexistent import x\nfrom .also_missing import y\n"

    assert unresolved("billing/invoices.py", new, before=old) == [".also_missing"]


def test_ts_imports():
    source = b"""import React from "react";
import { a } from "./api";
import { b } from "./api.js";
import { u } from "./util";
import "./style.css";
import { g } from "./ghost";
export { z } from "../../../outside";
export { w } from "../../missing_at_root";
import { t } from "@/aliased";
"""
    # ../../ from web/src/ is the repo root: still in-repo. ../../../ is outside: not ours to judge.
    assert unresolved("web/src/app.ts", source) == ["./ghost", "../../missing_at_root"]


# ---------------------------------------------------------------- the definition of done of Step 6


def commit_and_replace(repo, case: str) -> str:
    """Commit the case's `before` tree, lay its `after` tree over the working tree, return HEAD."""
    shutil.copytree(FIXTURES / "run" / case / "before", repo, dirs_exist_ok=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "before")
    shutil.copytree(FIXTURES / "run" / case / "after", repo, dirs_exist_ok=True)
    return git(repo, "rev-parse", "HEAD").strip()


def test_step6_definition_of_done(repo):
    head = commit_and_replace(repo, "step6")

    result = analyze_turn(repo, head, gitstate.snapshot(repo), Config())

    assert result.errors == []
    assert sorted(f.message for f in result.findings) == [
        "Import not found: billing/invoices.py imports .nonexistent",
        "New dependency: python-dateutil in pyproject.toml",
        "Sensitive file touched: .env.example (modified)",
        "Tests disabled or focused: tests/test_invoices.py (+1 skip/xfail/only)",
    ]


def test_reordering_dependencies_lists_nothing(repo):
    head = commit_and_replace(repo, "step6-reorder")

    result = analyze_turn(repo, head, gitstate.snapshot(repo), Config())

    assert result.findings == [] and result.errors == []


def test_a_broken_signal_does_not_silence_the_others(repo, monkeypatch):
    head = commit_and_replace(repo, "step6")

    def boom(*args):
        raise RuntimeError("simulated")

    monkeypatch.setattr(deps, "new_dependencies", boom)
    result = analyze_turn(repo, head, gitstate.snapshot(repo), Config())

    assert result.errors == ["dependencies: RuntimeError: simulated"]
    assert len(result.findings) == 3


def test_fixture_directories_are_data_for_every_signal(repo):
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    data = repo / "tests" / "fixtures" / "case"
    data.mkdir(parents=True)
    (data / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (data / "broken.py").write_text("def f(:\n", encoding="utf-8")
    (data / "package.json").write_text('{"dependencies": {"x": "1"}}\n', encoding="utf-8")

    result = analyze_turn(repo, "HEAD", gitstate.snapshot(repo), Config())

    assert result.findings == []
