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
                if (result.repair_attempt.attempt_index == selection.selected_attempt_index)
                and (result.repair_attempt.attempt_count == selection.selected_attempt_count)
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
            result
            for result in task_results
            if result.patch_outcome.status in {"validated", "failed"}
        ]
        if not attempted:
            continue
        selected = min(attempted, key=selection_sort_key)
        attempt = selected.repair_attempt
        outcome = selected.patch_outcome
        trace = selected.trace_evidence
        usage = selected.model_usage
        process = selected.process_quality
        selections.append(
            ComplexBenchmarkSelection(
                task_id=task_id,
                selected_attempt_index=attempt.attempt_index,
                selected_attempt_count=attempt.attempt_count,
                status=outcome.status,
                strict_status=outcome.strict_status,
                validation_passed=outcome.validation_passed,
                patch_quality_severity=outcome.quality_severity,
                patch_quality_codes=outcome.quality_codes,
                retry_event_count=trace.retry_event_count,
                response_count=usage.response_count,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
                agent_trajectory_score=process.agent_trajectory_score,
                report_path=trace.report_path,
                selection_reason=selection_reason(selected),
                progress_score=outcome.progress_score,
                progress_stage=outcome.progress_stage,
                failure_class=outcome.failure_class,
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
    attempt = result.repair_attempt
    outcome = result.patch_outcome
    trace = result.trace_evidence
    usage = result.model_usage
    process = result.process_quality
    return (
        0 if outcome.validation_passed else 1,
        -outcome.progress_score,
        quality_rank(outcome.quality_severity),
        target_alignment_rank(result),
        0 if outcome.patch_generated else 1,
        trace.retry_event_count,
        trace.failed_trace_event_count,
        optional_float_rank(usage.estimated_cost_usd),
        optional_int_rank(usage.total_tokens),
        -process.agent_trajectory_score,
        attempt.attempt_index,
    )


def selection_reason(result: ComplexBenchmarkResult) -> str:
    outcome = result.patch_outcome
    context = result.context_evidence
    usage = result.model_usage
    cost = result.cost_evidence
    process = result.process_quality
    basis = [
        (
            "strict validated"
            if outcome.validation_passed
            else f"strict_status={outcome.strict_status}"
        ),
        f"raw_status={outcome.status}",
        f"quality={outcome.quality_severity or 'unknown'}",
        f"target_alignment={outcome.target_alignment_status}",
        f"retries={result.trace_evidence.retry_event_count}",
        f"progress={outcome.progress_score:.2f}:{outcome.progress_stage}",
        f"failure_class={outcome.failure_class}",
    ]
    if outcome.quality_codes:
        basis.append(f"quality_codes={','.join(outcome.quality_codes)}")
    if usage.estimated_cost_usd is not None:
        basis.append(f"cost={format_cost(usage.estimated_cost_usd)}")
    if cost.live_cost_budget_overage_usd is not None:
        basis.append(f"budget_overage={format_cost(cost.live_cost_budget_overage_usd)}")
    if usage.total_tokens is not None:
        basis.append(f"tokens={usage.total_tokens}")
    if usage.response_count is not None:
        basis.append(f"responses={usage.response_count}")
    if context.virtual_file_count is not None:
        basis.append(f"virtual_files={context.virtual_file_count}")
    if context.context_budgeted and context.max_context_files is not None:
        basis.append(f"context_cap={context.max_context_files}")
    if context.context_budget_omitted_file_count is not None:
        basis.append(f"context_omitted={context.context_budget_omitted_file_count}")
    if cost.resource_budgeted:
        response_cap = cost.resource_budget_max_model_responses
        token_cap = cost.resource_budget_max_model_tokens
        basis.append(f"resource_cap=responses:{response_cap},tokens:{token_cap}")
    basis.append(f"trajectory={process.agent_trajectory_score:.2f}")
    return ", ".join(basis)


def quality_rank(severity: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity or "", 3)


def target_alignment_rank(result: ComplexBenchmarkResult) -> int:
    return {"aligned": 0, "unavailable": 1, "misaligned": 2}.get(
        result.patch_outcome.target_alignment_status,
        3,
    )


def optional_float_rank(value: float | None) -> float:
    return value if value is not None else float("inf")


def optional_int_rank(value: int | None) -> int:
    return value if value is not None else 10**18


def format_cost(value: float | None) -> str:
    return f"${value:.6f}" if value is not None else "n/a"
