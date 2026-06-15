"""Evaluation runners scaffold (split from evaluation.py)."""

from __future__ import annotations

import csv
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation.runners.repair import run_repair_evaluation
from patchsmith.evaluation_models import (
    SCAFFOLD_VARIANTS,
    ScaffoldComparisonResult,
    ScaffoldVariant,
)
from patchsmith.repair_reports import (
    render_scaffold_comparison_report,
)


def run_scaffold_comparison(
    *,
    dataset_dir: Path,
    variants: list[str],
    context_provider: str,
    output_dir: Path,
    max_tasks: int | None = None,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> list[ScaffoldComparisonResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_variants = [_scaffold_variant(name) for name in variants]
    comparison_results: list[ScaffoldComparisonResult] = []

    for variant in selected_variants:
        variant_output_dir = output_dir / variant.name
        _repair_results, summary = run_repair_evaluation(
            dataset_dir=dataset_dir,
            runtime=variant.runtime,
            planner=variant.planner,
            context_provider=context_provider,
            output_dir=variant_output_dir,
            max_tasks=max_tasks,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
        )
        comparison_results.append(
            ScaffoldComparisonResult(
                scaffold=variant.name,
                runtime=summary.runtime,
                planner=summary.planner,
                context_provider=summary.context_provider,
                attempted_tasks=summary.attempted_tasks,
                completed_tasks=summary.completed_tasks,
                patch_generated_rate=summary.patch_generated_rate,
                targeted_test_pass_rate=summary.targeted_test_pass_rate,
                avg_latency_ms=summary.avg_latency_ms,
                avg_trace_events=summary.avg_trace_events,
                avg_runtime_nodes=summary.avg_runtime_nodes,
                failed_trace_event_count=summary.failed_trace_event_count,
                avg_retry_events=summary.avg_retry_events,
                retry_label_counts=summary.retry_label_counts,
                avg_debuggability_score=summary.avg_debuggability_score,
                avg_agent_trajectory_score=summary.avg_agent_trajectory_score,
                todo_planning_rate=summary.todo_planning_rate,
                constrained_filesystem_rate=summary.constrained_filesystem_rate,
                specialist_review_rate=summary.specialist_review_rate,
                guardrails_rate=summary.guardrails_rate,
                structured_output_rate=summary.structured_output_rate,
                retry_feedback_rate=summary.retry_feedback_rate,
                patch_diagnostics_rate=summary.patch_diagnostics_rate,
                contextual_verifier_rate=summary.contextual_verifier_rate,
                model_provider=summary.model_provider,
                response_count=summary.response_count,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                total_tokens=summary.total_tokens,
                estimated_cost_usd=summary.estimated_cost_usd,
                repair_report_path=str(variant_output_dir / "repair_report.md"),
            )
        )

    write_scaffold_comparison_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=comparison_results,
    )
    return comparison_results


def write_scaffold_comparison_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> None:
    results_json = output_dir / "scaffold_results.json"
    results_csv = output_dir / "scaffold_results.csv"
    report_path = output_dir / "scaffold_report.md"

    write_json(results_json, [result.to_dict() for result in results])

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retry_label_counts"] = _format_label_counts(result.retry_label_counts)
                writer.writerow(row)

    report_path.write_text(
        render_scaffold_comparison_report(dataset_dir=dataset_dir, results=results),
        encoding="utf-8",
    )


def _scaffold_variant(name: str) -> ScaffoldVariant:
    try:
        return SCAFFOLD_VARIANTS[name]
    except KeyError as error:
        supported = ", ".join(sorted(SCAFFOLD_VARIANTS))
        raise ValueError(f"unsupported scaffold variant: {name}; supported: {supported}") from error


def _format_label_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{label}={count}" for label, count in sorted(counts.items()))
