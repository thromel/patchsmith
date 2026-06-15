from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_session import session_metrics as compatibility_session_metrics
from patchsmith.session.metrics import (
    AgentSessionMetrics,
    format_session_metrics,
    session_metrics,
    session_usage_payload,
)
from patchsmith.session.store import append_transcript_event

pytestmark = pytest.mark.unit


def test_session_metrics_reduces_transcript_events(tmp_path: Path) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session.jsonl"
    _append(transcript_path, "user_task", {"task": "fix parser"})
    _append(transcript_path, "preflight", {"status": "passed"})
    _append(transcript_path, "run_preflight", {"preflight": {"status": "passed"}})
    _append(transcript_path, "model_preflight", {"available": True})
    _append(
        transcript_path,
        "run_result",
        {
            "run_id": "run-1",
            "test_exit_code": 0,
            "model_call_count": 1,
            "model_response_count": 2,
            "model_total_tokens": 300,
            "estimated_cost_usd": 0.01,
        },
    )
    _append(transcript_path, "diff_view", {"mode": "stat"})
    _append(
        transcript_path,
        "diff_review",
        {"risk_level": "high", "diff_path": "final.diff"},
    )
    _append(transcript_path, "apply_check_result", {"status": "ready"})
    _append(
        transcript_path,
        "apply_approval",
        {"risk_level": "high", "status": "approved"},
    )
    _append(transcript_path, "apply_result", {"applied": True})
    _append(transcript_path, "rewind_result", {"applied": True})
    _append(transcript_path, "verify_result", {"status": "passed"})
    _append(transcript_path, "config_update", {"field": "resource_budget"})
    _append(transcript_path, "plan_update", {"items": []})
    _append(transcript_path, "feedback_update", {"items": []})
    _append(transcript_path, "session_gate", {"gate": {"status": "failed"}})
    _append(transcript_path, "run_evidence", {})
    _append(transcript_path, "session_checkpoint", {})
    _append(transcript_path, "session_restore", {})
    _append(transcript_path, "session_timeline", {})
    _append(transcript_path, "session_next", {})

    metrics = session_metrics(transcript_path)

    assert isinstance(metrics, AgentSessionMetrics)
    assert metrics.task_count == 1
    assert metrics.preflight_count == 1
    assert metrics.preflight_passed_count == 1
    assert metrics.run_preflight_count == 1
    assert metrics.run_preflight_passed_count == 1
    assert metrics.model_preflight_count == 1
    assert metrics.model_preflight_passed_count == 1
    assert metrics.run_count == 1
    assert metrics.validated_run_count == 1
    assert metrics.verify_count == 1
    assert metrics.verify_passed_count == 1
    assert metrics.diff_view_count == 1
    assert metrics.diff_review_count == 1
    assert metrics.diff_review_high_count == 1
    assert metrics.current_diff_review_count == 1
    assert metrics.current_diff_review_high_count == 1
    assert metrics.apply_check_count == 1
    assert metrics.apply_check_ready_count == 1
    assert metrics.current_apply_check_ready_count == 1
    assert metrics.apply_approval_count == 1
    assert metrics.high_risk_apply_approval_count == 1
    assert metrics.apply_attempt_count == 1
    assert metrics.apply_success_count == 1
    assert metrics.rewind_attempt_count == 1
    assert metrics.rewind_success_count == 1
    assert metrics.budget_update_count == 1
    assert metrics.plan_update_count == 1
    assert metrics.feedback_update_count == 1
    assert metrics.session_gate_count == 1
    assert metrics.session_gate_failure_count == 1
    assert metrics.run_evidence_count == 1
    assert metrics.checkpoint_count == 1
    assert metrics.restore_count == 1
    assert metrics.timeline_view_count == 1
    assert metrics.next_view_count == 1
    assert metrics.model_call_count == 1
    assert metrics.model_response_count == 2
    assert metrics.model_total_tokens == 300
    assert metrics.estimated_cost_usd == 0.01
    assert metrics.validation_rate == 1.0
    assert metrics.preflight_to_run_rate == 1.0
    assert metrics.apply_success_rate == 1.0
    assert metrics.rewind_success_rate == 1.0
    assert metrics.cost_per_validated_run_usd == 0.01


def test_session_metrics_keeps_agent_session_compatibility_export(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session.jsonl"
    _append(transcript_path, "user_task", {"task": "fix parser"})
    _append(transcript_path, "run_error", {"message": "failed"})

    assert compatibility_session_metrics(transcript_path) == session_metrics(transcript_path)
    assert session_usage_payload(transcript_path) == {
        "task_count": 1,
        "run_count": 0,
        "validated_run_count": 0,
        "run_error_count": 1,
        "model_call_count": 0,
        "model_response_count": 0,
        "model_total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def test_format_session_metrics_includes_rates_and_cost(tmp_path: Path) -> None:
    transcript_path = tmp_path / "chat_sessions" / "session.jsonl"
    _append(transcript_path, "preflight", {"status": "passed"})
    _append(
        transcript_path,
        "run_result",
        {
            "test_exit_code": 0,
            "model_response_count": 1,
            "model_total_tokens": 42,
            "estimated_cost_usd": 0.5,
        },
    )

    text = format_session_metrics(session_metrics(transcript_path))

    assert "- Validation rate: 100.00%" in text
    assert "- Preflight-to-run rate: 100.00%" in text
    assert "- Estimated cost: $0.500000" in text
    assert "- Cost per validated run: $0.500000" in text


def _append(
    transcript_path: Path,
    event: str,
    payload: dict[str, object],
) -> None:
    append_transcript_event(
        transcript_path,
        session_id="session-1",
        event=event,
        payload=payload,
        timestamp="2026-06-15T00:00:00+00:00",
    )
