"""Gate evaluation for complex benchmark suites."""

from __future__ import annotations

from patchsmith.evaluation.complex.models import ComplexBenchmarkSuiteGate
from patchsmith.evaluation.complex.thresholds import (
    complex_threshold_kwargs_from_mapping,
)
from patchsmith.evaluation_models import ComplexBenchmarkSummary


def complex_benchmark_suite_gate(
    summary: ComplexBenchmarkSummary,
    *,
    min_validation_rate: float | None = None,
    min_live_provider_tasks: int | None = None,
    min_unique_tasks: int | None = None,
    max_attempted_cost_per_validated_task_usd: float | None = None,
    max_attempted_tokens_per_validated_task: float | None = None,
    max_attempted_responses_per_validated_task: float | None = None,
    max_attempted_task_cost_usd: float | None = None,
    max_attempted_task_tokens: int | None = None,
    max_attempted_task_responses: int | None = None,
    max_selected_cost_per_validated_task_usd: float | None = None,
    max_selected_tokens_per_validated_task: float | None = None,
    max_selected_responses_per_validated_task: float | None = None,
    max_selected_virtual_files_per_validated_task: float | None = None,
    max_selected_tokens_per_virtual_file: float | None = None,
    max_selected_responses_per_virtual_file: float | None = None,
    min_selected_progress_score: float | None = None,
    min_selected_context_target_recall: float | None = None,
    min_selected_context_target_precision: float | None = None,
    max_selected_task_cost_usd: float | None = None,
    max_selected_task_tokens: int | None = None,
    max_selected_task_responses: int | None = None,
    max_live_cost_budget_overage_tasks: int | None = None,
    min_agent_trajectory_score: float | None = None,
    min_contextual_verifier_rate: float | None = None,
    min_process_quality_score: float | None = None,
    max_process_risky_validated_tasks: int | None = None,
    min_target_alignment_rate: float | None = None,
    min_repo_instructions_manifest_rate: float | None = None,
    min_repo_instructions_read_first_rate: float | None = None,
    min_acceptance_rubric_manifest_rate: float | None = None,
    min_acceptance_rubric_read_first_rate: float | None = None,
    min_acceptance_rubric_alignment_rate: float | None = None,
) -> ComplexBenchmarkSuiteGate:
    failures: list[str] = []
    if (
        min_validation_rate is not None
        and summary.validation_rate < min_validation_rate
    ):
        failures.append(
            "validation_rate "
            f"{summary.validation_rate:.2f} below required {min_validation_rate:.2f}"
        )
    if (
        min_live_provider_tasks is not None
        and summary.live_provider_tasks < min_live_provider_tasks
    ):
        failures.append(
            "live_provider_tasks "
            f"{summary.live_provider_tasks} below required {min_live_provider_tasks}"
        )
    if min_unique_tasks is not None and summary.unique_task_count < min_unique_tasks:
        failures.append(
            f"unique_task_count {summary.unique_task_count} below required {min_unique_tasks}"
        )
    if max_attempted_cost_per_validated_task_usd is not None:
        attempted_cost = summary.attempted_cost_per_validated_task_usd
        if attempted_cost is None:
            failures.append("attempted cost per validated task is unavailable")
        elif attempted_cost > max_attempted_cost_per_validated_task_usd:
            failures.append(
                "attempted cost per validated task "
                f"{_format_cost(attempted_cost)} exceeds "
                f"{_format_cost(max_attempted_cost_per_validated_task_usd)}"
            )
    if max_attempted_tokens_per_validated_task is not None:
        attempted_tokens = summary.attempted_tokens_per_validated_task
        if attempted_tokens is None:
            failures.append("attempted tokens per validated task is unavailable")
        elif attempted_tokens > max_attempted_tokens_per_validated_task:
            failures.append(
                "attempted tokens per validated task "
                f"{attempted_tokens:.2f} exceeds "
                f"{max_attempted_tokens_per_validated_task:.2f}"
            )
    if max_attempted_responses_per_validated_task is not None:
        attempted_responses = summary.attempted_responses_per_validated_task
        if attempted_responses is None:
            failures.append("attempted responses per validated task is unavailable")
        elif attempted_responses > max_attempted_responses_per_validated_task:
            failures.append(
                "attempted responses per validated task "
                f"{attempted_responses:.2f} exceeds "
                f"{max_attempted_responses_per_validated_task:.2f}"
            )
    if max_attempted_task_cost_usd is not None:
        max_attempted_cost = summary.max_attempted_task_cost_usd
        if max_attempted_cost is None:
            failures.append("max attempted task cost is unavailable")
        elif max_attempted_cost > max_attempted_task_cost_usd:
            failures.append(
                "max attempted task cost "
                f"{_format_cost(max_attempted_cost)} exceeds "
                f"{_format_cost(max_attempted_task_cost_usd)}"
            )
    if max_attempted_task_tokens is not None:
        max_attempted_tokens = summary.max_attempted_task_tokens
        if max_attempted_tokens is None:
            failures.append("max attempted task tokens is unavailable")
        elif max_attempted_tokens > max_attempted_task_tokens:
            failures.append(
                "max attempted task tokens "
                f"{max_attempted_tokens} exceeds {max_attempted_task_tokens}"
            )
    if max_attempted_task_responses is not None:
        max_attempted_responses = summary.max_attempted_task_responses
        if max_attempted_responses is None:
            failures.append("max attempted task responses is unavailable")
        elif max_attempted_responses > max_attempted_task_responses:
            failures.append(
                "max attempted task responses "
                f"{max_attempted_responses} exceeds {max_attempted_task_responses}"
            )
    if max_selected_cost_per_validated_task_usd is not None:
        cost = summary.selected_cost_per_validated_task_usd
        if cost is None:
            failures.append("selected cost per validated task is unavailable")
        elif cost > max_selected_cost_per_validated_task_usd:
            failures.append(
                "selected cost per validated task "
                f"{_format_cost(cost)} exceeds "
                f"{_format_cost(max_selected_cost_per_validated_task_usd)}"
            )
    if max_selected_tokens_per_validated_task is not None:
        tokens = summary.selected_tokens_per_validated_task
        if tokens is None:
            failures.append("selected tokens per validated task is unavailable")
        elif tokens > max_selected_tokens_per_validated_task:
            failures.append(
                "selected tokens per validated task "
                f"{tokens:.2f} exceeds {max_selected_tokens_per_validated_task:.2f}"
            )
    if max_selected_responses_per_validated_task is not None:
        responses = summary.selected_responses_per_validated_task
        if responses is None:
            failures.append("selected responses per validated task is unavailable")
        elif responses > max_selected_responses_per_validated_task:
            failures.append(
                "selected responses per validated task "
                f"{responses:.2f} exceeds "
                f"{max_selected_responses_per_validated_task:.2f}"
            )
    if max_selected_virtual_files_per_validated_task is not None:
        virtual_files = summary.selected_virtual_files_per_validated_task
        if virtual_files is None:
            failures.append("selected virtual files per validated task is unavailable")
        elif virtual_files > max_selected_virtual_files_per_validated_task:
            failures.append(
                "selected virtual files per validated task "
                f"{virtual_files:.2f} exceeds "
                f"{max_selected_virtual_files_per_validated_task:.2f}"
            )
    if max_selected_tokens_per_virtual_file is not None:
        tokens = summary.selected_tokens_per_virtual_file
        if tokens is None:
            failures.append("selected tokens per virtual file is unavailable")
        elif tokens > max_selected_tokens_per_virtual_file:
            failures.append(
                "selected tokens per virtual file "
                f"{tokens:.2f} exceeds {max_selected_tokens_per_virtual_file:.2f}"
            )
    if max_selected_responses_per_virtual_file is not None:
        responses = summary.selected_responses_per_virtual_file
        if responses is None:
            failures.append("selected responses per virtual file is unavailable")
        elif responses > max_selected_responses_per_virtual_file:
            failures.append(
                "selected responses per virtual file "
                f"{responses:.2f} exceeds "
                f"{max_selected_responses_per_virtual_file:.2f}"
            )
    if min_selected_progress_score is not None:
        if summary.selected_attempt_count == 0:
            failures.append("selected progress score is unavailable")
        elif summary.selected_avg_progress_score < min_selected_progress_score:
            failures.append(
                "selected progress score "
                f"{summary.selected_avg_progress_score:.2f} below required "
                f"{min_selected_progress_score:.2f}"
            )
    if min_selected_context_target_recall is not None:
        recall = summary.selected_context_target_recall
        if recall is None:
            failures.append("selected context-target recall is unavailable")
        elif recall < min_selected_context_target_recall:
            failures.append(
                "selected context-target recall "
                f"{recall:.2f} below required "
                f"{min_selected_context_target_recall:.2f}"
            )
    if min_selected_context_target_precision is not None:
        precision = summary.selected_context_target_precision
        if precision is None:
            failures.append("selected context-target precision is unavailable")
        elif precision < min_selected_context_target_precision:
            failures.append(
                "selected context-target precision "
                f"{precision:.2f} below required "
                f"{min_selected_context_target_precision:.2f}"
            )
    if max_selected_task_cost_usd is not None:
        max_selected_cost = summary.max_selected_task_cost_usd
        if max_selected_cost is None:
            failures.append("max selected task cost is unavailable")
        elif max_selected_cost > max_selected_task_cost_usd:
            failures.append(
                "max selected task cost "
                f"{_format_cost(max_selected_cost)} exceeds "
                f"{_format_cost(max_selected_task_cost_usd)}"
            )
    if max_selected_task_tokens is not None:
        max_selected_tokens = summary.max_selected_task_tokens
        if max_selected_tokens is None:
            failures.append("max selected task tokens is unavailable")
        elif max_selected_tokens > max_selected_task_tokens:
            failures.append(
                "max selected task tokens "
                f"{max_selected_tokens} exceeds {max_selected_task_tokens}"
            )
    if max_selected_task_responses is not None:
        max_selected_responses = summary.max_selected_task_responses
        if max_selected_responses is None:
            failures.append("max selected task responses is unavailable")
        elif max_selected_responses > max_selected_task_responses:
            failures.append(
                "max selected task responses "
                f"{max_selected_responses} exceeds {max_selected_task_responses}"
            )
    if (
        max_live_cost_budget_overage_tasks is not None
        and summary.live_cost_budget_overage_tasks
        > max_live_cost_budget_overage_tasks
    ):
        failures.append(
            "live cost budget overage tasks "
            f"{summary.live_cost_budget_overage_tasks} exceeds "
            f"{max_live_cost_budget_overage_tasks}"
        )
    if (
        min_agent_trajectory_score is not None
        and summary.avg_agent_trajectory_score < min_agent_trajectory_score
    ):
        failures.append(
            "average agent trajectory "
            f"{summary.avg_agent_trajectory_score:.2f} below required "
            f"{min_agent_trajectory_score:.2f}"
        )
    if (
        min_contextual_verifier_rate is not None
        and summary.contextual_verifier_rate < min_contextual_verifier_rate
    ):
        failures.append(
            "contextual verifier rate "
            f"{summary.contextual_verifier_rate:.2f} below required "
            f"{min_contextual_verifier_rate:.2f}"
        )
    if (
        min_process_quality_score is not None
        and summary.avg_process_quality_score < min_process_quality_score
    ):
        failures.append(
            "average process quality "
            f"{summary.avg_process_quality_score:.2f} below required "
            f"{min_process_quality_score:.2f}"
        )
    if (
        max_process_risky_validated_tasks is not None
        and summary.process_risky_validated_tasks
        > max_process_risky_validated_tasks
    ):
        failures.append(
            "process-risky validated tasks "
            f"{summary.process_risky_validated_tasks} exceeds "
            f"{max_process_risky_validated_tasks}"
        )
    if (
        min_target_alignment_rate is not None
        and summary.target_alignment_rate < min_target_alignment_rate
    ):
        failures.append(
            "target alignment rate "
            f"{summary.target_alignment_rate:.2f} below required "
            f"{min_target_alignment_rate:.2f}"
        )
    if min_repo_instructions_manifest_rate is not None:
        manifest_rate = _rate(
            summary.repo_instructions_manifest_tasks,
            summary.attempted_tasks,
        )
        if manifest_rate < min_repo_instructions_manifest_rate:
            failures.append(
                "repo-instructions manifest rate "
                f"{manifest_rate:.2f} below required "
                f"{min_repo_instructions_manifest_rate:.2f}"
            )
    if (
        min_repo_instructions_read_first_rate is not None
        and summary.repo_instructions_read_first_rate
        < min_repo_instructions_read_first_rate
    ):
        failures.append(
            "repo-instructions read-first rate "
            f"{summary.repo_instructions_read_first_rate:.2f} below required "
            f"{min_repo_instructions_read_first_rate:.2f}"
        )
    if min_acceptance_rubric_manifest_rate is not None:
        manifest_rate = _rate(
            summary.acceptance_rubric_manifest_tasks,
            summary.attempted_tasks,
        )
        if manifest_rate < min_acceptance_rubric_manifest_rate:
            failures.append(
                "acceptance-rubric manifest rate "
                f"{manifest_rate:.2f} below required "
                f"{min_acceptance_rubric_manifest_rate:.2f}"
            )
    if (
        min_acceptance_rubric_read_first_rate is not None
        and summary.acceptance_rubric_read_first_rate
        < min_acceptance_rubric_read_first_rate
    ):
        failures.append(
            "acceptance-rubric read-first rate "
            f"{summary.acceptance_rubric_read_first_rate:.2f} below required "
            f"{min_acceptance_rubric_read_first_rate:.2f}"
        )
    if (
        min_acceptance_rubric_alignment_rate is not None
        and summary.acceptance_rubric_alignment_rate
        < min_acceptance_rubric_alignment_rate
    ):
        failures.append(
            "acceptance-rubric alignment rate "
            f"{summary.acceptance_rubric_alignment_rate:.2f} below required "
            f"{min_acceptance_rubric_alignment_rate:.2f}"
        )
    return ComplexBenchmarkSuiteGate(
        status="failed" if failures else "passed",
        failures=tuple(failures),
        **complex_threshold_kwargs_from_mapping(locals()),
    )


def _format_cost(value: float | None) -> str:
    return f"${value:.6f}" if value is not None else "n/a"


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
