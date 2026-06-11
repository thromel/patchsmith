"""Observability models (split from observability.py)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

REPORT_FILENAMES = (
    "report.md",
    "repair_report.md",
    "validation_report.md",
    "scaffold_report.md",
    "patch_search_report.md",
)


SUMMARY_FILENAMES = (
    "summary.json",
    "repair_summary.json",
    "validation_summary.json",
    "scaffold_results.json",
    "patch_search_summary.json",
)


RESULT_FILENAMES = (
    "results.json",
    "repair_results.json",
    "validation_results.json",
    "scaffold_results.json",
    "patch_search_results.json",
)


RECENT_RUN_LIMIT = 25


GENERATED_EXPERIMENT_DIR_NAMES = {"run-details", "run_details"}


@dataclass(frozen=True)
class ExperimentArtifactIndexEntry:
    name: str
    kind: str
    report_path: str | None
    summary_path: str | None
    results_path: str | None
    result_count: int | None
    run_count: int
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunArtifactIndexEntry:
    run_id: str
    experiment: str | None
    variant: str | None
    report_path: str | None
    trace_path: str | None
    diff_path: str | None
    stdout_path: str | None
    stderr_path: str | None
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentMetricIndexEntry:
    experiment: str
    kind: str
    lane: str
    task_count: int | None
    completed_count: int | None
    primary_label: str
    primary_value: int | float | str | None
    secondary_label: str | None
    secondary_value: int | float | str | None
    avg_latency_ms: float | None
    estimated_cost_usd: float | None
    risk_note: str | None
    report_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactIndex:
    artifacts_dir: str
    generated_at: str
    experiment_count: int
    run_count: int
    experiments: list[ExperimentArtifactIndexEntry]
    metrics: list[ExperimentMetricIndexEntry]
    runs: list[RunArtifactIndexEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "experiments": [entry.to_dict() for entry in self.experiments],
            "metrics": [entry.to_dict() for entry in self.metrics],
            "runs": [run.to_dict() for run in self.runs],
        }


@dataclass(frozen=True)
class FailureRunInsight:
    run_id: str
    experiment: str | None
    variant: str | None
    updated_at: str | None
    report_path: str | None
    trace_path: str | None
    diff_path: str | None
    failure_category: str
    verdict: str | None
    status: str | None
    summary: str
    next_action: str
    patch_generated: bool | None
    tests_passed: bool | None
    test_exit_code: int | None
    failed_event_count: int
    failed_nodes: list[str]
    trace_event_count: int
    total_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailureArtifactReport:
    artifacts_dir: str
    generated_at: str
    runs_scanned: int
    runs_requiring_attention: int
    failed_event_count: int
    category_counts: dict[str, int]
    insights: list[FailureRunInsight]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "runs_scanned": self.runs_scanned,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failed_event_count": self.failed_event_count,
            "category_counts": self.category_counts,
            "insights": [insight.to_dict() for insight in self.insights],
        }
