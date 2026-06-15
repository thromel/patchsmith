from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_session import (
    export_session_report as compatibility_export_session_report,
)
from patchsmith.agent_session import (
    session_markdown_report as compatibility_session_markdown_report,
)
from patchsmith.session.report import export_session_report, session_markdown_report
from patchsmith.session.store import append_transcript_event

pytestmark = pytest.mark.unit


def test_session_markdown_report_includes_usage_runs_and_context_events(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _write_report_transcript(transcript_path)

    report = session_markdown_report(transcript_path)

    assert compatibility_session_markdown_report is session_markdown_report
    assert "# PatchSmith Chat Session" in report
    assert "- Session: `session-a`" in report
    assert "- Repo: `/repo`" in report
    assert "## Usage" in report
    assert "- Validated runs: `1`" in report
    assert "- Estimated cost: `$0.250000`" in report
    assert "## Process Metrics" in report
    assert "- Validation rate: `100.00%`" in report
    assert "## Runs" in report
    assert "- `run-1`: status `completed`, test exit `0`" in report
    assert "## Tasks" in report
    assert "1. fix parser" in report
    assert "## Context, Plan, And Config Events" in report
    assert "`diff_review`" in report
    assert "## Latest State" in report
    assert "- Last run: `run-1`" in report


def test_export_session_report_writes_requested_path_and_keeps_compatibility(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    report_path = tmp_path / "reports" / "session-a.md"
    _write_report_transcript(transcript_path)

    export = export_session_report(
        transcript_path=transcript_path,
        report_path=report_path,
    )
    assert compatibility_export_session_report is export_session_report
    compatibility_export = compatibility_export_session_report(
        transcript_path=transcript_path,
        report_path=tmp_path / "reports" / "session-a-compat.md",
    )

    assert export.transcript_path == transcript_path
    assert export.report_path == report_path
    assert report_path.is_file()
    assert report_path.read_text(encoding="utf-8").startswith(
        "# PatchSmith Chat Session"
    )
    assert compatibility_export.transcript_path == transcript_path
    assert compatibility_export.report_path.is_file()


def _write_report_transcript(transcript_path: Path) -> None:
    _append(
        transcript_path,
        "session_start",
        {
            "config": {
                "repo": "/repo",
                "context_provider": "native_hybrid",
                "max_model_responses": 12,
                "max_model_tokens": 200_000,
            }
        },
        "2026-06-15T00:00:00+00:00",
    )
    _append(
        transcript_path,
        "user_task",
        {"task": "fix parser"},
        "2026-06-15T00:01:00+00:00",
    )
    _append(
        transcript_path,
        "run_result",
        {
            "run_id": "run-1",
            "status": "completed",
            "test_exit_code": 0,
            "report_path": "artifacts/runs/run-1/report.md",
            "trace_path": "artifacts/runs/run-1/traces.jsonl",
            "final_diff_path": "artifacts/runs/run-1/final.diff",
            "model_response_count": 2,
            "model_total_tokens": 100,
            "estimated_cost_usd": 0.25,
        },
        "2026-06-15T00:02:00+00:00",
    )
    _append(
        transcript_path,
        "diff_review",
        {"risk_level": "low", "decision": "ready", "findings": []},
        "2026-06-15T00:03:00+00:00",
    )


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
