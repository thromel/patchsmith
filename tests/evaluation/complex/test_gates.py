from __future__ import annotations

import pytest

from patchsmith.evaluation.complex.gates import complex_benchmark_suite_gate
from patchsmith.evaluation.complex.models import ComplexBenchmarkSuiteThresholds
from patchsmith.evaluation.runners import complex as runner_complex
from patchsmith.evaluation_models import ComplexBenchmarkSummary

pytestmark = pytest.mark.unit


def test_complex_benchmark_suite_gate_passes_budget_and_manifest_thresholds() -> None:
    summary = _summary(
        validation_rate=1.0,
        live_provider_tasks=2,
        unique_task_count=2,
        selected_cost_per_validated_task_usd=0.05,
        selected_tokens_per_validated_task=50_000.0,
        selected_responses_per_validated_task=4.0,
        selected_virtual_files_per_validated_task=2.0,
        selected_tokens_per_virtual_file=25_000.0,
        selected_responses_per_virtual_file=2.0,
        selected_avg_progress_score=1.0,
        target_alignment_rate=1.0,
        repo_instructions_manifest_tasks=2,
        repo_instructions_read_first_rate=1.0,
        acceptance_rubric_manifest_tasks=2,
        acceptance_rubric_read_first_rate=1.0,
        acceptance_rubric_alignment_rate=1.0,
    )

    gate = complex_benchmark_suite_gate(
        summary,
        min_validation_rate=1.0,
        min_live_provider_tasks=2,
        min_unique_tasks=2,
        max_selected_cost_per_validated_task_usd=0.07,
        max_selected_tokens_per_validated_task=90_000.0,
        max_selected_responses_per_validated_task=6.0,
        max_selected_virtual_files_per_validated_task=3.0,
        max_selected_tokens_per_virtual_file=45_000.0,
        max_selected_responses_per_virtual_file=3.0,
        min_selected_progress_score=0.9,
        min_target_alignment_rate=1.0,
        min_repo_instructions_manifest_rate=1.0,
        min_repo_instructions_read_first_rate=1.0,
        min_acceptance_rubric_manifest_rate=1.0,
        min_acceptance_rubric_read_first_rate=1.0,
        min_acceptance_rubric_alignment_rate=1.0,
    )

    assert gate.status == "passed"
    assert gate.failures == ()


def test_complex_benchmark_suite_gate_reports_resource_and_manifest_failures() -> None:
    summary = _summary(
        validation_rate=0.5,
        live_provider_tasks=1,
        unique_task_count=1,
        selected_cost_per_validated_task_usd=0.12,
        selected_tokens_per_validated_task=120_000.0,
        selected_responses_per_validated_task=9.0,
        selected_avg_progress_score=0.4,
        target_alignment_rate=0.5,
        attempted_tasks=2,
        repo_instructions_manifest_tasks=1,
        repo_instructions_read_first_rate=0.5,
        acceptance_rubric_manifest_tasks=1,
        acceptance_rubric_read_first_rate=0.5,
        acceptance_rubric_alignment_rate=0.5,
        live_cost_budget_overage_tasks=2,
    )

    gate = complex_benchmark_suite_gate(
        summary,
        min_validation_rate=1.0,
        min_live_provider_tasks=2,
        min_unique_tasks=2,
        max_selected_cost_per_validated_task_usd=0.07,
        max_selected_tokens_per_validated_task=90_000.0,
        max_selected_responses_per_validated_task=6.0,
        min_selected_progress_score=0.9,
        min_target_alignment_rate=1.0,
        min_repo_instructions_manifest_rate=1.0,
        min_repo_instructions_read_first_rate=1.0,
        min_acceptance_rubric_manifest_rate=1.0,
        min_acceptance_rubric_read_first_rate=1.0,
        min_acceptance_rubric_alignment_rate=1.0,
        max_live_cost_budget_overage_tasks=0,
    )

    assert gate.status == "failed"
    assert "validation_rate 0.50 below required 1.00" in gate.failures
    assert "live_provider_tasks 1 below required 2" in gate.failures
    assert "unique_task_count 1 below required 2" in gate.failures
    assert "selected cost per validated task $0.120000 exceeds $0.070000" in gate.failures
    assert "selected tokens per validated task 120000.00 exceeds 90000.00" in gate.failures
    assert "selected responses per validated task 9.00 exceeds 6.00" in gate.failures
    assert "selected progress score 0.40 below required 0.90" in gate.failures
    assert "target alignment rate 0.50 below required 1.00" in gate.failures
    assert "repo-instructions manifest rate 0.50 below required 1.00" in gate.failures
    assert "repo-instructions read-first rate 0.50 below required 1.00" in gate.failures
    assert "acceptance-rubric manifest rate 0.50 below required 1.00" in gate.failures
    assert "acceptance-rubric read-first rate 0.50 below required 1.00" in gate.failures
    assert "acceptance-rubric alignment rate 0.50 below required 1.00" in gate.failures
    assert "live cost budget overage tasks 2 exceeds 0" in gate.failures


def test_thresholds_and_runner_use_extracted_gate_boundary() -> None:
    thresholds = ComplexBenchmarkSuiteThresholds(min_validation_rate=1.0)
    summary = _summary(validation_rate=0.0)

    assert thresholds.gate(summary).status == "failed"
    assert runner_complex.complex_benchmark_suite_gate is complex_benchmark_suite_gate


