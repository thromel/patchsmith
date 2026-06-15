from __future__ import annotations

import pytest

from patchsmith.agent_session import (
    AgentSessionGateConfig as CompatibilityAgentSessionGateConfig,
)
from patchsmith.agent_session import (
    evaluate_session_gate as compatibility_evaluate_session_gate,
)
from patchsmith.agent_session import (
    format_session_gate as compatibility_format_session_gate,
)
from patchsmith.session.gates import (
    AgentSessionGateConfig,
    evaluate_session_gate,
    format_session_gate,
)
from patchsmith.session.metrics import AgentSessionMetrics

pytestmark = pytest.mark.unit


def test_session_gate_passes_when_required_metrics_meet_thresholds() -> None:
    metrics = _metrics(
        run_count=2,
        validated_run_count=2,
        preflight_count=2,
        current_diff_review_count=1,
        current_apply_check_ready_count=1,
        apply_attempt_count=2,
        apply_success_count=2,
        estimated_cost_usd=0.25,
    )

    result = evaluate_session_gate(
        metrics,
        AgentSessionGateConfig(
            require_validated_run=True,
            require_diff_review=True,
            require_ready_apply_check=True,
            min_validation_rate=1.0,
            min_preflight_to_run_rate=1.0,
            min_apply_success_rate=1.0,
            max_high_risk_diff_reviews=0,
            max_cost_per_validated_run_usd=0.20,
            max_run_errors=0,
        ),
    )

    assert result.status == "passed"
    assert {check.name: check.status for check in result.checks} == {
        "validated_run": "passed",
        "diff_review_count": "passed",
        "ready_apply_check_count": "passed",
        "validation_rate": "passed",
        "preflight_to_run_rate": "passed",
        "apply_success_rate": "passed",
        "high_risk_diff_review_count": "passed",
        "cost_per_validated_run_usd": "passed",
        "run_error_count": "passed",
    }


def test_session_gate_fails_when_required_evidence_is_missing() -> None:
    metrics = _metrics(run_count=1, preflight_count=2, run_error_count=1)

    result = evaluate_session_gate(
        metrics,
        AgentSessionGateConfig(
            require_validated_run=True,
            require_diff_review=True,
            require_ready_apply_check=True,
            min_validation_rate=0.5,
            min_preflight_to_run_rate=1.0,
            min_apply_success_rate=1.0,
            max_run_errors=0,
        ),
    )

    checks = {check.name: check for check in result.checks}
    assert result.status == "failed"
    assert checks["validated_run"].status == "failed"
    assert checks["diff_review_count"].status == "failed"
    assert checks["ready_apply_check_count"].status == "failed"
    assert checks["validation_rate"].status == "failed"
    assert checks["preflight_to_run_rate"].status == "failed"
    assert checks["apply_success_rate"].status == "failed"
    assert checks["run_error_count"].status == "failed"


def test_format_session_gate_includes_each_check() -> None:
    result = evaluate_session_gate(
        _metrics(validated_run_count=1),
        AgentSessionGateConfig(require_validated_run=True),
    )

    text = format_session_gate(result)

    assert text.startswith("Session gate: passed")
    assert "- validated_run: passed - 1 validated run(s)" in text
    assert "- validation_rate: skipped - no threshold configured" in text


def test_agent_session_keeps_gate_compatibility_exports() -> None:
    metrics = _metrics(validated_run_count=1)
    result = compatibility_evaluate_session_gate(
        metrics,
        CompatibilityAgentSessionGateConfig(require_validated_run=True),
    )

    assert result == evaluate_session_gate(
        metrics,
        AgentSessionGateConfig(require_validated_run=True),
    )
    assert compatibility_format_session_gate(result) == format_session_gate(result)


def _metrics(**overrides: object) -> AgentSessionMetrics:
    base: dict[str, object] = {
        "task_count": 0,
        "preflight_count": 0,
        "preflight_passed_count": 0,
        "run_preflight_count": 0,
        "run_preflight_passed_count": 0,
        "model_preflight_count": 0,
        "model_preflight_passed_count": 0,
        "model_preflight_blocked_count": 0,
        "run_count": 0,
        "validated_run_count": 0,
        "run_error_count": 0,
        "verify_count": 0,
        "verify_passed_count": 0,
        "diff_view_count": 0,
        "diff_review_count": 0,
        "diff_review_high_count": 0,
        "current_diff_review_count": 0,
        "current_diff_review_high_count": 0,
        "apply_check_count": 0,
        "apply_check_ready_count": 0,
        "current_apply_check_ready_count": 0,
        "apply_approval_count": 0,
        "high_risk_apply_approval_count": 0,
        "apply_rejection_count": 0,
        "high_risk_apply_rejection_count": 0,
        "apply_block_count": 0,
        "apply_auto_deferred_count": 0,
        "apply_attempt_count": 0,
        "apply_success_count": 0,
        "rewind_attempt_count": 0,
        "rewind_success_count": 0,
        "custom_command_count": 0,
        "hook_run_count": 0,
        "hook_block_count": 0,
        "context_update_count": 0,
        "permission_update_count": 0,
        "model_update_count": 0,
        "budget_update_count": 0,
        "agent_profile_update_count": 0,
        "instruction_update_count": 0,
        "instruction_view_count": 0,
        "memory_view_count": 0,
        "plan_update_count": 0,
        "plan_view_count": 0,
        "feedback_update_count": 0,
        "feedback_view_count": 0,
        "session_gate_count": 0,
        "session_gate_failure_count": 0,
        "run_evidence_count": 0,
        "checkpoint_count": 0,
        "restore_count": 0,
        "timeline_view_count": 0,
        "next_view_count": 0,
        "model_call_count": 0,
        "model_response_count": 0,
        "model_total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    base.update(overrides)
    return AgentSessionMetrics(**base)  # type: ignore[arg-type]
