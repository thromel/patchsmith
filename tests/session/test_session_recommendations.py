from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_session import (
    format_session_recommendation as compatibility_format_session_recommendation,
)
from patchsmith.agent_session import (
    session_recommendation as compatibility_session_recommendation,
)
from patchsmith.session.recommendations import (
    format_session_recommendation,
    session_recommendation,
)
from patchsmith.session.store import append_transcript_event

pytestmark = pytest.mark.unit


def test_session_recommendation_starts_with_preflight_for_new_sessions(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"

    recommendation = session_recommendation(transcript_path)

    assert recommendation.action == (
        "Run a bounded preflight, then start the first repair run."
    )
    assert recommendation.commands == ("/preflight <task>", "/run <task>")
    assert recommendation.to_dict()["evidence"] == ["run_count=0"]


def test_session_recommendation_flags_validated_run_without_trace_review(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _append(
        transcript_path,
        "run_result",
        {"run_id": "run-1", "status": "completed", "test_exit_code": 0},
        "2026-06-15T00:00:00+00:00",
    )

    recommendation = session_recommendation(transcript_path)
    compatibility_recommendation = compatibility_session_recommendation(transcript_path)

    assert compatibility_recommendation == recommendation
    assert recommendation.action == "Inspect the latest validated run artifacts."
    assert recommendation.commands == ("/trace", "/gate clean")
    assert "trace_review=missing_after_latest_run" in recommendation.evidence
    assert format_session_recommendation(
        recommendation
    ) == compatibility_format_session_recommendation(recommendation)


def test_session_recommendation_detects_repeated_unresolved_runs(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session-a.jsonl"
    _append(
        transcript_path,
        "session_start",
        {"config": {"max_model_responses": 12, "max_model_tokens": 200_000}},
        "2026-06-15T00:00:00+00:00",
    )
    _append(
        transcript_path,
        "run_result",
        _failed_run_payload("run-stuck-1"),
        "2026-06-15T00:01:00+00:00",
    )
    _append(
        transcript_path,
        "run_result",
        _failed_run_payload("run-stuck-2"),
        "2026-06-15T00:02:00+00:00",
    )

    recommendation = session_recommendation(transcript_path)

    assert recommendation.action == "Break the repeated failure loop before another run."
    assert recommendation.commands == (
        "/trace",
        "/feedback add <what changed after reviewing the failure>",
        "/context add <path[#symbol]>",
    )
    assert "repeat_count=2" in recommendation.evidence
    assert any(
        item.startswith("failure=no_patch_generated")
        for item in recommendation.evidence
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


def _failed_run_payload(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "status": "completed",
        "test_exit_code": 1,
        "retrieved_files": ["calc.py", "test_calc.py"],
        "repair_verdict": "no_patch_tests_failed",
        "repair_failure_category": "no_patch_generated",
        "repair_patch_generated": False,
        "repair_tests_passed": False,
        "model_response_count": 2,
        "model_total_tokens": 21_056,
        "estimated_cost_usd": 0.01,
    }
