from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.session.events import TranscriptEvent, UnknownTranscriptEvent
from patchsmith.session.store import (
    append_transcript_event,
    read_transcript_events,
    read_transcript_rows,
)

pytestmark = pytest.mark.unit


def test_append_transcript_event_writes_compatible_json_row(tmp_path: Path) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session.jsonl"

    event = append_transcript_event(
        transcript_path,
        session_id="session-1",
        event="user_task",
        payload={"task": "fix parser"},
        timestamp="2026-06-15T00:00:00+00:00",
    )

    assert event == TranscriptEvent(
        timestamp="2026-06-15T00:00:00+00:00",
        session_id="session-1",
        event="user_task",
        payload={"task": "fix parser"},
    )
    rows = read_transcript_rows(transcript_path)
    assert rows == [
        {
            "timestamp": "2026-06-15T00:00:00+00:00",
            "session_id": "session-1",
            "event": "user_task",
            "payload": {"task": "fix parser"},
        }
    ]
    decoded = read_transcript_events(transcript_path)
    assert decoded == [event]


def test_read_transcript_rows_skips_bad_json_but_preserves_dict_rows(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text(
        "{not-json}\n"
        + json.dumps({"event": "legacy_event", "payload": "not-a-dict"})
        + "\n"
        + json.dumps({"event": "valid", "payload": {"ok": True}})
        + "\n",
        encoding="utf-8",
    )

    rows = read_transcript_rows(transcript_path)

    assert rows == [
        {"event": "legacy_event", "payload": "not-a-dict"},
        {"event": "valid", "payload": {"ok": True}},
    ]


def test_read_transcript_events_isolates_unknown_historical_rows(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text(
        json.dumps({"event": "legacy_event", "payload": "not-a-dict"})
        + "\n"
        + json.dumps({"payload": {"ok": True}})
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-06-15T00:00:00+00:00",
                "session_id": "session-1",
                "event": "valid",
                "payload": {"ok": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    decoded = read_transcript_events(transcript_path)

    assert isinstance(decoded[0], UnknownTranscriptEvent)
    assert decoded[0].reason == "invalid_payload"
    assert decoded[0].to_dict() == {"event": "legacy_event", "payload": "not-a-dict"}
    assert isinstance(decoded[1], UnknownTranscriptEvent)
    assert decoded[1].reason == "missing_event"
    assert decoded[2] == TranscriptEvent(
        timestamp="2026-06-15T00:00:00+00:00",
        session_id="session-1",
        event="valid",
        payload={"ok": True},
    )
