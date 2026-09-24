from agentcheck.collector import transcript_state

from conftest import FIXTURES

FINAL = "Ho aggiunto i test per parse_invoice — tutto verde ✓"
TRANSCRIPTS = FIXTURES / "transcripts"


def test_transcript_with_the_final_message():
    state = transcript_state(str(TRANSCRIPTS / "complete.jsonl"), FINAL)

    assert state["lines"] == 10
    assert state["last_assistant_uuid"] == "a3"
    assert state["last_assistant_text"] == FINAL
    assert state["has_final_message"] is True


def test_lagging_transcript_is_detected():
    state = transcript_state(str(TRANSCRIPTS / "lagging.jsonl"), FINAL)

    # The half-written last line is counted but not parsed; the subagent's text is skipped.
    assert state["lines"] == 10
    assert state["last_assistant_uuid"] == "a1"
    assert state["has_final_message"] is False


def test_whitespace_differences_are_not_lag():
    state = transcript_state(str(TRANSCRIPTS / "complete.jsonl"), f"\n{FINAL}  \n")

    assert state["has_final_message"] is True


def test_without_a_final_message_there_is_nothing_to_compare():
    state = transcript_state(str(TRANSCRIPTS / "complete.jsonl"))

    assert state["has_final_message"] is None
    assert state["last_assistant_text"] == FINAL


def test_long_text_is_truncated_in_the_record(tmp_path):
    path = tmp_path / "t.jsonl"
    long = "x" * 500
    path.write_text(
        '{"type": "assistant", "uuid": "a", "message": {"content": [{"type": "text", "text": "%s"}]}}\n' % long,
        encoding="utf-8",
    )

    state = transcript_state(str(path), long)

    assert len(state["last_assistant_text"]) == 200
    assert state["last_assistant_chars"] == 500
    assert state["has_final_message"] is True


def test_missing_transcript(tmp_path):
    assert transcript_state(None) is None
    assert transcript_state(str(tmp_path / "nope.jsonl")) is None
