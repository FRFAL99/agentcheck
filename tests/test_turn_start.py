"""Step 4: a turn starts when the prompt is submitted (plan v2, decision 1)."""

import json
from pathlib import Path

from agentcheck import hooks

from test_hooks import errors, hook_input, ready  # noqa: F401 — `ready` is a fixture
from test_stop import notes, start, turns


def prompt(repo: Path, prompt_id: str | None = "p-1", fixture: str = "user-prompt-submit") -> None:
    payload = json.loads(hook_input(fixture, repo))
    if "prompt_id" in payload:
        payload["prompt_id"] = prompt_id
    assert hooks.run_hook("UserPromptSubmit", json.dumps(payload, ensure_ascii=False)) == ""


def stop(repo: Path, prompt_id: str | None = "p-1", fixture: str = "stop") -> None:
    payload = json.loads(hook_input(fixture, repo))
    if prompt_id is not None:
        payload["prompt_id"] = prompt_id
    assert hooks.run_hook("Stop", json.dumps(payload, ensure_ascii=False)) == ""


def write(repo: Path, name: str, text: str = "x\n") -> None:
    (repo / name).write_text(text, encoding="utf-8")


def turn_start_file(repo: Path) -> Path:
    return repo / ".agentcheck" / "sessions" / "sess-1.turn-start.json"


def test_the_developers_edits_between_turns_are_not_the_agents(ready):
    # The definition of done of Step 4, without Claude.
    start(ready)
    prompt(ready, "p-1")
    write(ready, "agent1.py")
    stop(ready, "p-1")
    write(ready, "by_hand.md")  # the developer, between turns
    prompt(ready, "p-2")
    write(ready, "agent2.py")
    stop(ready, "p-2")

    t1, t2 = turns(ready)
    assert t1["changed_this_turn"] == [["A", "agent1.py"]]
    assert t2["changed_this_turn"] == [["A", "agent2.py"]]
    assert t2["changed_between_turns"] == [["A", "by_hand.md"]]
    assert t2["turn_start"] == "prompt"
    assert t2["previous_turn_interrupted"] is False
    assert [c[1] for c in t2["changed_since_start"]] == ["agent1.py", "agent2.py", "by_hand.md"]
    assert errors(ready) == ""


def test_the_turn_start_is_consumed_by_stop(ready):
    start(ready)
    prompt(ready)
    assert turn_start_file(ready).exists()

    stop(ready)

    assert not turn_start_file(ready).exists()


def test_the_prompt_is_kept_short(ready):
    start(ready)
    prompt(ready)
    stop(ready)

    assert turns(ready)[0]["prompt_preview"].startswith("Aggiungi un parametro `currency`")
    assert turns(ready)[0]["prompt_id"] == "p-1"


def test_an_older_claude_code_without_prompt_id(ready):
    start(ready)
    prompt(ready, fixture="user-prompt-submit-2.1.23")
    write(ready, "agent.py")
    stop(ready, prompt_id=None, fixture="stop-2.1.23")

    record = turns(ready)[0]
    assert record["turn_start"] == "prompt"
    assert record["changed_this_turn"] == [["A", "agent.py"]]


def test_without_a_turn_start_it_falls_back_to_the_previous_stop(ready):
    # A repo initialised before Step 4 has no UserPromptSubmit hook.
    start(ready)
    write(ready, "a.py")
    stop(ready)

    record = turns(ready)[0]
    assert record["turn_start"] == "previous_stop"
    assert record["changed_this_turn"] == [["A", "a.py"]]
    assert record["changed_between_turns"] is None


def test_an_interrupted_turn_is_flagged(ready):
    start(ready)
    prompt(ready, "p-1")
    write(ready, "half_done.py")  # the agent, then the user presses Esc: no Stop
    prompt(ready, "p-2")
    write(ready, "agent.py")
    stop(ready, "p-2")

    record = turns(ready)[0]
    assert record["previous_turn_interrupted"] is True
    # The interrupted turn's edit is outside this turn, and its author is not asserted.
    assert record["changed_this_turn"] == [["A", "agent.py"]]
    assert record["changed_between_turns"] == [["A", "half_done.py"]]


def test_a_turn_start_of_another_prompt_is_not_used(ready):
    start(ready)
    prompt(ready, "p-1")
    write(ready, "a.py")

    stop(ready, "p-other")

    record = turns(ready)[0]
    assert record["turn_start"] == "previous_stop"
    assert "does not match" in notes(ready)
    assert not turn_start_file(ready).exists()


def test_no_baseline_no_turn_start(ready):
    prompt(ready)

    assert not turn_start_file(ready).exists()
    assert "UserPromptSubmit without a baseline" in notes(ready)
