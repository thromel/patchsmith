from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_session import (
    format_session_timeline as compatibility_format_session_timeline,
)
from patchsmith.agent_session import session_timeline as compatibility_session_timeline
from patchsmith.session.store import append_transcript_event
from patchsmith.session.timeline import format_session_timeline, session_timeline

pytestmark = pytest.mark.unit


def test_session_timeline_summarizes_recent_events(tmp_path: Path) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _append(
        transcript_path,
        "user_task",
        {"task": "fix parser"},
        "2026-06-15T00:00:00+00:00",
    )
    _append(
        transcript_path,
        "run_result",
        {
            "run_id": "run-1",
            "status": "validated",
            "test_exit_code": 0,
            "estimated_cost_usd": 0.25,
        },
        "2026-06-15T00:01:00+00:00",
    )
    _append(
        transcript_path,
        "diff_review",
        {"risk_level": "high", "decision": "manual", "findings": ["check tests"]},
        "2026-06-15T00:02:00+00:00",
    )

    entries = session_timeline(transcript_path, limit=2)

    assert [entry.event for entry in entries] == ["run_result", "diff_review"]
    assert entries[0].summary == "run=run-1 status=validated test=0 cost=$0.250000"
    assert entries[1].summary == "risk=high decision=manual confirm=n/a findings=1"
    assert entries[0].to_dict() == {
        "timestamp": "2026-06-15T00:01:00+00:00",
        "event": "run_result",
        "summary": "run=run-1 status=validated test=0 cost=$0.250000",
    }


def test_format_session_timeline_keeps_agent_session_compatibility(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _append(
        transcript_path,
        "session_start",
        {"config": {"repo": "/repo"}},
        "2026-06-15T00:00:00+00:00",
    )
    _append(
        transcript_path,
        "session_timeline",
        {"limit": 20},
        "2026-06-15T00:01:00+00:00",
    )

    entries = session_timeline(transcript_path, limit=0)
    compatibility_entries = compatibility_session_timeline(transcript_path, limit=0)

    assert compatibility_entries == entries
    assert format_session_timeline(entries) == compatibility_format_session_timeline(entries)
    text = format_session_timeline(entries)
    assert text.startswith("Session timeline:")
    assert "2026-06-15T00:00:00 | session_start | repo=/repo" in text
    assert "2026-06-15T00:01:00 | session_timeline | limit=20" in text


def _append(
    transcript_path: Path,
    event: str,
    payload: dict[str, object],
    timestamp: str,
) -> None:
    append_transcript_event(
        transcript_path,
        session_id="session-a",
        event=event,
        payload=payload,
        timestamp=timestamp,
    )
