"""Portfolio models (split from portfolio.py)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

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
            "openai_agents_compatibility_run_count": (self.openai_agents_compatibility_run_count),
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
            "openai_agents_compatibility_run_count": (self.openai_agents_compatibility_run_count),
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
            "evidence_freshness": [freshness.to_dict() for freshness in self.evidence_freshness],
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
