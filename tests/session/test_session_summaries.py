from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_session import (
    format_session_summaries as compatibility_format_session_summaries,
)
from patchsmith.agent_session import (
    list_session_summaries as compatibility_list_session_summaries,
)
from patchsmith.session.store import append_transcript_event
from patchsmith.session.summaries import (
    format_session_summaries,
    list_session_summaries,
    session_summary,
)

pytestmark = pytest.mark.unit


def test_session_summary_reads_usage_config_and_latest_run(tmp_path: Path) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _append(
        transcript_path,
        "session-a",
        "session_start",
        {"config": {"repo": "/repo"}},
        "2026-06-15T00:00:00+00:00",
    )
    _append(
        transcript_path,
        "session-a",
        "user_task",
        {"task": "fix parser"},
        "2026-06-15T00:01:00+00:00",
    )
    _append(
        transcript_path,
        "session-a",
        "run_result",
        {
            "run_id": "run-1",
            "status": "validated",
            "test_exit_code": 0,
            "estimated_cost_usd": 0.25,
        },
        "2026-06-15T00:02:00+00:00",
    )

    summary = session_summary(transcript_path)

    assert summary.session_id == "session-a"
    assert summary.started_at == "2026-06-15T00:00:00+00:00"
    assert summary.updated_at == "2026-06-15T00:02:00+00:00"
    assert summary.repo == "/repo"
    assert summary.task_count == 1
    assert summary.run_count == 1
    assert summary.validated_run_count == 1
    assert summary.estimated_cost_usd == 0.25
    assert summary.last_run_id == "run-1"
    assert summary.last_status == "validated"


def test_list_and_format_session_summaries_keep_agent_session_compatibility(
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    older = artifacts_dir / "chat_sessions" / "older.jsonl"
    newer = artifacts_dir / "chat_sessions" / "newer.jsonl"
    _append(
        older,
        "older",
        "run_result",
        {"run_id": "old-run", "status": "failed", "estimated_cost_usd": 0.1},
        "2026-06-15T00:01:00+00:00",
    )
    _append(
        newer,
        "newer",
        "run_result",
        {"run_id": "new-run", "status": "validated", "estimated_cost_usd": 0.2},
        "2026-06-15T00:02:00+00:00",
    )

    summaries = list_session_summaries(artifacts_dir)
    compatibility_summaries = compatibility_list_session_summaries(artifacts_dir)

    assert [summary.session_id for summary in summaries] == ["newer", "older"]
    assert compatibility_summaries == summaries
    assert format_session_summaries(summaries) == compatibility_format_session_summaries(summaries)
    text = format_session_summaries(summaries)
    assert "newer" in text
    assert "$0.200000" in text
    assert "new-run (validated)" in text


def _append(
    transcript_path: Path,
    session_id: str,
    event: str,
    payload: dict[str, object],
    timestamp: str,
) -> None:
    append_transcript_event(
        transcript_path,
        session_id=session_id,
        event=event,
        payload=payload,
        timestamp=timestamp,
    )
