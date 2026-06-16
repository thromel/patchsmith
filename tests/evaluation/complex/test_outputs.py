from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.outputs import (
    write_complex_outputs,
    write_complex_suite_outputs,
)
from patchsmith.evaluation.complex.selection import select_attempts
from patchsmith.evaluation.complex.summary import complex_summary
from patchsmith.evaluation.runners import complex as runner_complex
from patchsmith.evaluation_models import ComplexBenchmarkResult

pytestmark = pytest.mark.unit


def test_write_complex_outputs_persists_machine_and_markdown_artifacts(
    tmp_path: Path,
) -> None:
    result = _result(
        task_id="expensive-task",
        status="validated",
        strict_status="validated",
        validation_passed=True,
        failure_class="validated",
        harness_layer="none",
        estimated_cost_usd=0.12,
        total_tokens=130_000,
        response_count=8,
    )
    selections = select_attempts([result])
    summary = complex_summary(
        benchmark="public_issue_repair_attempts",
        attempt_dir=Path("attempts"),
        results=[result],
        selections=selections,
    )
    output_dir = tmp_path / "complex"

    write_complex_outputs(
        output_dir=output_dir,
        attempt_dir=Path("attempts"),
        results=[result],
        selections=selections,
        summary=summary,
    )

    results_payload = json.loads(
        (output_dir / "complex_benchmark_results.json").read_text(encoding="utf-8")
    )
    followups_payload = json.loads(
        (output_dir / "complex_benchmark_followup_candidates.json").read_text(encoding="utf-8")
    )
    assert results_payload[0]["task_id"] == "expensive-task"
    assert followups_payload[0]["action"] == "cost_optimization_rerun"
    assert "expensive-task" in (output_dir / "complex_benchmark_results.csv").read_text(
        encoding="utf-8"
    )
    assert "# Complex Benchmark Report" in (output_dir / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "# Complex Benchmark Follow-up Runbook" in (
        output_dir / "complex_benchmark_followup_runbook.md"
    ).read_text(encoding="utf-8")


def test_write_complex_suite_outputs_persists_attempt_summaries_and_report(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "suite"
    output_dir.mkdir()
    result = _result(task_id="suite-task", status="validated", validation_passed=True)
    selections = select_attempts([result])
    summary = complex_summary(
        benchmark="public_issue_repair_attempts",
        attempt_dir=Path("attempts"),
        results=[result],
        selections=selections,
    )

    write_complex_suite_outputs(
        output_dir=output_dir,
        attempt_summaries=[summary],
        aggregate_summary=summary,
        followup_candidates=[],
    )

    attempts_payload = json.loads(
        (output_dir / "complex_benchmark_attempt_summaries.json").read_text(encoding="utf-8")
    )
    report = (output_dir / "complex_benchmark_suite_report.md").read_text(encoding="utf-8")
    assert attempts_payload[0]["task_count"] == 1
    assert "# Complex Benchmark Suite Report" in report
    assert "- Attempt directories: `1`" in report


def test_runner_delegates_output_writing_to_complex_package() -> None:
    assert runner_complex._write_complex_outputs is write_complex_outputs
    assert runner_complex._write_complex_suite_outputs is write_complex_suite_outputs


def _result(**overrides: object) -> ComplexBenchmarkResult:
    values: dict[str, object] = {
        "task_id": "task",
        "repository": None,
        "issue_url": None,
        "status": "failed",
        "strict_status": "failed",
        "runtime": "deepagents",
        "planner": "deepagents",
        "context_provider": "native_hybrid",
        "reproduced": True,
        "patch_generated": True,
        "validation_passed": False,
        "test_exit_code": 1,
        "trace_path": None,
        "report_path": None,
        "progress_score": 0.5,
        "progress_stage": "target_aligned_patch",
        "failure_class": "test_failure",
        "harness_layer": "validation",
        "patch_quality_severity": "low",
        "target_alignment_status": "aligned",
        "patch_target_aligned": True,
        "model_provider": "deepagents_openai_chat",
        "preflight_status": "passed",
        "preflight_gates": [],
    }
    values.update(overrides)
    return ComplexBenchmarkResult(**values)  # type: ignore[arg-type]
