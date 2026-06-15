"""File outputs for complex benchmark summaries."""

from __future__ import annotations

import csv
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation.complex.followups import (
    complex_followup_candidates as _followup_candidates,
)
from patchsmith.evaluation.complex.render import (
    render_complex_benchmark_report,
    render_complex_benchmark_suite_report,
    render_complex_followup_runbook,
)
from patchsmith.evaluation_models import (
    ComplexBenchmarkFollowupCandidate,
    ComplexBenchmarkResult,
    ComplexBenchmarkSelection,
    ComplexBenchmarkSummary,
)

__all__ = [
    "write_complex_outputs",
    "write_complex_suite_outputs",
]


def write_complex_outputs(
    *,
    output_dir: Path,
    attempt_dir: Path,
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection],
    summary: ComplexBenchmarkSummary,
    followup_candidates: list[ComplexBenchmarkFollowupCandidate] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ranked_followups = list(followup_candidates or _followup_candidates(results))
    write_json(
        output_dir / "complex_benchmark_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "complex_benchmark_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    write_json(
        output_dir / "complex_benchmark_selected_results.json",
        [selection.to_dict() for selection in selections],
        trailing_newline=True,
    )
    write_json(
        output_dir / "complex_benchmark_followup_candidates.json",
        [candidate.to_dict() for candidate in ranked_followups],
        trailing_newline=True,
    )
    (output_dir / "complex_benchmark_followup_runbook.md").write_text(
        render_complex_followup_runbook(ranked_followups),
        encoding="utf-8",
    )
    with (output_dir / "complex_benchmark_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_dict())
    with (output_dir / "complex_benchmark_selected_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(selections[0].to_dict()) if selections else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for selection in selections:
            writer.writerow(selection.to_dict())
    (output_dir / "complex_benchmark_report.md").write_text(
        render_complex_benchmark_report(
            attempt_dir=attempt_dir,
            results=results,
            selections=selections,
            summary=summary,
            followup_candidates=ranked_followups,
        ),
        encoding="utf-8",
    )


def write_complex_suite_outputs(
    *,
    output_dir: Path,
    attempt_summaries: list[ComplexBenchmarkSummary],
    aggregate_summary: ComplexBenchmarkSummary,
    followup_candidates: list[ComplexBenchmarkFollowupCandidate] | None = None,
) -> None:
    write_json(
        output_dir / "complex_benchmark_attempt_summaries.json",
        [summary.to_dict() for summary in attempt_summaries],
        trailing_newline=True,
    )
    (output_dir / "complex_benchmark_suite_report.md").write_text(
        render_complex_benchmark_suite_report(
            attempt_summaries=attempt_summaries,
            aggregate_summary=aggregate_summary,
            followup_candidates=followup_candidates,
        ),
        encoding="utf-8",
    )
