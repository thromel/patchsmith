"""Evaluation runners repair (split from evaluation.py)."""

from __future__ import annotations

import csv
import time
from collections.abc import Iterable
from pathlib import Path

from patchsmith.artifacts import sum_optional_float as _sum_optional_float
from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _average,
    _model_usage_from_trace,
    _patch_quality_from_trace,
    _sum_optional,
    _trace_metrics_from_trace,
)
from patchsmith.evaluation.seeded import load_seeded_tasks
from patchsmith.evaluation_models import (
    RepairEvalResult,
    RepairEvalSummary,
)
from patchsmith.models import RunRequest
from patchsmith.patch_quality import assess_diff_quality
from patchsmith.repair_reports import (
    render_repair_eval_report,
)
from patchsmith.workflow import RepairRunner


def run_repair_evaluation(
    *,
    dataset_dir: Path,
    runtime: str,
    planner: str = "heuristic",
    max_retries: int = 0,
    max_tasks: int | None = None,
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> tuple[list[RepairEvalResult], RepairEvalSummary]:
    tasks = load_seeded_tasks(dataset_dir)
    if max_tasks is not None and max_tasks > 0:
        tasks = tasks[:max_tasks]
    output_dir.mkdir(parents=True, exist_ok=True)
    run_artifacts_dir = output_dir / "run_artifacts"
    runner = RepairRunner(artifacts_dir=run_artifacts_dir)
    results: list[RepairEvalResult] = []

    for task in tasks:
        started = time.perf_counter()
        try:
            result = runner.run(
                RunRequest(
                    repo=str(task.repo),
                    issue_text=task.issue_text,
                    test_command=task.test_command,
                    runtime=runtime,
                    planner=planner,
                    max_retries=max_retries,
                    context_provider=context_provider,
                    retrieval_strategy=context_provider,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                )
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            final_diff = result.final_diff_path.read_text(encoding="utf-8")
            test_exit_code = result.test_result.exit_code if result.test_result else None
            usage = _model_usage_from_trace(result.trace_path)
            trace_metrics = _trace_metrics_from_trace(result.trace_path)
            patch_quality = _patch_quality_from_trace(result.trace_path)
            if patch_quality["patch_quality_severity"] is None and final_diff.strip():
                diff_quality = assess_diff_quality(final_diff)
                patch_quality = {
                    "patch_quality_severity": diff_quality.severity,
                    "patch_quality_warning": diff_quality.severity == "high",
                }
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status=result.status,
                    error=None,
                    patch_generated=bool(final_diff.strip()),
                    targeted_tests_passed=test_exit_code == 0,
                    test_exit_code=test_exit_code,
                    report_path=str(result.report_path),
                    trace_path=str(result.trace_path),
                    final_diff_path=str(result.final_diff_path),
                    retrieved_files=[context.path for context in result.retrieved_context],
                    latency_ms=latency_ms,
                    patch_quality_severity=patch_quality["patch_quality_severity"],
                    patch_quality_warning=patch_quality["patch_quality_warning"],
                    trace_event_count=trace_metrics["trace_event_count"],
                    runtime_node_count=trace_metrics["runtime_node_count"],
                    failed_trace_event_count=trace_metrics["failed_trace_event_count"],
                    retry_event_count=trace_metrics["retry_event_count"],
                    retry_labels=trace_metrics["retry_labels"],
                    retry_label_counts=trace_metrics["retry_label_counts"],
                    debuggability_score=trace_metrics["debuggability_score"],
                    agent_trajectory_score=trace_metrics["agent_trajectory_score"],
                    todo_planning=trace_metrics["todo_planning"],
                    constrained_filesystem=trace_metrics["constrained_filesystem"],
                    specialist_review=trace_metrics["specialist_review"],
                    guardrails=trace_metrics["guardrails"],
                    structured_output=trace_metrics["structured_output"],
                    retry_feedback=trace_metrics["retry_feedback"],
                    patch_diagnostics=trace_metrics["patch_diagnostics"],
                    contextual_verifier=trace_metrics["contextual_verifier"],
                    model_provider=usage["model_provider"],
                    response_count=usage["response_count"],
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                    estimated_cost_usd=usage["estimated_cost_usd"],
                )
            )
        except Exception as error:
            latency_ms = int((time.perf_counter() - started) * 1000)
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status="failed",
                    error=str(error),
                    patch_generated=False,
                    targeted_tests_passed=False,
                    test_exit_code=None,
                    report_path=None,
                    trace_path=None,
                    final_diff_path=None,
                    retrieved_files=[],
                    latency_ms=latency_ms,
                )
            )

    summary = summarize_repair_results(
        results,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
    )
    write_repair_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_repair_results(
    results: list[RepairEvalResult],
    *,
    runtime: str,
    planner: str,
    context_provider: str,
) -> RepairEvalSummary:
    completed = [result for result in results if result.status == "completed"]
    providers = sorted(
        {result.model_provider for result in completed if result.model_provider is not None}
    )
    return RepairEvalSummary(
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        attempted_tasks=len(results),
        completed_tasks=len(completed),
        patch_generated_rate=_average(
            1.0 if result.patch_generated else 0.0 for result in completed
        ),
        targeted_test_pass_rate=_average(
            1.0 if result.targeted_tests_passed else 0.0 for result in completed
        ),
        avg_latency_ms=_average(result.latency_ms for result in completed),
        avg_trace_events=_average(result.trace_event_count for result in completed),
        avg_runtime_nodes=_average(result.runtime_node_count for result in completed),
        failed_trace_event_count=sum(result.failed_trace_event_count for result in completed),
        avg_retry_events=_average(result.retry_event_count for result in completed),
        retry_label_counts=_merge_retry_label_counts(
            result.retry_label_counts for result in completed
        ),
        patch_quality_warning_rate=_average(
            1.0 if result.patch_quality_warning else 0.0 for result in completed
        ),
        avg_debuggability_score=_average(result.debuggability_score for result in completed),
        avg_agent_trajectory_score=_average(result.agent_trajectory_score for result in completed),
        todo_planning_rate=_average(1.0 if result.todo_planning else 0.0 for result in completed),
        constrained_filesystem_rate=_average(
            1.0 if result.constrained_filesystem else 0.0 for result in completed
        ),
        specialist_review_rate=_average(
            1.0 if result.specialist_review else 0.0 for result in completed
        ),
        guardrails_rate=_average(1.0 if result.guardrails else 0.0 for result in completed),
        structured_output_rate=_average(
            1.0 if result.structured_output else 0.0 for result in completed
        ),
        retry_feedback_rate=_average(1.0 if result.retry_feedback else 0.0 for result in completed),
        patch_diagnostics_rate=_average(
            1.0 if result.patch_diagnostics else 0.0 for result in completed
        ),
        contextual_verifier_rate=_average(
            1.0 if result.contextual_verifier else 0.0 for result in completed
        ),
        model_provider=",".join(providers) if providers else None,
        response_count=_sum_optional(result.response_count for result in completed),
        input_tokens=_sum_optional(result.input_tokens for result in completed),
        output_tokens=_sum_optional(result.output_tokens for result in completed),
        total_tokens=_sum_optional(result.total_tokens for result in completed),
        estimated_cost_usd=_sum_optional_float(result.estimated_cost_usd for result in completed),
    )


def write_repair_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> None:
    results_json = output_dir / "repair_results.json"
    results_csv = output_dir / "repair_results.csv"
    summary_json = output_dir / "repair_summary.json"
    report_path = output_dir / "repair_report.md"

    write_json(results_json, [result.to_dict() for result in results])
    write_json(summary_json, summary.to_dict())

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retrieved_files"] = ";".join(result.retrieved_files)
                row["retry_labels"] = ";".join(result.retry_labels)
                row["retry_label_counts"] = _format_label_counts(result.retry_label_counts)
                writer.writerow(row)

    report_path.write_text(
        render_repair_eval_report(dataset_dir=dataset_dir, results=results, summary=summary),
        encoding="utf-8",
    )


def _merge_retry_label_counts(counts: Iterable[dict[str, int]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in counts:
        for label, count in item.items():
            merged[label] = merged.get(label, 0) + count
    return dict(sorted(merged.items()))


def _format_label_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{label}={count}" for label, count in sorted(counts.items()))
