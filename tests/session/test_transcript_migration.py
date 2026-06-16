from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.session.events import TranscriptEvent
from patchsmith.session.metrics import session_metrics, session_usage_payload
from patchsmith.session.report import session_markdown_report
from patchsmith.session.store import read_transcript_events
from patchsmith.session.timeline import session_timeline

pytestmark = pytest.mark.unit


def test_legacy_transcript_rows_without_metadata_still_feed_session_reducers(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "legacy-session.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        "\n".join(
            [
                json.dumps({"event": "user_task", "payload": {"task": "fix parser"}}),
                json.dumps(
                    {
                        "event": "run_result",
                        "payload": {
                            "run_id": "run-1",
                            "status": "completed",
                            "test_exit_code": 0,
                            "model_response_count": 1,
                            "model_total_tokens": 123,
                            "estimated_cost_usd": 0.02,
                        },
                    }
                ),
                json.dumps({"event": "session_timeline", "payload": {}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    decoded = read_transcript_events(transcript_path)
    metrics = session_metrics(transcript_path)
    timeline = session_timeline(transcript_path, limit=0)
    report = session_markdown_report(transcript_path)

    assert decoded[0] == TranscriptEvent(
        timestamp="",
        session_id="",
        event="user_task",
        payload={"task": "fix parser"},
    )
    assert session_usage_payload(transcript_path) == {
        "task_count": 1,
        "run_count": 1,
        "validated_run_count": 1,
        "run_error_count": 0,
        "model_call_count": 0,
        "model_response_count": 1,
        "model_total_tokens": 123,
        "estimated_cost_usd": 0.02,
    }
    assert metrics.task_count == 1
    assert metrics.run_count == 1
    assert metrics.validated_run_count == 1
    assert metrics.timeline_view_count == 1
    assert timeline[0].timestamp == "n/a"
    assert timeline[0].summary == "fix parser"
    assert "- Session: `legacy-session`" in report
    assert "- Validated runs: `1`" in report
