"""Imports added in this turn that point inside the repo and don't resolve (plan v2, decision 5).

Third-party imports are out of scope: whether `import requests` resolves depends on an environment
agentcheck doesn't see. A Python absolute import counts as in-repo only when its top-level package
is a module or directory at the repo root or under `src/`.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from pathlib import PurePosixPath

from agentcheck.findings import Finding
from agentcheck.structural.model import Parsed

_PY_ROOTS = ("", "src/")
_TS_EXTENSIONS = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".json")
# TypeScript ESM imports `./x.js` for a source file `x.ts`.
_JS_TO_TS = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}

Exists = Callable[[str], bool]


def _py_module(base: str, exists: Exists) -> bool:
    return exists(f"{base}.py") or exists(f"{base}.pyi") or exists(base + "/")


def _python_resolves(importer: str, spec: str, exists: Exists) -> bool | None:
    """True/False for an in-repo import, None when it isn't in-repo (third-party, stdlib)."""
    if spec.startswith("."):
        level = len(spec) - len(spec.lstrip("."))
        rest = spec[level:]
        package = list(PurePosixPath(importer).parts[:-1])
        if level - 1 > len(package):
            return False  # climbs above the repo root
        package = package[: len(package) - (level - 1)]
        if not rest:
            return True  # `from . import x`: the package itself
        return _py_module("/".join(package + rest.split(".")), exists)
    parts = spec.split(".")
    for root in _PY_ROOTS:
        if _py_module(root + parts[0], exists):
            return _py_module(root + "/".join(parts), exists)
    return None


def _ts_resolves(importer: str, spec: str, exists: Exists) -> bool | None:
    if not spec.startswith(("./", "../")) and spec not in (".", ".."):
        return None  # a package, or an alias like "@/x" configured in tsconfig
    target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
    if target.startswith(".."):
        return None  # outside the repo
    candidates = [target] + [target + ext for ext in _TS_EXTENSIONS]
    candidates += [f"{target}/index{ext}" for ext in _TS_EXTENSIONS]
    stem, ext = posixpath.splitext(target)
    candidates += [stem + ts_ext for ts_ext in _JS_TO_TS.get(ext, ())]
    return any(exists(c) for c in candidates if not c.endswith("/"))


def unresolved_imports(
    changes: list[tuple[str, str]],
    parsed_before: dict[str, Parsed | None],
    parsed_after: dict[str, Parsed | None],
    exists: Exists,
) -> list[Finding]:
    """`exists(path)` answers for a file (`a/b.py`) or, with a trailing slash, a directory (`a/b/`)."""
    findings = []
    for _status, path in changes:
        new = parsed_after.get(path)
        if new is None or not new.ok:
            continue
        old = parsed_before.get(path)
        previous = set(old.imports) if old is not None and old.ok else set()
        resolve = _python_resolves if path.endswith((".py", ".pyi")) else _ts_resolves
        for spec in dict.fromkeys(new.imports):  # ordered, without duplicates
            if spec in previous:
                continue
            if resolve(path, spec, exists) is False:
                findings.append(Finding("import_not_found", "high", path, f"Import not found: {path} imports {spec}"))
    return findings
