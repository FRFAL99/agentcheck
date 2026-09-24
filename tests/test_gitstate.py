import hashlib
from pathlib import Path

from agentcheck import gitstate

from conftest import git


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def index_hash(repo: Path) -> str:
    return hashlib.sha1((repo / ".git" / "index").read_bytes()).hexdigest()


def files_in(repo: Path, tree: str) -> list[str]:
    return git(repo, "ls-tree", "-r", "--name-only", tree).splitlines()


def committed(repo: Path) -> Path:
    write(repo, "a.txt", "a\n")
    write(repo, ".gitignore", "ignored.log\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    return repo


def test_snapshot_leaves_the_users_git_state_alone(repo):
    committed(repo)
    write(repo, "a.txt", "changed\n")
    write(repo, "staged.txt", "s\n")
    git(repo, "add", "staged.txt")
    write(repo, "untracked.txt", "u\n")
    before = (index_hash(repo), git(repo, "status", "--porcelain"), git(repo, "for-each-ref"))

    gitstate.snapshot(repo)

    after = (index_hash(repo), git(repo, "status", "--porcelain"), git(repo, "for-each-ref"))
    assert after == before
    assert git(repo, "stash", "list") == ""


def test_snapshot_includes_untracked_and_excludes_ignored(repo):
    committed(repo)
    write(repo, "untracked.txt", "u\n")
    write(repo, "ignored.log", "x\n")
    write(repo, ".agentcheck/logs/hooks.jsonl", "{}\n")  # no .agentcheck/.gitignore: the pathspec guards

    tree = gitstate.snapshot(repo)

    assert files_in(repo, tree) == [".gitignore", "a.txt", "untracked.txt"]


def test_snapshot_leaves_no_temporary_index(repo):
    committed(repo)

    gitstate.snapshot(repo)

    assert list((repo / ".agentcheck" / "tmp").iterdir()) == []


def test_snapshot_is_stable_when_nothing_changes(repo):
    committed(repo)
    write(repo, "untracked.txt", "u\n")

    assert gitstate.snapshot(repo) == gitstate.snapshot(repo)


def test_snapshot_of_a_clean_tree_is_heads_tree(repo):
    committed(repo)

    assert gitstate.snapshot(repo) == git(repo, "rev-parse", "HEAD^{tree}").strip()


def test_unborn_branch(repo):
    # No commits, no .git/index: the snapshot starts from an empty index.
    write(repo, "first.py", "print('hi')\n")
    assert not (repo / ".git" / "index").exists()

    tree = gitstate.snapshot(repo)

    assert gitstate.head(repo) is None
    assert files_in(repo, tree) == ["first.py"]
    assert not (repo / ".git" / "index").exists()


def test_diff_between_snapshots(repo):
    committed(repo)
    before = gitstate.snapshot(repo)
    write(repo, "a.txt", "changed\n")
    write(repo, "dir with space/nuovo è.py", "x = 1\n")
    (repo / ".gitignore").unlink()

    after = gitstate.snapshot(repo)

    assert gitstate.diff(repo, before, after) == [
        ("D", ".gitignore"),
        ("M", "a.txt"),
        ("A", "dir with space/nuovo è.py"),
    ]
    assert gitstate.diff(repo, after, after) == []


def test_head_and_repo_root(repo):
    committed(repo)
    sub = repo / "src"
    sub.mkdir()

    assert gitstate.head(repo) == git(repo, "rev-parse", "HEAD").strip()
    assert gitstate.repo_root(sub).resolve() == repo.resolve()


def test_repo_root_outside_a_repo(tmp_path):
    assert gitstate.repo_root(tmp_path) is None


def test_tree_exists(repo):
    committed(repo)
    tree = gitstate.snapshot(repo)

    assert gitstate.tree_exists(repo, tree)
    assert not gitstate.tree_exists(repo, "0" * 40)


def test_read_blobs(repo):
    committed(repo)
    write(repo, "dir with space/è.py", "x = 1\n")
    (repo / "bin.dat").write_bytes(b"\x00\x01\n\xff" * 3)
    tree = gitstate.snapshot(repo)

    blobs = gitstate.read_blobs(repo, tree, ["a.txt", "dir with space/è.py", "missing.py", "bin.dat"])

    # Exactly the bytes on disk: on Windows write_text wrote "\r\n", and autocrlf is off here.
    assert blobs == {
        "a.txt": (repo / "a.txt").read_bytes(),
        "dir with space/è.py": (repo / "dir with space" / "è.py").read_bytes(),
        "missing.py": None,
        "bin.dat": b"\x00\x01\n\xff" * 3,
    }
    assert gitstate.read_blobs(repo, tree, []) == {}
