import hashlib
import json
from pathlib import Path

from agentcheck import gitstate, hooks

from conftest import FIXTURES, git
from test_hooks import errors, hook_input, ready  # noqa: F401 — `ready` is a fixture

FINAL = "Ho aggiunto i test per parse_invoice — tutto verde ✓"


def start(repo: Path) -> None:
    hooks.run_hook("SessionStart", hook_input("session-start-startup", repo))


def stop(repo: Path, fixture: str = "stop", transcript: str | None = None) -> None:
    payload = json.loads(hook_input(fixture, repo))
    if transcript:
        payload["transcript_path"] = str(FIXTURES / "transcripts" / f"{transcript}.jsonl")
    assert hooks.run_hook("Stop", json.dumps(payload, ensure_ascii=False)) == ""


def turns(repo: Path) -> list[dict]:
    path = repo / ".agentcheck" / "sessions" / "sess-1.turns.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def notes(repo: Path) -> str:
    path = repo / ".agentcheck" / "logs" / "agentcheck.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_three_turns_edit_add_talk(ready):
    # The definition of done of Step 3, without Claude: edit, add, then a turn that only talks.
    start(ready)
    (ready / "a.txt").write_text("edited by the agent\n", encoding="utf-8")
    stop(ready)
    (ready / "new.py").write_text("x = 1\n", encoding="utf-8")
    stop(ready)
    stop(ready)

    t1, t2, t3 = turns(ready)
    assert [t["turn"] for t in (t1, t2, t3)] == [1, 2, 3]
    assert t1["changed_this_turn"] == [["M", "a.txt"]]
    assert t2["changed_this_turn"] == [["A", "new.py"]]
    assert t2["changed_since_start"] == [["M", "a.txt"], ["A", "new.py"]]
    assert t3["changed_this_turn"] == []
    assert t3["changed_since_start"] == t2["changed_since_start"]
    assert errors(ready) == ""


def test_changes_made_before_the_session_are_not_the_agents(ready):
    # `a.txt` was already dirty when the session started (see the `ready` fixture).
    start(ready)
    stop(ready)

    assert turns(ready)[0]["changed_since_start"] == []


def test_a_change_undone_disappears_from_since_start_but_not_from_the_turn(ready):
    start(ready)
    original = (ready / "a.txt").read_text(encoding="utf-8")
    (ready / "a.txt").write_text("temporary\n", encoding="utf-8")
    stop(ready)
    (ready / "a.txt").write_text(original, encoding="utf-8")
    stop(ready)

    t1, t2 = turns(ready)
    assert t2["changed_this_turn"] == [["M", "a.txt"]]
    assert t2["changed_since_start"] == []


def test_the_record_carries_what_the_agent_said(ready):
    start(ready)
    stop(ready, transcript="complete")

    record = turns(ready)[0]
    assert record["last_assistant_message"] == FINAL
    assert record["stop_hook_active"] is False
    assert record["transcript_at_stop"]["has_final_message"] is True
    assert record["head"] == git(ready, "rev-parse", "HEAD").strip()
    assert record["elapsed_ms"] >= 0


def test_an_older_claude_code_without_last_assistant_message(ready):
    start(ready)
    stop(ready, fixture="stop-2.1.23", transcript="lagging")

    record = turns(ready)[0]
    assert record["last_assistant_message"] is None
    assert record["transcript_at_stop"]["has_final_message"] is None
    assert record["transcript_at_stop"]["last_assistant_uuid"] == "a1"


def test_no_baseline_no_invented_one(ready):
    stop(ready)

    assert turns(ready) == []
    assert not (ready / ".agentcheck" / "sessions" / "sess-1.json").exists()
    assert "without a baseline" in notes(ready)
    assert errors(ready) == ""


def test_baseline_tree_gone_after_gc(ready, monkeypatch):
    start(ready)
    monkeypatch.setattr(gitstate, "tree_exists", lambda repo, tree: False)

    stop(ready)

    assert turns(ready) == []
    assert "is gone" in notes(ready)


def test_previous_turn_tree_gone_keeps_since_start(ready, monkeypatch):
    start(ready)
    # Turn 1 must change something, or its tree would be the baseline's tree.
    (ready / "a.txt").write_text("turn 1\n", encoding="utf-8")
    stop(ready)
    base_tree = json.loads((ready / ".agentcheck" / "sessions" / "sess-1.json").read_text())["tree"]
    real = gitstate.tree_exists
    monkeypatch.setattr(gitstate, "tree_exists", lambda repo, tree: tree == base_tree and real(repo, tree))
    (ready / "b.txt").write_text("b\n", encoding="utf-8")

    stop(ready)

    record = turns(ready)[1]
    assert record["changed_this_turn"] is None
    assert record["changed_since_start"] == [["M", "a.txt"], ["A", "b.txt"]]
    assert "changed_this_turn unknown" in notes(ready)


def test_the_users_index_is_untouched_across_turns(ready):
    def index_hash():
        return hashlib.sha1((ready / ".git" / "index").read_bytes()).hexdigest()

    before = (index_hash(), git(ready, "status", "--porcelain"))
    start(ready)
    stop(ready)

    assert (index_hash(), git(ready, "status", "--porcelain")) == before
