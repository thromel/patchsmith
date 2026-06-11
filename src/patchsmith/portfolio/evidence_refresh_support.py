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


def _evidence_refresh_status(steps: list[EvidenceRefreshStep]) -> str:
    statuses = {step.status for step in steps}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"
