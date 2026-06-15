"""Portfolio project-status and evidence-refresh report models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS = 24 * 60 * 60


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
    complex_suite_refreshed: bool
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
            "complex_suite_refreshed": self.complex_suite_refreshed,
            "steps": [step.to_dict() for step in self.steps],
        }


__all__ = [
    "PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS",
    "EvidenceRefreshReport",
    "EvidenceRefreshStep",
    "ProjectEvidenceFreshness",
    "ProjectStatusReport",
    "ProjectStatusSurface",
]
