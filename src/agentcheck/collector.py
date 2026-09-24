"""What the agent said: the transcript as it is when a hook fires.

Phase 0 only takes a measurement. The transcript is written asynchronously and may lag the turn
that just ended (hooks reference), and the terminal CLI 2.1.23 doesn't send
`last_assistant_message` at all — so Phase 2 will have to know whether it can trust the file.
"""

from __future__ import annotations

import json
from pathlib import Path

PREVIEW_CHARS = 200


def _assistant_text(entry: dict) -> str | None:
    """The text of a main-thread assistant entry, or None if it has none (tool calls, thinking)."""
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content or None
    if not isinstance(content, list):
        return None
    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(texts)
    return text or None


def transcript_state(path: str | None, final_message: str | None = None) -> dict | None:
    """Line count and last main-thread assistant text of the transcript, right now.

    With `final_message` (the Stop input's `last_assistant_message`), also whether the transcript
    already contains it — `None` when there is nothing to compare against.

    None when there is no transcript to read. Unparseable lines are counted and skipped: a line
    being written while we read is exactly the case this measures.
    """
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        return None

    lines = 0
    last_uuid, last_text = None, None
    with file.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            lines += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            text = _assistant_text(entry)
            if text is not None:
                last_uuid, last_text = entry.get("uuid"), text

    return {
        "lines": lines,
        "last_assistant_uuid": last_uuid,
        "last_assistant_text": last_text[:PREVIEW_CHARS] if last_text else None,
        "last_assistant_chars": len(last_text) if last_text else 0,
        "has_final_message": (
            None if final_message is None else (last_text or "").strip() == final_message.strip()
        ),
    }
