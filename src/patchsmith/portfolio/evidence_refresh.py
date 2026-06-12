"""Portfolio evidence refresh (split from portfolio.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import _utc_now
from patchsmith.portfolio.evidence_refresh_steps import (
    EvidenceRefreshConfig,
    build_evidence_refresh_steps,
)
from patchsmith.portfolio.evidence_refresh_support import (
    _evidence_refresh_status,
    render_evidence_refresh_report,
)
from patchsmith.portfolio.models import EvidenceRefreshReport
from patchsmith.portfolio.quality_gate import (
    DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
)


def build_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
    include_docker_smoke: bool = False,
    docker_smoke_skip_run: bool = False,
    docker_smoke_image: str = "patchsmith-seeded-smoke:py312",
    docker_binary: str = "docker",
) -> EvidenceRefreshReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    steps = build_evidence_refresh_steps(
        EvidenceRefreshConfig(
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
    quality_timeout_seconds: int = DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
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
    write_markdown(output_path, render_evidence_refresh_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report
