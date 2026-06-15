"""Selection policy for complex benchmark attempts."""

from __future__ import annotations

from patchsmith.evaluation_models import (
    ComplexBenchmarkResult,
    ComplexBenchmarkSelection,
)


def selected_results(
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection],
) -> list[ComplexBenchmarkResult]:
    grouped_results = results_by_task(results)
    selected: list[ComplexBenchmarkResult] = []
    for selection in selections:
        selected_result = next(
            (
                result
                for result in grouped_results.get(selection.task_id, [])
                if result.attempt_index == selection.selected_attempt_index
                and result.attempt_count == selection.selected_attempt_count
            ),
            None,
        )
        if selected_result is not None:
            selected.append(selected_result)
    return selected


def select_attempts(
    results: list[ComplexBenchmarkResult],
) -> list[ComplexBenchmarkSelection]:
    selections: list[ComplexBenchmarkSelection] = []
    for task_id, task_results in results_by_task(results).items():
        attempted = [
            result for result in task_results if result.status in {"validated", "failed"}
        ]
        if not attempted:
            continue
        selected = min(attempted, key=selection_sort_key)
        selections.append(
            ComplexBenchmarkSelection(
                task_id=task_id,
                selected_attempt_index=selected.attempt_index,
                selected_attempt_count=selected.attempt_count,
                status=selected.status,
                strict_status=selected.strict_status,
                validation_passed=selected.validation_passed,
                patch_quality_severity=selected.patch_quality_severity,
                patch_quality_codes=selected.patch_quality_codes,
                retry_event_count=selected.retry_event_count,
                response_count=selected.response_count,
                total_tokens=selected.total_tokens,
                estimated_cost_usd=selected.estimated_cost_usd,
                agent_trajectory_score=selected.agent_trajectory_score,
                report_path=selected.report_path,
                selection_reason=selection_reason(selected),
                progress_score=selected.progress_score,
                progress_stage=selected.progress_stage,
                failure_class=selected.failure_class,
            )
        )
    return selections


def results_by_task(
    results: list[ComplexBenchmarkResult],
) -> dict[str, list[ComplexBenchmarkResult]]:
    grouped: dict[str, list[ComplexBenchmarkResult]] = {}
    for index, result in enumerate(results, start=1):
        grouped.setdefault(task_key(index, result), []).append(result)
    return grouped


def task_key(index: int, result: ComplexBenchmarkResult) -> str:
    return result.task_id if result.task_id else f"row:{index}"


def selection_sort_key(result: ComplexBenchmarkResult) -> tuple[object, ...]:
    return (
        0 if result.validation_passed else 1,
        -result.progress_score,
        quality_rank(result.patch_quality_severity),
        target_alignment_rank(result),
        0 if result.patch_generated else 1,
        result.retry_event_count,
        result.failed_trace_event_count,
        optional_float_rank(result.estimated_cost_usd),
        optional_int_rank(result.total_tokens),
        -result.agent_trajectory_score,
        result.attempt_index,
    )


def selection_reason(result: ComplexBenchmarkResult) -> str:
    basis = [
        (
            "strict validated"
            if result.validation_passed
            else f"strict_status={result.strict_status}"
        ),
        f"raw_status={result.status}",
        f"quality={result.patch_quality_severity or 'unknown'}",
        f"target_alignment={result.target_alignment_status}",
        f"retries={result.retry_event_count}",
        f"progress={result.progress_score:.2f}:{result.progress_stage}",
        f"failure_class={result.failure_class}",
    ]
    if result.patch_quality_codes:
        basis.append(f"quality_codes={','.join(result.patch_quality_codes)}")
    if result.estimated_cost_usd is not None:
        basis.append(f"cost={format_cost(result.estimated_cost_usd)}")
    if result.live_cost_budget_overage_usd is not None:
        basis.append(
            f"budget_overage={format_cost(result.live_cost_budget_overage_usd)}"
        )
    if result.total_tokens is not None:
        basis.append(f"tokens={result.total_tokens}")
    if result.response_count is not None:
        basis.append(f"responses={result.response_count}")
    if result.deepagents_virtual_file_count is not None:
        basis.append(f"virtual_files={result.deepagents_virtual_file_count}")
    if (
        result.deepagents_context_budgeted
        and result.deepagents_max_context_files is not None
    ):
        basis.append(f"context_cap={result.deepagents_max_context_files}")
    if result.deepagents_context_budget_omitted_file_count is not None:
        basis.append(
            f"context_omitted={result.deepagents_context_budget_omitted_file_count}"
        )
    if result.deepagents_resource_budgeted:
        response_cap = result.deepagents_resource_budget_max_model_responses
        token_cap = result.deepagents_resource_budget_max_model_tokens
        basis.append(f"resource_cap=responses:{response_cap},tokens:{token_cap}")
    basis.append(f"trajectory={result.agent_trajectory_score:.2f}")
    return ", ".join(basis)


def quality_rank(severity: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity or "", 3)


def target_alignment_rank(result: ComplexBenchmarkResult) -> int:
    return {"aligned": 0, "unavailable": 1, "misaligned": 2}.get(
        result.target_alignment_status,
        3,
    )


def optional_float_rank(value: float | None) -> float:
    return value if value is not None else float("inf")


def optional_int_rank(value: int | None) -> int:
    return value if value is not None else 10**18


def format_cost(value: float | None) -> str:
    return f"${value:.6f}" if value is not None else "n/a"
