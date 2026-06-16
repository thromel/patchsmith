"""Summary aggregation for complex benchmark results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.evaluation.complex.selection import results_by_task as _results_by_task
from patchsmith.evaluation.complex.selection import (
    selected_results as _selected_results,
)
from patchsmith.evaluation_models import (
    ComplexBenchmarkResult,
    ComplexBenchmarkSelection,
    ComplexBenchmarkSummary,
)

LIVE_MODEL_PROVIDERS = {"openai_responses", "deepagents_openai_chat"}

__all__ = [
    "complex_summary",
    "preflight_gate_blocked_from_gates",
]


def complex_summary(
    *,
    benchmark: str,
    attempt_dir: Path,
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection],
) -> ComplexBenchmarkSummary:
    attempted = [
        result for result in results if result.patch_outcome.status in {"validated", "failed"}
    ]
    providers = sorted(
        {
            result.model_usage.provider
            for result in attempted
            if result.model_usage.provider is not None
        }
    )
    grouped_results = _results_by_task(results)
    attempted_by_task = {
        task_id: task_results
        for task_id, task_results in grouped_results.items()
        if any(result.patch_outcome.status in {"validated", "failed"} for result in task_results)
    }
    tasks_with_validated_attempt = sum(
        1
        for task_results in attempted_by_task.values()
        if any(result.patch_outcome.validation_passed for result in task_results)
    )
    tasks_with_failed_attempts_only = sum(
        1
        for task_results in attempted_by_task.values()
        if not any(result.patch_outcome.validation_passed for result in task_results)
    )
    selected_validated_tasks = sum(1 for selection in selections if selection.validation_passed)
    selected = _selected_results(results, selections)
    attempted_with_target_alignment = [
        result for result in attempted if result.patch_outcome.target_aligned is not None
    ]
    target_aligned_tasks = sum(
        1 for result in attempted_with_target_alignment if result.patch_outcome.target_aligned
    )
    (
        selected_context_target_available_tasks,
        selected_context_target_covered_tasks,
        selected_context_target_recall,
        selected_context_target_precision,
    ) = _context_target_metrics(selected)
    return ComplexBenchmarkSummary(
        benchmark=benchmark,
        attempt_dir=str(attempt_dir),
        task_count=len(results),
        attempted_tasks=len(attempted),
        reproduced_tasks=sum(1 for result in results if result.patch_outcome.reproduced),
        validated_tasks=sum(1 for result in results if result.patch_outcome.validation_passed),
        failed_tasks=sum(1 for result in attempted if not result.patch_outcome.validation_passed),
        blocked_tasks=sum(1 for result in results if result.patch_outcome.status == "blocked"),
        preflight_passed_tasks=sum(
            1 for result in results if result.repair_attempt.preflight_status == "passed"
        ),
        preflight_skipped_tasks=sum(
            1 for result in results if result.repair_attempt.preflight_status == "skipped"
        ),
        preflight_blocked_tasks=sum(
            1 for result in results if result.repair_attempt.preflight_status == "blocked"
        ),
        sandbox_preflight_blocked_tasks=sum(
            1 for result in results if _preflight_gate_blocked(result, "sandbox")
        ),
        model_preflight_blocked_tasks=sum(
            1 for result in results if _preflight_gate_blocked(result, "model")
        ),
        budget_preflight_blocked_tasks=sum(
            1 for result in results if _preflight_gate_blocked(result, "budget")
        ),
        patch_generated_rate=_rate(
            sum(1 for result in attempted if result.patch_outcome.patch_generated),
            len(attempted),
        ),
        validation_rate=_rate(
            sum(1 for result in attempted if result.patch_outcome.validation_passed),
            len(attempted),
        ),
        reproduced_input_rate=_rate(
            sum(1 for result in results if result.patch_outcome.reproduced),
            len(results),
        ),
        avg_trace_events=_average(result.trace_evidence.trace_event_count for result in attempted),
        avg_runtime_nodes=_average(
            result.trace_evidence.runtime_node_count for result in attempted
        ),
        failed_trace_event_count=sum(
            result.trace_evidence.failed_trace_event_count for result in attempted
        ),
        avg_retry_events=_average(result.trace_evidence.retry_event_count for result in attempted),
        retry_feedback_artifact_tasks=sum(
            1 for result in attempted if result.trace_evidence.retry_feedback_artifact_count > 0
        ),
        retry_feedback_artifact_count=sum(
            result.trace_evidence.retry_feedback_artifact_count for result in attempted
        ),
        retry_label_counts=_merge_label_counts(
            result.trace_evidence.retry_label_counts for result in attempted
        ),
        retry_failure_class_counts=_merge_label_counts(
            result.trace_evidence.retry_failure_class_counts for result in attempted
        ),
        avg_deepagents_virtual_file_count=_average_optional(
            result.context_evidence.virtual_file_count for result in attempted
        ),
        context_budgeted_tasks=sum(
            1 for result in attempted if result.context_evidence.context_budgeted
        ),
        context_budget_manifest_tasks=sum(
            1
            for result in attempted
            if result.context_evidence.context_budget_manifest_path is not None
        ),
        context_budget_omitted_file_count=sum(
            result.context_evidence.context_budget_omitted_file_count or 0 for result in attempted
        ),
        avg_context_budget_omitted_files=_average_optional(
            result.context_evidence.context_budget_omitted_file_count
            for result in attempted
            if result.context_evidence.context_budget_manifest_path is not None
        ),
        repo_map_manifest_tasks=sum(
            1 for result in attempted if result.context_evidence.repo_map_manifest_path is not None
        ),
        repo_instructions_manifest_tasks=sum(
            1
            for result in attempted
            if result.context_evidence.repo_instructions_manifest_path is not None
        ),
        repo_instructions_read_first_rate=_average(
            (1.0 if result.context_evidence.repo_instructions_manifest_read_first else 0.0)
            for result in attempted
            if result.context_evidence.repo_instructions_manifest_path is not None
        ),
        acceptance_rubric_manifest_tasks=sum(
            1 for result in attempted if result.rubric_evidence.manifest_path is not None
        ),
        acceptance_rubric_read_first_rate=_average(
            (1.0 if result.rubric_evidence.manifest_read_first else 0.0)
            for result in attempted
            if result.rubric_evidence.manifest_path is not None
        ),
        acceptance_rubric_aligned_tasks=sum(
            1 for result in attempted if result.rubric_evidence.aligned is True
        ),
        acceptance_rubric_alignment_rate=_average(
            1.0 if result.rubric_evidence.aligned is True else 0.0
            for result in attempted
            if result.rubric_evidence.manifest_path is not None
        ),
        repair_interface_manifest_tasks=sum(
            1
            for result in attempted
            if result.context_evidence.repair_interface_manifest_path is not None
        ),
        repair_interface_read_first_rate=_average(
            1.0 if result.context_evidence.repair_interface_manifest_read_first else 0.0
            for result in attempted
            if result.context_evidence.repair_interface_manifest_path is not None
        ),
        avg_deepagents_max_context_files=_average_optional(
            result.context_evidence.max_context_files
            for result in attempted
            if result.context_evidence.context_budgeted
        ),
        resource_budgeted_tasks=sum(
            1 for result in attempted if result.cost_evidence.resource_budgeted
        ),
        resource_budget_read_first_rate=_average(
            1.0 if result.cost_evidence.resource_budget_read_first else 0.0
            for result in attempted
            if result.cost_evidence.resource_budgeted
        ),
        avg_resource_budget_max_model_responses=_average_optional(
            result.cost_evidence.resource_budget_max_model_responses
            for result in attempted
            if result.cost_evidence.resource_budgeted
        ),
        avg_resource_budget_max_model_tokens=_average_optional(
            result.cost_evidence.resource_budget_max_model_tokens
            for result in attempted
            if result.cost_evidence.resource_budgeted
        ),
        quality_warning_tasks=sum(
            1 for result in attempted if result.patch_outcome.quality_warning
        ),
        quality_warning_rate=_rate(
            sum(1 for result in attempted if result.patch_outcome.quality_warning),
            len(attempted),
        ),
        target_alignment_available_tasks=len(attempted_with_target_alignment),
        target_aligned_tasks=target_aligned_tasks,
        target_misaligned_tasks=(len(attempted_with_target_alignment) - target_aligned_tasks),
        target_alignment_rate=_rate(
            target_aligned_tasks,
            len(attempted_with_target_alignment),
        ),
        avg_debuggability_score=_average(
            result.process_quality.debuggability_score for result in attempted
        ),
        avg_agent_trajectory_score=_average(
            result.process_quality.agent_trajectory_score for result in attempted
        ),
        todo_planning_rate=_average(
            1.0 if result.process_quality.todo_planning else 0.0 for result in attempted
        ),
        constrained_filesystem_rate=_average(
            1.0 if result.process_quality.constrained_filesystem else 0.0 for result in attempted
        ),
        specialist_review_rate=_average(
            1.0 if result.process_quality.specialist_review else 0.0 for result in attempted
        ),
        guardrails_rate=_average(
            1.0 if result.process_quality.guardrails else 0.0 for result in attempted
        ),
        structured_output_rate=_average(
            1.0 if result.process_quality.structured_output else 0.0 for result in attempted
        ),
        retry_feedback_rate=_average(
            1.0 if result.process_quality.retry_feedback else 0.0 for result in attempted
        ),
        patch_diagnostics_rate=_average(
            1.0 if result.process_quality.patch_diagnostics else 0.0 for result in attempted
        ),
        contextual_verifier_rate=_average(
            1.0 if result.process_quality.contextual_verifier else 0.0 for result in attempted
        ),
        avg_process_quality_score=_average(result.process_quality.score for result in attempted),
        process_quality_label_counts=_count_labels(
            result.process_quality.label for result in attempted
        ),
        process_quality_flag_counts=_count_labels(
            flag for result in attempted for flag in result.process_quality.flags
        ),
        process_risky_validated_tasks=sum(
            1
            for result in attempted
            if result.patch_outcome.validation_passed and result.process_quality.label == "risky"
        ),
        live_provider_tasks=sum(
            1 for result in attempted if result.model_usage.provider in LIVE_MODEL_PROVIDERS
        ),
        live_cost_budgeted_tasks=sum(
            1 for result in attempted if result.cost_evidence.live_cost_budget_usd is not None
        ),
        live_cost_budget_overage_tasks=sum(
            1 for result in attempted if result.cost_evidence.live_cost_budget_overage
        ),
        max_live_cost_budget_overage_usd=_max_optional_float(
            result.cost_evidence.live_cost_budget_overage_usd for result in attempted
        ),
        model_provider=",".join(providers) if providers else None,
        response_count=_sum_optional(result.model_usage.response_count for result in attempted),
        input_tokens=_sum_optional(result.model_usage.input_tokens for result in attempted),
        output_tokens=_sum_optional(result.model_usage.output_tokens for result in attempted),
        total_tokens=_sum_optional(result.model_usage.total_tokens for result in attempted),
        estimated_cost_usd=_sum_optional_float(
            result.model_usage.estimated_cost_usd for result in attempted
        ),
        attempted_cost_per_validated_task_usd=_per_validated_result_cost(
            attempted,
        ),
        attempted_tokens_per_validated_task=_per_validated_result_tokens(
            attempted,
        ),
        attempted_responses_per_validated_task=_per_validated_result_responses(
            attempted,
        ),
        max_attempted_task_cost_usd=_max_optional_float(
            result.model_usage.estimated_cost_usd for result in attempted
        ),
        max_attempted_task_tokens=_max_optional(
            result.model_usage.total_tokens for result in attempted
        ),
        max_attempted_task_responses=_max_optional(
            result.model_usage.response_count for result in attempted
        ),
        repeat_count=max(
            (result.repair_attempt.attempt_count for result in results),
            default=1,
        ),
        unique_task_count=len(grouped_results),
        unique_attempted_tasks=len(attempted_by_task),
        tasks_with_validated_attempt=tasks_with_validated_attempt,
        tasks_with_failed_attempts_only=tasks_with_failed_attempts_only,
        validated_task_pass_at_n_rate=_rate(
            tasks_with_validated_attempt,
            len(attempted_by_task),
        ),
        selected_attempt_count=len(selections),
        selected_validated_tasks=selected_validated_tasks,
        selected_validation_rate=_rate(
            selected_validated_tasks,
            len(selections),
        ),
        selected_total_tokens=_sum_optional(selection.total_tokens for selection in selections),
        selected_response_count=_sum_optional(selection.response_count for selection in selections),
        selected_estimated_cost_usd=_sum_optional_float(
            selection.estimated_cost_usd for selection in selections
        ),
        selected_virtual_file_count=_sum_optional(
            result.context_evidence.virtual_file_count for result in selected
        ),
        selected_virtual_files_per_validated_task=(
            _selected_virtual_files_per_validated_task(
                selected,
                selected_validated_tasks,
            )
        ),
        selected_tokens_per_virtual_file=_tokens_per_virtual_file(selected),
        selected_responses_per_virtual_file=_responses_per_virtual_file(selected),
        selected_context_target_available_tasks=(selected_context_target_available_tasks),
        selected_context_target_covered_tasks=selected_context_target_covered_tasks,
        selected_context_target_recall=selected_context_target_recall,
        selected_context_target_precision=selected_context_target_precision,
        selected_cost_per_validated_task_usd=_per_validated_selection_cost(
            selections,
        ),
        selected_tokens_per_validated_task=_per_validated_selection_tokens(
            selections,
        ),
        selected_responses_per_validated_task=_per_validated_selection_responses(
            selections,
        ),
        max_selected_task_cost_usd=_max_optional_float(
            selection.estimated_cost_usd for selection in selections
        ),
        max_selected_task_tokens=_max_optional(selection.total_tokens for selection in selections),
        max_selected_task_responses=_max_optional(
            selection.response_count for selection in selections
        ),
        partial_progress_tasks=sum(
            1
            for result in attempted
            if not result.patch_outcome.validation_passed
            and result.patch_outcome.progress_score >= 0.45
        ),
        avg_progress_score=_average(result.patch_outcome.progress_score for result in attempted),
        selected_avg_progress_score=_average(
            result.patch_outcome.progress_score for result in selected
        ),
        failure_class_counts=_count_labels(
            result.patch_outcome.failure_class for result in attempted
        ),
        selected_failure_class_counts=_count_labels(
            result.patch_outcome.failure_class for result in selected
        ),
        harness_layer_counts=_count_labels(
            result.patch_outcome.harness_layer for result in attempted
        ),
        selected_harness_layer_counts=_count_labels(
            result.patch_outcome.harness_layer for result in selected
        ),
    )


def _preflight_gate_blocked(result: ComplexBenchmarkResult, name: str) -> bool:
    return preflight_gate_blocked_from_gates(
        result.repair_attempt.preflight_gates or [],
        name,
    )


def preflight_gate_blocked_from_gates(
    gates: list[dict[str, str]],
    name: str,
) -> bool:
    return any(gate.get("name") == name and gate.get("status") == "blocked" for gate in gates)


def _average(values: Any) -> float:
    numbers = [float(value) for value in values]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _average_optional(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _sum_optional(values: Any) -> int | None:
    numbers = [int(value) for value in values if value is not None]
    return sum(numbers) if numbers else None


def _sum_optional_float(values: Any) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) if numbers else None


def _max_optional(values: Any) -> int | None:
    numbers = [int(value) for value in values if value is not None]
    return max(numbers) if numbers else None


def _max_optional_float(values: Any) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return max(numbers) if numbers else None


def _count_labels(labels: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in labels:
        if not isinstance(label, str) or not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _merge_label_counts(counts: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for count_map in counts:
        if not isinstance(count_map, dict):
            continue
        for label, count in count_map.items():
            if not isinstance(label, str) or not label:
                continue
            try:
                parsed_count = int(count)
            except (TypeError, ValueError):
                continue
            if parsed_count <= 0:
                continue
            merged[label] = merged.get(label, 0) + parsed_count
    return dict(sorted(merged.items()))


def _per_validated_result_cost(
    attempted: list[ComplexBenchmarkResult],
) -> float | None:
    return _cost_per_success(
        costs=[result.model_usage.estimated_cost_usd for result in attempted],
        success_count=sum(1 for result in attempted if result.patch_outcome.validation_passed),
    )


def _per_validated_result_tokens(
    attempted: list[ComplexBenchmarkResult],
) -> float | None:
    return _tokens_per_success(
        tokens=[result.model_usage.total_tokens for result in attempted],
        success_count=sum(1 for result in attempted if result.patch_outcome.validation_passed),
    )


def _per_validated_result_responses(
    attempted: list[ComplexBenchmarkResult],
) -> float | None:
    return _tokens_per_success(
        tokens=[result.model_usage.response_count for result in attempted],
        success_count=sum(1 for result in attempted if result.patch_outcome.validation_passed),
    )


def _per_validated_selection_cost(
    selections: list[ComplexBenchmarkSelection],
) -> float | None:
    return _cost_per_success(
        costs=[selection.estimated_cost_usd for selection in selections],
        success_count=sum(1 for selection in selections if selection.validation_passed),
    )


def _per_validated_selection_tokens(
    selections: list[ComplexBenchmarkSelection],
) -> float | None:
    return _tokens_per_success(
        tokens=[selection.total_tokens for selection in selections],
        success_count=sum(1 for selection in selections if selection.validation_passed),
    )


def _per_validated_selection_responses(
    selections: list[ComplexBenchmarkSelection],
) -> float | None:
    return _tokens_per_success(
        tokens=[selection.response_count for selection in selections],
        success_count=sum(1 for selection in selections if selection.validation_passed),
    )


def _selected_virtual_files_per_validated_task(
    selected_results: list[ComplexBenchmarkResult],
    selected_validated_tasks: int,
) -> float | None:
    virtual_file_count = _sum_optional(
        result.context_evidence.virtual_file_count for result in selected_results
    )
    if selected_validated_tasks == 0 or virtual_file_count is None:
        return None
    return virtual_file_count / selected_validated_tasks


def _tokens_per_virtual_file(
    selected_results: list[ComplexBenchmarkResult],
) -> float | None:
    token_pairs = [
        (result.model_usage.total_tokens, result.context_evidence.virtual_file_count)
        for result in selected_results
        if result.model_usage.total_tokens is not None
        and result.context_evidence.virtual_file_count is not None
        and result.context_evidence.virtual_file_count > 0
    ]
    if not token_pairs:
        return None
    total_tokens = sum(tokens for tokens, _virtual_files in token_pairs)
    total_virtual_files = sum(virtual_files for _tokens, virtual_files in token_pairs)
    return total_tokens / total_virtual_files if total_virtual_files else None


def _responses_per_virtual_file(
    selected_results: list[ComplexBenchmarkResult],
) -> float | None:
    response_pairs = [
        (
            result.model_usage.response_count,
            result.context_evidence.virtual_file_count,
        )
        for result in selected_results
        if result.model_usage.response_count is not None
        and result.context_evidence.virtual_file_count is not None
        and result.context_evidence.virtual_file_count > 0
    ]
    if not response_pairs:
        return None
    total_responses = sum(responses for responses, _virtual_files in response_pairs)
    total_virtual_files = sum(virtual_files for _responses, virtual_files in response_pairs)
    return total_responses / total_virtual_files if total_virtual_files else None


def _context_target_metrics(
    selected_results: list[ComplexBenchmarkResult],
) -> tuple[int, int, float | None, float | None]:
    available = [
        result
        for result in selected_results
        if (
            result.patch_outcome.localized_target_paths
            and result.context_evidence.virtual_file_paths
        )
    ]
    if not available:
        return 0, 0, None, None

    covered_tasks = 0
    covered_targets = 0
    total_targets = 0
    targeted_context_paths = 0
    total_context_paths = 0
    for result in available:
        targets = set(result.patch_outcome.localized_target_paths)
        context_paths = set(result.context_evidence.virtual_file_paths)
        covered = targets & context_paths
        total_targets += len(targets)
        covered_targets += len(covered)
        total_context_paths += len(context_paths)
        targeted_context_paths += len(context_paths & targets)
        if covered:
            covered_tasks += 1

    recall = covered_targets / total_targets if total_targets else None
    precision = targeted_context_paths / total_context_paths if total_context_paths else None
    return len(available), covered_tasks, recall, precision


def _cost_per_success(
    *,
    costs: list[float | None],
    success_count: int,
) -> float | None:
    if success_count == 0 or not costs or any(cost is None for cost in costs):
        return None
    return sum(float(cost) for cost in costs if cost is not None) / success_count


def _tokens_per_success(
    *,
    tokens: list[int | None],
    success_count: int,
) -> float | None:
    if success_count == 0 or not tokens or any(value is None for value in tokens):
        return None
    return sum(float(value) for value in tokens if value is not None) / success_count
