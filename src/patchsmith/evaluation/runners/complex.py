"""Complex benchmark summaries from public issue repair-attempt artifacts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from patchsmith.evaluation.complex.extract import (
    complex_results_from_attempt_dir as _complex_results_from_attempt_dir,
)
from patchsmith.evaluation.complex.followups import (
    complex_suite_followup_candidates as _suite_followup_candidates,
)
from patchsmith.evaluation.complex.gates import complex_benchmark_suite_gate
from patchsmith.evaluation.complex.models import (
    ComplexBenchmarkSuiteConfig,
    ComplexBenchmarkSuiteGate,
    ComplexBenchmarkSuitePreflight,
    ComplexBenchmarkSuiteSpec,
    ComplexBenchmarkSuiteThresholds,
)
from patchsmith.evaluation.complex.outputs import (
    write_complex_outputs as _write_complex_outputs,
)
from patchsmith.evaluation.complex.outputs import (
    write_complex_suite_outputs as _write_complex_suite_outputs,
)
from patchsmith.evaluation.complex.render import (
    render_complex_benchmark_report,
    render_complex_benchmark_suite_report,
    render_complex_followup_runbook,
)
from patchsmith.evaluation.complex.selection import (
    select_attempts as _select_attempts,
)
from patchsmith.evaluation.complex.spec import (
    DEFAULT_COMPLEX_BENCHMARK,
    DEFAULT_COMPLEX_SUITE_OUTPUT_DIR,
    load_complex_benchmark_suite_spec,
    resolve_complex_benchmark_suite_config,
    resolve_complex_benchmark_suite_thresholds,
    validate_complex_benchmark_suite_inputs,
)
from patchsmith.evaluation.complex.summary import (
    complex_summary as _complex_summary,
)
from patchsmith.evaluation_models import (
    ComplexBenchmarkFollowupCandidate,
    ComplexBenchmarkResult,
    ComplexBenchmarkSummary,
)

__all__ = [
    "DEFAULT_COMPLEX_BENCHMARK",
    "DEFAULT_COMPLEX_SUITE_OUTPUT_DIR",
    "ComplexBenchmarkSuiteConfig",
    "ComplexBenchmarkSuiteGate",
    "ComplexBenchmarkSuitePreflight",
    "ComplexBenchmarkSuiteSpec",
    "ComplexBenchmarkSuiteThresholds",
    "complex_benchmark_suite_gate",
    "load_complex_benchmark_suite_spec",
    "render_complex_benchmark_report",
    "render_complex_benchmark_suite_report",
    "render_complex_followup_runbook",
    "resolve_complex_benchmark_suite_config",
    "resolve_complex_benchmark_suite_thresholds",
    "summarize_complex_benchmark",
    "summarize_complex_benchmark_suite",
    "validate_complex_benchmark_suite_inputs",
]


def summarize_complex_benchmark(
    *,
    attempt_dir: Path,
    output_dir: Path,
    benchmark: str = "public_issue_repair_attempts",
) -> tuple[list[ComplexBenchmarkResult], ComplexBenchmarkSummary]:
    results = _complex_results_from_attempt_dir(attempt_dir)
    selections = _select_attempts(results)
    summary = _complex_summary(
        benchmark=benchmark,
        attempt_dir=attempt_dir,
        results=results,
        selections=selections,
    )
    _write_complex_outputs(
        output_dir=output_dir,
        attempt_dir=attempt_dir,
        results=results,
        selections=selections,
        summary=summary,
    )
    return results, summary


def summarize_complex_benchmark_suite(
    *,
    attempt_dirs: list[Path],
    output_dir: Path,
    benchmark: str = "public_issue_repair_attempts",
    thresholds: ComplexBenchmarkSuiteThresholds | None = None,
) -> tuple[
    list[ComplexBenchmarkResult],
    ComplexBenchmarkSummary,
    list[ComplexBenchmarkSummary],
    list[ComplexBenchmarkFollowupCandidate],
]:
    if not attempt_dirs:
        raise ValueError("at least one attempt directory is required")

    all_results: list[ComplexBenchmarkResult] = []
    attempt_summaries: list[ComplexBenchmarkSummary] = []
    for attempt_dir in attempt_dirs:
        results = _complex_results_from_attempt_dir(attempt_dir)
        selections = _select_attempts(results)
        attempt_summaries.append(
            _complex_summary(
                benchmark=benchmark,
                attempt_dir=attempt_dir,
                results=results,
                selections=selections,
            )
        )
        all_results.extend(results)

    selections = _select_attempts(all_results)
    summary = _complex_summary(
        benchmark=benchmark,
        attempt_dir=Path("complex benchmark suite"),
        results=all_results,
        selections=selections,
    )
    summary = replace(summary, attempt_dir=_attempt_dir_label(attempt_dirs))
    followup_candidates = _suite_followup_candidates(
        results=all_results,
        selections=selections,
        summary=summary,
        thresholds=thresholds,
    )
    _write_complex_outputs(
        output_dir=output_dir,
        attempt_dir=Path(summary.attempt_dir),
        results=all_results,
        selections=selections,
        summary=summary,
        followup_candidates=followup_candidates,
    )
    _write_complex_suite_outputs(
        output_dir=output_dir,
        attempt_summaries=attempt_summaries,
        aggregate_summary=summary,
        followup_candidates=followup_candidates,
    )
    return all_results, summary, attempt_summaries, followup_candidates

def _attempt_dir_label(attempt_dirs: list[Path]) -> str:
    return "; ".join(str(path) for path in attempt_dirs)
