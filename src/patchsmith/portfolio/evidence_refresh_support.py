"""Support helpers for portfolio evidence refresh reports."""

from __future__ import annotations

import time
from typing import Any

from patchsmith.portfolio._helpers import _markdown_cell
from patchsmith.portfolio.models import EvidenceRefreshReport, EvidenceRefreshStep


def render_evidence_refresh_report(report: EvidenceRefreshReport) -> str:
    lines = [
        "# PatchSmith Evidence Refresh Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Refresh status: `{report.refresh_status}`",
        f"- Steps: `{report.step_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Failed: `{report.failed_count}`",
        f"- Skipped: `{report.skipped_count}`",
        f"- Quality gate refreshed: `{str(report.quality_gate_refreshed).lower()}`",
        f"- Docker smoke refreshed: `{str(report.docker_smoke_refreshed).lower()}`",
        f"- Complex suite refreshed: `{str(report.complex_suite_refreshed).lower()}`",
        "",
        "## Steps",
        "",
        "| Step | Status | Duration | Artifacts | Summary | Error |",
        "|---|---|---:|---|---|---|",
    ]
    for step in report.steps:
        artifacts = "<br>".join(f"`{path}`" for path in step.artifact_paths)
        lines.append(
            "| "
            f"{step.name} | "
            f"{step.status} | "
            f"{step.duration_ms}ms | "
            f"{artifacts} | "
            f"{_markdown_cell(step.summary)} | "
            f"{_markdown_cell(step.error or '')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This command refreshes saved review/status artifacts.",
            "- It executes Docker smoke only when `--include-docker-smoke` is set.",
            "- It does not call live model providers.",
            "- It aggregates complex benchmark suites only from saved attempt artifacts.",
            "- By default it skips the full quality gate; use `--include-quality-gate` to run tests and package build.",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_evidence_refresh_step(
    *,
    name: str,
    artifact_paths: list[str],
    action: Any,
) -> EvidenceRefreshStep:
    started = time.perf_counter()
    try:
        result = action()
    except Exception as error:  # pragma: no cover - exercised through callers.
        return EvidenceRefreshStep(
            name=name,
            status="failed",
            duration_ms=int((time.perf_counter() - started) * 1000),
            artifact_paths=artifact_paths,
            summary=f"{type(error).__name__}: {error}",
            error=str(error),
        )
    return EvidenceRefreshStep(
        name=name,
        status="passed",
        duration_ms=int((time.perf_counter() - started) * 1000),
        artifact_paths=artifact_paths,
        summary=_evidence_refresh_summary(result),
    )


def _evidence_refresh_summary(result: Any) -> str:
    if hasattr(result, "overall_status"):
        return (
            f"overall_status={result.overall_status}, "
            f"mvp={getattr(result, 'mvp_completion_percent', 0.0):.1f}%, "
            f"delivery={getattr(result, 'delivery_completion_percent', 0.0):.1f}%"
        )
    if hasattr(result, "refresh_status"):
        return f"refresh_status={result.refresh_status}"
    if hasattr(result, "smoke_status"):
        return (
            f"smoke_status={result.smoke_status}, "
            f"run_id={getattr(result, 'run_id', None) or 'none'}"
        )
    if hasattr(result, "quality_status"):
        return (
            f"quality_status={result.quality_status}, "
            f"passed={result.passed_count}, failed={result.failed_count}"
        )
    if hasattr(result, "complex_suite_status"):
        cost = getattr(result, "selected_cost_per_validated_task_usd", None)
        cost_text = "n/a" if cost is None else f"${cost:.6f}"
        tokens = getattr(result, "selected_tokens_per_validated_task", None)
        tokens_text = "n/a" if tokens is None else f"{tokens:.2f}"
        avg_progress_score = getattr(result, "avg_progress_score", None)
        avg_progress_score_text = (
            "n/a" if avg_progress_score is None else f"{avg_progress_score:.2f}"
        )
        selected_progress_score = getattr(result, "selected_avg_progress_score", None)
        selected_progress_score_text = (
            "n/a" if selected_progress_score is None else f"{selected_progress_score:.2f}"
        )
        partial_progress_tasks = getattr(result, "partial_progress_tasks", None)
        partial_progress_tasks_text = (
            "n/a" if partial_progress_tasks is None else str(partial_progress_tasks)
        )
        failure_class_counts_text = _format_count_map(getattr(result, "failure_class_counts", None))
        selected_failure_class_counts_text = _format_count_map(
            getattr(result, "selected_failure_class_counts", None)
        )
        harness_layer_counts_text = _format_count_map(getattr(result, "harness_layer_counts", None))
        selected_harness_layer_counts_text = _format_count_map(
            getattr(result, "selected_harness_layer_counts", None)
        )
        retry_failure_class_counts_text = _format_count_map(
            getattr(result, "retry_failure_class_counts", None)
        )
        process_quality_label_counts_text = _format_count_map(
            getattr(result, "process_quality_label_counts", None)
        )
        process_quality_flag_counts_text = _format_count_map(
            getattr(result, "process_quality_flag_counts", None)
        )
        virtual_files = getattr(
            result,
            "selected_virtual_files_per_validated_task",
            None,
        )
        virtual_files_text = "n/a" if virtual_files is None else f"{virtual_files:.2f}"
        tokens_per_virtual_file = getattr(
            result,
            "selected_tokens_per_virtual_file",
            None,
        )
        tokens_per_virtual_file_text = (
            "n/a" if tokens_per_virtual_file is None else f"{tokens_per_virtual_file:.2f}"
        )
        responses_per_virtual_file = getattr(
            result,
            "selected_responses_per_virtual_file",
            None,
        )
        responses_per_virtual_file_text = (
            "n/a" if responses_per_virtual_file is None else f"{responses_per_virtual_file:.2f}"
        )
        context_recall = getattr(result, "selected_context_target_recall", None)
        context_recall_text = "n/a" if context_recall is None else f"{context_recall:.2f}"
        context_precision = getattr(result, "selected_context_target_precision", None)
        context_precision_text = "n/a" if context_precision is None else f"{context_precision:.2f}"
        acceptance_manifest_rate = getattr(
            result,
            "acceptance_rubric_manifest_rate",
            None,
        )
        repo_instructions_manifest_rate = getattr(
            result,
            "repo_instructions_manifest_rate",
            None,
        )
        repo_instructions_manifest_rate_text = (
            "n/a"
            if repo_instructions_manifest_rate is None
            else f"{repo_instructions_manifest_rate:.2f}"
        )
        repo_instructions_read_first_rate = getattr(
            result,
            "repo_instructions_read_first_rate",
            None,
        )
        repo_instructions_read_first_rate_text = (
            "n/a"
            if repo_instructions_read_first_rate is None
            else f"{repo_instructions_read_first_rate:.2f}"
        )
        acceptance_manifest_rate_text = (
            "n/a" if acceptance_manifest_rate is None else f"{acceptance_manifest_rate:.2f}"
        )
        acceptance_read_first_rate = getattr(
            result,
            "acceptance_rubric_read_first_rate",
            None,
        )
        acceptance_read_first_rate_text = (
            "n/a" if acceptance_read_first_rate is None else f"{acceptance_read_first_rate:.2f}"
        )
        acceptance_alignment_rate = getattr(
            result,
            "acceptance_rubric_alignment_rate",
            None,
        )
        acceptance_alignment_rate_text = (
            "n/a" if acceptance_alignment_rate is None else f"{acceptance_alignment_rate:.2f}"
        )
        contextual_verifier_rate = getattr(
            result,
            "contextual_verifier_rate",
            None,
        )
        contextual_verifier_rate_text = (
            "n/a" if contextual_verifier_rate is None else f"{contextual_verifier_rate:.2f}"
        )
        return (
            f"suite_status={result.complex_suite_status}, "
            f"validated={result.validated_tasks}, "
            f"unique={result.unique_task_count}, "
            f"live={result.live_provider_tasks}, "
            f"progress={avg_progress_score_text}, "
            f"selected_progress={selected_progress_score_text}, "
            f"partial_progress={partial_progress_tasks_text}, "
            f"failure_classes={failure_class_counts_text}, "
            f"selected_failure_classes={selected_failure_class_counts_text}, "
            f"harness_layers={harness_layer_counts_text}, "
            f"selected_harness_layers={selected_harness_layer_counts_text}, "
            f"retry_failure_classes={retry_failure_class_counts_text}, "
            f"process_quality={process_quality_label_counts_text}, "
            f"process_flags={process_quality_flag_counts_text}, "
            f"cost_per_validated={cost_text}, "
            f"tokens_per_validated={tokens_text}, "
            f"virtual_files_per_validated={virtual_files_text}, "
            f"tokens_per_virtual_file={tokens_per_virtual_file_text}, "
            f"responses_per_virtual_file={responses_per_virtual_file_text}, "
            f"context_target_recall={context_recall_text}, "
            f"context_target_precision={context_precision_text}, "
            f"repo_instructions_manifest_rate={repo_instructions_manifest_rate_text}, "
            f"repo_instructions_read_first_rate={repo_instructions_read_first_rate_text}, "
            f"acceptance_rubric_manifest_rate={acceptance_manifest_rate_text}, "
            f"acceptance_rubric_read_first_rate={acceptance_read_first_rate_text}, "
            f"acceptance_rubric_alignment_rate={acceptance_alignment_rate_text}, "
            f"trajectory={result.avg_agent_trajectory_score:.2f}, "
            f"contextual_verifier={contextual_verifier_rate_text}, "
            f"target_alignment={result.target_alignment_rate:.2f}"
        )
    if hasattr(result, "delivery_status"):
        return (
            f"delivery_status={result.delivery_status}, completion={result.completion_percent:.1f}%"
        )
    if hasattr(result, "completion_percent") and hasattr(result, "status"):
        return f"status={result.status}, completion={result.completion_percent:.1f}%"
    if hasattr(result, "release_status"):
        return (
            f"release_status={result.release_status}, "
            f"warnings={result.warning_count}, blockers={result.blocked_count}"
        )
    if hasattr(result, "launch_status"):
        return (
            f"launch_status={result.launch_status}, "
            f"blockers={result.blocked_count}, warnings={result.warning_count}"
        )
    if hasattr(result, "readiness_status") and hasattr(result, "blocked_count"):
        return (
            f"readiness_status={result.readiness_status}, "
            f"blocked={result.blocked_count}, warnings={result.warning_count}"
        )
    if hasattr(result, "readiness_status"):
        return (
            f"readiness_status={result.readiness_status}, "
            f"experiments={getattr(result, 'experiment_count', 0)}, "
            f"runs={getattr(result, 'run_count', 0)}"
        )
    if hasattr(result, "calibration_status"):
        return (
            f"calibration_status={result.calibration_status}, "
            f"live_runs={getattr(result, 'saved_live_provider_count', 0)}"
        )
    if hasattr(result, "plan_status"):
        return f"plan_status={result.plan_status}, ready_runs={getattr(result, 'ready_runs', 0)}"
    if hasattr(result, "repair_command_tasks"):
        return (
            f"ready={result.ready_tasks}, warning={result.warning_tasks}, "
            f"blocked={result.blocked_tasks}, commands={result.repair_command_tasks}"
        )
    if hasattr(result, "reproduced_tasks"):
        return (
            f"reproduced={result.reproduced_tasks}, "
            f"dry_run={result.dry_run_tasks}, blocked={result.blocked_tasks}, "
            f"manual_specs={result.manual_spec_required_tasks}"
        )
    if hasattr(result, "validated_tasks"):
        return (
            f"validated={result.validated_tasks}, "
            f"attempted={result.attempted_tasks}, blocked={result.blocked_tasks}"
        )
    if hasattr(result, "manual_spec_required_tasks"):
        return (
            f"planned={result.planned_tasks}, warning={result.warning_tasks}, "
            f"blocked={result.blocked_tasks}, manual_specs={result.manual_spec_required_tasks}"
        )
    if hasattr(result, "experiment_count"):
        return (
            f"experiments={result.experiment_count}, "
            f"runs={getattr(result, 'run_count', 0)}, "
            f"metrics={len(getattr(result, 'metrics', []))}"
        )
    if hasattr(result, "runs_requiring_attention"):
        return (
            f"runs_scanned={result.runs_scanned}, "
            f"requiring_attention={result.runs_requiring_attention}"
        )
    if hasattr(result, "target_duration_seconds"):
        return f"target_duration_seconds={result.target_duration_seconds}"
    if hasattr(result, "png_path"):
        return f"png_path={result.png_path}"
    return type(result).__name__


def _format_count_map(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "none"
    counts: list[tuple[str, int]] = []
    for label, count in value.items():
        if not isinstance(label, str) or not label:
            continue
        try:
            parsed_count = int(count)
        except (TypeError, ValueError):
            continue
        if parsed_count > 0:
            counts.append((label, parsed_count))
    if not counts:
        return "none"
    return ";".join(f"{label}={count}" for label, count in sorted(counts))


def _evidence_refresh_status(steps: list[EvidenceRefreshStep]) -> str:
    statuses = {step.status for step in steps}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"
