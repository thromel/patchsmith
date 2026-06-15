from __future__ import annotations

import pytest

from patchsmith.evaluation.complex.selection import (
    results_by_task,
    select_attempts,
    selected_results,
    selection_reason,
)
from patchsmith.evaluation_models import ComplexBenchmarkResult

pytestmark = pytest.mark.unit


def test_select_attempts_prefers_strict_validation_then_cost() -> None:
    expensive = _result(
        task_id="task-a",
        attempt_index=1,
        attempt_count=3,
        status="validated",
        strict_status="validated",
        validation_passed=True,
        estimated_cost_usd=0.25,
        total_tokens=2500,
        progress_score=1.0,
    )
    failed_progress = _result(
        task_id="task-a",
        attempt_index=2,
        attempt_count=3,
        status="failed",
        strict_status="failed",
        validation_passed=False,
        estimated_cost_usd=0.01,
        total_tokens=100,
        progress_score=0.99,
    )
    cheap = _result(
        task_id="task-a",
        attempt_index=3,
        attempt_count=3,
        status="validated",
        strict_status="validated",
        validation_passed=True,
        estimated_cost_usd=0.05,
        total_tokens=500,
        progress_score=1.0,
        response_count=1,
        deepagents_virtual_file_count=3,
    )

    selections = select_attempts([expensive, failed_progress, cheap])

    assert len(selections) == 1
    assert selections[0].task_id == "task-a"
    assert selections[0].selected_attempt_index == 3
    assert selections[0].estimated_cost_usd == 0.05
    assert "strict validated" in selections[0].selection_reason
    assert "cost=$0.050000" in selections[0].selection_reason
    assert selected_results([expensive, failed_progress, cheap], selections) == [cheap]


def test_selection_reason_includes_context_and_resource_budget_signals() -> None:
    result = _result(
        task_id="task-b",
        status="failed",
        strict_status="failed",
        validation_passed=False,
        estimated_cost_usd=0.07,
        live_cost_budget_overage_usd=0.02,
        total_tokens=90_000,
        response_count=6,
        deepagents_virtual_file_count=2,
        deepagents_context_budgeted=True,
        deepagents_max_context_files=2,
        deepagents_context_budget_omitted_file_count=5,
        deepagents_resource_budgeted=True,
        deepagents_resource_budget_max_model_responses=6,
        deepagents_resource_budget_max_model_tokens=90_000,
        agent_trajectory_score=0.75,
    )

    reason = selection_reason(result)

    assert "strict_status=failed" in reason
    assert "budget_overage=$0.020000" in reason
    assert "tokens=90000" in reason
    assert "responses=6" in reason
    assert "virtual_files=2" in reason
    assert "context_cap=2" in reason
    assert "context_omitted=5" in reason
    assert "resource_cap=responses:6,tokens:90000" in reason
    assert reason.endswith("trajectory=0.75")


def test_results_by_task_uses_row_key_for_missing_task_ids() -> None:
    first = _result(task_id="")
    second = _result(task_id="task-c")

    grouped = results_by_task([first, second])

    assert grouped["row:1"] == [first]
    assert grouped["task-c"] == [second]


def _result(
    *,
    task_id: str = "task",
    status: str = "validated",
    strict_status: str = "validated",
    validation_passed: bool = True,
    attempt_index: int = 1,
    attempt_count: int = 1,
    progress_score: float = 1.0,
    estimated_cost_usd: float | None = None,
    total_tokens: int | None = None,
    response_count: int | None = None,
    deepagents_virtual_file_count: int | None = None,
    deepagents_context_budgeted: bool = False,
    deepagents_max_context_files: int | None = None,
    deepagents_context_budget_omitted_file_count: int | None = None,
    deepagents_resource_budgeted: bool = False,
    deepagents_resource_budget_max_model_responses: int | None = None,
    deepagents_resource_budget_max_model_tokens: int | None = None,
    live_cost_budget_overage_usd: float | None = None,
    agent_trajectory_score: float = 1.0,
) -> ComplexBenchmarkResult:
    return ComplexBenchmarkResult(
        task_id=task_id,
        repository=None,
        issue_url=None,
        status=status,
        strict_status=strict_status,
        runtime="deepagents",
        planner="deepagents",
        context_provider="repo-map",
        reproduced=True,
        patch_generated=True,
        validation_passed=validation_passed,
        test_exit_code=0 if validation_passed else 1,
        trace_path=None,
        report_path=f"/tmp/{task_id or 'row'}.md",
        progress_score=progress_score,
        progress_stage="validated" if validation_passed else "target_aligned_patch",
        failure_class="validated" if validation_passed else "test_failure",
        harness_layer="validation",
        patch_quality_severity="low",
        target_alignment_status="aligned",
        retry_event_count=0,
        response_count=response_count,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        live_cost_budget_overage_usd=live_cost_budget_overage_usd,
        attempt_index=attempt_index,
        attempt_count=attempt_count,
        deepagents_virtual_file_count=deepagents_virtual_file_count,
        deepagents_context_budgeted=deepagents_context_budgeted,
        deepagents_max_context_files=deepagents_max_context_files,
        deepagents_context_budget_omitted_file_count=(
            deepagents_context_budget_omitted_file_count
        ),
        deepagents_resource_budgeted=deepagents_resource_budgeted,
        deepagents_resource_budget_max_model_responses=(
            deepagents_resource_budget_max_model_responses
        ),
        deepagents_resource_budget_max_model_tokens=(
            deepagents_resource_budget_max_model_tokens
        ),
        agent_trajectory_score=agent_trajectory_score,
    )
