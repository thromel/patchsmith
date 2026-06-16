from __future__ import annotations

from dataclasses import fields

import pytest

from patchsmith.evaluation.complex.followups import (
    complex_followup_candidates,
    complex_suite_followup_candidates,
)
from patchsmith.evaluation.complex.models import ComplexBenchmarkSuiteThresholds
from patchsmith.evaluation.complex.selection import select_attempts
from patchsmith.evaluation.runners import complex as runner_complex
from patchsmith.evaluation_models import (
    ComplexBenchmarkResult,
    ComplexBenchmarkSummary,
)

pytestmark = pytest.mark.unit


def test_complex_followup_candidates_build_budget_critical_cost_rerun() -> None:
    result = _result(
        task_id="requests-7341",
        validation_passed=True,
        status="validated",
        strict_status="validated",
        failure_class="validated",
        harness_layer="none",
        estimated_cost_usd=0.12,
        total_tokens=130_000,
        response_count=8,
    )

    candidates = complex_followup_candidates([result])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.action == "cost_optimization_rerun"
    assert candidate.suggested_profile == "budget_critical_context_cap"
    assert candidate.priority == 60
    assert candidate.reasons == ("high_response_count", "high_token_count", "high_cost")
    assert candidate.recommended_env == {"OPENAI_API_KEY": "<required>"}
    assert (
        candidate.recommended_command[candidate.recommended_command.index("--task-id") + 1]
        == "requests-7341"
    )
    assert (
        candidate.recommended_command[
            candidate.recommended_command.index("--deepagents-max-context-files") + 1
        ]
        == "4"
    )
    assert (
        candidate.recommended_command[
            candidate.recommended_command.index("--max-actual-model-responses") + 1
        ]
        == "6"
    )
    assert (
        candidate.recommended_command[
            candidate.recommended_command.index("--max-live-cost-usd") + 1
        ]
        == "0.07"
    )
    assert "max_attempted_task_responses <= 6" in candidate.success_criteria


def test_complex_suite_followup_candidates_adds_verifier_threshold_reruns() -> None:
    result = _result(
        task_id="pytest-14552",
        validation_passed=True,
        status="validated",
        strict_status="validated",
        failure_class="validated",
        harness_layer="none",
        contextual_verifier=False,
        deepagents_acceptance_rubric_manifest_path=None,
        deepagents_acceptance_rubric_manifest_read_first=False,
        deepagents_acceptance_rubric_aligned=None,
    )
    thresholds = ComplexBenchmarkSuiteThresholds(
        min_contextual_verifier_rate=1.0,
        min_acceptance_rubric_manifest_rate=1.0,
        min_acceptance_rubric_read_first_rate=1.0,
        min_acceptance_rubric_alignment_rate=1.0,
    )

    candidates = complex_suite_followup_candidates(
        results=[result],
        selections=select_attempts([result]),
        summary=_summary(
            attempted_tasks=1,
            contextual_verifier_rate=0.0,
            acceptance_rubric_manifest_tasks=0,
            acceptance_rubric_read_first_rate=0.0,
            acceptance_rubric_alignment_rate=0.0,
        ),
        thresholds=thresholds,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.action == "verifier_contract_rerun"
    assert candidate.suggested_profile == "acceptance_rubric_verifier"
    assert candidate.priority == 400
    assert candidate.reasons == (
        "contextual_verifier_missing",
        "acceptance_rubric_manifest_missing",
        "acceptance_rubric_read_first_missing",
        "acceptance_rubric_alignment_missing",
    )
    assert "--min-contextual-verifier-rate" in candidate.validation_command
    assert "acceptance_rubric_alignment_rate >= 1.0" in candidate.success_criteria


def test_runner_delegates_followup_policy_to_complex_package() -> None:
    assert runner_complex._suite_followup_candidates is complex_suite_followup_candidates


def _result(**overrides: object) -> ComplexBenchmarkResult:
    values: dict[str, object] = {
        "task_id": "task",
        "repository": None,
        "issue_url": None,
        "status": "failed",
        "strict_status": "failed",
        "runtime": "deepagents",
        "planner": "deepagents",
        "context_provider": "native_hybrid",
        "reproduced": True,
        "patch_generated": True,
        "validation_passed": False,
        "test_exit_code": 1,
        "trace_path": None,
        "report_path": None,
        "progress_score": 0.5,
        "progress_stage": "target_aligned_patch",
        "failure_class": "test_failure",
        "harness_layer": "validation",
        "process_quality_label": "solid",
        "patch_target_aligned": True,
    }
    values.update(overrides)
    return ComplexBenchmarkResult(**values)  # type: ignore[arg-type]


def _summary(**overrides: object) -> ComplexBenchmarkSummary:
    values: dict[str, object] = {
        field.name: _summary_default(field.name) for field in fields(ComplexBenchmarkSummary)
    }
    values.update(
        {
            "benchmark": "public_issue_repair_attempts",
            "attempt_dir": "attempt",
            "model_provider": "deepagents_openai_chat",
        }
    )
    values.update(overrides)
    return ComplexBenchmarkSummary(**values)  # type: ignore[arg-type]


def _summary_default(name: str) -> object:
    if name.endswith("_counts"):
        return {}
    if name.endswith(("_rate", "_score")) or name.startswith("avg_"):
        return 0.0
    if name.endswith("_usd"):
        return None
    if name.endswith(("_tokens", "_responses")):
        return None
    if name in {"benchmark", "attempt_dir", "model_provider"}:
        return ""
    return 0
