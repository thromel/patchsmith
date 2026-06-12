"""Portfolio evaluation, progress, delivery, and quality report models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


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


__all__ = [
    "DeliveryAuditItem",
    "DeliveryAuditReport",
    "FinalEvaluationMetric",
    "FinalEvaluationReport",
    "MvpProgressCategory",
    "MvpProgressItem",
    "MvpProgressReport",
    "QualityGateCheck",
    "QualityGateReport",
]
