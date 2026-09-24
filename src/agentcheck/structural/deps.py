"""New dependencies: package names added to a manifest, not lines.

Reordering `pyproject.toml` or bumping a version adds lines without adding a package, so manifests
are parsed and compared as sets of names. A manifest that doesn't parse gives no finding: a broken
`pyproject.toml` isn't "a new dependency".
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import PurePosixPath

from agentcheck.findings import Finding

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_NPM_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def is_manifest(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in ("pyproject.toml", "package.json") or (name.startswith("requirements") and name.endswith(".txt"))


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()  # PEP 503


def _requirement(spec: str) -> str | None:
    spec = spec.strip()
    if not spec or spec.startswith(("#", "-", ".", "/")) or "://" in spec.split("@")[0]:
        return None
    match = _REQ_NAME.match(spec)
    return _normalize(match.group(1)) if match else None


def _pyproject(data: dict) -> set[str]:
    specs: list[str] = []
    project = data.get("project", {})
    specs += project.get("dependencies", []) or []
    for group in (project.get("optional-dependencies") or {}).values():
        specs += group or []
    for group in (data.get("dependency-groups") or {}).values():
        specs += [s for s in group or [] if isinstance(s, str)]  # {include-group = ...} isn't a package
    names = {n for n in (_requirement(s) for s in specs if isinstance(s, str)) if n}

    poetry = data.get("tool", {}).get("poetry", {})
    tables = [poetry.get("dependencies"), poetry.get("dev-dependencies")]
    tables += [g.get("dependencies") for g in (poetry.get("group") or {}).values() if isinstance(g, dict)]
    for table in tables:
        if isinstance(table, dict):
            names |= {_normalize(k) for k in table if k.lower() != "python"}
    return names


def names(path: str, source: bytes) -> set[str] | None:
    """Package names a manifest declares, or None if it doesn't parse."""
    text = source.decode("utf-8", errors="replace")
    name = PurePosixPath(path).name
    try:
        if name == "pyproject.toml":
            return _pyproject(tomllib.loads(text))
        if name == "package.json":
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            return {k for section in _NPM_SECTIONS if isinstance(data.get(section), dict) for k in data[section]}
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, AttributeError, TypeError):
        return None
    return {n for n in (_requirement(line) for line in text.splitlines()) if n}


def new_dependencies(
    changes: list[tuple[str, str]],
    before: dict[str, bytes | None],
    after: dict[str, bytes | None],
) -> list[Finding]:
    findings = []
    for _status, path in changes:
        if not is_manifest(path) or after.get(path) is None:
            continue
        new = names(path, after[path])
        old = names(path, before[path]) if before.get(path) is not None else set()
        if new is None or old is None:
            continue
        added = sorted(new - old)
        if added:
            shown = ", ".join(added[:3]) + (f" and {len(added) - 3} more" if len(added) > 3 else "")
            findings.append(Finding("new_dependency", "medium", path, f"New dependency: {shown} in {path}"))
    return findings