def _summary(**overrides: object) -> ComplexBenchmarkSummary:
    values: dict[str, object] = {
        "benchmark": "public_issue_repair_attempts",
        "attempt_dir": "attempt",
        "task_count": 2,
        "attempted_tasks": 2,
        "reproduced_tasks": 2,
        "validated_tasks": 2,
        "failed_tasks": 0,
        "blocked_tasks": 0,
        "preflight_passed_tasks": 2,
        "preflight_skipped_tasks": 0,
        "preflight_blocked_tasks": 0,
        "sandbox_preflight_blocked_tasks": 0,
        "model_preflight_blocked_tasks": 0,
        "budget_preflight_blocked_tasks": 0,
        "patch_generated_rate": 1.0,
        "validation_rate": 1.0,
        "reproduced_input_rate": 1.0,
        "avg_trace_events": 3.0,
        "avg_runtime_nodes": 2.0,
        "failed_trace_event_count": 0,
        "avg_retry_events": 0.0,
        "retry_feedback_artifact_tasks": 0,
        "retry_feedback_artifact_count": 0,
        "retry_label_counts": {},
        "retry_failure_class_counts": {},
        "avg_deepagents_virtual_file_count": 2.0,
        "context_budgeted_tasks": 2,
        "context_budget_manifest_tasks": 2,
        "context_budget_omitted_file_count": 0,
        "avg_context_budget_omitted_files": 0.0,
        "repo_map_manifest_tasks": 2,
        "repo_instructions_manifest_tasks": 2,
        "repo_instructions_read_first_rate": 1.0,
        "acceptance_rubric_manifest_tasks": 2,
        "acceptance_rubric_read_first_rate": 1.0,
        "acceptance_rubric_aligned_tasks": 2,
        "acceptance_rubric_alignment_rate": 1.0,
        "repair_interface_manifest_tasks": 2,
        "repair_interface_read_first_rate": 1.0,
        "avg_deepagents_max_context_files": 2.0,
        "resource_budgeted_tasks": 2,
        "resource_budget_read_first_rate": 1.0,
        "avg_resource_budget_max_model_responses": 6.0,
        "avg_resource_budget_max_model_tokens": 90_000.0,
        "quality_warning_tasks": 0,
        "quality_warning_rate": 0.0,
        "target_alignment_available_tasks": 2,
        "target_aligned_tasks": 2,
        "target_misaligned_tasks": 0,
        "target_alignment_rate": 1.0,
        "avg_debuggability_score": 1.0,
        "avg_agent_trajectory_score": 1.0,
        "todo_planning_rate": 1.0,
        "constrained_filesystem_rate": 1.0,
        "specialist_review_rate": 1.0,
        "guardrails_rate": 1.0,
        "structured_output_rate": 1.0,
        "retry_feedback_rate": 1.0,
        "patch_diagnostics_rate": 1.0,
        "contextual_verifier_rate": 1.0,
        "avg_process_quality_score": 1.0,
        "process_quality_label_counts": {"solid": 2},
        "process_quality_flag_counts": {},
        "process_risky_validated_tasks": 0,
        "live_provider_tasks": 2,
        "live_cost_budgeted_tasks": 2,
        "live_cost_budget_overage_tasks": 0,
        "max_live_cost_budget_overage_usd": None,
        "model_provider": "deepagents_openai_chat",
        "response_count": 8,
        "input_tokens": 80_000,
        "output_tokens": 2_000,
        "total_tokens": 82_000,
        "estimated_cost_usd": 0.1,
        "attempted_cost_per_validated_task_usd": 0.05,
        "attempted_tokens_per_validated_task": 41_000.0,
        "attempted_responses_per_validated_task": 4.0,
        "max_attempted_task_cost_usd": 0.05,
        "max_attempted_task_tokens": 41_000,
        "max_attempted_task_responses": 4,
        "repeat_count": 1,
        "unique_task_count": 2,
        "unique_attempted_tasks": 2,
        "tasks_with_validated_attempt": 2,
        "tasks_with_failed_attempts_only": 0,
        "validated_task_pass_at_n_rate": 1.0,
        "selected_attempt_count": 2,
        "selected_validated_tasks": 2,
        "selected_validation_rate": 1.0,
        "selected_total_tokens": 82_000,
        "selected_response_count": 8,
        "selected_estimated_cost_usd": 0.1,
        "selected_virtual_file_count": 4,
        "selected_virtual_files_per_validated_task": 2.0,
        "selected_tokens_per_virtual_file": 20_500.0,
        "selected_responses_per_virtual_file": 2.0,
        "selected_context_target_available_tasks": 2,
        "selected_context_target_covered_tasks": 2,
        "selected_context_target_recall": 1.0,
        "selected_context_target_precision": 1.0,
        "selected_cost_per_validated_task_usd": 0.05,
        "selected_tokens_per_validated_task": 41_000.0,
        "selected_responses_per_validated_task": 4.0,
        "max_selected_task_cost_usd": 0.05,
        "max_selected_task_tokens": 41_000,
        "max_selected_task_responses": 4,
        "partial_progress_tasks": 0,
        "avg_progress_score": 1.0,
        "selected_avg_progress_score": 1.0,
        "failure_class_counts": {"validated": 2},
        "selected_failure_class_counts": {"validated": 2},
        "harness_layer_counts": {"validation": 2},
        "selected_harness_layer_counts": {"validation": 2},
    }
    values.update(overrides)
    return ComplexBenchmarkSummary(**values)  # type: ignore[arg-type]
