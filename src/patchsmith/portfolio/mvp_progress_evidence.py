"""Evidence extraction for MVP progress checklist items."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from patchsmith.observability import ArtifactIndex, FailureArtifactReport
from patchsmith.portfolio._helpers import _file_contains
from patchsmith.portfolio.docker_smoke import (
    _docker_sandbox_success_count,
    _latest_docker_smoke_status,
)
from patchsmith.portfolio.models import DemoReadinessReport, LiveCalibrationReport


@dataclass(frozen=True)
class MvpProgressEvidence:
    project_root: Path
    artifacts_dir: Path
    readiness: DemoReadinessReport
    calibration: LiveCalibrationReport
    failure_report: FailureArtifactReport
    run_count: int
    seeded_task_count: int
    has_run: bool
    has_report: bool
    has_trace: bool
    has_diff: bool
    has_test_output: bool
    has_latency: bool
    has_cost: bool
    has_retrieval: bool
    has_repair: bool
    has_patch_search: bool
    has_langgraph: bool
    has_docker_runner: bool
    docker_smoke_count: int
    latest_docker_smoke_status: str | None
    issue_corpus_count: int
    run_artifact_reports: int
    run_artifact_diffs: int
    run_artifact_traces: int


def build_mvp_progress_evidence(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
    readiness: DemoReadinessReport,
    calibration: LiveCalibrationReport,
    failure_report: FailureArtifactReport,
) -> MvpProgressEvidence:
    metric_kinds = {metric.kind for metric in index.metrics}
    metric_lanes = {metric.lane for metric in index.metrics}
    has_docker_runner = _file_contains(
        project_root / "src" / "patchsmith" / "sandbox.py",
        "class DockerSandboxRunner",
    )
    return MvpProgressEvidence(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        readiness=readiness,
        calibration=calibration,
        failure_report=failure_report,
        run_count=index.run_count,
        seeded_task_count=_seeded_task_count(project_root),
        has_run=index.run_count > 0,
        has_report=any(run.report_path for run in index.runs),
        has_trace=any(run.trace_path for run in index.runs),
        has_diff=any(run.diff_path for run in index.runs),
        has_test_output=any(run.stdout_path or run.stderr_path for run in index.runs),
        has_latency=any(metric.avg_latency_ms is not None for metric in index.metrics),
        has_cost=any(metric.estimated_cost_usd is not None for metric in index.metrics),
        has_retrieval="retrieval" in metric_kinds,
        has_repair=any(kind in metric_kinds for kind in ("repair", "scaffold")),
        has_patch_search="patch_search" in metric_kinds,
        has_langgraph=any("langgraph" in lane for lane in metric_lanes),
        has_docker_runner=has_docker_runner,
        docker_smoke_count=_docker_sandbox_success_count(artifacts_dir),
        latest_docker_smoke_status=_latest_docker_smoke_status(artifacts_dir),
        issue_corpus_count=_validated_issue_corpus_count(artifacts_dir),
        run_artifact_reports=sum(1 for run in index.runs if run.report_path),
        run_artifact_diffs=sum(1 for run in index.runs if run.diff_path),
        run_artifact_traces=sum(1 for run in index.runs if run.trace_path),
    )


def _seeded_task_count(project_root: Path) -> int:
    task_root = project_root / "evals" / "tasks" / "seeded_bugs_v1"
    if not task_root.exists():
        return 0
    return sum(1 for path in task_root.iterdir() if path.is_dir() and path.name.startswith("task_"))


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


__all__ = [
    "MvpProgressEvidence",
    "build_mvp_progress_evidence",
]
