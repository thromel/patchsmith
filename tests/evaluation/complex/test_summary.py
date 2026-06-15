from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.evaluation.complex.selection import select_attempts
from patchsmith.evaluation.complex.summary import (
    complex_summary,
    preflight_gate_blocked_from_gates,
)
from patchsmith.evaluation.runners import complex as runner_complex
from patchsmith.evaluation_models import ComplexBenchmarkResult

pytestmark = pytest.mark.unit


def test_complex_summary_aggregates_attempts_selected_costs_and_budget_signals() -> None:
    validated = _result(
        task_id="task-a",
        status="validated",
        strict_status="validated",
        validation_passed=True,
        attempt_index=1,
        attempt_count=2,
        progress_score=1.0,
        failure_class="validated",
        harness_layer="none",
        response_count=2,
        input_tokens=900,
        output_tokens=100,
        total_tokens=1_000,
        estimated_cost_usd=0.05,
        deepagents_virtual_file_count=2,
        deepagents_virtual_file_paths=("src/app.py", "tests/test_app.py"),
        localized_target_paths=("src/app.py",),
        deepagents_context_budgeted=True,
        deepagents_context_budget_manifest_path="/.patchsmith/context-budget.json",
        deepagents_context_budget_omitted_file_count=1,
        deepagents_resource_budgeted=True,
        deepagents_resource_budget_read_first=True,
        deepagents_resource_budget_max_model_responses=6,
        deepagents_resource_budget_max_model_tokens=90_000,
        patch_target_aligned=True,
        target_alignment_status="aligned",
        process_quality_label="solid",
        process_quality_score=1.0,
    )
    failed = _result(
        task_id="task-a",
        status="failed",
        strict_status="failed",
        validation_passed=False,
        attempt_index=2,
        attempt_count=2,
        progress_score=0.5,
        failure_class="test_failure",
        harness_layer="validation",
        response_count=4,
        input_tokens=1_800,
        output_tokens=200,
        total_tokens=2_000,
        estimated_cost_usd=0.07,
        retry_label_counts={"targeted": 2},
        retry_failure_class_counts={"repeat": 1},
        retry_failure_classes=("repeat",),
        process_quality_flags=("risky_context",),
        patch_target_aligned=False,
        target_alignment_status="misaligned",
    )
    blocked = _result(
        task_id="task-b",
        status="blocked",
        strict_status="blocked",
        validation_passed=False,
        reproduced=False,
        patch_generated=False,
        preflight_status="blocked",
        preflight_gates=[{"name": "sandbox", "status": "blocked"}],
    )
    results = [validated, failed, blocked]

    summary = complex_summary(
        benchmark="public_issue_repair_attempts",
        attempt_dir=Path("attempts"),
        results=results,
        selections=select_attempts(results),
    )

    assert summary.task_count == 3
    assert summary.attempted_tasks == 2
    assert summary.blocked_tasks == 1
    assert summary.sandbox_preflight_blocked_tasks == 1
    assert summary.unique_task_count == 2
    assert summary.unique_attempted_tasks == 1
    assert summary.validated_task_pass_at_n_rate == 1.0
    assert summary.validation_rate == 0.5
    assert summary.live_provider_tasks == 2
    assert summary.estimated_cost_usd == pytest.approx(0.12)
    assert summary.attempted_tokens_per_validated_task == 3_000.0
    assert summary.attempted_responses_per_validated_task == 6.0
    assert summary.selected_cost_per_validated_task_usd == 0.05
    assert summary.selected_tokens_per_validated_task == 1_000.0
    assert summary.selected_responses_per_validated_task == 2.0
    assert summary.selected_virtual_file_count == 2
    assert summary.selected_tokens_per_virtual_file == 500.0
    assert summary.selected_responses_per_virtual_file == 1.0
    assert summary.selected_context_target_available_tasks == 1
    assert summary.selected_context_target_covered_tasks == 1
    assert summary.selected_context_target_recall == 1.0
    assert summary.selected_context_target_precision == 0.5
    assert summary.context_budgeted_tasks == 1
    assert summary.context_budget_omitted_file_count == 1
    assert summary.resource_budgeted_tasks == 1
    assert summary.resource_budget_read_first_rate == 1.0
    assert summary.retry_label_counts == {"targeted": 2}
    assert summary.retry_failure_class_counts == {"repeat": 1}
    assert summary.process_quality_flag_counts == {"risky_context": 1}
    assert summary.failure_class_counts == {"test_failure": 1, "validated": 1}
    assert summary.selected_failure_class_counts == {"validated": 1}


def test_preflight_gate_blocked_from_gates_matches_saved_gate_rows() -> None:
    gates = [
        {"name": "model", "status": "passed"},
        {"name": "budget", "status": "blocked"},
    ]

    assert preflight_gate_blocked_from_gates(gates, "budget")
    assert not preflight_gate_blocked_from_gates(gates, "model")
    assert not preflight_gate_blocked_from_gates(gates, "sandbox")


def test_runner_delegates_summary_to_complex_package() -> None:
    assert runner_complex._complex_summary is complex_summary


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
        "patch_quality_severity": "low",
        "target_alignment_status": "aligned",
        "patch_target_aligned": True,
        "model_provider": "deepagents_openai_chat",
        "preflight_status": "passed",
        "preflight_gates": [],
    }
    values.update(overrides)
    return ComplexBenchmarkResult(**values)  # type: ignore[arg-type]
