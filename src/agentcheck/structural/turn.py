"""All the deterministic signals of one turn, between two trees.

Each family of signals runs on its own: an exception drops that family and is returned in `errors`,
the others still produce their findings (plan v2, Step 7's point not to forget).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from agentcheck import gitstate
from agentcheck.config import Config
from agentcheck.findings import Finding
from agentcheck.structural import deps, diff, files, imports
from agentcheck.structural.globs import matches


@dataclass
class TurnAnalysis:
    changes: list[tuple[str, str]]
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _existence(repo: Path, tree: str):
    """`exists(path)` over the after-tree, falling back to the working tree for ignored files.

    A generated, gitignored module (`_version.py` from setuptools-scm) isn't in any snapshot but is
    importable: without the fallback it would be "not found".
    """
    listed = set(gitstate.list_files(repo, tree))
    dirs = {f"{parent}/" for f in listed for parent in list(PurePosixPath(f).parents)[:-1]}

    def exists(path: str) -> bool:
        if path in listed or path in dirs:
            return True
        return (repo / path.rstrip("/")).exists()

    return exists


def analyze_turn(repo: Path, old_tree: str, new_tree: str, config: Config) -> TurnAnalysis:
    all_changes = gitstate.diff(repo, old_tree, new_tree)
    result = TurnAnalysis(all_changes)
    # Fixture directories hold sample files kept as data (`.env.example`, broken code on purpose):
    # no signal applies to them, except that they still count as files touched.
    changes = [(s, p) for s, p in all_changes if not diff.is_data_path(p)]

    def is_test(path: str) -> bool:
        return matches(path, config.tests)

    def is_code(path: str) -> bool:
        return diff.language(path) is not None

    wanted = [p for _s, p in changes if is_code(p) or deps.is_manifest(p)]
    before = gitstate.read_blobs(repo, old_tree, wanted)
    after = gitstate.read_blobs(repo, new_tree, wanted)

    def run(name: str, signal) -> None:
        try:
            result.findings.extend(signal())
        except Exception as exc:  # one broken signal must not silence the others
            result.errors.append(f"{name}: {type(exc).__name__}: {exc}")

    run("symbols", lambda: diff.analyze(changes, before, after, is_test))
    run("sensitive", lambda: files.sensitive(changes, config.sensitive))
    run("tests", lambda: files.tests_removed_or_disabled(changes, before, after, is_test, is_code))
    run("no_tests", lambda: files.code_without_tests(changes, is_code, is_test))
    run("dependencies", lambda: deps.new_dependencies(changes, before, after))

    def unresolved():
        code = [p for _s, p in changes if is_code(p)]
        parsed_before = {p: diff.parse(p, before[p]) if before.get(p) is not None else None for p in code}
        parsed_after = {p: diff.parse(p, after[p]) if after.get(p) is not None else None for p in code}
        return imports.unresolved_imports(changes, parsed_before, parsed_after, _existence(repo, new_tree))

    run("imports", unresolved)
    run("many_files", lambda: files.many_files(all_changes, config.many_files_threshold))
    return result
