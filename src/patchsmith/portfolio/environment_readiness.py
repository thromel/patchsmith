"""Portfolio environment readiness (split from portfolio.py)."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import (
    _dedupe_strings,
    _load_json_artifact,
    _markdown_cell,
    _payload_string,
    _payload_string_list,
    _utc_now,
)
from patchsmith.portfolio.live_calibration import build_live_calibration_report
from patchsmith.portfolio.models import (
    EnvironmentReadinessCheck,
    EnvironmentReadinessReport,
    LiveCalibrationCheck,
    LiveCalibrationReport,
)


def build_environment_readiness_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> EnvironmentReadinessReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    environment = dict(os.environ if environment is None else environment)
    calibration = build_live_calibration_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    docker_payload = _load_json_artifact(artifacts_dir / "experiments" / "docker_smoke.json")
    checks = _environment_readiness_checks(
        docker_payload=docker_payload,
        calibration=calibration,
    )
    status_counts = Counter(check.status for check in checks)
    return EnvironmentReadinessReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        readiness_status=_environment_readiness_status(checks),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        checks=checks,
        remediation_commands=_environment_remediation_commands(
            docker_payload=docker_payload,
            calibration=calibration,
        ),
    )


def write_environment_readiness_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> EnvironmentReadinessReport:
    report = build_environment_readiness_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    write_markdown(output_path, render_environment_readiness_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_environment_readiness_report(report: EnvironmentReadinessReport) -> str:
    lines = [
        "# PatchSmith Environment Readiness",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blocked: `{report.blocked_count}`",
        "",
        "## Checks",
        "",
        "| Area | Check | Status | Evidence | Next Action |",
        "|---|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.area} | "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(["", "## Remediation Commands", ""])
    if report.remediation_commands:
        lines.extend(["```bash", *report.remediation_commands, "```"])
    else:
        lines.append("No command needed.")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report summarizes current-shell prerequisites and saved evidence.",
            "- It does not execute Docker smoke; run `docker-smoke` or `refresh-evidence --include-docker-smoke` to refresh Docker evidence.",
            "- It does not call live model providers.",
        ]
    )
    return "\n".join(lines) + "\n"


def _environment_readiness_checks(
    *,
    docker_payload: dict[str, Any] | None,
    calibration: LiveCalibrationReport,
) -> list[EnvironmentReadinessCheck]:
    checks = [_environment_docker_smoke_check(docker_payload)]
    for check in calibration.checks:
        checks.append(_environment_live_calibration_check(check))
    return checks


def _environment_docker_smoke_check(
    docker_payload: dict[str, Any] | None,
) -> EnvironmentReadinessCheck:
    if docker_payload is None:
        return _environment_check(
            area="Docker",
            name="Saved Docker Smoke Evidence",
            status="blocked",
            evidence="Docker smoke artifact is missing or invalid.",
            next_action="Run `docker-smoke` or `refresh-evidence --include-docker-smoke`.",
        )
    smoke_status = _payload_string(docker_payload, "smoke_status", "missing")
    if smoke_status == "passed":
        status = "passed"
        next_action = "No action needed."
    elif smoke_status == "skipped":
        status = "warning"
        next_action = "Run Docker smoke without `--skip-run` for executable evidence."
    else:
        status = "blocked"
        next_action = "Resolve Docker daemon/image availability and rerun Docker smoke."
    generated_at = _payload_string(docker_payload, "generated_at", "unknown")
    host_summary = _docker_environment_evidence(docker_payload.get("environment"))
    evidence = f"Docker smoke is `{smoke_status}` from `{generated_at}`."
    if host_summary:
        evidence = f"{evidence} {host_summary}"
    return _environment_check(
        area="Docker",
        name="Saved Docker Smoke Evidence",
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def _docker_environment_evidence(environment: Any) -> str:
    if not isinstance(environment, dict):
        return ""
    details = []
    for key in [
        "docker_cli_path",
        "DOCKER_HOST",
        "docker_desktop_application",
        "colima_binary",
    ]:
        value = environment.get(key)
        if value:
            details.append(f"{key}=`{value}`")
    if not details:
        return ""
    return "Host hints: " + ", ".join(details) + "."


def _environment_live_calibration_check(
    check: LiveCalibrationCheck,
) -> EnvironmentReadinessCheck:
    status = "passed" if check.status == "passed" else "warning"
    return _environment_check(
        area="Model Providers",
        name=check.name,
        status=status,
        evidence=check.evidence,
        next_action=check.next_action,
    )


def _environment_check(
    *,
    area: str,
    name: str,
    status: str,
    evidence: str,
    next_action: str,
) -> EnvironmentReadinessCheck:
    return EnvironmentReadinessCheck(
        area=area,
        name=name,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def _environment_readiness_status(checks: list[EnvironmentReadinessCheck]) -> str:
    statuses = {check.status for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _environment_remediation_commands(
    *,
    docker_payload: dict[str, Any] | None,
    calibration: LiveCalibrationReport,
) -> list[str]:
    commands: list[str] = []
    if docker_payload is not None:
        commands.extend(_payload_string_list(docker_payload, "remediation_commands"))
    else:
        commands.extend(
            [
                "docker context ls",
                "docker version",
                "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke --json",
            ]
        )
    commands.extend(calibration.smoke_commands)
    commands.append(
        "PYTHONPATH=src python3 -m patchsmith.cli environment-readiness "
        "--project-root . --artifacts-dir artifacts --json"
    )
    return _dedupe_strings(commands)
