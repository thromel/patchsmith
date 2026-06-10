from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import struct
import time
import tomllib
import zlib
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from patchsmith.observability import (
    ArtifactIndex,
    ExperimentMetricIndexEntry,
    FailureArtifactReport,
    build_artifact_index,
    build_failure_report,
    write_artifact_index,
    write_failure_report,
)

PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class DemoReadinessGate:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoReadinessReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    experiment_count: int
    run_count: int
    metric_count: int
    runs_requiring_attention: int
    failure_categories: dict[str, int]
    model_providers: dict[str, int]
    gates: list[DemoReadinessGate]
    demo_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failure_categories": self.failure_categories,
            "model_providers": self.model_providers,
            "gates": [gate.to_dict() for gate in self.gates],
            "demo_commands": self.demo_commands,
        }


@dataclass(frozen=True)
class LiveCalibrationCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveCalibrationReport:
    artifacts_dir: str
    generated_at: str
    calibration_status: str
    saved_live_provider_count: int
    deepagents_package_run_count: int
    deepagents_compatibility_run_count: int
    openai_agents_package_run_count: int
    openai_agents_compatibility_run_count: int
    model_providers: dict[str, int]
    checks: list[LiveCalibrationCheck]
    smoke_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "calibration_status": self.calibration_status,
            "saved_live_provider_count": self.saved_live_provider_count,
            "deepagents_package_run_count": self.deepagents_package_run_count,
            "deepagents_compatibility_run_count": self.deepagents_compatibility_run_count,
            "openai_agents_package_run_count": self.openai_agents_package_run_count,
            "openai_agents_compatibility_run_count": (
                self.openai_agents_compatibility_run_count
            ),
            "model_providers": self.model_providers,
            "checks": [check.to_dict() for check in self.checks],
            "smoke_commands": self.smoke_commands,
        }


@dataclass(frozen=True)
class LiveCalibrationPlanRun:
    name: str
    stage: str
    status: str
    runtime: str
    planner: str
    context_provider: str
    output_path: str
    requires_credentials: bool
    command: str
    success_evidence: str
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveCalibrationPlanReport:
    artifacts_dir: str
    generated_at: str
    plan_status: str
    calibration_status: str
    saved_live_provider_count: int
    credentials_configured: bool
    model: str
    cost_rates_configured: bool
    runs: list[LiveCalibrationPlanRun]
    prerequisites: list[LiveCalibrationCheck]
    claim_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        run_statuses = [run.status for run in self.runs]
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "plan_status": self.plan_status,
            "calibration_status": self.calibration_status,
            "saved_live_provider_count": self.saved_live_provider_count,
            "credentials_configured": self.credentials_configured,
            "model": self.model,
            "cost_rates_configured": self.cost_rates_configured,
            "run_count": len(self.runs),
            "ready_runs": run_statuses.count("ready"),
            "blocked_runs": run_statuses.count("blocked"),
            "runs": [run.to_dict() for run in self.runs],
            "prerequisites": [check.to_dict() for check in self.prerequisites],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class DockerSmokeCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DockerSmokeReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    smoke_status: str
    docker_binary: str
    image: str
    task_dir: str
    test_command: str
    runtime: str
    context_provider: str
    run_report_path: str | None
    run_trace_path: str | None
    run_id: str | None
    test_exit_code: int | None
    checks: list[DockerSmokeCheck]
    environment: dict[str, str]
    remediation_commands: list[str]
    build_command: str
    smoke_command: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "smoke_status": self.smoke_status,
            "docker_binary": self.docker_binary,
            "image": self.image,
            "task_dir": self.task_dir,
            "test_command": self.test_command,
            "runtime": self.runtime,
            "context_provider": self.context_provider,
            "run_report_path": self.run_report_path,
            "run_trace_path": self.run_trace_path,
            "run_id": self.run_id,
            "test_exit_code": self.test_exit_code,
            "checks": [check.to_dict() for check in self.checks],
            "environment": self.environment,
            "remediation_commands": self.remediation_commands,
            "build_command": self.build_command,
            "smoke_command": self.smoke_command,
        }


@dataclass(frozen=True)
class EnvironmentReadinessCheck:
    area: str
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentReadinessReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    passed_count: int
    warning_count: int
    blocked_count: int
    checks: list[EnvironmentReadinessCheck]
    remediation_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "checks": [check.to_dict() for check in self.checks],
            "remediation_commands": self.remediation_commands,
        }


@dataclass(frozen=True)
class DemoScriptSection:
    title: str
    duration_seconds: int
    on_screen: str
    narration: str
    artifact: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoScriptReport:
    artifacts_dir: str
    generated_at: str
    target_duration_seconds: int
    readiness_status: str
    caveat: str
    sections: list[DemoScriptSection]
    rehearsal_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "target_duration_seconds": self.target_duration_seconds,
            "readiness_status": self.readiness_status,
            "caveat": self.caveat,
            "sections": [section.to_dict() for section in self.sections],
            "rehearsal_commands": self.rehearsal_commands,
        }


@dataclass(frozen=True)
class DemoMediaReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    width: int
    height: int
    markdown_path: str
    svg_path: str
    png_path: str
    highlights: list[str]
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalEvaluationMetric:
    experiment: str
    kind: str
    lane: str
    task_count: int | None
    completed_count: int | None
    primary_metric: str
    secondary_metric: str
    avg_latency_ms: float | None
    estimated_cost_usd: float | None
    risk_note: str | None
    report_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalEvaluationReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    experiment_count: int
    run_count: int
    metric_count: int
    runs_requiring_attention: int
    failure_categories: dict[str, int]
    model_providers: dict[str, int]
    deepagents_package_run_count: int
    deepagents_compatibility_run_count: int
    openai_agents_package_run_count: int
    openai_agents_compatibility_run_count: int
    metrics: list[FinalEvaluationMetric]
    decisions: list[str]
    limitations: list[str]
    review_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failure_categories": self.failure_categories,
            "model_providers": self.model_providers,
            "deepagents_package_run_count": self.deepagents_package_run_count,
            "deepagents_compatibility_run_count": self.deepagents_compatibility_run_count,
            "openai_agents_package_run_count": self.openai_agents_package_run_count,
            "openai_agents_compatibility_run_count": (
                self.openai_agents_compatibility_run_count
            ),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "decisions": self.decisions,
            "limitations": self.limitations,
            "review_artifacts": self.review_artifacts,
        }


@dataclass(frozen=True)
class MvpProgressItem:
    category: str
    item: str
    status: str
    evidence: str
    next_action: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MvpProgressCategory:
    name: str
    item_count: int
    passed_count: int
    warning_count: int
    blocked_count: int
    missing_count: int
    completion_percent: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MvpProgressReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    completion_percent: float
    status: str
    item_count: int
    passed_count: int
    warning_count: int
    blocked_count: int
    missing_count: int
    categories: list[MvpProgressCategory]
    items: list[MvpProgressItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "completion_percent": self.completion_percent,
            "status": self.status,
            "item_count": self.item_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "missing_count": self.missing_count,
            "categories": [category.to_dict() for category in self.categories],
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class DeliveryAuditItem:
    requirement: str
    status: str
    evidence: str
    source: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryAuditReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    delivery_status: str
    completion_percent: float
    item_count: int
    passed_count: int
    warning_count: int
    blocked_count: int
    missing_count: int
    items: list[DeliveryAuditItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "delivery_status": self.delivery_status,
            "completion_percent": self.completion_percent,
            "item_count": self.item_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "missing_count": self.missing_count,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class QualityGateCheck:
    name: str
    status: str
    command: list[str]
    cwd: str
    exit_code: int | None
    duration_ms: int
    stdout_path: str | None
    stderr_path: str | None
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityGateReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    quality_status: str
    passed_count: int
    failed_count: int
    skipped_count: int
    checks: list[QualityGateCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "quality_status": self.quality_status,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ReleaseHygieneCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseHygieneReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    release_status: str
    passed_count: int
    warning_count: int
    blocked_count: int
    checks: list[ReleaseHygieneCheck]
    review_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "release_status": self.release_status,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "checks": [check.to_dict() for check in self.checks],
            "review_artifacts": self.review_artifacts,
        }


@dataclass(frozen=True)
class LaunchBlockerItem:
    blocker_id: str
    status: str
    severity: str
    area: str
    summary: str
    evidence: str
    next_action: str
    source_artifact: str
    dependencies: list[str] = field(default_factory=list)
    remediation_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaunchBlockerReport:
    artifacts_dir: str
    generated_at: str
    launch_status: str
    item_count: int
    blocked_count: int
    warning_count: int
    ready_count: int
    items: list[LaunchBlockerItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "launch_status": self.launch_status,
            "item_count": self.item_count,
            "blocked_count": self.blocked_count,
            "warning_count": self.warning_count,
            "ready_count": self.ready_count,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class ProjectStatusSurface:
    name: str
    status: str
    evidence: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectEvidenceFreshness:
    source: str
    status: str
    generated_at: str | None
    age_seconds: int | None
    threshold_seconds: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectStatusReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    overall_status: str
    mvp_status: str
    mvp_completion_percent: float
    delivery_status: str
    delivery_completion_percent: float
    quality_status: str
    launch_status: str
    release_status: str
    docker_smoke_status: str
    environment_readiness_status: str
    live_calibration_status: str
    saved_live_provider_count: int
    deepagents_package_run_count: int
    deepagents_compatibility_run_count: int
    openai_agents_package_run_count: int
    openai_agents_compatibility_run_count: int
    experiment_count: int
    run_count: int
    metric_count: int
    blocker_count: int
    warning_count: int
    evidence_freshness_status: str
    stale_source_count: int
    undated_source_count: int
    missing_sources: list[str]
    surfaces: list[ProjectStatusSurface]
    evidence_freshness: list[ProjectEvidenceFreshness]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "overall_status": self.overall_status,
            "mvp_status": self.mvp_status,
            "mvp_completion_percent": self.mvp_completion_percent,
            "delivery_status": self.delivery_status,
            "delivery_completion_percent": self.delivery_completion_percent,
            "quality_status": self.quality_status,
            "launch_status": self.launch_status,
            "release_status": self.release_status,
            "docker_smoke_status": self.docker_smoke_status,
            "environment_readiness_status": self.environment_readiness_status,
            "live_calibration_status": self.live_calibration_status,
            "saved_live_provider_count": self.saved_live_provider_count,
            "deepagents_package_run_count": self.deepagents_package_run_count,
            "deepagents_compatibility_run_count": self.deepagents_compatibility_run_count,
            "openai_agents_package_run_count": self.openai_agents_package_run_count,
            "openai_agents_compatibility_run_count": self.openai_agents_compatibility_run_count,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "evidence_freshness_status": self.evidence_freshness_status,
            "stale_source_count": self.stale_source_count,
            "undated_source_count": self.undated_source_count,
            "missing_sources": self.missing_sources,
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "evidence_freshness": [
                freshness.to_dict() for freshness in self.evidence_freshness
            ],
        }


@dataclass(frozen=True)
class EvidenceRefreshStep:
    name: str
    status: str
    duration_ms: int
    artifact_paths: list[str]
    summary: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceRefreshReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    refresh_status: str
    step_count: int
    passed_count: int
    failed_count: int
    skipped_count: int
    quality_gate_refreshed: bool
    docker_smoke_refreshed: bool
    steps: list[EvidenceRefreshStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "refresh_status": self.refresh_status,
            "step_count": self.step_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "quality_gate_refreshed": self.quality_gate_refreshed,
            "docker_smoke_refreshed": self.docker_smoke_refreshed,
            "steps": [step.to_dict() for step in self.steps],
        }


def build_demo_readiness_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> DemoReadinessReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    failure_report = build_failure_report(
        artifacts_dir=artifacts_dir,
        max_runs=max_failure_runs,
    )
    model_providers = _discover_model_providers(Path(index.artifacts_dir))
    gates = _demo_readiness_gates(
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        metric_kinds={metric.kind for metric in index.metrics},
        failure_report=failure_report,
        model_providers=model_providers,
    )
    return DemoReadinessReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_now(),
        readiness_status=_readiness_status(gates),
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        runs_requiring_attention=failure_report.runs_requiring_attention,
        failure_categories=failure_report.category_counts,
        model_providers=model_providers,
        gates=gates,
        demo_commands=_demo_commands(),
    )


def build_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    checks = _release_hygiene_checks(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        readiness=readiness,
    )
    status_counts = Counter(check.status for check in checks)
    return ReleaseHygieneReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        release_status=_release_status(checks),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        checks=checks,
        review_artifacts=[
            "artifacts/experiments/index.html",
            "artifacts/experiments/failure_report.md",
            "artifacts/experiments/demo_readiness.md",
            "artifacts/experiments/calibration_readiness.md",
            "artifacts/experiments/launch_blockers.md",
            "artifacts/experiments/demo_script.md",
            "artifacts/experiments/demo_media.svg",
            "artifacts/experiments/demo_media.png",
            "artifacts/experiments/quality_gate.md",
            "artifacts/experiments/project_status.md",
            "artifacts/experiments/final_evaluation.md",
            "artifacts/experiments/delivery_audit.md",
            "artifacts/experiments/release_hygiene.md",
        ],
    )


def write_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    report = build_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_release_hygiene_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_release_hygiene_report(report: ReleaseHygieneReport) -> str:
    lines = [
        "# PatchSmith Release Hygiene Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Release status: `{report.release_status}`",
        f"- Passed checks: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            _release_decision(report),
        ]
    )
    return "\n".join(lines) + "\n"


def build_launch_blocker_report(*, artifacts_dir: Path) -> LaunchBlockerReport:
    artifacts_dir = artifacts_dir.resolve()
    items = _launch_blocker_items(artifacts_dir)
    status_counts = Counter(item.status for item in items)
    return LaunchBlockerReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        launch_status=_launch_blocker_status(items),
        item_count=len(items),
        blocked_count=status_counts.get("blocked", 0),
        warning_count=status_counts.get("warning", 0),
        ready_count=status_counts.get("ready", 0),
        items=items,
    )


def write_launch_blocker_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> LaunchBlockerReport:
    report = build_launch_blocker_report(artifacts_dir=artifacts_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_launch_blocker_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_launch_blocker_report(report: LaunchBlockerReport) -> str:
    lines = [
        "# PatchSmith Launch Blocker Backlog",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Launch status: `{report.launch_status}`",
        f"- Items: `{report.item_count}`",
        f"- Blocked: `{report.blocked_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Ready: `{report.ready_count}`",
        "",
        "## Prioritized Items",
        "",
        "| ID | Status | Severity | Area | Summary | Evidence | Next Action | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            f"{item.blocker_id} | "
            f"{item.status} | "
            f"{item.severity} | "
            f"{item.area} | "
            f"{_markdown_cell(item.summary)} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.next_action)} | "
            f"`{item.source_artifact}` |"
        )
    lines.extend(["", "## Dependency Chain", ""])
    for item in report.items:
        dependencies = ", ".join(f"`{dependency}`" for dependency in item.dependencies)
        lines.append(
            f"- `{item.blocker_id}`: "
            f"{dependencies if dependencies else 'no upstream blocker dependency'}"
        )
    lines.extend(["", "## Remediation Commands", ""])
    for item in report.items:
        lines.append(f"### `{item.blocker_id}`")
        lines.append("")
        if item.remediation_commands:
            lines.append("```bash")
            lines.extend(item.remediation_commands)
            lines.append("```")
        else:
            lines.append("No command needed.")
        lines.append("")
    lines.extend(["## Decision", "", _launch_blocker_decision(report)])
    return "\n".join(lines) + "\n"


def build_project_status_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
) -> ProjectStatusReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    generated_at_dt = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = _format_utc(generated_at_dt)
    sources = {
        "mvp": "experiments/mvp_progress.json",
        "delivery": "experiments/delivery_audit.json",
        "quality": "experiments/quality_gate.json",
        "launch": "experiments/launch_blockers.json",
        "docker": "experiments/docker_smoke.json",
        "environment": "experiments/environment_readiness.json",
        "release": "experiments/release_hygiene.json",
        "calibration": "experiments/calibration_readiness.json",
        "final": "experiments/final_evaluation.json",
        "index": "experiments/index.json",
    }
    payloads = {
        name: _load_json_artifact(artifacts_dir / source)
        for name, source in sources.items()
    }
    missing_sources = [
        source for name, source in sources.items() if payloads[name] is None
    ]
    evidence_freshness = _project_evidence_freshness(
        sources=sources,
        payloads=payloads,
        as_of=generated_at_dt,
    )
    stale_source_count = sum(
        1 for freshness in evidence_freshness if freshness.status == "stale"
    )
    undated_source_count = sum(
        1 for freshness in evidence_freshness if freshness.status == "undated"
    )
    mvp = payloads["mvp"] or {}
    delivery = payloads["delivery"] or {}
    quality = payloads["quality"] or {}
    launch = payloads["launch"] or {}
    docker = payloads["docker"] or {}
    environment = payloads["environment"] or {}
    release = payloads["release"] or {}
    calibration = payloads["calibration"] or {}
    final = payloads["final"] or {}
    index = payloads["index"] or {}

    mvp_status = _payload_string(mvp, "status", "missing")
    mvp_completion = _payload_float(mvp, "completion_percent")
    delivery_status = _payload_string(delivery, "delivery_status", "missing")
    delivery_completion = _payload_float(delivery, "completion_percent")
    quality_status = _payload_string(quality, "quality_status", "missing")
    launch_status = _payload_string(launch, "launch_status", "missing")
    release_status = _payload_string(release, "release_status", "missing")
    docker_status = _payload_string(docker, "smoke_status", "missing")
    environment_status = _payload_string(
        environment, "readiness_status", "missing"
    )
    calibration_status = _payload_string(calibration, "calibration_status", "missing")
    blocker_count = _payload_int(launch, "blocked_count")
    warning_count = _payload_int(launch, "warning_count")
    experiment_count = _payload_int(final, "experiment_count") or _payload_int(
        index, "experiment_count"
    )
    run_count = _payload_int(final, "run_count") or _payload_int(index, "run_count")
    metric_count = _payload_int(final, "metric_count") or _payload_int(
        index, "metric_count"
    )
    model_providers = calibration.get("model_providers")
    model_provider_counts = model_providers if isinstance(model_providers, dict) else {}
    surfaces = [
        _project_status_surface(
            name="MVP Progress",
            status=mvp_status,
            evidence=(
                f"{mvp_completion:.1f}% complete; "
                f"{_payload_int(mvp, 'passed_count')} passed, "
                f"{_payload_int(mvp, 'warning_count')} warnings, "
                f"{_payload_int(mvp, 'blocked_count')} blocked."
            ),
            source=sources["mvp"],
        ),
        _project_status_surface(
            name="Delivery Audit",
            status=delivery_status,
            evidence=(
                f"{delivery_completion:.1f}% evidence-weighted; "
                f"{_payload_int(delivery, 'passed_count')} passed, "
                f"{_payload_int(delivery, 'warning_count')} warnings, "
                f"{_payload_int(delivery, 'blocked_count')} blockers."
            ),
            source=sources["delivery"],
        ),
        _project_status_surface(
            name="Quality Gate",
            status=quality_status,
            evidence=(
                f"{_payload_int(quality, 'passed_count')} passed, "
                f"{_payload_int(quality, 'failed_count')} failed, "
                f"{_payload_int(quality, 'skipped_count')} skipped."
            ),
            source=sources["quality"],
        ),
        _project_status_surface(
            name="Launch Blockers",
            status=launch_status,
            evidence=(
                f"{blocker_count} blockers, {warning_count} warnings, "
                f"{_payload_int(launch, 'ready_count')} ready items."
            ),
            source=sources["launch"],
        ),
        _project_status_surface(
            name="Docker Smoke",
            status=docker_status,
            evidence=(
                f"Image `{_payload_string(docker, 'image', 'unknown')}`; "
                f"run_id `{_payload_string(docker, 'run_id', 'none') or 'none'}`; "
                f"test_exit_code `{docker.get('test_exit_code')}`."
            ),
            source=sources["docker"],
        ),
        _project_status_surface(
            name="Live LLM Calibration",
            status=calibration_status,
            evidence=(
                f"{_payload_int(calibration, 'saved_live_provider_count')} live-provider runs; "
                f"providers {_provider_summary(model_provider_counts)}."
            ),
            source=sources["calibration"],
        ),
        _project_status_surface(
            name="Environment Readiness",
            status=environment_status,
            evidence=(
                f"{_payload_int(environment, 'passed_count')} passed, "
                f"{_payload_int(environment, 'warning_count')} warnings, "
                f"{_payload_int(environment, 'blocked_count')} blocked."
            ),
            source=sources["environment"],
        ),
        _project_status_surface(
            name="Adapter Evidence",
            status="recorded" if calibration else "missing",
            evidence=(
                f"{_payload_int(calibration, 'deepagents_package_run_count')} DeepAgents package-backed, "
                f"{_payload_int(calibration, 'deepagents_compatibility_run_count')} DeepAgents compatibility, "
                f"{_payload_int(calibration, 'openai_agents_package_run_count')} OpenAI Agents package-backed, "
                f"{_payload_int(calibration, 'openai_agents_compatibility_run_count')} OpenAI Agents compatibility."
            ),
            source=sources["calibration"],
        ),
        _project_status_surface(
            name="Release Hygiene",
            status=release_status,
            evidence=(
                f"{_payload_int(release, 'passed_count')} passed, "
                f"{_payload_int(release, 'warning_count')} warnings, "
                f"{_payload_int(release, 'blocked_count')} blocked."
            ),
            source=sources["release"],
        ),
        _project_status_surface(
            name="Saved Evidence Index",
            status="available" if experiment_count or run_count else "missing",
            evidence=(
                f"{experiment_count} experiments, {run_count} runs, "
                f"{metric_count} metric rows."
            ),
            source=sources["final"] if final else sources["index"],
        ),
    ]
    return ProjectStatusReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=generated_at,
        overall_status=_project_overall_status(
            missing_sources=missing_sources,
            delivery_status=delivery_status,
            launch_status=launch_status,
            quality_status=quality_status,
            release_status=release_status,
            mvp_status=mvp_status,
            calibration_status=calibration_status,
            environment_status=environment_status,
        ),
        mvp_status=mvp_status,
        mvp_completion_percent=mvp_completion,
        delivery_status=delivery_status,
        delivery_completion_percent=delivery_completion,
        quality_status=quality_status,
        launch_status=launch_status,
        release_status=release_status,
        docker_smoke_status=docker_status,
        environment_readiness_status=environment_status,
        live_calibration_status=calibration_status,
        saved_live_provider_count=_payload_int(calibration, "saved_live_provider_count"),
        deepagents_package_run_count=_payload_int(
            calibration, "deepagents_package_run_count"
        ),
        deepagents_compatibility_run_count=_payload_int(
            calibration, "deepagents_compatibility_run_count"
        ),
        openai_agents_package_run_count=_payload_int(
            calibration, "openai_agents_package_run_count"
        ),
        openai_agents_compatibility_run_count=_payload_int(
            calibration, "openai_agents_compatibility_run_count"
        ),
        experiment_count=experiment_count,
        run_count=run_count,
        metric_count=metric_count,
        blocker_count=blocker_count,
        warning_count=warning_count,
        evidence_freshness_status=_project_evidence_freshness_status(
            evidence_freshness
        ),
        stale_source_count=stale_source_count,
        undated_source_count=undated_source_count,
        missing_sources=missing_sources,
        surfaces=surfaces,
        evidence_freshness=evidence_freshness,
    )


