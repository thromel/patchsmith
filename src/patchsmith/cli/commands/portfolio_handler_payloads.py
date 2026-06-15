"""JSON payload helpers for portfolio CLI command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def print_json_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def live_calibration_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "calibration_status": report.calibration_status,
        "saved_live_provider_count": report.saved_live_provider_count,
        "deepagents_package_run_count": report.deepagents_package_run_count,
        "deepagents_compatibility_run_count": report.deepagents_compatibility_run_count,
        "model_providers": report.model_providers,
        **_report_paths(output, json_output_path),
    }


def live_calibration_plan_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
    ready_runs: int,
    blocked_runs: int,
) -> dict[str, Any]:
    return {
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "plan_status": report.plan_status,
        "calibration_status": report.calibration_status,
        "saved_live_provider_count": report.saved_live_provider_count,
        "run_count": len(report.runs),
        "ready_runs": ready_runs,
        "blocked_runs": blocked_runs,
        **_report_paths(output, json_output_path),
    }


def docker_smoke_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "smoke_status": report.smoke_status,
        "image": report.image,
        "task_dir": report.task_dir,
        "run_id": report.run_id,
        "test_exit_code": report.test_exit_code,
        "environment": report.environment,
        "remediation_commands": report.remediation_commands,
        **_report_paths(output, json_output_path),
    }


def environment_readiness_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "readiness_status": report.readiness_status,
        "passed_count": report.passed_count,
        "warning_count": report.warning_count,
        "blocked_count": report.blocked_count,
        **_report_paths(output, json_output_path),
    }


def release_hygiene_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "release_status": report.release_status,
        "passed_count": report.passed_count,
        "warning_count": report.warning_count,
        "blocked_count": report.blocked_count,
        **_report_paths(output, json_output_path),
    }


def launch_blockers_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "launch_status": report.launch_status,
        "item_count": report.item_count,
        "blocked_count": report.blocked_count,
        "warning_count": report.warning_count,
        "ready_count": report.ready_count,
        **_report_paths(output, json_output_path),
    }


def mvp_progress_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "status": report.status,
        "completion_percent": report.completion_percent,
        "item_count": report.item_count,
        "passed_count": report.passed_count,
        "warning_count": report.warning_count,
        "blocked_count": report.blocked_count,
        "missing_count": report.missing_count,
        **_report_paths(output, json_output_path),
    }


def delivery_audit_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "delivery_status": report.delivery_status,
        "completion_percent": report.completion_percent,
        "item_count": report.item_count,
        "passed_count": report.passed_count,
        "warning_count": report.warning_count,
        "blocked_count": report.blocked_count,
        "missing_count": report.missing_count,
        **_report_paths(output, json_output_path),
    }


def quality_gate_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "quality_status": report.quality_status,
        "passed_count": report.passed_count,
        "failed_count": report.failed_count,
        "skipped_count": report.skipped_count,
        **_report_paths(output, json_output_path),
    }


def project_status_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "overall_status": report.overall_status,
        "mvp_status": report.mvp_status,
        "mvp_completion_percent": report.mvp_completion_percent,
        "delivery_status": report.delivery_status,
        "delivery_completion_percent": report.delivery_completion_percent,
        "quality_status": report.quality_status,
        "launch_status": report.launch_status,
        "release_status": report.release_status,
        "docker_smoke_status": report.docker_smoke_status,
        "environment_readiness_status": report.environment_readiness_status,
        "live_calibration_status": report.live_calibration_status,
        "saved_live_provider_count": report.saved_live_provider_count,
        "blocker_count": report.blocker_count,
        "warning_count": report.warning_count,
        "evidence_freshness_status": report.evidence_freshness_status,
        "stale_source_count": report.stale_source_count,
        "undated_source_count": report.undated_source_count,
        "missing_source_count": len(report.missing_sources),
        **_report_paths(output, json_output_path),
    }


def evidence_refresh_payload(
    report: Any,
    *,
    output: str | Path,
    json_output_path: Path | None,
) -> dict[str, Any]:
    return {
        "project_root": report.project_root,
        "artifacts_dir": report.artifacts_dir,
        "generated_at": report.generated_at,
        "refresh_status": report.refresh_status,
        "step_count": report.step_count,
        "passed_count": report.passed_count,
        "failed_count": report.failed_count,
        "skipped_count": report.skipped_count,
        "quality_gate_refreshed": report.quality_gate_refreshed,
        "docker_smoke_refreshed": report.docker_smoke_refreshed,
        "complex_suite_refreshed": report.complex_suite_refreshed,
        **_report_paths(output, json_output_path),
    }


def _report_paths(output: str | Path, json_output_path: Path | None) -> dict[str, str | None]:
    return {
        "report_path": str(Path(output)),
        "json_path": str(json_output_path) if json_output_path else None,
    }


__all__ = [
    "delivery_audit_payload",
    "docker_smoke_payload",
    "environment_readiness_payload",
    "evidence_refresh_payload",
    "launch_blockers_payload",
    "live_calibration_payload",
    "live_calibration_plan_payload",
    "mvp_progress_payload",
    "print_json_payload",
    "project_status_payload",
    "quality_gate_payload",
    "release_hygiene_payload",
]
