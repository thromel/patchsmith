"""Portfolio release and launch report models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from patchsmith.portfolio.evaluation_summary_models import QualityGateCheck


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
class ReleaseGateReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    release_status: str
    passed_count: int
    failed_count: int
    skipped_count: int
    checks: list[QualityGateCheck]
    review_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "release_status": self.release_status,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
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


__all__ = [
    "LaunchBlockerItem",
    "LaunchBlockerReport",
    "ReleaseGateReport",
    "ReleaseHygieneCheck",
    "ReleaseHygieneReport",
]