def write_project_status_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> ProjectStatusReport:
    report = build_project_status_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_project_status_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_project_status_report(report: ProjectStatusReport) -> str:
    lines = [
        "# PatchSmith Project Status Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Overall status: `{report.overall_status}`",
        f"- MVP progress: `{report.mvp_completion_percent:.1f}%` (`{report.mvp_status}`)",
        (
            f"- Delivery audit: `{report.delivery_completion_percent:.1f}%` "
            f"(`{report.delivery_status}`)"
        ),
        f"- Quality gate: `{report.quality_status}`",
        f"- Launch status: `{report.launch_status}`",
        f"- Release status: `{report.release_status}`",
        f"- Docker smoke: `{report.docker_smoke_status}`",
        f"- Environment readiness: `{report.environment_readiness_status}`",
        f"- Live calibration: `{report.live_calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- OpenAI Agents package-backed runs: `{report.openai_agents_package_run_count}`",
        f"- OpenAI Agents compatibility-mode runs: `{report.openai_agents_compatibility_run_count}`",
        f"- Indexed experiments: `{report.experiment_count}`",
        f"- Indexed runs: `{report.run_count}`",
        f"- Metric rows: `{report.metric_count}`",
        f"- Launch blockers: `{report.blocker_count}`",
        f"- Launch warnings: `{report.warning_count}`",
        (
            f"- Evidence freshness: `{report.evidence_freshness_status}` "
            f"(`{report.stale_source_count}` stale, "
            f"`{report.undated_source_count}` undated)"
        ),
        "",
        "## Status Surfaces",
        "",
        "| Surface | Status | Evidence | Source |",
        "|---|---|---|---|",
    ]
    for surface in report.surfaces:
        lines.append(
            "| "
            f"{surface.name} | "
            f"{surface.status} | "
            f"{_markdown_cell(surface.evidence)} | "
            f"`{surface.source}` |"
        )
    lines.extend(["", "## Missing Sources", ""])
    if report.missing_sources:
        lines.extend(f"- `{source}`" for source in report.missing_sources)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Evidence Freshness",
            "",
            "| Source | Status | Generated At | Age | Detail |",
            "|---|---|---|---|---|",
        ]
    )
    for freshness in report.evidence_freshness:
        lines.append(
            "| "
            f"`{freshness.source}` | "
            f"{freshness.status} | "
            f"{_project_freshness_generated_at(freshness)} | "
            f"{_project_freshness_age(freshness)} | "
            f"{_markdown_cell(freshness.detail)} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report summarizes saved evidence artifacts; it does not rerun checks.",
            "- Use `quality-gate` for executable verification.",
            "- Use `docker-smoke` for Docker sandbox evidence.",
            "- Use `live-calibration` for live model-provider evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = 180,
    include_docker_smoke: bool = False,
    docker_smoke_skip_run: bool = False,
    docker_smoke_image: str = "patchsmith-seeded-smoke:py312",
    docker_binary: str = "docker",
) -> EvidenceRefreshReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    experiments_dir = artifacts_dir / "experiments"
    steps: list[EvidenceRefreshStep] = []

    def experiment_path(relative_path: str) -> Path:
        return experiments_dir / relative_path

    def output_paths(*relative_paths: str) -> list[str]:
        return [str(experiment_path(path)) for path in relative_paths]

    steps.append(
        _run_evidence_refresh_step(
            name="Artifact index",
            artifact_paths=output_paths("index.md", "index.json", "index.html"),
            action=lambda: write_artifact_index(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("index.md"),
                json_output_path=experiment_path("index.json"),
                html_output_path=experiment_path("index.html"),
                run_detail_output_dir=experiment_path("run-details"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Failure report",
            artifact_paths=output_paths("failure_report.md", "failure_report.json"),
            action=lambda: write_failure_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("failure_report.md"),
                json_output_path=experiment_path("failure_report.json"),
                max_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo readiness",
            artifact_paths=output_paths("demo_readiness.md", "demo_readiness.json"),
            action=lambda: write_demo_readiness_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_readiness.md"),
                json_output_path=experiment_path("demo_readiness.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Live calibration readiness",
            artifact_paths=output_paths(
                "calibration_readiness.md",
                "calibration_readiness.json",
            ),
            action=lambda: write_live_calibration_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("calibration_readiness.md"),
                json_output_path=experiment_path("calibration_readiness.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Live calibration plan",
            artifact_paths=output_paths(
                "live_calibration_plan.md",
                "live_calibration_plan.json",
            ),
            action=lambda: write_live_calibration_plan_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("live_calibration_plan.md"),
                json_output_path=experiment_path("live_calibration_plan.json"),
            ),
        )
    )
    if include_docker_smoke:
        steps.append(
            _run_evidence_refresh_step(
                name="Docker smoke",
                artifact_paths=output_paths("docker_smoke.md", "docker_smoke.json"),
                action=lambda: write_docker_smoke_report(
                    project_root=project_root,
                    artifacts_dir=artifacts_dir,
                    output_path=experiment_path("docker_smoke.md"),
                    json_output_path=experiment_path("docker_smoke.json"),
                    image=docker_smoke_image,
                    docker_binary=docker_binary,
                    run_seeded=not docker_smoke_skip_run,
                ),
            )
        )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Docker smoke",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths("docker_smoke.md", "docker_smoke.json"),
                summary=(
                    "Skipped by request. Run `docker-smoke` or pass "
                    "`--include-docker-smoke` to refresh Docker sandbox evidence."
                ),
            )
        )
    steps.append(
        _run_evidence_refresh_step(
            name="Environment readiness",
            artifact_paths=output_paths(
                "environment_readiness.md",
                "environment_readiness.json",
            ),
            action=lambda: write_environment_readiness_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("environment_readiness.md"),
                json_output_path=experiment_path("environment_readiness.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo script",
            artifact_paths=output_paths("demo_script.md", "demo_script.json"),
            action=lambda: write_demo_script_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_script.md"),
                json_output_path=experiment_path("demo_script.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo media",
            artifact_paths=output_paths(
                "demo_media.md",
                "demo_media.svg",
                "demo_media.png",
                "demo_media.json",
            ),
            action=lambda: write_demo_media_assets(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_media.md"),
                svg_output_path=experiment_path("demo_media.svg"),
                png_output_path=experiment_path("demo_media.png"),
                json_output_path=experiment_path("demo_media.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Final evaluation",
            artifact_paths=output_paths("final_evaluation.md", "final_evaluation.json"),
            action=lambda: write_final_evaluation_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("final_evaluation.md"),
                json_output_path=experiment_path("final_evaluation.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Launch blockers",
            artifact_paths=output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("launch_blockers.md"),
                json_output_path=experiment_path("launch_blockers.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="MVP progress",
            artifact_paths=output_paths("mvp_progress.md", "mvp_progress.json"),
            action=lambda: write_mvp_progress_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("mvp_progress.md"),
                json_output_path=experiment_path("mvp_progress.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    if include_quality_gate:
        steps.append(
            _run_evidence_refresh_step(
                name="Quality gate",
                artifact_paths=output_paths("quality_gate.md", "quality_gate.json"),
                action=lambda: write_quality_gate_report(
                    project_root=project_root,
                    artifacts_dir=artifacts_dir,
                    output_path=experiment_path("quality_gate.md"),
                    json_output_path=experiment_path("quality_gate.json"),
                    logs_dir=experiment_path("quality_gate_logs"),
                    timeout_seconds=quality_timeout_seconds,
                ),
            )
        )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Quality gate",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths("quality_gate.md", "quality_gate.json"),
                summary=(
                    "Skipped by request. Run `quality-gate` or pass "
                    "`--include-quality-gate` to execute tests and package build."
                ),
            )
        )
    steps.append(
        _run_evidence_refresh_step(
            name="Delivery audit pre-release",
            artifact_paths=output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("delivery_audit.md"),
                json_output_path=experiment_path("delivery_audit.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Project status pre-release",
            artifact_paths=output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("project_status.md"),
                json_output_path=experiment_path("project_status.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Release hygiene",
            artifact_paths=output_paths("release_hygiene.md", "release_hygiene.json"),
            action=lambda: write_release_hygiene_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("release_hygiene.md"),
                json_output_path=experiment_path("release_hygiene.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Launch blockers final",
            artifact_paths=output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("launch_blockers.md"),
                json_output_path=experiment_path("launch_blockers.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Delivery audit final",
            artifact_paths=output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("delivery_audit.md"),
                json_output_path=experiment_path("delivery_audit.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Project status final",
            artifact_paths=output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("project_status.md"),
                json_output_path=experiment_path("project_status.json"),
            ),
        )
    )
    status_counts = Counter(step.status for step in steps)
    return EvidenceRefreshReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        refresh_status=_evidence_refresh_status(steps),
        step_count=len(steps),
        passed_count=status_counts.get("passed", 0),
        failed_count=status_counts.get("failed", 0),
        skipped_count=status_counts.get("skipped", 0),
        quality_gate_refreshed=include_quality_gate,
        docker_smoke_refreshed=include_docker_smoke,
        steps=steps,
    )


def write_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = 180,
    include_docker_smoke: bool = False,
    docker_smoke_skip_run: bool = False,
    docker_smoke_image: str = "patchsmith-seeded-smoke:py312",
    docker_binary: str = "docker",
) -> EvidenceRefreshReport:
    report = build_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
        include_quality_gate=include_quality_gate,
        quality_timeout_seconds=quality_timeout_seconds,
        include_docker_smoke=include_docker_smoke,
        docker_smoke_skip_run=docker_smoke_skip_run,
        docker_smoke_image=docker_smoke_image,
        docker_binary=docker_binary,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_evidence_refresh_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


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


def build_live_calibration_report(
    *,
    artifacts_dir: Path,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationReport:
    artifacts_dir = artifacts_dir.resolve()
    environment = dict(os.environ if environment is None else environment)
    model_providers = _discover_model_providers(artifacts_dir)
    live_providers = _live_providers(model_providers)
    deepagents_modes = _discover_deepagents_adapter_modes(artifacts_dir)
    openai_agents_modes = _discover_openai_agents_adapter_modes(artifacts_dir)
    checks = _live_calibration_checks(
        model_providers=model_providers,
        deepagents_modes=deepagents_modes,
        openai_agents_modes=openai_agents_modes,
        environment=environment,
        package_availability=package_availability,
    )
    return LiveCalibrationReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        calibration_status=_live_calibration_status(checks, live_providers),
        saved_live_provider_count=sum(model_providers[provider] for provider in live_providers),
        deepagents_package_run_count=deepagents_modes.get("package_available", 0),
        deepagents_compatibility_run_count=deepagents_modes.get("compatibility_mode", 0),
        openai_agents_package_run_count=openai_agents_modes.get("package_available", 0),
        openai_agents_compatibility_run_count=openai_agents_modes.get(
            "compatibility_mode", 0
        ),
        model_providers=model_providers,
        checks=checks,
        smoke_commands=_live_calibration_commands(),
    )


def write_live_calibration_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationReport:
    report = build_live_calibration_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_live_calibration_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_live_calibration_report(report: LiveCalibrationReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Readiness",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- OpenAI Agents package-backed runs: `{report.openai_agents_package_run_count}`",
        (
            "- OpenAI Agents compatibility-mode runs: "
            f"`{report.openai_agents_compatibility_run_count}`"
        ),
        f"- Model providers: `{_provider_summary(report.model_providers)}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(["", "## Smoke Commands", ""])
    for command in report.smoke_commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(["## Decision", "", _live_calibration_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def build_live_calibration_plan_report(
    *,
    artifacts_dir: Path,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationPlanReport:
    artifacts_dir = artifacts_dir.resolve()
    environment = dict(os.environ if environment is None else environment)
    readiness = build_live_calibration_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    credentials_configured = bool(environment.get("OPENAI_API_KEY"))
    openai_sdk_available = _package_available("openai", package_availability)
    cost_rates_configured = bool(
        environment.get("PATCHSMITH_OPENAI_INPUT_COST_PER_1M", "").strip()
        and environment.get("PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M", "").strip()
    )
    model = environment.get("PATCHSMITH_OPENAI_MODEL", "").strip() or "planner_default"
    runs = _live_calibration_plan_runs(
        openai_sdk_available=openai_sdk_available,
        credentials_configured=credentials_configured,
        deepagents_available=_package_available("deepagents", package_availability),
        openai_agents_available=_package_available("agents", package_availability),
        saved_live_provider_count=readiness.saved_live_provider_count,
    )
    return LiveCalibrationPlanReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        plan_status=_live_calibration_plan_status(
            readiness=readiness,
            openai_sdk_available=openai_sdk_available,
            credentials_configured=credentials_configured,
        ),
        calibration_status=readiness.calibration_status,
        saved_live_provider_count=readiness.saved_live_provider_count,
        credentials_configured=credentials_configured,
        model=model,
        cost_rates_configured=cost_rates_configured,
        runs=runs,
        prerequisites=readiness.checks,
        claim_boundary=[
            "The plan artifact does not prove live model execution.",
            (
                "A publishable live-provider claim requires a saved run trace with "
                "non-offline model provider metadata and token usage."
            ),
            (
                "Run the single seeded smoke before the full seeded evaluation to "
                "control cost and failure blast radius."
            ),
        ],
    )


def write_live_calibration_plan_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationPlanReport:
    report = build_live_calibration_plan_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_live_calibration_plan_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_live_calibration_plan_report(report: LiveCalibrationPlanReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Plan",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Plan status: `{report.plan_status}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- Credentials configured: `{str(report.credentials_configured).lower()}`",
        f"- Model: `{report.model}`",
        f"- Cost rates configured: `{str(report.cost_rates_configured).lower()}`",
        "",
        "## Prerequisites",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.prerequisites:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Planned Runs",
            "",
            "| Run | Stage | Status | Runtime | Planner | Context | Credentials | Output | Success Evidence | Claim Boundary |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in report.runs:
        lines.append(
            "| "
            f"{run.name} | "
            f"{run.stage} | "
            f"{run.status} | "
            f"{run.runtime} | "
            f"{run.planner} | "
            f"{run.context_provider} | "
            f"{str(run.requires_credentials).lower()} | "
            f"{_markdown_cell(run.output_path)} | "
            f"{_markdown_cell(run.success_evidence)} | "
            f"{_markdown_cell(run.claim_boundary)} |"
        )
    lines.extend(["", "## Commands", ""])
    for run in report.runs:
        lines.extend([f"### {run.name}", "", "```bash", run.command, "```", ""])
    lines.extend(["## Claim Boundary", ""])
    for claim in report.claim_boundary:
        lines.append(f"- {claim}")
    lines.extend(["", "## Decision", "", _live_calibration_plan_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def build_docker_smoke_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    image: str = "patchsmith-seeded-smoke:py312",
    task_dir: Path | None = None,
    test_command: str = "python3 -m pytest",
    runtime: str = "heuristic",
    context_provider: str = "native_hybrid",
    docker_binary: str = "docker",
    run_seeded: bool = True,
) -> DockerSmokeReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    task_dir = (
        project_root / "evals" / "tasks" / "seeded_bugs_v1" / "task_001_logic_bug"
        if task_dir is None
        else (task_dir if task_dir.is_absolute() else project_root / task_dir)
    )
    task_dir = task_dir.resolve()
    checks: list[DockerSmokeCheck] = []
    run_report_path: str | None = None
    run_trace_path: str | None = None
    run_id: str | None = None
    test_exit_code: int | None = None

    docker_check = _docker_daemon_check(docker_binary)
    checks.append(docker_check)
    if docker_check.status != "passed":
        checks.append(
            DockerSmokeCheck(
                name="Smoke Image",
                status="skipped",
                evidence="Docker daemon was not available, so the image was not inspected.",
                next_action=f"Start Docker and build `{image}` before running the smoke.",
            )
        )
        checks.append(
            DockerSmokeCheck(
                name="Seeded Docker Test Run",
                status="skipped",
                evidence="Docker daemon was not available, so the seeded test was not run.",
                next_action="Rerun `docker-smoke` when Docker is available.",
            )
        )
    else:
        image_check = _docker_image_check(docker_binary, image)
        checks.append(image_check)
        if image_check.status != "passed":
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="skipped",
                    evidence="Required Docker image was not available locally.",
                    next_action=f"Build `{image}` and rerun `docker-smoke`.",
                )
            )
        elif not run_seeded:
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="skipped",
                    evidence="Seeded run was skipped by request.",
                    next_action="Rerun without `--skip-run` for executable smoke evidence.",
                )
            )
        else:
            result = _run_docker_seeded_smoke(
                task_dir=task_dir,
                artifacts_dir=artifacts_dir,
                test_command=test_command,
                runtime=runtime,
                context_provider=context_provider,
                sandbox_image=image,
            )
            run_report_path = str(result.report_path)
            run_trace_path = str(result.trace_path)
            run_id = result.run_id
            test_exit_code = result.test_result.exit_code if result.test_result else None
            passed = result.test_result is not None and result.test_result.exit_code == 0
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="passed" if passed else "failed",
                    evidence=(
                        f"Run `{result.run_id}` test exit code: "
                        f"{test_exit_code if test_exit_code is not None else 'none'}."
                    ),
                    next_action=(
                        "No action needed."
                        if passed
                        else "Inspect the run report and Docker stderr for image/dependency gaps."
                    ),
                )
            )

    build_command = (
        f"{docker_binary} build -f docker/seeded-smoke.Dockerfile "
        f"-t {image} ."
    )
    smoke_command = (
        "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke "
        f"--image {image} --json"
    )
    environment_snapshot = _docker_environment_snapshot(docker_binary)
    return DockerSmokeReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        smoke_status=_docker_smoke_status(checks),
        docker_binary=docker_binary,
        image=image,
        task_dir=str(task_dir),
        test_command=test_command,
        runtime=runtime,
        context_provider=context_provider,
        run_report_path=run_report_path,
        run_trace_path=run_trace_path,
        run_id=run_id,
        test_exit_code=test_exit_code,
        checks=checks,
        environment=environment_snapshot,
        remediation_commands=_docker_remediation_commands(
            docker_binary=docker_binary,
            build_command=build_command,
            smoke_command=smoke_command,
            environment=environment_snapshot,
        ),
        build_command=build_command,
        smoke_command=smoke_command,
    )


def write_docker_smoke_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    image: str = "patchsmith-seeded-smoke:py312",
    task_dir: Path | None = None,
    test_command: str = "python3 -m pytest",
    runtime: str = "heuristic",
    context_provider: str = "native_hybrid",
    docker_binary: str = "docker",
    run_seeded: bool = True,
) -> DockerSmokeReport:
    report = build_docker_smoke_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        image=image,
        task_dir=task_dir,
        test_command=test_command,
        runtime=runtime,
        context_provider=context_provider,
        docker_binary=docker_binary,
        run_seeded=run_seeded,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_docker_smoke_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_docker_smoke_report(report: DockerSmokeReport) -> str:
    lines = [
        "# PatchSmith Docker Smoke Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Smoke status: `{report.smoke_status}`",
        f"- Docker binary: `{report.docker_binary}`",
        f"- Image: `{report.image}`",
        f"- Task directory: `{report.task_dir}`",
        f"- Test command: `{report.test_command}`",
        f"- Runtime: `{report.runtime}`",
        f"- Context provider: `{report.context_provider}`",
        f"- Run ID: `{report.run_id or 'n/a'}`",
        f"- Test exit code: `{report.test_exit_code if report.test_exit_code is not None else 'n/a'}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Environment",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
    )
    for key, value in report.environment.items():
        lines.append(f"| {key} | {_markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "Diagnostic and remediation commands:",
            "",
            "```bash",
            *report.remediation_commands,
            "```",
            "",
            "Build the seeded smoke image:",
            "",
            "```bash",
            report.build_command,
            "```",
            "",
            "Run the smoke:",
            "",
            "```bash",
            report.smoke_command,
            "```",
        ]
    )
    if report.run_report_path or report.run_trace_path:
        lines.extend(["", "## Run Artifacts", ""])
        if report.run_report_path:
            lines.append(f"- Report: `{report.run_report_path}`")
        if report.run_trace_path:
            lines.append(f"- Trace: `{report.run_trace_path}`")
    lines.extend(["", "## Decision", "", _docker_smoke_decision(report)])
    return "\n".join(lines) + "\n"


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
    docker_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "docker_smoke.json"
    )
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_environment_readiness_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
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


def build_final_evaluation_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    metrics = [_final_metric(metric) for metric in index.metrics]
    deepagents_modes = _discover_deepagents_adapter_modes(Path(index.artifacts_dir))
    openai_agents_modes = _discover_openai_agents_adapter_modes(Path(index.artifacts_dir))
    return FinalEvaluationReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_now(),
        readiness_status=readiness.readiness_status,
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        runs_requiring_attention=readiness.runs_requiring_attention,
        failure_categories=readiness.failure_categories,
        model_providers=readiness.model_providers,
        deepagents_package_run_count=deepagents_modes.get("package_available", 0),
        deepagents_compatibility_run_count=deepagents_modes.get("compatibility_mode", 0),
        openai_agents_package_run_count=openai_agents_modes.get("package_available", 0),
        openai_agents_compatibility_run_count=openai_agents_modes.get(
            "compatibility_mode", 0
        ),
        metrics=metrics,
        decisions=_final_evaluation_decisions(
            readiness, metrics, deepagents_modes, openai_agents_modes
        ),
        limitations=_final_evaluation_limitations(
            readiness, deepagents_modes, openai_agents_modes
        ),
        review_artifacts=_final_review_artifacts(),
    )


def write_final_evaluation_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    report = build_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_final_evaluation_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def build_mvp_progress_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> MvpProgressReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    calibration = build_live_calibration_report(artifacts_dir=artifacts_dir)
    failure_report = build_failure_report(
        artifacts_dir=artifacts_dir,
        max_runs=max_failure_runs,
    )
    items = _mvp_progress_items(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
        readiness=readiness,
        calibration=calibration,
        failure_report=failure_report,
    )
    categories = _mvp_progress_categories(items)
    passed_count = sum(1 for item in items if item.status == "passed")
    warning_count = sum(1 for item in items if item.status == "warning")
    blocked_count = sum(1 for item in items if item.status == "blocked")
    missing_count = sum(1 for item in items if item.status == "missing")
    completion_percent = _mvp_completion_percent(items)
    status = _mvp_progress_status(
        completion_percent=completion_percent,
        warning_count=warning_count,
        blocked_count=blocked_count,
        missing_count=missing_count,
    )
    return MvpProgressReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        completion_percent=completion_percent,
        status=status,
        item_count=len(items),
        passed_count=passed_count,
        warning_count=warning_count,
        blocked_count=blocked_count,
        missing_count=missing_count,
        categories=categories,
        items=items,
    )


def write_mvp_progress_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> MvpProgressReport:
    report = build_mvp_progress_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_mvp_progress_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_mvp_progress_report(report: MvpProgressReport) -> str:
    lines = [
        "# PatchSmith MVP Progress Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Status: `{report.status}`",
        f"- Evidence-weighted completion: `{report.completion_percent:.1f}%`",
        f"- Items: `{report.item_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        f"- Missing: `{report.missing_count}`",
        "",
        "## Category Summary",
        "",
        "| Category | Completion | Passed | Warnings | Blockers | Missing | Items |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category in report.categories:
        lines.append(
            "| "
            f"{category.name} | "
            f"{category.completion_percent:.1f}% | "
            f"{category.passed_count} | "
            f"{category.warning_count} | "
            f"{category.blocked_count} | "
            f"{category.missing_count} | "
            f"{category.item_count} |"
        )
    lines.extend(
        [
            "",
            "## Checklist Evidence",
            "",
            "| Category | Item | Status | Evidence | Next Action |",
            "|---|---|---|---|---|",
        ]
    )
    for item in report.items:
        lines.append(
            "| "
            f"{item.category} | "
            f"{item.item} | "
            f"{item.status} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Scoring",
            "",
            "- Passed items count as 1.0.",
            "- Warning items count as 0.5 because evidence exists but is incomplete.",
            "- Blocked and missing items count as 0.0.",
            "- This is an evidence report, not a substitute for rerunning verification gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
) -> DeliveryAuditReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    items = _delivery_audit_items(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
    )
    status_counts = Counter(item.status for item in items)
    return DeliveryAuditReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        delivery_status=_delivery_status(items),
        completion_percent=_delivery_completion_percent(items),
        item_count=len(items),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        missing_count=status_counts.get("missing", 0),
        items=items,
    )


def write_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> DeliveryAuditReport:
    report = build_delivery_audit_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_delivery_audit_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_delivery_audit_report(report: DeliveryAuditReport) -> str:
    lines = [
        "# PatchSmith Delivery Audit",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Delivery status: `{report.delivery_status}`",
        f"- Evidence-weighted completion: `{report.completion_percent:.1f}%`",
        f"- Items: `{report.item_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        f"- Missing: `{report.missing_count}`",
        "",
        "## Requirement Evidence",
        "",
        "| Requirement | Status | Evidence | Source | Next Action |",
        "|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            f"{item.requirement} | "
            f"{item.status} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.source)} | "
            f"{_markdown_cell(item.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Scoring",
            "",
            "- Passed items count as 1.0.",
            "- Warning items count as 0.5 because evidence exists but is incomplete.",
            "- Blocked and missing items count as 0.0.",
            "- This audit is a delivery status artifact; it does not replace rerunning tests or live calibration.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_quality_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    logs_dir: Path | None = None,
    timeout_seconds: int = 180,
    include_tests: bool = True,
    include_build: bool = True,
) -> QualityGateReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    logs_dir = (
        artifacts_dir / "experiments" / "quality_gate_logs"
        if logs_dir is None
        else logs_dir.resolve()
    )
    build_outdir = Path("/tmp/patchsmith-quality-gate-dist")
    commands: list[tuple[str, list[str] | None, str]] = [
        (
            "Compile Python sources",
            ["python3", "-m", "compileall", "-q", "src/patchsmith", "tests"],
            "Python compileall finished successfully.",
        ),
        (
            "Whitespace diff check",
            ["git", "diff", "--check"],
            "Git diff whitespace check passed.",
        ),
        (
            "Pytest suite",
            ["python3", "-m", "pytest", "-q"] if include_tests else None,
            "Pytest completed successfully.",
        ),
        (
            "Package build",
            [
                "uv",
                "run",
                "--with",
                "build",
                "--no-project",
                "python",
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                str(build_outdir),
            ]
            if include_build
            else None,
            "Source distribution and wheel build completed successfully.",
        ),
    ]
    checks = [
        _run_quality_gate_check(
            name=name,
            command=command,
            success_summary=success_summary,
            project_root=project_root,
            logs_dir=logs_dir,
            timeout_seconds=timeout_seconds,
        )
        for name, command, success_summary in commands
    ]
    status_counts = Counter(check.status for check in checks)
    return QualityGateReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        quality_status=_quality_gate_status(checks),
        passed_count=status_counts.get("passed", 0),
        failed_count=status_counts.get("failed", 0),
        skipped_count=status_counts.get("skipped", 0),
        checks=checks,
    )


def write_quality_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    logs_dir: Path | None = None,
    timeout_seconds: int = 180,
    include_tests: bool = True,
    include_build: bool = True,
) -> QualityGateReport:
    report = build_quality_gate_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        logs_dir=logs_dir,
        timeout_seconds=timeout_seconds,
        include_tests=include_tests,
        include_build=include_build,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_quality_gate_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_quality_gate_report(report: QualityGateReport) -> str:
    lines = [
        "# PatchSmith Quality Gate Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Quality status: `{report.quality_status}`",
        f"- Passed checks: `{report.passed_count}`",
        f"- Failed checks: `{report.failed_count}`",
        f"- Skipped checks: `{report.skipped_count}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Exit | Duration | Command | Stdout | Stderr | Summary |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{check.exit_code if check.exit_code is not None else ''} | "
            f"{check.duration_ms}ms | "
            f"{_markdown_cell(shlex.join(check.command))} | "
            f"{_markdown_cell(check.stdout_path or '')} | "
            f"{_markdown_cell(check.stderr_path or '')} | "
            f"{_markdown_cell(check.summary)} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- A passed quality gate proves local command execution for this checkout.",
            "- It does not prove Docker sandbox availability or live LLM calibration.",
            "- Release readiness still depends on release hygiene and launch blocker artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_final_evaluation_report(report: FinalEvaluationReport) -> str:
    lines = [
        "# PatchSmith Final Evaluation Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Experiment count: `{report.experiment_count}`",
        f"- Saved run count: `{report.run_count}`",
        f"- Normalized metric rows: `{report.metric_count}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- OpenAI Agents package-backed runs: `{report.openai_agents_package_run_count}`",
        (
            "- OpenAI Agents compatibility-mode runs: "
            f"`{report.openai_agents_compatibility_run_count}`"
        ),
        "",
        "## Executive Conclusion",
        "",
        _executive_conclusion(report),
        "",
        "## Metric Evidence",
        "",
        (
            "| Experiment | Kind | Lane | Tasks | Primary | Secondary | Latency | "
            "Cost | Risk Note | Report |"
        ),
        "|---|---|---|---:|---|---|---:|---:|---|---|",
    ]
    for metric in report.metrics:
        lines.append(
            "| "
            f"{metric.experiment} | "
            f"{metric.kind} | "
            f"{metric.lane} | "
            f"{_task_count_cell(metric)} | "
            f"{metric.primary_metric} | "
            f"{metric.secondary_metric} | "
            f"{_latency_cell(metric.avg_latency_ms)} | "
            f"{_cost_cell(metric.estimated_cost_usd)} | "
            f"{_markdown_cell(metric.risk_note or '')} | "
            f"{_path_cell(metric.report_path)} |"
        )

    lines.extend(["", "## Decisions", ""])
    for decision in report.decisions:
        lines.append(f"- {decision}")

    lines.extend(["", "## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")

    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")

    lines.extend(
        [
            "",
            "## Public Claim Boundary",
            "",
            (
                "This report supports an offline seeded-suite portfolio demo. It does not "
                "claim live LLM quality unless saved artifacts include non-offline provider "
                "metadata and corresponding cost/token evidence."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def build_demo_script_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> DemoScriptReport:
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    sections = _demo_script_sections(readiness)
    return DemoScriptReport(
        artifacts_dir=readiness.artifacts_dir,
        generated_at=_utc_now(),
        target_duration_seconds=sum(section.duration_seconds for section in sections),
        readiness_status=readiness.readiness_status,
        caveat=_demo_script_caveat(readiness),
        sections=sections,
        rehearsal_commands=_demo_script_rehearsal_commands(),
    )


def build_demo_media_report(
    *,
    artifacts_dir: Path,
    markdown_path: Path,
    svg_path: Path,
    png_path: Path,
    max_failure_runs: int | None = None,
) -> DemoMediaReport:
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    highlights = [
        f"{readiness.experiment_count} experiments",
        f"{readiness.run_count} saved runs",
        f"{readiness.metric_count} metric rows",
        f"{readiness.runs_requiring_attention} runs requiring attention",
        f"providers: {_provider_summary(readiness.model_providers)}",
    ]
    return DemoMediaReport(
        artifacts_dir=str(Path(readiness.artifacts_dir)),
        generated_at=_utc_now(),
        readiness_status=readiness.readiness_status,
        width=1200,
        height=675,
        markdown_path=str(markdown_path),
        svg_path=str(svg_path),
        png_path=str(png_path),
        highlights=highlights,
        caveat=_demo_script_caveat(readiness),
    )


def write_demo_media_assets(
    *,
    artifacts_dir: Path,
    output_path: Path,
    svg_output_path: Path,
    png_output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoMediaReport:
    report = build_demo_media_report(
        artifacts_dir=artifacts_dir,
        markdown_path=output_path,
        svg_path=svg_output_path,
        png_path=png_output_path,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    svg_output_path.parent.mkdir(parents=True, exist_ok=True)
    png_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_media_report(report), encoding="utf-8")
    svg_output_path.write_text(render_demo_media_svg(report), encoding="utf-8")
    _write_demo_media_png(report, png_output_path)
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_media_report(report: DemoMediaReport) -> str:
    return "\n".join(
        [
            "# PatchSmith Demo Media",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Readiness status: `{report.readiness_status}`",
            f"- SVG asset: `{report.svg_path}`",
            f"- PNG asset: `{report.png_path}`",
            f"- Dimensions: `{report.width}x{report.height}`",
            f"- Caveat: {report.caveat}",
            "",
            "## Highlights",
            "",
            *[f"- {highlight}" for highlight in report.highlights],
            "",
            "## Usage",
            "",
            "Use the SVG for readable README or portfolio embedding. Use the PNG as a compact social or presentation preview.",
        ]
    ) + "\n"


def render_demo_media_svg(report: DemoMediaReport) -> str:
    highlight_items = "\n".join(
        (
            f'<text x="92" y="{258 + index * 54}" class="metric">'
            f"{escape(highlight)}</text>"
        )
        for index, highlight in enumerate(report.highlights)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{report.width}" height="{report.height}" viewBox="0 0 {report.width} {report.height}" role="img" aria-labelledby="title desc">
  <title id="title">PatchSmith demo summary</title>
  <desc id="desc">Portfolio demo summary generated from saved PatchSmith artifacts.</desc>
  <style>
    .bg {{ fill: #f7f8fa; }}
    .ink {{ fill: #1d2430; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    .muted {{ fill: #596579; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    .panel {{ fill: #ffffff; stroke: #d9dee7; stroke-width: 2; }}
    .accent {{ fill: #147d75; }}
    .warn {{ fill: #945f00; }}
    .title {{ font-size: 58px; font-weight: 760; }}
    .subtitle {{ font-size: 26px; }}
    .metric {{ fill: #1d2430; font-family: Inter, ui-sans-serif, system-ui, sans-serif; font-size: 30px; font-weight: 650; }}
    .small {{ font-size: 21px; }}
  </style>
  <rect class="bg" width="1200" height="675"/>
  <rect x="56" y="48" width="1088" height="579" rx="18" class="panel"/>
  <rect x="56" y="48" width="1088" height="122" rx="18" class="accent"/>
  <text x="92" y="125" class="ink title" fill="#ffffff">PatchSmith Research</text>
  <text x="94" y="207" class="muted subtitle">Issue-to-tested-patch agent lab with honest evaluation artifacts</text>
  {highlight_items}
  <rect x="676" y="244" width="380" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="314" width="460" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="384" width="325" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="454" width="238" height="40" rx="8" fill="#f4e3bd"/>
  <text x="92" y="568" class="muted small">{escape(report.caveat)}</text>
  <text x="92" y="604" class="muted small">Open artifacts/experiments/demo_script.md to record the 3m10s walkthrough.</text>
</svg>
"""


def write_demo_script_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoScriptReport:
    report = build_demo_script_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_script_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_script_report(report: DemoScriptReport) -> str:
    lines = [
        "# PatchSmith Demo Script",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Target duration: `{_format_duration(report.target_duration_seconds)}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Caveat: {report.caveat}",
        "",
        "## Run Of Show",
        "",
        "| Segment | Duration | On Screen | Artifact |",
        "|---|---:|---|---|",
    ]
    for section in report.sections:
        lines.append(
            "| "
            f"{section.title} | "
            f"{_format_duration(section.duration_seconds)} | "
            f"{_markdown_cell(section.on_screen)} | "
            f"`{section.artifact}` |"
        )

    lines.extend(["", "## Narration", ""])
    for index, section in enumerate(report.sections, start=1):
        lines.extend(
            [
                f"### {index}. {section.title}",
                "",
                f"On screen: `{section.artifact}`",
                "",
                section.narration,
                "",
            ]
        )

    lines.extend(
        [
            "## Rehearsal Commands",
            "",
            "```bash",
            *report.rehearsal_commands,
            "```",
            "",
            "## Guardrails",
            "",
            "- Do not claim live LLM calibration unless the readiness report shows a non-offline provider.",
            "- Present failure cases as part of the research evidence, not as hidden defects.",
            "- Keep the demo on seeded or preselected repositories until public sandboxing is hardened.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_demo_readiness_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoReadinessReport:
    report = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_readiness_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_readiness_report(report: DemoReadinessReport) -> str:
    lines = [
        "# PatchSmith Demo Readiness Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Experiment count: `{report.experiment_count}`",
        f"- Saved run count: `{report.run_count}`",
        f"- Normalized metric rows: `{report.metric_count}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        "",
        "## Gate Status",
        "",
        "| Gate | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for gate in report.gates:
        lines.append(
            "| "
            f"{gate.name} | "
            f"{gate.status} | "
            f"{_markdown_cell(gate.evidence)} | "
            f"{_markdown_cell(gate.next_action)} |"
        )

    lines.extend(["", "## Failure Categories", ""])
    if report.failure_categories:
        lines.extend(["| Category | Runs |", "|---|---:|"])
        for category, count in report.failure_categories.items():
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("No failure categories were found in the scanned run traces.")

    lines.extend(["", "## Model Provider Evidence", ""])
    if report.model_providers:
        lines.extend(["| Provider | Rows |", "|---|---:|"])
        for provider, count in report.model_providers.items():
            lines.append(f"| {provider} | {count} |")
    else:
        lines.append("No model-provider metadata was found in saved summaries/results.")

    lines.extend(
        [
            "",
            "## Reproducible Demo Commands",
            "",
            "Run these from the repository root after installing project dependencies.",
            "",
            "```bash",
            *report.demo_commands,
            "```",
            "",
            "## Review Path",
            "",
            "1. Open `artifacts/experiments/index.html` for metrics and run navigation.",
            "2. Open `artifacts/experiments/failure_report.md` to inspect failure cases.",
            "3. Use the scaffold and patch-search reports to explain quality versus cost.",
            "4. State clearly that current model evidence is offline unless live-provider rows exist.",
        ]
    )
    return "\n".join(lines) + "\n"


def _demo_readiness_gates(
    *,
    experiment_count: int,
    run_count: int,
    metric_count: int,
    metric_kinds: set[str],
    failure_report: FailureArtifactReport,
    model_providers: dict[str, int],
) -> list[DemoReadinessGate]:
    gates = [
        _gate(
            name="Experiment Evidence",
            passed=experiment_count >= 3,
            evidence=f"{experiment_count} experiment directories discovered.",
            missing_action="Run retrieval, scaffold, and patch-search evaluations.",
        ),
        _gate(
            name="Saved Run Artifacts",
            passed=run_count > 0,
            evidence=f"{run_count} saved run artifacts discovered.",
            missing_action="Run at least one seeded repair or scaffold evaluation.",
        ),
        _gate(
            name="Metrics Surface",
            passed=metric_count > 0,
            evidence=f"{metric_count} normalized metric rows discovered.",
            missing_action="Regenerate experiment summaries and artifact index.",
        ),
        _kind_gate(
            name="Retrieval Evidence",
            kind="retrieval",
            metric_kinds=metric_kinds,
            missing_action="Run `eval-retrieval` before demo review.",
        ),
        _kind_gate(
            name="Repair Or Scaffold Evidence",
            kind="repair",
            metric_kinds=metric_kinds,
            alternate_kind="scaffold",
            missing_action="Run `eval-repair` or `eval-scaffold` before demo review.",
        ),
        _kind_gate(
            name="Patch Search Evidence",
            kind="patch_search",
            metric_kinds=metric_kinds,
            missing_action="Run `eval-patch-search` before demo review.",
        ),
    ]
    if failure_report.runs_requiring_attention > 0:
        gates.append(
            DemoReadinessGate(
                name="Failure Visibility",
                status="passed",
                evidence=(
                    f"{failure_report.runs_requiring_attention} runs requiring attention "
                    "are visible in the failure report."
                ),
                next_action="Use failure cases in the demo narrative instead of hiding them.",
            )
        )
    else:
        gates.append(
            DemoReadinessGate(
                name="Failure Visibility",
                status="warning",
                evidence="No failure cases were found in saved run traces.",
                next_action="Add or preserve at least one failure example for public analysis.",
            )
        )
    live_providers = [
        provider
        for provider in model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        gates.append(
            DemoReadinessGate(
                name="Live LLM Calibration",
                status="passed",
                evidence=f"Live provider metadata found: {', '.join(live_providers)}.",
                next_action="Report cost and token usage next to quality metrics.",
            )
        )
    else:
        gates.append(
            DemoReadinessGate(
                name="Live LLM Calibration",
                status="warning",
                evidence="No non-offline model provider metadata found.",
                next_action=(
                    "Keep demo claims scoped to offline evidence or run a credential-gated "
                    "live-provider smoke test."
                ),
            )
        )
    return gates


def _gate(
    *,
    name: str,
    passed: bool,
    evidence: str,
    missing_action: str,
) -> DemoReadinessGate:
    return DemoReadinessGate(
        name=name,
        status="passed" if passed else "missing",
        evidence=evidence,
        next_action="No action needed for the current demo slice." if passed else missing_action,
    )


def _kind_gate(
    *,
    name: str,
    kind: str,
    metric_kinds: set[str],
    missing_action: str,
    alternate_kind: str | None = None,
) -> DemoReadinessGate:
    passed = kind in metric_kinds or (
        alternate_kind is not None and alternate_kind in metric_kinds
    )
    evidence_kind = (
        kind
        if kind in metric_kinds
        else alternate_kind if alternate_kind in metric_kinds else kind
    )
    return _gate(
        name=name,
        passed=passed,
        evidence=f"`{evidence_kind}` metric evidence {'found' if passed else 'missing'}.",
        missing_action=missing_action,
    )


def _readiness_status(gates: list[DemoReadinessGate]) -> str:
    statuses = {gate.status for gate in gates}
    if "missing" in statuses:
        return "not_ready"
    if "warning" in statuses:
        return "ready_with_caveats"
    return "ready"


def _delivery_audit_items(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
) -> list[DeliveryAuditItem]:
    mvp_payload = _load_json_artifact(artifacts_dir / "experiments" / "mvp_progress.json")
    release_payload = _load_json_artifact(artifacts_dir / "experiments" / "release_hygiene.json")
    environment_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "environment_readiness.json"
    )
    docker_payload = _load_json_artifact(artifacts_dir / "experiments" / "docker_smoke.json")
    launch_payload = _load_json_artifact(artifacts_dir / "experiments" / "launch_blockers.json")
    calibration_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "calibration_readiness.json"
    )
    calibration_plan_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "live_calibration_plan.json"
    )
    setup_validation_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "focused_test_setup_validation_summary.json"
    )
    quality_payload = _load_json_artifact(artifacts_dir / "experiments" / "quality_gate.json")

    return [
        _delivery_path_item(
            project_root=project_root,
            requirement="Requirements and roadmaps are saved.",
            source="README.md, docs/01_product_requirements.md, docs/09_roadmap.md, docs/12_release_and_portfolio_plan.md",
            paths=[
                "README.md",
                "docs/01_product_requirements.md",
                "docs/09_roadmap.md",
                "docs/12_release_and_portfolio_plan.md",
            ],
            next_action="Restore missing source planning docs before claiming delivery continuity.",
        ),
        _delivery_sprint_plan_item(project_root),
        _delivery_path_item(
            project_root=project_root,
            requirement="Industry process docs are saved.",
            source="docs/10_testing_strategy.md, docs/14_risk_register.md, docs/18_delivery_process.md, docs/06_safety_and_sandboxing.md",
            paths=[
                "docs/10_testing_strategy.md",
                "docs/14_risk_register.md",
                "docs/18_delivery_process.md",
                "docs/06_safety_and_sandboxing.md",
            ],
            next_action="Restore missing testing, risk, safety, or delivery-process docs.",
        ),
        _delivery_git_item(project_root),
        _delivery_path_item(
            project_root=project_root,
            requirement="Automated verification surfaces exist.",
            source="tests/, pyproject.toml, .github/workflows",
            paths=["tests", "pyproject.toml", ".github/workflows"],
            next_action="Keep pytest, packaging, and CI workflow surfaces available.",
        ),
        _delivery_item(
            requirement="Saved evaluation artifacts exist.",
            status="passed" if index.experiment_count and index.run_count and index.metrics else "missing",
            evidence=(
                f"{index.experiment_count} experiments, {index.run_count} runs, "
                f"{len(index.metrics)} normalized metric rows."
            ),
            source="artifacts/experiments/index.json",
            next_action=(
                "Regenerate `index-artifacts` before review."
                if not (index.experiment_count and index.run_count and index.metrics)
                else "Keep artifact index current after new evals."
            ),
        ),
        _delivery_payload_status_item(
            requirement="Executable quality gate has passed.",
            payload=quality_payload,
            status_key="quality_status",
            pass_values={"passed"},
            warning_values={"passed_with_skips"},
            blocked_values={"failed"},
            evidence_keys=["passed_count", "failed_count", "skipped_count"],
            source="artifacts/experiments/quality_gate.json",
            missing_action="Run `quality-gate` and preserve the generated logs.",
        ),
        _delivery_payload_status_item(
            requirement="MVP checklist progress is evidence-backed.",
            payload=mvp_payload,
            status_key="status",
            pass_values={"ready"},
            warning_values={"ready_with_caveats"},
            blocked_values={"blocked"},
            evidence_keys=["completion_percent", "blocked_count", "warning_count"],
            source="artifacts/experiments/mvp_progress.json",
            missing_action="Regenerate `mvp-progress`.",
        ),
        _delivery_payload_status_item(
            requirement="Release hygiene gate is current.",
            payload=release_payload,
            status_key="release_status",
            pass_values={"ready"},
            warning_values={"ready_with_warnings"},
            blocked_values={"blocked"},
            evidence_keys=["blocked_count", "warning_count"],
            source="artifacts/experiments/release_hygiene.json",
            missing_action="Regenerate `release-hygiene` from a clean worktree.",
        ),
        _delivery_payload_status_item(
            requirement="Environment readiness prerequisites are captured.",
            payload=environment_payload,
            status_key="readiness_status",
            pass_values={"ready"},
            warning_values={"ready_with_warnings"},
            blocked_values={"blocked"},
            evidence_keys=["passed_count", "warning_count", "blocked_count"],
            source="artifacts/experiments/environment_readiness.json",
            missing_action=(
                "Regenerate `environment-readiness` and resolve blocked external prerequisites."
            ),
        ),
        _delivery_launch_blockers_item(launch_payload),
        _delivery_payload_status_item(
            requirement="Docker sandbox smoke has executable evidence.",
            payload=docker_payload,
            status_key="smoke_status",
            pass_values={"passed"},
            warning_values={"skipped"},
            blocked_values={"failed", "not_available"},
            evidence_keys=["smoke_status"],
            source="artifacts/experiments/docker_smoke.json",
            missing_action="Start Docker, build the smoke image, and rerun `docker-smoke`.",
        ),
        _delivery_setup_validation_item(setup_validation_payload),
        _delivery_payload_status_item(
            requirement="Live LLM calibration has provider evidence.",
            payload=calibration_payload,
            status_key="calibration_status",
            pass_values={"calibrated"},
            warning_values={"ready_to_run", "needs_review"},
            blocked_values={"not_configured"},
            evidence_keys=["saved_live_provider_count", "deepagents_package_run_count", "openai_agents_package_run_count"],
            source="artifacts/experiments/calibration_readiness.json",
            missing_action="Configure credentials and run the required live-provider smoke.",
        ),
        _delivery_calibration_plan_item(calibration_plan_payload),
    ]


def _delivery_path_item(
    *,
    project_root: Path,
    requirement: str,
    source: str,
    paths: list[str],
    next_action: str,
) -> DeliveryAuditItem:
    missing = [path for path in paths if not (project_root / path).exists()]
    return _delivery_item(
        requirement=requirement,
        status="passed" if not missing else "missing",
        evidence=(
            f"All {len(paths)} required paths exist."
            if not missing
            else f"Missing: {', '.join(missing)}."
        ),
        source=source,
        next_action="No action needed." if not missing else next_action,
    )


def _delivery_sprint_plan_item(project_root: Path) -> DeliveryAuditItem:
    path = project_root / "docs" / "17_sprint_plans.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    sprint_count = text.count("### Sprint ")
    task_marker_count = text.count("| S")
    passed = sprint_count >= 10 and task_marker_count >= 10
    return _delivery_item(
        requirement="Roadmap is decomposed into sprint plans.",
        status="passed" if passed else "missing",
        evidence=f"{sprint_count} sprint sections and {task_marker_count} sprint-task rows found.",
        source="docs/17_sprint_plans.md",
        next_action=(
            "No action needed."
            if passed
            else "Restore sprint sections and task breakdown rows in docs/17_sprint_plans.md."
        ),
    )


def _delivery_git_item(project_root: Path) -> DeliveryAuditItem:
    if not (project_root / ".git").exists():
        return _delivery_item(
            requirement="Development is versioned in Git.",
            status="missing",
            evidence="No .git directory found.",
            source="git",
            next_action="Initialize or restore Git metadata.",
        )
    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if head.returncode != 0:
        return _delivery_item(
            requirement="Development is versioned in Git.",
            status="missing",
            evidence="Git repository has no readable HEAD.",
            source="git",
            next_action="Create a verified baseline commit.",
        )
    dirty = bool(status.stdout.strip()) if status.returncode == 0 else True
    return _delivery_item(
        requirement="Development is versioned in Git.",
        status="warning" if dirty else "passed",
        evidence=(
            f"Current commit {head.stdout.strip()}; worktree {'dirty' if dirty else 'clean'}."
        ),
        source="git status",
        next_action=(
            "Commit or intentionally discard pending changes before release audit."
            if dirty
            else "No action needed."
        ),
    )


def _delivery_payload_status_item(
    *,
    requirement: str,
    payload: dict[str, Any] | None,
    status_key: str,
    pass_values: set[str],
    warning_values: set[str],
    blocked_values: set[str],
    evidence_keys: list[str],
    source: str,
    missing_action: str,
) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement=requirement,
            status="missing",
            evidence="Saved JSON artifact is missing or invalid.",
            source=source,
            next_action=missing_action,
        )
    raw_status = str(payload.get(status_key) or "unknown")
    if raw_status in pass_values:
        status = "passed"
    elif raw_status in warning_values:
        status = "warning"
    elif raw_status in blocked_values:
        status = "blocked"
    else:
        status = "warning"
    details = [f"{status_key}={raw_status}"]
    for key in evidence_keys:
        if key in payload and key != status_key:
            details.append(f"{key}={payload[key]}")
    return _delivery_item(
        requirement=requirement,
        status=status,
        evidence=", ".join(details),
        source=source,
        next_action="No action needed." if status == "passed" else missing_action,
    )


def _delivery_launch_blockers_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Launch blockers are tracked.",
            status="missing",
            evidence="Launch blocker artifact is missing.",
            source="artifacts/experiments/launch_blockers.json",
            next_action="Regenerate `launch-blockers`.",
        )
    launch_status = str(payload.get("launch_status") or "unknown")
    return _delivery_item(
        requirement="Launch blockers are tracked.",
        status="passed",
        evidence=(
            f"launch_status={launch_status}, "
            f"blocked_count={_payload_int(payload, 'blocked_count')}, "
            f"warning_count={_payload_int(payload, 'warning_count')}"
        ),
        source="artifacts/experiments/launch_blockers.json",
        next_action="Work the listed blocker next actions before public launch claims.",
    )


def _delivery_calibration_plan_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Live calibration execution plan is saved.",
            status="missing",
            evidence="Live calibration plan artifact is missing.",
            source="artifacts/experiments/live_calibration_plan.json",
            next_action="Regenerate `live-calibration-plan`.",
        )
    plan_status = str(payload.get("plan_status") or "unknown")
    run_count, ready_runs, blocked_runs = _calibration_plan_run_counts(payload)
    return _delivery_item(
        requirement="Live calibration execution plan is saved.",
        status="passed",
        evidence=(
            f"plan_status={plan_status}, "
            f"run_count={run_count}, "
            f"ready_runs={ready_runs}, "
            f"blocked_runs={blocked_runs}"
        ),
        source="artifacts/experiments/live_calibration_plan.json",
        next_action="Run the required live smoke only after credentials and budget are available.",
    )


def _calibration_plan_run_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    runs = payload.get("runs")
    if isinstance(runs, list):
        statuses = [
            str(run.get("status") or "")
            for run in runs
            if isinstance(run, dict)
        ]
        return len(statuses), statuses.count("ready"), statuses.count("blocked")
    return (
        _payload_int(payload, "run_count"),
        _payload_int(payload, "ready_runs"),
        _payload_int(payload, "blocked_runs"),
    )


def _delivery_setup_validation_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Public issue setup validation has a safe gate.",
            status="missing",
            evidence="Setup-validation summary artifact is missing.",
            source="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
            next_action="Regenerate `validate-focused-test-setups`.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    passed = _payload_int(payload, "passed_tasks")
    status = "passed" if passed else "warning" if attempted else "blocked"
    return _delivery_item(
        requirement="Public issue setup validation has a safe gate.",
        status=status,
        evidence=(
            f"blocked_tasks={blocked}, attempted_tasks={attempted}, passed_tasks={passed}"
        ),
        source="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        next_action=(
            "No action needed."
            if status == "passed"
            else "Resolve Docker/setup blockers before claiming public issue reproduction."
        ),
    )


def _delivery_item(
    *,
    requirement: str,
    status: str,
    evidence: str,
    source: str,
    next_action: str,
) -> DeliveryAuditItem:
    return DeliveryAuditItem(
        requirement=requirement,
        status=status,
        evidence=evidence,
        source=source,
        next_action=next_action,
    )


def _delivery_status(items: list[DeliveryAuditItem]) -> str:
    statuses = {item.status for item in items}
    if "blocked" in statuses:
        return "in_progress_with_blockers"
    if "missing" in statuses:
        return "in_progress_missing_evidence"
    if "warning" in statuses:
        return "in_progress_with_caveats"
    return "ready_for_completion_review"


def _delivery_completion_percent(items: list[DeliveryAuditItem]) -> float:
    if not items:
        return 0.0
    score = 0.0
    for item in items:
        if item.status == "passed":
            score += 1.0
        elif item.status == "warning":
            score += 0.5
    return round(score / len(items) * 100.0, 1)


def _safe_artifact_name(value: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in value.lower())
    return safe.strip("_") or "artifact"


def _run_quality_gate_check(
    *,
    name: str,
    command: list[str] | None,
    success_summary: str,
    project_root: Path,
    logs_dir: Path,
    timeout_seconds: int,
) -> QualityGateCheck:
    safe_name = _safe_artifact_name(name)
    stdout_path = logs_dir / f"{safe_name}_stdout.txt"
    stderr_path = logs_dir / f"{safe_name}_stderr.txt"
    if command is None:
        return QualityGateCheck(
            name=name,
            status="skipped",
            command=[],
            cwd=str(project_root),
            exit_code=None,
            duration_ms=0,
            stdout_path=None,
            stderr_path=None,
            summary="Skipped by request.",
        )
    logs_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        status = "passed" if result.returncode == 0 else "failed"
        summary = success_summary if status == "passed" else f"Command exited {result.returncode}."
        return QualityGateCheck(
            name=name,
            status=status,
            command=command,
            cwd=str(project_root),
            exit_code=result.returncode,
            duration_ms=duration_ms,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            summary=summary,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = getattr(error, "stdout", "") or ""
        stderr = getattr(error, "stderr", "") or str(error)
        stdout_path.write_text(str(stdout), encoding="utf-8")
        stderr_path.write_text(str(stderr), encoding="utf-8")
        return QualityGateCheck(
            name=name,
            status="failed",
            command=command,
            cwd=str(project_root),
            exit_code=None,
            duration_ms=duration_ms,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            summary=f"{type(error).__name__}: {error}",
        )


def _quality_gate_status(checks: list[QualityGateCheck]) -> str:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"


def _mvp_progress_items(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
    readiness: DemoReadinessReport,
    calibration: LiveCalibrationReport,
    failure_report: FailureArtifactReport,
) -> list[MvpProgressItem]:
    metric_kinds = {metric.kind for metric in index.metrics}
    metric_lanes = {metric.lane for metric in index.metrics}
    seeded_task_count = _seeded_task_count(project_root)
    has_run = index.run_count > 0
    has_report = any(run.report_path for run in index.runs)
    has_trace = any(run.trace_path for run in index.runs)
    has_diff = any(run.diff_path for run in index.runs)
    has_latency = any(metric.avg_latency_ms is not None for metric in index.metrics)
    has_cost = any(metric.estimated_cost_usd is not None for metric in index.metrics)
    has_retrieval = "retrieval" in metric_kinds
    has_repair = any(kind in metric_kinds for kind in ("repair", "scaffold"))
    has_patch_search = "patch_search" in metric_kinds
    has_langgraph = any("langgraph" in lane for lane in metric_lanes)
    has_docker_runner = _file_contains(
        project_root / "src" / "patchsmith" / "sandbox.py",
        "class DockerSandboxRunner",
    )
    docker_smoke_count = _docker_sandbox_success_count(artifacts_dir)
    latest_docker_smoke_status = _latest_docker_smoke_status(artifacts_dir)
    issue_corpus_count = _validated_issue_corpus_count(artifacts_dir)
    run_artifact_reports = sum(1 for run in index.runs if run.report_path)
    run_artifact_diffs = sum(1 for run in index.runs if run.diff_path)
    run_artifact_traces = sum(1 for run in index.runs if run.trace_path)

    return [
        _mvp_item(
            "Core flow",
            "User can submit repository URL and issue text.",
            "passed" if _cli_has_run_inputs(project_root) else "missing",
            "CLI `run` exposes repository and issue inputs.",
            "Keep the run CLI stable.",
        ),
        _mvp_item(
            "Core flow",
            "System clones repository into isolated workspace.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "ingest.py", "clone_or_copy_repository") else "missing",
            "`clone_or_copy_repository` exists in the ingest layer.",
            "Keep clone/copy behavior covered by workflow tests.",
        ),
        _mvp_item(
            "Core flow",
            "System records commit hash.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "models.py", "commit_hash") else "missing",
            "Repository snapshots include `commit_hash`.",
            "Keep commit metadata visible in reports.",
        ),
        _mvp_item(
            "Core flow",
            "System builds basic file index.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "ingest.py", "index_repository") else "missing",
            "`index_repository` exists and is used by CLI/evaluation flows.",
            "Keep index output covered by tests.",
        ),
        _mvp_item(
            "Core flow",
            "System retrieves candidate files.",
            "passed" if has_retrieval else "missing",
            f"Retrieval metric evidence {'exists' if has_retrieval else 'is missing'}.",
            "Run `eval-retrieval` if retrieval evidence is missing.",
        ),
        _mvp_item(
            "Core flow",
            "LangGraph repair loop runs.",
            "passed" if has_langgraph else "missing",
            f"LangGraph metric lanes {'exist' if has_langgraph else 'are missing'}.",
            "Run `eval-repair --runtime langgraph` if missing.",
        ),
        _mvp_item(
            "Core flow",
            "Agent can read files through bounded tool.",
            "passed" if has_retrieval else "missing",
            (
                "Bounded retrieved-context contracts provide controlled repository "
                "file excerpts to the repair runtime."
            ),
            "Keep file access bounded and consider a first-class read tool before broad repos.",
        ),
        _mvp_item(
            "Core flow",
            "Agent can apply patch through controlled tool.",
            "passed" if has_repair and _file_contains(project_root / "src" / "patchsmith" / "patching.py", "apply_text_replacement") else "missing",
            "`apply_text_replacement` and repair/scaffold metrics exist.",
            "Keep patch application path-validated and tested.",
        ),
        _mvp_item(
            "Core flow",
            "Tests run in Docker sandbox.",
            "passed" if docker_smoke_count else "warning" if has_docker_runner else "missing",
            (
                f"{docker_smoke_count} saved Docker sandbox success trace(s)."
                if docker_smoke_count
                else (
                    f"Opt-in Docker runner exists; latest `docker-smoke` status is "
                    f"`{latest_docker_smoke_status}`."
                    if latest_docker_smoke_status
                    else "Opt-in Docker runner exists, but no saved Docker-mode success trace was found."
                )
            ),
            "Run a Docker-mode seeded smoke when the Docker daemon and image are available.",
        ),
        _mvp_item(
            "Core flow",
            "Final diff is generated.",
            "passed" if has_diff else "missing",
            f"{run_artifact_diffs} saved run diff artifact(s) discovered.",
            "Run a repair/scaffold evaluation if diffs are missing.",
        ),
        _mvp_item(
            "Core flow",
            "Markdown run report is generated.",
            "passed" if has_report else "missing",
            f"{run_artifact_reports} saved run report artifact(s) discovered.",
            "Run a repair/scaffold evaluation if reports are missing.",
        ),
        _mvp_item(
            "Observability",
            "Run status is persisted.",
            "passed" if has_run else "missing",
            f"{index.run_count} saved run artifact(s) discovered.",
            "Run at least one repair/scaffold evaluation if missing.",
        ),
        _mvp_item(
            "Observability",
            "Retrieved context is saved.",
            "passed" if has_retrieval and has_report else "missing",
            "Retrieval metrics and run reports are present.",
            "Regenerate retrieval and run artifacts if missing.",
        ),
        _mvp_item(
            "Observability",
            "Tool calls are logged.",
            "passed" if has_trace else "missing",
            f"{run_artifact_traces} trace artifact(s) discovered.",
            "Keep runtime/tool events in `traces.jsonl`.",
        ),
        _mvp_item(
            "Observability",
            "Sandbox commands are logged.",
            "passed" if has_trace else "missing",
            "Saved traces include workflow events for sandbox command execution.",
            "Run workflow tests if sandbox trace events are missing.",
        ),
        _mvp_item(
            "Observability",
            "Test output is saved.",
            "passed" if any(run.stdout_path or run.stderr_path for run in index.runs) else "missing",
            "Saved runs include stdout/stderr artifacts.",
            "Ensure sandbox command output stays persisted.",
        ),
        _mvp_item(
            "Observability",
            "Cost is estimated.",
            "passed" if has_cost else "warning",
            (
                "At least one metric row has estimated cost."
                if has_cost
                else "Offline evidence exists, but live-provider cost is not calibrated."
            ),
            "Set cost-rate env vars for publishable live-provider calibration.",
        ),
        _mvp_item(
            "Observability",
            "Latency is recorded.",
            "passed" if has_latency else "missing",
            "Normalized metrics include latency values.",
            "Keep latency in trace and summary artifacts.",
        ),
        _mvp_item(
            "Safety",
            "No host secrets are mounted.",
            "passed" if has_docker_runner and _file_contains(project_root / "src" / "patchsmith" / "sandbox.py", "_docker_host_env") else "missing",
            "Docker and local runners use sanitized environment helpers.",
            "Keep env filtering covered by security tests.",
        ),
        _mvp_item(
            "Safety",
            "Command allowlist exists.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "security.py", "CommandPolicy") else "missing",
            "`CommandPolicy` exists.",
            "Keep command policy narrow.",
        ),
        _mvp_item(
            "Safety",
            "Timeout exists.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "sandbox.py", "timeout_seconds") else "missing",
            "Sandbox runners enforce `timeout_seconds`.",
            "Keep timeout tests for local and Docker paths.",
        ),
        _mvp_item(
            "Safety",
            "Workspace path validation exists.",
            "passed" if _file_contains(project_root / "src" / "patchsmith" / "security.py", "absolute path outside workspace") else "missing",
            "Command policy rejects absolute paths outside the workspace.",
            "Keep path traversal tests passing.",
        ),
        _mvp_item(
            "Safety",
            "Unsafe command rejection test exists.",
            "passed" if _file_contains(project_root / "tests" / "test_security.py", "rejects_shell_chaining") else "missing",
            "Security tests cover shell chaining rejection.",
            "Keep unsafe-command tests in CI.",
        ),
        _mvp_item(
            "Evaluation",
            "At least 5 seeded bugs exist.",
            "passed" if seeded_task_count >= 5 else "missing",
            f"{seeded_task_count} seeded bug task(s) found.",
            "Add seeded tasks if the suite drops below five.",
        ),
        _mvp_item(
            "Evaluation",
            "Live LLM calibration has been run.",
            "passed" if calibration.saved_live_provider_count else "warning",
            (
                f"{calibration.saved_live_provider_count} saved live-provider run(s)."
                if calibration.saved_live_provider_count
                else "No non-offline model-provider run was found in saved artifacts."
            ),
            "Run a credential-gated calibration with budget and provider settings.",
        ),
        _mvp_item(
            "Evaluation",
            "Evaluation runner can run the seeded suite.",
            "passed" if has_repair and has_patch_search else "missing",
            "Repair/scaffold and patch-search metric evidence exists.",
            "Run repair/scaffold and patch-search evaluations if missing.",
        ),
        _mvp_item(
            "Evaluation",
            "Results table includes success, cost, latency, and failure category.",
            "passed" if readiness.metric_count and failure_report.category_counts else "warning",
            (
                f"{readiness.metric_count} metric row(s); failure categories: "
                f"{_failure_summary(failure_report.category_counts)}."
            ),
            "Keep final, failure, and artifact-index reports regenerated together.",
        ),
        _mvp_item(
            "Portfolio",
            "README explains the project in under 60 seconds.",
            "passed" if _path_exists(project_root / "README.md") else "missing",
            "README exists and includes quickstart/current-status sections.",
            "Keep README caveats synchronized with generated reports.",
        ),
        _mvp_item(
            "Portfolio",
            "Real-world task breadth is proven.",
            "passed" if issue_corpus_count >= 3 else "warning" if seeded_task_count >= 5 and has_repair else "missing",
            (
                f"{issue_corpus_count} validated public issue candidate(s) found."
                if issue_corpus_count
                else (
                    f"{seeded_task_count} seeded bug task(s) exist; no saved real-world "
                    "issue corpus artifact was found."
                )
            ),
            "Generate the public issue corpus validation report.",
        ),
        _mvp_item(
            "Portfolio",
            "Architecture diagram exists.",
            "passed" if _file_contains(project_root / "docs" / "03_architecture.md", "```mermaid") else "missing",
            "Architecture doc includes a Mermaid diagram.",
            "Keep architecture docs synchronized with runtime adapters.",
        ),
    ]


def _mvp_item(
    category: str,
    item: str,
    status: str,
    evidence: str,
    next_action: str,
) -> MvpProgressItem:
    return MvpProgressItem(
        category=category,
        item=item,
        status=status,
        evidence=evidence,
        next_action="No action needed." if status == "passed" else next_action,
        score=_mvp_status_score(status),
    )


def _mvp_status_score(status: str) -> float:
    if status == "passed":
        return 1.0
    if status == "warning":
        return 0.5
    return 0.0


def _mvp_completion_percent(items: list[MvpProgressItem]) -> float:
    if not items:
        return 0.0
    return round((sum(item.score for item in items) / len(items)) * 100, 1)


def _mvp_progress_status(
    *,
    completion_percent: float,
    warning_count: int,
    blocked_count: int,
    missing_count: int,
) -> str:
    if blocked_count or missing_count:
        return "in_progress"
    if warning_count:
        return "ready_with_caveats" if completion_percent >= 80 else "in_progress"
    return "complete"


def _mvp_progress_categories(items: list[MvpProgressItem]) -> list[MvpProgressCategory]:
    categories: list[MvpProgressCategory] = []
    for category_name in dict.fromkeys(item.category for item in items):
        category_items = [item for item in items if item.category == category_name]
        categories.append(
            MvpProgressCategory(
                name=category_name,
                item_count=len(category_items),
                passed_count=sum(1 for item in category_items if item.status == "passed"),
                warning_count=sum(1 for item in category_items if item.status == "warning"),
                blocked_count=sum(1 for item in category_items if item.status == "blocked"),
                missing_count=sum(1 for item in category_items if item.status == "missing"),
                completion_percent=_mvp_completion_percent(category_items),
            )
        )
    return categories


def _cli_has_run_inputs(project_root: Path) -> bool:
    cli_path = project_root / "src" / "patchsmith" / "cli.py"
    if not cli_path.exists():
        return False
    text = cli_path.read_text(encoding="utf-8")
    return "run = subparsers.add_parser(\"run\"" in text and "--repo" in text


def _seeded_task_count(project_root: Path) -> int:
    task_root = project_root / "evals" / "tasks" / "seeded_bugs_v1"
    if not task_root.exists():
        return 0
    return sum(1 for path in task_root.iterdir() if path.is_dir() and path.name.startswith("task_"))


def _docker_sandbox_success_count(artifacts_dir: Path) -> int:
    run_ids: set[str] = set()
    for trace_path in sorted(artifacts_dir.glob("**/traces.jsonl")):
        try:
            lines = trace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if (
                event.get("event_type") == "sandbox_command"
                and payload.get("sandbox_mode") == "docker"
                and payload.get("exit_code") == 0
            ):
                run_ids.add(str(event.get("run_id") or trace_path.parent.name))
    return len(run_ids) + _docker_smoke_success_count(artifacts_dir)


def _docker_smoke_success_count(artifacts_dir: Path) -> int:
    count = 0
    for report_path in sorted(artifacts_dir.glob("**/docker_smoke*.json")):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("smoke_status") == "passed":
            count += 1
    return count


def _latest_docker_smoke_status(artifacts_dir: Path) -> str | None:
    report_paths = sorted(
        artifacts_dir.glob("**/docker_smoke*.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for report_path in report_paths:
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("smoke_status"), str):
            return payload["smoke_status"]
    return None


def _validated_issue_corpus_count(artifacts_dir: Path) -> int:
    counts: list[int] = []
    for summary_path in sorted(artifacts_dir.glob("**/corpus_summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        valid_entries = payload.get("valid_entries")
        invalid_entries = payload.get("invalid_entries")
        if isinstance(valid_entries, int) and invalid_entries == 0:
            counts.append(valid_entries)
    return max(counts, default=0)


def _docker_daemon_check(docker_binary: str) -> DockerSmokeCheck:
    try:
        result = subprocess.run(
            [docker_binary, "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DockerSmokeCheck(
            name="Docker Daemon",
            status="missing",
            evidence=f"Docker daemon check failed: {error}.",
            next_action="Start Docker Desktop or point DOCKER_HOST at a reachable daemon.",
        )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "no output"
        return DockerSmokeCheck(
            name="Docker Daemon",
            status="missing",
            evidence=f"`{docker_binary} version` failed: {stderr}",
            next_action="Start Docker Desktop or point DOCKER_HOST at a reachable daemon.",
        )
    version = result.stdout.strip() or "unknown"
    return DockerSmokeCheck(
        name="Docker Daemon",
        status="passed",
        evidence=f"Docker server version `{version}` is reachable.",
        next_action="No action needed.",
    )


def _docker_image_check(docker_binary: str, image: str) -> DockerSmokeCheck:
    try:
        result = subprocess.run(
            [docker_binary, "image", "inspect", image],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DockerSmokeCheck(
            name="Smoke Image",
            status="missing",
            evidence=f"Docker image inspection failed: {error}.",
            next_action=f"Build `{image}` before running the smoke.",
        )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "image not found"
        return DockerSmokeCheck(
            name="Smoke Image",
            status="missing",
            evidence=f"`{image}` is not available locally: {stderr}",
            next_action=f"Run `docker build -f docker/seeded-smoke.Dockerfile -t {image} .`.",
        )
    return DockerSmokeCheck(
        name="Smoke Image",
        status="passed",
        evidence=f"`{image}` is available locally.",
        next_action="No action needed.",
    )


def _docker_environment_snapshot(docker_binary: str) -> dict[str, str]:
    home_socket = Path.home() / ".docker" / "run" / "docker.sock"
    default_socket = Path("/var/run/docker.sock")
    docker_desktop_paths = [
        Path("/Applications/Docker.app"),
        Path.home() / "Applications" / "Docker.app",
    ]
    return {
        "docker_binary": docker_binary,
        "docker_cli_path": shutil.which(docker_binary) or "missing",
        "DOCKER_HOST": os.environ.get("DOCKER_HOST", "unset"),
        "DOCKER_CONTEXT": os.environ.get("DOCKER_CONTEXT", "unset"),
        "DOCKER_CONFIG": os.environ.get("DOCKER_CONFIG", "unset"),
        "docker_desktop_application": (
            "exists" if any(path.exists() for path in docker_desktop_paths) else "missing"
        ),
        "colima_binary": shutil.which("colima") or "missing",
        str(home_socket): "exists" if home_socket.exists() else "missing",
        str(default_socket): "exists" if default_socket.exists() else "missing",
    }


def _docker_remediation_commands(
    *,
    docker_binary: str,
    build_command: str,
    smoke_command: str,
    environment: dict[str, str],
) -> list[str]:
    commands = [
        f"{docker_binary} context ls",
        f"{docker_binary} version",
    ]
    if environment.get("docker_desktop_application") == "exists":
        commands.append("open -a Docker")
    if environment.get("colima_binary", "missing") != "missing":
        commands.append("colima start")
    commands.extend([build_command, smoke_command])
    return commands


def _run_docker_seeded_smoke(
    *,
    task_dir: Path,
    artifacts_dir: Path,
    test_command: str,
    runtime: str,
    context_provider: str,
    sandbox_image: str,
):
    from patchsmith.models import RunRequest
    from patchsmith.workflow import RepairRunner

    run_artifacts_dir = artifacts_dir / "experiments" / "docker_smoke_v1" / "run_artifacts"
    issue_path = task_dir / "issue.md"
    repo_path = task_dir / "repo"
    return RepairRunner(artifacts_dir=run_artifacts_dir).run(
        RunRequest(
            repo=str(repo_path),
            issue_text=issue_path.read_text(encoding="utf-8"),
            test_command=test_command,
            runtime=runtime,
            planner="heuristic",
            context_provider=context_provider,
            retrieval_strategy=context_provider,
            sandbox_mode="docker",
            sandbox_image=sandbox_image,
        )
    )


def _docker_smoke_status(checks: list[DockerSmokeCheck]) -> str:
    statuses = [check.status for check in checks]
    if "failed" in statuses:
        return "failed"
    if "missing" in statuses:
        return "not_available"
    if "skipped" in statuses:
        return "skipped"
    return "passed"


def _docker_smoke_decision(report: DockerSmokeReport) -> str:
    if report.smoke_status == "passed":
        return "Docker sandbox smoke passed. The MVP Docker-sandbox evidence can be cited."
    if report.smoke_status == "failed":
        return "Docker sandbox smoke ran but failed. Inspect the run artifacts before claiming Docker readiness."
    if report.smoke_status == "skipped":
        return "Docker preflight passed but the executable seeded run was skipped."
    return "Docker sandbox smoke is not available in this environment. Keep Docker readiness as a caveat."


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


def _path_exists(path: Path) -> bool:
    return path.exists()


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _live_calibration_checks(
    *,
    model_providers: dict[str, int],
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
    environment: dict[str, str],
    package_availability: dict[str, bool] | None,
) -> list[LiveCalibrationCheck]:
    live_providers = _live_providers(model_providers)
    openai_sdk_available = _package_available("openai", package_availability)
    deepagents_available = _package_available("deepagents", package_availability)
    openai_agents_available = _package_available("agents", package_availability)
    openai_key_present = bool(environment.get("OPENAI_API_KEY"))
    model_name = environment.get("PATCHSMITH_OPENAI_MODEL", "").strip()
    input_rate = environment.get("PATCHSMITH_OPENAI_INPUT_COST_PER_1M", "").strip()
    output_rate = environment.get("PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M", "").strip()
    deepagents_package_runs = deepagents_modes.get("package_available", 0)
    deepagents_compatibility_runs = deepagents_modes.get("compatibility_mode", 0)
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    openai_agents_compatibility_runs = openai_agents_modes.get("compatibility_mode", 0)

    return [
        LiveCalibrationCheck(
            name="OpenAI SDK",
            status="passed" if openai_sdk_available else "missing",
            evidence=(
                "`openai` package is importable."
                if openai_sdk_available
                else "`openai` package is not importable."
            ),
            next_action=(
                "No action needed."
                if openai_sdk_available
                else "Install runtime dependencies before attempting a live-provider run."
            ),
        ),
        LiveCalibrationCheck(
            name="OpenAI Credentials",
            status="passed" if openai_key_present else "missing",
            evidence="OPENAI_API_KEY is configured." if openai_key_present else "OPENAI_API_KEY is not set.",
            next_action=(
                "Run the live smoke command and save artifacts."
                if openai_key_present
                else "Set OPENAI_API_KEY only in the local shell used for calibration."
            ),
        ),
        LiveCalibrationCheck(
            name="OpenAI Model Selection",
            status="passed" if model_name else "warning",
            evidence=(
                f"PATCHSMITH_OPENAI_MODEL={model_name}."
                if model_name
                else "PATCHSMITH_OPENAI_MODEL is not set; planner default will be used."
            ),
            next_action=(
                "Keep the model name in the saved run metadata."
                if model_name
                else "Set PATCHSMITH_OPENAI_MODEL explicitly before a publishable calibration run."
            ),
        ),
        LiveCalibrationCheck(
            name="Cost Rate Configuration",
            status="passed" if input_rate and output_rate else "warning",
            evidence=(
                "Input and output cost rates are configured."
                if input_rate and output_rate
                else "Cost rates are not fully configured."
            ),
            next_action=(
                "Report quality, token use, and estimated cost together."
                if input_rate and output_rate
                else (
                    "Set PATCHSMITH_OPENAI_INPUT_COST_PER_1M and "
                    "PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M when cost claims matter."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="DeepAgents Package",
            status="passed" if deepagents_available else "warning",
            evidence=(
                "`deepagents` package is importable."
                if deepagents_available
                else (
                    "`deepagents` package is not importable in the current shell; "
                    "use saved trace evidence for package-backed adapter claims."
                    if deepagents_package_runs
                    else (
                        "`deepagents` package is not importable; adapter evidence remains "
                        "compatibility-mode only."
                    )
                )
            ),
            next_action=(
                "Run the DeepAgents adapter under the installed package before making package-backed claims."
                if deepagents_available
                else (
                    "Install the optional `deepagents` extra in the active environment for "
                    "new package-backed runs."
                    if deepagents_package_runs
                    else "Install the optional `deepagents` extra before claiming real package execution."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved DeepAgents Package Evidence",
            status="passed" if deepagents_package_runs else "warning",
            evidence=(
                f"{deepagents_package_runs} package-backed run(s); "
                f"{deepagents_compatibility_runs} compatibility-mode run(s)."
                if deepagents_package_runs
                else f"0 package-backed runs; {deepagents_compatibility_runs} compatibility-mode run(s)."
            ),
            next_action=(
                "Use package-backed traces for adapter-import claims; still avoid live-model claims."
                if deepagents_package_runs
                else "Run the DeepAgents adapter with the optional extra installed and save traces."
            ),
        ),
        LiveCalibrationCheck(
            name="OpenAI Agents Package",
            status="passed" if openai_agents_available else "warning",
            evidence=(
                "`agents` package is importable."
                if openai_agents_available
                else (
                    "`agents` package is not importable in the current shell; "
                    "use saved trace evidence for package-backed adapter claims."
                    if openai_agents_package_runs
                    else (
                        "`agents` package is not importable; adapter evidence remains "
                        "compatibility-mode only."
                    )
                )
            ),
            next_action=(
                (
                    "Run the OpenAI Agents adapter under the installed package before "
                    "making package-backed claims."
                )
                if openai_agents_available
                else (
                    "Install the optional `openai-agents` extra in the active environment for "
                    "new package-backed runs."
                    if openai_agents_package_runs
                    else (
                        "Install the optional `openai-agents` extra before claiming real "
                        "package execution."
                    )
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved OpenAI Agents Package Evidence",
            status="passed" if openai_agents_package_runs else "warning",
            evidence=(
                f"{openai_agents_package_runs} package-backed run(s); "
                f"{openai_agents_compatibility_runs} compatibility-mode run(s)."
                if openai_agents_package_runs
                else (
                    f"0 package-backed runs; "
                    f"{openai_agents_compatibility_runs} compatibility-mode run(s)."
                )
            ),
            next_action=(
                (
                    "Use package-backed traces for adapter-import claims; still avoid "
                    "live-model claims."
                )
                if openai_agents_package_runs
                else (
                    "Run the OpenAI Agents adapter with the optional extra installed and "
                    "save traces."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved Live Provider Evidence",
            status="passed" if live_providers else "missing",
            evidence=(
                _provider_summary({provider: model_providers[provider] for provider in live_providers})
                if live_providers
                else "No non-offline model provider metadata found in saved artifacts."
            ),
            next_action=(
                "Use saved live-provider rows for calibrated claims."
                if live_providers
                else "Run and preserve at least one credential-gated live-provider smoke artifact."
            ),
        ),
    ]


def _live_calibration_status(
    checks: list[LiveCalibrationCheck],
    live_providers: list[str],
) -> str:
    if live_providers:
        return "calibrated"
    statuses = {check.name: check.status for check in checks}
    if (
        statuses.get("OpenAI SDK") == "passed"
        and statuses.get("OpenAI Credentials") == "passed"
    ):
        return "ready_to_run"
    if "missing" in statuses.values():
        return "not_configured"
    return "needs_review"


def _live_calibration_plan_runs(
    *,
    openai_sdk_available: bool,
    credentials_configured: bool,
    deepagents_available: bool,
    openai_agents_available: bool,
    saved_live_provider_count: int,
) -> list[LiveCalibrationPlanRun]:
    live_smoke_status = (
        "ready"
        if openai_sdk_available and credentials_configured
        else "blocked"
    )
    live_suite_status = (
        "ready"
        if saved_live_provider_count
        else "waiting_for_smoke"
        if live_smoke_status == "ready"
        else "blocked"
    )
    return [
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph single-task smoke",
            stage="required",
            status=live_smoke_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/runs/<run_id>",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
                "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
                "--test-command \"python3 -m pytest\" "
                "--runtime langgraph --planner openai --context-provider native_hybrid "
                "--artifacts-dir artifacts --json"
            ),
            success_evidence=(
                "Run trace contains model_provider `openai_responses`, response metadata, "
                "token counts, and a saved report."
            ),
            claim_boundary="Proves one bounded live planner smoke, not broad repair quality.",
        ),
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph seeded-suite eval",
            stage="follow_up",
            status=live_suite_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/live_openai_repair_eval_v1",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime langgraph --planner openai --context-provider native_hybrid "
                "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
            ),
            success_evidence=(
                "Repair evaluation summary includes non-offline model provider metadata "
                "and token/cost rows."
            ),
            claim_boundary=(
                "Supports seeded-suite live-provider calibration only; public-issue "
                "repair claims still require separate artifacts."
            ),
        ),
        LiveCalibrationPlanRun(
            name="DeepAgents package-backed adapter refresh",
            stage="optional",
            status="ready" if deepagents_available else "setup_required",
            runtime="deepagents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/deepagents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime deepagents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
            ),
            success_evidence="Trace harness status is `package_available` for DeepAgents rows.",
            claim_boundary=(
                "Proves optional package import compatibility, not live DeepAgents model quality."
            ),
        ),
        LiveCalibrationPlanRun(
            name="OpenAI Agents package-backed adapter refresh",
            stage="optional",
            status="ready" if openai_agents_available else "setup_required",
            runtime="openai_agents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/openai_agents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
            ),
            success_evidence=(
                "Trace harness status is `package_available` for OpenAI Agents SDK rows."
            ),
            claim_boundary=(
                "Proves optional package import compatibility, not live OpenAI Agents model quality."
            ),
        ),
    ]


def _live_calibration_plan_status(
    *,
    readiness: LiveCalibrationReport,
    openai_sdk_available: bool,
    credentials_configured: bool,
) -> str:
    if readiness.calibration_status == "calibrated":
        return "calibrated"
    if openai_sdk_available and credentials_configured:
        return "ready_to_run"
    return "blocked"


def _live_calibration_plan_decision(report: LiveCalibrationPlanReport) -> str:
    if report.plan_status == "calibrated":
        return "Live-provider evidence already exists; rerun only when recalibrating a new model or scaffold."
    if report.plan_status == "ready_to_run":
        return "Run the required single-task smoke first, then regenerate `live-calibration` before broader evals."
    return (
        "Live calibration is planned but blocked by missing prerequisites. Do not claim "
        "live LLM execution until a required run saves non-offline provider metadata."
    )


def _package_available(
    package_name: str,
    package_availability: dict[str, bool] | None,
) -> bool:
    if package_availability is not None and package_name in package_availability:
        return package_availability[package_name]
    return find_spec(package_name) is not None


def _discover_deepagents_adapter_modes(artifacts_dir: Path) -> dict[str, int]:
    return _discover_adapter_modes(artifacts_dir, framework="deepagents")


def _discover_openai_agents_adapter_modes(artifacts_dir: Path) -> dict[str, int]:
    return _discover_adapter_modes(artifacts_dir, framework="openai_agents")


def _discover_adapter_modes(artifacts_dir: Path, *, framework: str) -> dict[str, int]:
    modes: dict[str, set[str]] = {
        "package_available": set(),
        "compatibility_mode": set(),
    }
    experiments_dir = artifacts_dir / "experiments"
    if not experiments_dir.exists():
        return {}
    for trace_path in sorted(experiments_dir.glob("**/traces.jsonl")):
        try:
            lines = trace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if (
                event.get("event_type") != "runtime_node"
                or payload.get("framework") != framework
                or payload.get("node") != "harness"
            ):
                continue
            mode = str(payload.get("status") or event.get("status") or "")
            run_id = str(event.get("run_id") or trace_path.parent.name)
            if mode in modes:
                modes[mode].add(run_id)
    return {
        mode: len(run_ids)
        for mode, run_ids in sorted(modes.items())
        if run_ids
    }


def _discover_model_providers(artifacts_dir: Path) -> dict[str, int]:
    providers: Counter[str] = Counter()
    experiments_dir = artifacts_dir / "experiments"
    if not experiments_dir.exists():
        return {}
    for path in sorted(experiments_dir.glob("**/*.json")):
        if path.name in {
            "index.json",
            "failure_report.json",
            "demo_readiness.json",
            "calibration_readiness.json",
            "live_calibration_plan.json",
            "demo_script.json",
            "demo_media.json",
            "quality_gate.json",
            "final_evaluation.json",
            "delivery_audit.json",
            "release_hygiene.json",
        }:
            continue
        payload = _load_json(path)
        _collect_model_providers(payload, providers)
    return dict(sorted(providers.items()))


def _collect_model_providers(payload: Any, providers: Counter[str]) -> None:
    if isinstance(payload, dict):
        provider = payload.get("model_provider")
        if isinstance(provider, str) and provider:
            providers[provider] += 1
        for value in payload.values():
            if isinstance(value, dict | list):
                _collect_model_providers(value, providers)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict | list):
                _collect_model_providers(item, providers)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_demo_media_png(report: DemoMediaReport, output_path: Path) -> None:
    width = report.width
    height = report.height
    pixels = bytearray(_rgb("#f7f8fa") * width * height)
    _fill_rect(pixels, width, height, 56, 48, 1088, 579, _rgb("#ffffff"))
    _stroke_rect(pixels, width, height, 56, 48, 1088, 579, _rgb("#d9dee7"), 2)
    _fill_rect(pixels, width, height, 56, 48, 1088, 122, _rgb("#147d75"))
    _fill_rect(pixels, width, height, 92, 246, 456, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 316, 512, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 386, 398, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 456, 310, 38, _rgb("#f4e3bd"))
    _fill_rect(pixels, width, height, 676, 244, 380, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 314, 460, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 384, 325, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 454, 238, 40, _rgb("#f4e3bd"))
    _write_png(output_path, width, height, bytes(pixels))


def _write_png(path: Path, width: int, height: int, rgb_bytes: bytes) -> None:
    rows = bytearray()
    stride = width * 3
    for row in range(height):
        rows.append(0)
        start = row * stride
        rows.extend(rgb_bytes[start : start + stride])
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(payload)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: bytes,
) -> None:
    x_end = min(width, x + rect_width)
    y_end = min(height, y + rect_height)
    for row in range(max(0, y), y_end):
        for column in range(max(0, x), x_end):
            offset = (row * width + column) * 3
            pixels[offset : offset + 3] = color


def _stroke_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: bytes,
    thickness: int,
) -> None:
    _fill_rect(pixels, width, height, x, y, rect_width, thickness, color)
    _fill_rect(
        pixels,
        width,
        height,
        x,
        y + rect_height - thickness,
        rect_width,
        thickness,
        color,
    )
    _fill_rect(pixels, width, height, x, y, thickness, rect_height, color)
    _fill_rect(
        pixels,
        width,
        height,
        x + rect_width - thickness,
        y,
        thickness,
        rect_height,
        color,
    )


def _rgb(hex_color: str) -> bytes:
    normalized = hex_color.lstrip("#")
    return bytes(
        int(normalized[index : index + 2], 16)
        for index in range(0, 6, 2)
    )


def _release_hygiene_checks(
    *,
    project_root: Path,
    artifacts_dir: Path,
    readiness: DemoReadinessReport,
) -> list[ReleaseHygieneCheck]:
    required_docs = [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]
    required_artifacts = [
        "experiments/index.md",
        "experiments/index.json",
        "experiments/index.html",
        "experiments/failure_report.md",
        "experiments/failure_report.json",
        "experiments/demo_readiness.md",
        "experiments/demo_readiness.json",
        "experiments/calibration_readiness.md",
        "experiments/calibration_readiness.json",
        "experiments/live_calibration_plan.md",
        "experiments/live_calibration_plan.json",
        "experiments/launch_blockers.md",
        "experiments/launch_blockers.json",
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/public_issue_corpus_v1/context_preview_report.md",
        "experiments/public_issue_corpus_v1/context_preview_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_validation_summary.json",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "experiments/public_issue_corpus_v1/focused_test_run_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/environment_readiness.md",
        "experiments/environment_readiness.json",
        "experiments/quality_gate.md",
        "experiments/quality_gate.json",
        "experiments/project_status.md",
        "experiments/project_status.json",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
        "experiments/delivery_audit.md",
        "experiments/delivery_audit.json",
    ]
    checks = [
        _path_check(
            name="Planning Docs",
            root=project_root,
            paths=required_docs,
            missing_action="Restore the missing planning, safety, release, or process docs.",
            blocked=True,
        ),
        _path_check(
            name="Generated Review Artifacts",
            root=artifacts_dir,
            paths=required_artifacts,
            missing_action="Regenerate index, failure, readiness, demo script, and final evaluation artifacts.",
            blocked=True,
        ),
        _project_status_freshness_check(artifacts_dir),
        _environment_readiness_release_check(artifacts_dir),
        _release_check(
            name="Demo Readiness",
            status="passed" if readiness.readiness_status != "not_ready" else "blocked",
            evidence=(
                f"Readiness is {readiness.readiness_status}; "
                f"{readiness.experiment_count} experiments, {readiness.run_count} runs, "
                f"{readiness.metric_count} metric rows."
            ),
            next_action=(
                "Keep caveats visible in public claims."
                if readiness.readiness_status != "not_ready"
                else "Resolve missing readiness gates before launch."
            ),
        ),
        _release_check(
            name="Failure Visibility",
            status="passed" if readiness.runs_requiring_attention > 0 else "warning",
            evidence=(
                f"{readiness.runs_requiring_attention} runs requiring attention; "
                f"categories: {_failure_summary(readiness.failure_categories)}."
            ),
            next_action=(
                "Use failure cases in the final narrative."
                if readiness.runs_requiring_attention > 0
                else "Preserve at least one failure example for honest evaluation."
            ),
        ),
        _release_check(
            name="Live LLM Claim Boundary",
            status="warning"
            if not _live_providers(readiness.model_providers)
            else "passed",
            evidence=_provider_summary(readiness.model_providers),
            next_action=(
                "Do not claim live LLM calibration in release materials."
                if not _live_providers(readiness.model_providers)
                else "Report token usage and cost next to live-provider quality metrics."
            ),
        ),
        _git_repository_check(project_root),
        _packaging_config_check(project_root),
        _release_check(
            name="CI Workflow",
            status="passed"
            if (project_root / ".github" / "workflows").exists()
            else "warning",
            evidence=(
                ".github/workflows exists."
                if (project_root / ".github" / "workflows").exists()
                else "No CI workflow directory found."
            ),
            next_action=(
                "Keep pytest and artifact checks in CI."
                if (project_root / ".github" / "workflows").exists()
                else "Add a CI workflow before public repository release."
            ),
        ),
        _release_check(
            name="Demo Media",
            status="passed" if _has_demo_media(project_root) else "warning",
            evidence=(
                "Demo media asset found."
                if _has_demo_media(project_root)
                else "No GIF, MP4, or screenshot asset found under docs, artifacts, or assets."
            ),
            next_action=(
                "Reference the media in README."
                if _has_demo_media(project_root)
                else "Capture a screenshot, GIF, or short video from the generated demo script."
            ),
        ),
        _release_check(
            name="Architecture Diagram Asset",
            status="passed" if _has_architecture_diagram(project_root) else "warning",
            evidence=(
                "Architecture diagram evidence found."
                if _has_architecture_diagram(project_root)
                else "No Mermaid block or diagram asset found in architecture surfaces."
            ),
            next_action=(
                "Keep diagram synchronized with architecture docs."
                if _has_architecture_diagram(project_root)
                else "Add a simple architecture diagram before public launch."
            ),
        ),
        _content_check(
            name="Public Claim Caveats",
            path=project_root / "README.md",
            needles=["ready_with_caveats", "offline", "live LLM calibration"],
            missing_action="Update README so live-provider and offline-demo caveats are visible.",
            blocked=False,
        ),
    ]
    return checks


def _launch_blocker_items(artifacts_dir: Path) -> list[LaunchBlockerItem]:
    items = [
        _docker_smoke_launch_item(artifacts_dir),
        _focused_setup_readiness_launch_item(artifacts_dir),
        _live_calibration_launch_item(artifacts_dir),
        _release_hygiene_launch_item(artifacts_dir),
    ]
    return sorted(items, key=_launch_blocker_sort_key)


def _docker_smoke_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/docker_smoke.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="docker_smoke",
            status="blocked",
            severity="P0",
            area="Sandbox",
            summary="Docker sandbox smoke evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `docker-smoke` after Docker Desktop or DOCKER_HOST is available.",
            source_artifact=source,
            remediation_commands=[
                "docker context ls",
                "docker version",
                "docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .",
                (
                    "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke "
                    "--project-root . --artifacts-dir artifacts "
                    "--image patchsmith-seeded-smoke:py312 "
                    "--output artifacts/experiments/docker_smoke.md "
                    "--json-output artifacts/experiments/docker_smoke.json --json"
                ),
            ],
        )

    smoke_status = _payload_string(payload, "smoke_status", "unknown")
    checks = payload.get("checks")
    actionable_check = _first_actionable_check(checks if isinstance(checks, list) else [])
    next_action = (
        actionable_check.get("next_action")
        if actionable_check
        else payload.get("smoke_command")
    )
    evidence = (
        actionable_check.get("evidence")
        if actionable_check
        else f"Docker smoke status is `{smoke_status}`."
    )
    commands = _dedupe_strings(
        [
            *_payload_string_list(payload, "remediation_commands"),
            _payload_string(payload, "build_command"),
            _payload_string(payload, "smoke_command"),
        ]
    )
    return _launch_item(
        blocker_id="docker_smoke",
        status="ready" if smoke_status == "passed" else "blocked",
        severity="P2" if smoke_status == "passed" else "P0",
        area="Sandbox",
        summary=(
            "Docker sandbox smoke passed."
            if smoke_status == "passed"
            else f"Docker sandbox smoke is `{smoke_status}`."
        ),
        evidence=str(evidence),
        next_action=(
            "No action needed."
            if smoke_status == "passed"
            else str(next_action or "Start Docker, build the smoke image, and rerun `docker-smoke`.")
        ),
        source_artifact=source,
        remediation_commands=[] if smoke_status == "passed" else commands,
    )


def _focused_setup_readiness_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="focused_setup_readiness",
            status="blocked",
            severity="P0",
            area="Public Issue Setup",
            summary="Focused public issue setup-readiness evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `check-focused-test-setup-readiness` after setup planning.",
            source_artifact=source,
        )

    task_count = _payload_int(payload, "task_count")
    blocked_tasks = _payload_int(payload, "blocked_tasks")
    warning_tasks = _payload_int(payload, "warning_tasks")
    ready_tasks = _payload_int(payload, "ready_tasks")
    docker_status = _payload_string(payload, "docker_smoke_status", "unknown")
    if blocked_tasks:
        status = "blocked"
        severity = "P0"
        summary = f"{blocked_tasks} focused public issue setup task(s) are blocked."
        next_action = "Resolve Docker smoke availability before executing setup commands."
    elif warning_tasks:
        status = "warning"
        severity = "P1"
        summary = f"{warning_tasks} focused public issue setup task(s) need review."
        next_action = "Review warnings before running dependency setup against public repos."
    else:
        status = "ready"
        severity = "P2"
        summary = "Focused public issue setup tasks are ready."
        next_action = "Proceed with focused setup execution under the approved sandbox policy."
    return _launch_item(
        blocker_id="focused_setup_readiness",
        status=status,
        severity=severity,
        area="Public Issue Setup",
        summary=summary,
        evidence=(
            f"{ready_tasks}/{task_count} ready, {warning_tasks} warning, "
            f"{blocked_tasks} blocked; Docker smoke `{docker_status}`."
        ),
        next_action=next_action,
        source_artifact=source,
        dependencies=["docker_smoke"],
        remediation_commands=[
            (
                "PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness "
                "--setup-plan artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_plan_results.json "
                "--docker-smoke artifacts/experiments/docker_smoke.json "
                "--output artifacts/experiments/public_issue_corpus_v1 --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups "
                "--readiness artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_readiness_results.json "
                "--output artifacts/experiments/public_issue_corpus_v1 "
                "--allow-dependency-installs --sandbox-mode docker "
                "--sandbox-network bridge --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups "
                "--setup-execution artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_execution_results.json "
                "--output artifacts/experiments/public_issue_corpus_v1 "
                "--sandbox-mode docker --sandbox-network bridge --json"
            ),
        ],
    )


def _live_calibration_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/calibration_readiness.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="live_calibration",
            status="warning",
            severity="P1",
            area="Model Evidence",
            summary="Live calibration readiness evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `live-calibration` before making provider or model-quality claims.",
            source_artifact=source,
        )

    live_runs = _payload_int(payload, "saved_live_provider_count")
    deepagents_runs = _payload_int(payload, "deepagents_package_run_count")
    compatibility_runs = _payload_int(payload, "deepagents_compatibility_run_count")
    calibration_status = _payload_string(payload, "calibration_status", "unknown")
    status = "ready" if live_runs else "warning"
    return _launch_item(
        blocker_id="live_calibration",
        status=status,
        severity="P2" if status == "ready" else "P1",
        area="Model Evidence",
        summary=(
            "Saved live-provider calibration evidence exists."
            if live_runs
            else "Live-provider calibration remains unconfigured."
        ),
        evidence=(
            f"Calibration `{calibration_status}` with {live_runs} live-provider run(s), "
            f"{deepagents_runs} DeepAgents package-backed run(s), and "
            f"{compatibility_runs} DeepAgents compatibility-mode run(s)."
        ),
        next_action=(
            "Report live quality, token use, and estimated cost together."
            if live_runs
            else "Configure credentials and budget, then run a live calibration smoke before claiming live LLM quality."
        ),
        source_artifact=source,
        remediation_commands=[] if live_runs else [
            "export OPENAI_API_KEY=...",
            "export PATCHSMITH_OPENAI_MODEL=<model>",
            (
                "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/calibration_readiness.md "
                "--json-output artifacts/experiments/calibration_readiness.json --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/live_calibration_plan.md "
                "--json-output artifacts/experiments/live_calibration_plan.json --json"
            ),
        ],
    )


def _release_hygiene_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/release_hygiene.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="release_hygiene",
            status="warning",
            severity="P1",
            area="Release",
            summary="Release hygiene evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `release-hygiene` after refreshing launch blockers.",
            source_artifact=source,
        )

    release_status = _payload_string(payload, "release_status", "unknown")
    blocked_count = _payload_int(payload, "blocked_count")
    warning_count = _payload_int(payload, "warning_count")
    passed_count = _payload_int(payload, "passed_count")
    if release_status == "ready":
        status = "ready"
        severity = "P2"
        summary = "Release hygiene is ready."
        next_action = "No action needed."
    elif release_status == "ready_with_warnings":
        status = "warning"
        severity = "P1"
        summary = "Release hygiene has warnings."
        next_action = "Review warning checks and keep caveats visible in release materials."
    else:
        status = "blocked"
        severity = "P0"
        summary = "Release hygiene is blocked."
        next_action = "Resolve blocked release hygiene checks before claiming launch readiness."
    return _launch_item(
        blocker_id="release_hygiene",
        status=status,
        severity=severity,
        area="Release",
        summary=summary,
        evidence=(
            f"Release status `{release_status}` with {passed_count} passed, "
            f"{warning_count} warning, {blocked_count} blocked check(s)."
        ),
        next_action=next_action,
        source_artifact=source,
        dependencies=["quality_gate", "launch_blockers"],
        remediation_commands=[
            (
                "PYTHONPATH=src python3 -m patchsmith.cli quality-gate "
                "--project-root . --artifacts-dir artifacts "
                "--output artifacts/experiments/quality_gate.md "
                "--json-output artifacts/experiments/quality_gate.json "
                "--logs-dir artifacts/experiments/quality_gate_logs --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli launch-blockers "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/launch_blockers.md "
                "--json-output artifacts/experiments/launch_blockers.json --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli release-hygiene "
                "--project-root . --artifacts-dir artifacts "
                "--output artifacts/experiments/release_hygiene.md "
                "--json-output artifacts/experiments/release_hygiene.json --json"
            ),
        ],
    )


def _load_json_artifact(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _first_actionable_check(checks: list[Any]) -> dict[str, Any] | None:
    for check in checks:
        if isinstance(check, dict) and check.get("status") not in {"passed", "ready"}:
            return check
    return None


def _payload_int(payload: dict[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else default


def _payload_float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key)
    if isinstance(value, int | float):
        return float(value)
    return default


def _payload_string(payload: dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else default


def _project_status_surface(
    *,
    name: str,
    status: str,
    evidence: str,
    source: str,
) -> ProjectStatusSurface:
    return ProjectStatusSurface(
        name=name,
        status=status,
        evidence=evidence,
        source=source,
    )


def _project_overall_status(
    *,
    missing_sources: list[str],
    delivery_status: str,
    launch_status: str,
    quality_status: str,
    release_status: str,
    mvp_status: str,
    calibration_status: str,
    environment_status: str,
) -> str:
    if missing_sources:
        return "incomplete_evidence"
    if (
        delivery_status == "in_progress_with_blockers"
        or launch_status == "blocked"
        or quality_status == "failed"
        or release_status == "blocked"
        or environment_status == "blocked"
    ):
        return "in_progress_with_blockers"
    if (
        mvp_status == "ready_with_caveats"
        or release_status == "ready_with_warnings"
        or calibration_status == "not_configured"
    ):
        return "ready_with_caveats"
    return "ready"


def _project_evidence_freshness(
    *,
    sources: dict[str, str],
    payloads: dict[str, dict[str, Any] | None],
    as_of: datetime,
    threshold_seconds: int = PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS,
) -> list[ProjectEvidenceFreshness]:
    return [
        _project_source_freshness(
            source=source,
            payload=payloads.get(name),
            as_of=as_of,
            threshold_seconds=threshold_seconds,
        )
        for name, source in sources.items()
    ]


def _project_source_freshness(
    *,
    source: str,
    payload: dict[str, Any] | None,
    as_of: datetime,
    threshold_seconds: int,
) -> ProjectEvidenceFreshness:
    if payload is None:
        return ProjectEvidenceFreshness(
            source=source,
            status="missing",
            generated_at=None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="Artifact is missing or could not be parsed as JSON.",
        )
    generated_at = _payload_string(payload, "generated_at")
    generated_at_dt = _parse_utc_datetime(generated_at)
    if generated_at_dt is None:
        return ProjectEvidenceFreshness(
            source=source,
            status="undated",
            generated_at=generated_at or None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="Artifact has no parseable generated_at timestamp.",
        )
    age_seconds = max(0, int((as_of - generated_at_dt).total_seconds()))
    threshold_label = _format_age_seconds(threshold_seconds)
    age_label = _format_age_seconds(age_seconds)
    if age_seconds > threshold_seconds:
        return ProjectEvidenceFreshness(
            source=source,
            status="stale",
            generated_at=_format_utc(generated_at_dt),
            age_seconds=age_seconds,
            threshold_seconds=threshold_seconds,
            detail=f"Generated {age_label} ago; exceeds {threshold_label} threshold.",
        )
    return ProjectEvidenceFreshness(
        source=source,
        status="fresh",
        generated_at=_format_utc(generated_at_dt),
        age_seconds=age_seconds,
        threshold_seconds=threshold_seconds,
        detail=f"Generated {age_label} ago; within {threshold_label} threshold.",
    )


def _project_evidence_freshness_status(
    freshness: list[ProjectEvidenceFreshness],
) -> str:
    statuses = {item.status for item in freshness}
    if "missing" in statuses:
        return "missing"
    if "stale" in statuses:
        return "stale"
    if "undated" in statuses:
        return "undated"
    return "fresh"


def _project_freshness_generated_at(freshness: ProjectEvidenceFreshness) -> str:
    if freshness.generated_at is None:
        return ""
    return f"`{freshness.generated_at}`"


def _project_freshness_age(freshness: ProjectEvidenceFreshness) -> str:
    if freshness.age_seconds is None:
        return ""
    return _format_age_seconds(freshness.age_seconds)


def _payload_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


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
            f"delivery_status={result.delivery_status}, "
            f"completion={result.completion_percent:.1f}%"
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
        return (
            f"plan_status={result.plan_status}, "
            f"ready_runs={getattr(result, 'ready_runs', 0)}"
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


def _launch_item(
    *,
    blocker_id: str,
    status: str,
    severity: str,
    area: str,
    summary: str,
    evidence: str,
    next_action: str,
    source_artifact: str,
    dependencies: list[str] | None = None,
    remediation_commands: list[str] | None = None,
) -> LaunchBlockerItem:
    return LaunchBlockerItem(
        blocker_id=blocker_id,
        status=status,
        severity=severity,
        area=area,
        summary=summary,
        evidence=evidence,
        next_action=next_action,
        source_artifact=source_artifact,
        dependencies=dependencies or [],
        remediation_commands=remediation_commands or [],
    )


def _launch_blocker_sort_key(item: LaunchBlockerItem) -> tuple[int, int, str]:
    status_rank = {"blocked": 0, "warning": 1, "ready": 2}.get(item.status, 3)
    severity_rank = {"P0": 0, "P1": 1, "P2": 2}.get(item.severity, 3)
    return status_rank, severity_rank, item.blocker_id


def _launch_blocker_status(items: list[LaunchBlockerItem]) -> str:
    statuses = {item.status for item in items}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _launch_blocker_decision(report: LaunchBlockerReport) -> str:
    if report.launch_status == "ready":
        return "No launch blockers are present in the current readiness artifacts."
    if report.launch_status == "ready_with_warnings":
        return (
            "Launch can proceed only with the listed caveats and without live-provider "
            "or unsupported sandbox claims."
        )
    return (
        "Launch is blocked by readiness evidence. Resolve P0 items before claiming "
        "public or tagged release readiness."
    )


def _path_check(
    *,
    name: str,
    root: Path,
    paths: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    missing = [path for path in paths if not (root / path).exists()]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    evidence = (
        f"Found {len(paths) - len(missing)}/{len(paths)} required paths."
        if missing
        else f"All {len(paths)} required paths found."
    )
    if missing:
        evidence += f" Missing: {', '.join(missing)}."
    return _release_check(
        name=name,
        status=status,
        evidence=evidence,
        next_action="No action needed." if not missing else missing_action,
    )


def _content_check(
    *,
    name: str,
    path: Path,
    needles: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing = [needle for needle in needles if needle not in text]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    return _release_check(
        name=name,
        status=status,
        evidence=(
            f"All {len(needles)} caveat markers found."
            if not missing
            else f"Missing markers: {', '.join(missing)}."
        ),
        next_action="No action needed." if not missing else missing_action,
    )


def _project_status_freshness_check(artifacts_dir: Path) -> ReleaseHygieneCheck:
    payload = _load_json_artifact(artifacts_dir / "experiments" / "project_status.json")
    if payload is None:
        return _release_check(
            name="Project Status Freshness",
            status="blocked",
            evidence="Project status JSON is missing or invalid.",
            next_action="Run `project-status` or `refresh-evidence` before release review.",
        )

    freshness_status = _payload_string(
        payload, "evidence_freshness_status", "undated"
    )
    stale_count = _payload_int(payload, "stale_source_count")
    undated_count = _payload_int(payload, "undated_source_count")
    missing_count = len(_payload_string_list(payload, "missing_sources"))
    if freshness_status in {"missing", "stale"} or missing_count:
        status = "blocked"
        next_action = (
            "Regenerate missing or stale evidence with `refresh-evidence` before "
            "claiming release readiness."
        )
    elif freshness_status == "undated" or undated_count:
        status = "warning"
        next_action = (
            "Regenerate undated evidence so release claims have timestamped sources."
        )
    else:
        status = "passed"
        next_action = "No action needed."
    return _release_check(
        name="Project Status Freshness",
        status=status,
        evidence=(
            f"Freshness is {freshness_status}; {stale_count} stale, "
            f"{undated_count} undated, {missing_count} missing sources."
        ),
        next_action=next_action,
    )


def _environment_readiness_release_check(artifacts_dir: Path) -> ReleaseHygieneCheck:
    payload = _load_json_artifact(
        artifacts_dir / "experiments" / "environment_readiness.json"
    )
    if payload is None:
        return _release_check(
            name="Environment Readiness",
            status="blocked",
            evidence="Environment readiness JSON is missing or invalid.",
            next_action=(
                "Run `environment-readiness` or `refresh-evidence` before release review."
            ),
        )
    readiness_status = _payload_string(payload, "readiness_status", "missing")
    passed_count = _payload_int(payload, "passed_count")
    warning_count = _payload_int(payload, "warning_count")
    blocked_count = _payload_int(payload, "blocked_count")
    if readiness_status == "ready":
        status = "passed"
        next_action = "No action needed."
    elif readiness_status == "ready_with_warnings":
        status = "warning"
        next_action = "Keep environment caveats visible in release notes."
    elif readiness_status == "blocked":
        status = "warning"
        next_action = (
            "Resolve environment blockers before public launch; keep launch claims "
            "scoped to saved offline evidence."
        )
    else:
        status = "blocked"
        next_action = "Regenerate environment readiness before release review."
    return _release_check(
        name="Environment Readiness",
        status=status,
        evidence=(
            f"Environment readiness is {readiness_status}; {passed_count} passed, "
            f"{warning_count} warnings, {blocked_count} blocked."
        ),
        next_action=next_action,
    )


def _release_check(
    *,
    name: str,
    status: str,
    evidence: str,
    next_action: str,
) -> ReleaseHygieneCheck:
    return ReleaseHygieneCheck(
        name=name,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def _git_repository_check(project_root: Path) -> ReleaseHygieneCheck:
    if not (project_root / ".git").exists():
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="No .git directory found at project root.",
            next_action="Initialize or restore the Git repository before claiming a stable tagged release.",
        )

    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="Git repository exists but has no commit yet.",
            next_action="Create a verified baseline commit before claiming a stable tagged release.",
        )

    branch = _run_git(project_root, "branch", "--show-current")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Could not inspect Git worktree: {status.stderr.strip() or status.stdout.strip()}",
            next_action="Fix Git metadata before claiming release readiness.",
        )
    if status.stdout.strip():
        changed_count = len([line for line in status.stdout.splitlines() if line.strip()])
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Git commit {head.stdout.strip()} has {changed_count} uncommitted file changes.",
            next_action="Commit, stash, or intentionally remove worktree changes before tagging a release.",
        )

    branch_name = branch.stdout.strip() or "detached HEAD"
    return _release_check(
        name="Git Repository",
        status="passed",
        evidence=f"Git commit {head.stdout.strip()} on {branch_name}; worktree clean.",
        next_action="Create a tag only after final verification.",
    )


def _packaging_config_check(project_root: Path) -> ReleaseHygieneCheck:
    pyproject_path = project_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence="pyproject.toml is missing.",
            next_action="Restore project package metadata before release.",
        )
    except tomllib.TOMLDecodeError as error:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"pyproject.toml could not be parsed: {error}",
            next_action="Fix package metadata before release.",
        )

    project = pyproject.get("project", {})
    optional_deps = project.get("optional-dependencies", {})
    dev_extra = optional_deps.get("dev", [])
    wheel = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
    )
    wheel_packages = wheel.get("packages", [])
    project_name = project.get("name")
    project_version = project.get("version")
    missing: list[str] = []
    if not project_name:
        missing.append("project.name")
    if not project_version:
        missing.append("project.version")
    if "src/patchsmith" not in wheel_packages:
        missing.append("tool.hatch.build.targets.wheel.packages includes src/patchsmith")
    if not _dependency_present(dev_extra, "pytest"):
        missing.append("project.optional-dependencies.dev includes pytest")
    if not _dependency_present(dev_extra, "build"):
        missing.append("project.optional-dependencies.dev includes build")

    if missing:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"Missing package metadata: {', '.join(missing)}.",
            next_action="Fix pyproject package metadata before claiming release readiness.",
        )

    return _release_check(
        name="Packaging Config",
        status="passed",
        evidence=(
            f"{project_name} {project_version}; wheel packages {', '.join(wheel_packages)}; "
            "dev extra includes pytest and build."
        ),
        next_action="Keep package build validation in CI.",
    )


def _dependency_present(dependencies: list[Any], package_name: str) -> bool:
    prefix = package_name.lower()
    for dependency in dependencies:
        if isinstance(dependency, str) and dependency.lower().startswith(prefix):
            return True
    return False


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _release_status(checks: list[ReleaseHygieneCheck]) -> str:
    statuses = {check.status for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _release_decision(report: ReleaseHygieneReport) -> str:
    if report.release_status == "ready":
        return "Release hygiene is clean for the current scoped portfolio launch."
    if report.release_status == "ready_with_warnings":
        return (
            "Release hygiene has warnings. The offline demo can proceed if each warning "
            "is disclosed or deliberately deferred."
        )
    return (
        "Release hygiene is blocked. Resolve blocked checks before claiming a stable "
        "public or tagged release."
    )


def _live_providers(providers: dict[str, int]) -> list[str]:
    return [
        provider
        for provider in providers
        if provider and not provider.startswith("offline_")
    ]


def _has_demo_media(project_root: Path) -> bool:
    search_roots = [
        project_root / "docs",
        project_root / "artifacts",
        project_root / "assets",
    ]
    suffixes = {".gif", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}
    for root in search_roots:
        if not root.exists():
            continue
        if any(path.suffix.lower() in suffixes for path in root.rglob("*")):
            return True
    return False


def _has_architecture_diagram(project_root: Path) -> bool:
    architecture_path = project_root / "docs" / "03_architecture.md"
    try:
        architecture_text = architecture_path.read_text(encoding="utf-8")
    except OSError:
        architecture_text = ""
    if "```mermaid" in architecture_text:
        return True
    diagram_roots = [project_root / "docs", project_root / "assets"]
    suffixes = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
    for root in diagram_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if "arch" in path.name.lower() and path.suffix.lower() in suffixes:
                return True
    return False


def _final_metric(metric: ExperimentMetricIndexEntry) -> FinalEvaluationMetric:
    return FinalEvaluationMetric(
        experiment=metric.experiment,
        kind=metric.kind,
        lane=metric.lane,
        task_count=metric.task_count,
        completed_count=metric.completed_count,
        primary_metric=_metric_label_value(metric.primary_label, metric.primary_value),
        secondary_metric=_metric_label_value(
            metric.secondary_label,
            metric.secondary_value,
        ),
        avg_latency_ms=metric.avg_latency_ms,
        estimated_cost_usd=metric.estimated_cost_usd,
        risk_note=metric.risk_note,
        report_path=metric.report_path,
    )


def _metric_label_value(label: str | None, value: int | float | str | None) -> str:
    if label is None and value is None:
        return ""
    if label is None:
        return _metric_value("", value)
    return f"{label}: {_metric_value(label, value)}"


def _metric_value(label: str, value: int | float | str | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    normalized_label = label.lower()
    if "avg test runs" in normalized_label:
        if isinstance(value, int) or float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}"
    if any(
        token in normalized_label
        for token in (
            "recall",
            "related tests",
            "passed",
            "generated",
            "success",
            "valid",
        )
    ) and 0 <= value <= 1:
        return f"{value * 100:.0f}%"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _final_evaluation_decisions(
    readiness: DemoReadinessReport,
    metrics: list[FinalEvaluationMetric],
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    decisions = [
        (
            f"Portfolio evidence is `{readiness.readiness_status}` with "
            f"{readiness.experiment_count} experiments, {readiness.run_count} saved runs, "
            f"and {readiness.metric_count} normalized metric rows."
        ),
        (
            "Use the static dashboard, run-detail pages, failure report, readiness report, "
            "and demo script as the launch review surface before adding a hosted UI."
        ),
    ]
    retrieval_rows = [metric for metric in metrics if metric.kind == "retrieval"]
    if retrieval_rows:
        lanes = ", ".join(sorted({metric.lane for metric in retrieval_rows}))
        decisions.append(
            f"Retrieval evidence is available for these lanes: {lanes}."
        )
    repair_rows = [
        metric
        for metric in metrics
        if metric.kind in {"repair", "scaffold"}
        and "Targeted Tests Passed: 100%" in metric.primary_metric
    ]
    if repair_rows:
        lanes = ", ".join(sorted({metric.lane for metric in repair_rows}))
        decisions.append(
            f"Seeded repair/scaffold evidence shows targeted tests passing for: {lanes}."
        )
    patch_rows = [metric for metric in metrics if metric.kind == "patch_search"]
    if patch_rows:
        seen_test_run_lanes: set[str] = set()
        test_run_parts: list[str] = []
        for metric in patch_rows:
            if not metric.secondary_metric or metric.lane in seen_test_run_lanes:
                continue
            seen_test_run_lanes.add(metric.lane)
            test_run_parts.append(f"{metric.lane} {metric.secondary_metric}")
        test_runs = "; ".join(
            test_run_parts
        )
        decisions.append(
            "Patch-search evidence should be framed as a cost tradeoff; "
            f"current candidate lanes report {test_runs}."
        )
    if readiness.failure_categories:
        decisions.append(
            "Failure cases are preserved for review: "
            f"{_failure_summary(readiness.failure_categories)}."
        )
    package_runs = deepagents_modes.get("package_available", 0)
    compatibility_runs = deepagents_modes.get("compatibility_mode", 0)
    if package_runs:
        decisions.append(
            f"DeepAgents adapter evidence now includes {package_runs} package-backed "
            f"run(s) and {compatibility_runs} compatibility-mode run(s); this proves "
            "optional-package import compatibility, not live DeepAgents model quality."
        )
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    openai_agents_compatibility_runs = openai_agents_modes.get("compatibility_mode", 0)
    if openai_agents_package_runs:
        decisions.append(
            "OpenAI Agents adapter evidence now includes "
            f"{openai_agents_package_runs} package-backed run(s) and "
            f"{openai_agents_compatibility_runs} compatibility-mode run(s); this proves "
            "optional-package import compatibility, not live OpenAI Agents model quality."
        )
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        decisions.append(
            f"Live-provider evidence exists for {', '.join(live_providers)}; report cost "
            "and token usage next to any live-model quality claim."
        )
    else:
        decisions.append(
            "Do not claim live LLM calibration yet; saved provider metadata is offline-only."
        )
    return decisions


def _final_evaluation_limitations(
    readiness: DemoReadinessReport,
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    package_runs = deepagents_modes.get("package_available", 0)
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    deepagents_limitation = (
        "DeepAgents package-backed adapter smoke evidence exists, but live DeepAgents "
        "model execution remains uncalibrated."
        if package_runs
        else (
            "DeepAgents evidence is adapter compatibility evidence unless the optional "
            "package and live model provider are installed and reflected in saved artifacts."
        )
    )
    openai_agents_limitation = (
        "OpenAI Agents package-backed adapter smoke evidence exists, but live OpenAI "
        "Agents model execution remains uncalibrated."
        if openai_agents_package_runs
        else (
            "OpenAI Agents evidence is adapter compatibility evidence unless the optional "
            "package and live model provider are installed and reflected in saved artifacts."
        )
    )
    limitations = [
        "The seeded suite is intentionally small and controlled; it proves workflow plumbing and comparative instrumentation, not broad real-world coding-agent quality.",
        "Current public-demo mode should use seeded or preselected repositories until sandboxing is hardened for arbitrary untrusted repos.",
        deepagents_limitation,
        openai_agents_limitation,
    ]
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if not live_providers:
        limitations.append(
            "No non-offline model provider metadata was found; live LLM quality, token use, and cost remain uncalibrated."
        )
    if readiness.runs_requiring_attention:
        limitations.append(
            f"{readiness.runs_requiring_attention} saved runs still require attention; use them as failure-analysis material, not as hidden exclusions."
        )
    return limitations


def _final_review_artifacts() -> list[str]:
    return [
        "artifacts/experiments/index.html",
        "artifacts/experiments/index.md",
        "artifacts/experiments/failure_report.md",
        "artifacts/experiments/demo_readiness.md",
        "artifacts/experiments/calibration_readiness.md",
        "artifacts/experiments/live_calibration_plan.md",
        "artifacts/experiments/launch_blockers.md",
        "artifacts/experiments/demo_script.md",
        "artifacts/experiments/public_issue_corpus_v1/corpus_report.md",
        "artifacts/experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "artifacts/experiments/public_issue_corpus_v1/context_preview_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_task_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "artifacts/experiments/demo_media.md",
        "artifacts/experiments/demo_media.svg",
        "artifacts/experiments/demo_media.png",
        "artifacts/experiments/quality_gate.md",
        "artifacts/experiments/project_status.md",
        "artifacts/experiments/delivery_audit.md",
        "artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
        "artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
        "artifacts/experiments/retrieval_eval_v1/report.md",
    ]


def _executive_conclusion(report: FinalEvaluationReport) -> str:
    if report.readiness_status == "ready":
        return (
            "PatchSmith is ready for a portfolio demo with current saved evidence. "
            "Keep the demo scoped to the artifact set summarized here."
        )
    if report.readiness_status == "ready_with_caveats":
        return (
            "PatchSmith is ready for an offline portfolio demo with caveats. The saved "
            "artifacts support the issue-to-tested-patch research workflow, but live LLM "
            "calibration and arbitrary public execution should remain explicitly out of scope."
        )
    return (
        "PatchSmith is not ready for portfolio launch from the current saved artifacts; "
        "resolve the missing gates before recording a public demo."
    )


def _task_count_cell(metric: FinalEvaluationMetric) -> str:
    if metric.task_count is None:
        return ""
    if metric.completed_count is None:
        return str(metric.task_count)
    return f"{metric.completed_count}/{metric.task_count}"


def _latency_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.0f}ms"


def _cost_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:.4f}"


def _path_cell(path: str | None) -> str:
    if path is None:
        return ""
    return f"`{path}`"


def _demo_commands() -> list[str]:
    return [
        "python3 -m pytest -q",
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-scaffold "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--variant agentless --variant heuristic --variant langgraph "
            "--variant langgraph_fake_model --variant deepagents "
            "--variant openai_agents "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/scaffold_comparison_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--candidate-count 1 --candidate-count 3 "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/patch_search_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli index-artifacts "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/index.md "
            "--json-output artifacts/experiments/index.json "
            "--html-output artifacts/experiments/index.html "
            "--run-detail-output-dir artifacts/experiments/run-details --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli inspect-failures "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/failure_report.md "
            "--json-output artifacts/experiments/failure_report.json "
            "--max-runs 0 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-readiness "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_readiness.md "
            "--json-output artifacts/experiments/demo_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-script "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_script.md "
            "--json-output artifacts/experiments/demo_script.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-media "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_media.md "
            "--svg-output artifacts/experiments/demo_media.svg "
            "--png-output artifacts/experiments/demo_media.png "
            "--json-output artifacts/experiments/demo_media.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli final-evaluation "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/final_evaluation.md "
            "--json-output artifacts/experiments/final_evaluation.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli release-hygiene "
            "--project-root . "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/release_hygiene.md "
            "--json-output artifacts/experiments/release_hygiene.json --json"
        ),
    ]


def _demo_script_sections(readiness: DemoReadinessReport) -> list[DemoScriptSection]:
    failure_summary = _failure_summary(readiness.failure_categories)
    provider_summary = _provider_summary(readiness.model_providers)
    return [
        DemoScriptSection(
            title="Problem And Thesis",
            duration_seconds=25,
            on_screen="README project summary and architecture overview.",
            artifact="README.md",
            narration=(
                "PatchSmith is an AI software-maintenance agent and evaluation lab. "
                "The point of the demo is not a single lucky patch; it is a repeatable "
                "issue-to-tested-diff workflow with retrieval, orchestration, sandboxed "
                "tests, saved traces, and honest evaluation artifacts."
            ),
        ),
        DemoScriptSection(
            title="Evidence Dashboard",
            duration_seconds=35,
            on_screen="Open the static artifact dashboard and scan metrics.",
            artifact="artifacts/experiments/index.html",
            narration=(
                f"The current artifact set has {readiness.experiment_count} experiments, "
                f"{readiness.run_count} saved runs, and {readiness.metric_count} normalized "
                "metric rows. Use this screen to show retrieval, repair, scaffold, graph, "
                "and patch-search evidence from one review surface."
            ),
        ),
        DemoScriptSection(
            title="Runtime Comparison",
            duration_seconds=40,
            on_screen="Open scaffold comparison and explain the lanes.",
            artifact="artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
            narration=(
                "The scaffold comparison keeps Agentless, heuristic, LangGraph, "
                "LangGraph fake-model, DeepAgents, and OpenAI Agents SDK adapters "
                "under the same seeded task set and context provider. The important "
                "interview story is that quality, latency, trace complexity, and "
                "debuggability are measured together instead of treated as separate "
                "anecdotes."
            ),
        ),
        DemoScriptSection(
            title="Patch Search Cost Tradeoff",
            duration_seconds=30,
            on_screen="Open patch-search report and compare one versus three candidates.",
            artifact="artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
            narration=(
                "Patch search is included as a research mode. On the current easy seeded "
                "suite, three candidates do not improve success over one candidate, but "
                "they add test runs and latency. That result is useful because it prevents "
                "over-selling patch search before harder tasks justify the cost."
            ),
        ),
        DemoScriptSection(
            title="Failure Transparency",
            duration_seconds=35,
            on_screen="Open the failure report and show grouped failures.",
            artifact="artifacts/experiments/failure_report.md",
            narration=(
                f"The failure report keeps failure cases visible: {failure_summary}. "
                "For the current artifacts, most failures are expected Agentless control "
                "runs with no patch generated. This is exactly the kind of evidence a "
                "research demo should preserve rather than hide."
            ),
        ),
        DemoScriptSection(
            title="Caveats And Close",
            duration_seconds=25,
            on_screen="Open demo readiness report and state the launch status.",
            artifact="artifacts/experiments/demo_readiness.md",
            narration=(
                f"The readiness status is {readiness.readiness_status}. Provider evidence "
                f"is {provider_summary}. The correct closing claim is that the offline "
                "seeded-suite demo is coherent, while live LLM calibration remains a "
                "separate credential-gated step unless non-offline provider metadata is present."
            ),
        ),
    ]


def _demo_script_caveat(readiness: DemoReadinessReport) -> str:
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        return f"Live provider metadata found: {', '.join(live_providers)}."
    return (
        "Current model evidence is offline only; live LLM calibration must be run "
        "separately before making live-provider claims."
    )


def _demo_script_rehearsal_commands() -> list[str]:
    return [
        (
            "PYTHONPATH=src python3 -m patchsmith.cli index-artifacts "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/index.md "
            "--json-output artifacts/experiments/index.json "
            "--html-output artifacts/experiments/index.html "
            "--run-detail-output-dir artifacts/experiments/run-details --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli inspect-failures "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/failure_report.md "
            "--json-output artifacts/experiments/failure_report.json "
            "--max-runs 0 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-readiness "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_readiness.md "
            "--json-output artifacts/experiments/demo_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-script "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_script.md "
            "--json-output artifacts/experiments/demo_script.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-media "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_media.md "
            "--svg-output artifacts/experiments/demo_media.svg "
            "--png-output artifacts/experiments/demo_media.png "
            "--json-output artifacts/experiments/demo_media.json --json"
        ),
    ]


def _live_calibration_commands() -> list[str]:
    return [
        'python -m pip install -e ".[dev,deepagents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime deepagents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
        ),
        'python -m pip install -e ".[dev,openai-agents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
        ),
        (
            "export OPENAI_API_KEY=...\n"
            "export PATCHSMITH_OPENAI_MODEL=<model>\n"
            "export PATCHSMITH_OPENAI_INPUT_COST_PER_1M=<input_rate>\n"
            "export PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M=<output_rate>"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli run "
            "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
            "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
            "--test-command \"python3 -m pytest\" "
            "--runtime langgraph --planner openai --context-provider native_hybrid "
            "--artifacts-dir artifacts --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime langgraph --planner openai --context-provider native_hybrid "
            "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
    ]


def _live_calibration_decision(report: LiveCalibrationReport) -> str:
    if report.calibration_status == "calibrated":
        return (
            "Saved non-offline provider evidence exists. Report it with token and cost "
            "metadata before making live-provider claims."
        )
    if report.calibration_status == "ready_to_run":
        return (
            "The environment appears ready for a live OpenAI smoke run, but saved "
            "live-provider artifacts are still missing."
        )
    if report.calibration_status == "not_configured":
        return (
            "Live calibration is not configured. Keep current public claims scoped to "
            "offline seeded-suite evidence."
        )
    return (
        "Live calibration needs review before publishable claims. Resolve warning checks "
        "and preserve the resulting run artifacts."
    )


def _failure_summary(categories: dict[str, int]) -> str:
    if not categories:
        return "no saved failure categories"
    return ", ".join(f"{name} {count}" for name, count in categories.items())


def _provider_summary(providers: dict[str, int]) -> str:
    if not providers:
        return "missing"
    return ", ".join(f"{name} {count}" for name, count in providers.items())


def _format_duration(seconds: int) -> str:
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s"
    return f"{remainder}s"


def _markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def _utc_now() -> str:
    return _format_utc(datetime.now(timezone.utc).replace(microsecond=0))


def _format_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _format_age_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"
