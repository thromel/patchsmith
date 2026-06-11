"""Evaluation runners scaffold (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

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
                avg_debuggability_score=summary.avg_debuggability_score,
                model_provider=summary.model_provider,
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

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())

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
