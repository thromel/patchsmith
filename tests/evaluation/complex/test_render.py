from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.followups import complex_followup_candidates
from patchsmith.evaluation.complex.render import (
    render_complex_benchmark_report,
    render_complex_benchmark_suite_report,
    render_complex_followup_runbook,
)
from patchsmith.evaluation.complex.selection import select_attempts
from patchsmith.evaluation.runners import complex as runner_complex
from patchsmith.evaluation_models import ComplexBenchmarkResult, ComplexBenchmarkSummary

pytestmark = pytest.mark.unit


def test_render_complex_followup_runbook_quotes_required_environment() -> None:
    candidate = complex_followup_candidates(
        [
            _result(
                task_id="requests-7341",
                validation_passed=True,
                status="validated",
                strict_status="validated",
                failure_class="validated",
                harness_layer="none",
                estimated_cost_usd=0.12,
            )
        ]
    )[0]

    markdown = render_complex_followup_runbook([candidate])

    assert "# Complex Benchmark Follow-up Runbook" in markdown
    assert "export OPENAI_API_KEY='<required>'" in markdown
    assert "execute-public-issue-repairs --task-id requests-7341" in markdown
    assert "max_attempted_task_cost_usd <= 0.07" in markdown
    assert "deterministic recommendations from saved artifacts" in markdown


def test_render_complex_benchmark_report_includes_result_selection_and_boundary() -> None:
    result = _result(
        task_id="pytest-14552",
        validation_passed=True,
        status="validated",
        strict_status="validated",
        failure_class="validated",
        harness_layer="none",
        progress_score=1.0,
    )
    summary = _summary(
        task_count=1,
        unique_task_count=1,
        attempted_tasks=1,
        validated_tasks=1,
        validation_rate=1.0,
        selected_validation_rate=1.0,
        failure_class_counts={"validated": 1},
    )

    markdown = render_complex_benchmark_report(
        attempt_dir=Path("attempts"),
        results=[result],
        selections=select_attempts([result]),
        followup_candidates=[],
        summary=summary,
    )

    assert "# Complex Benchmark Report" in markdown
    assert "- Task count: `1`" in markdown
    assert "- Failure class counts: `validated=1`" in markdown
    assert "| pytest-14552 | 1/1 | validated | validated | true |" in markdown
    assert "## Selected Attempts" in markdown
    assert "Live LLM quality claims require non-offline provider metadata" in markdown


def test_render_complex_benchmark_suite_report_includes_followups() -> None:
    summary = _summary(
        task_count=1,
        unique_task_count=1,
        attempted_tasks=1,
        validated_tasks=1,
        validation_rate=1.0,
        validated_task_pass_at_n_rate=1.0,
    )
    followup = complex_followup_candidates(
        [
            _result(
                task_id="budget-task",
                validation_passed=True,
                status="validated",
                strict_status="validated",
                failure_class="validated",
                harness_layer="none",
                estimated_cost_usd=0.12,
            )
        ]
    )

    markdown = render_complex_benchmark_suite_report(
        attempt_summaries=[summary],
        aggregate_summary=summary,
        followup_candidates=followup,
    )

    assert "# Complex Benchmark Suite Report" in markdown
    assert "- Attempt directories: `1`" in markdown
    assert "## Follow-up Candidates" in markdown
    assert "| budget-task | 1/1 | cost_optimization_rerun |" in markdown
    assert "Duplicate task IDs across attempt directories" in markdown


def test_runner_delegates_rendering_to_complex_package() -> None:
    assert runner_complex.render_complex_followup_runbook is render_complex_followup_runbook
    assert (
        runner_complex.render_complex_benchmark_suite_report
        is render_complex_benchmark_suite_report
    )
    assert runner_complex.render_complex_benchmark_report is render_complex_benchmark_report


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
        "process_quality_label": "solid",
        "patch_target_aligned": True,
        "estimated_cost_usd": 0.01,
    }
    values.update(overrides)
    return ComplexBenchmarkResult(**values)  # type: ignore[arg-type]


def _summary(**overrides: object) -> ComplexBenchmarkSummary:
    values: dict[str, object] = {
        field.name: _summary_default(field.name) for field in fields(ComplexBenchmarkSummary)
    }
    values.update(
        {
            "benchmark": "public_issue_repair_attempts",
            "attempt_dir": "attempt",
            "model_provider": "deepagents_openai_chat",
        }
    )
    values.update(overrides)
    return ComplexBenchmarkSummary(**values)  # type: ignore[arg-type]


def _summary_default(name: str) -> object:
    if name.endswith("_counts"):
        return {}
    if name.endswith(("_rate", "_score")) or name.startswith("avg_"):
        return 0.0
    if name.endswith("_usd"):
        return None
    if name.endswith(("_tokens", "_responses")):
        return None
    if name in {"benchmark", "attempt_dir", "model_provider"}:
        return ""
    return 0
