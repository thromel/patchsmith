"""MVP progress checklist construction."""

from __future__ import annotations

from pathlib import Path

from patchsmith.observability import ArtifactIndex, FailureArtifactReport
from patchsmith.portfolio.models import (
    DemoReadinessReport,
    LiveCalibrationReport,
    MvpProgressItem,
)
from patchsmith.portfolio.mvp_progress_checklist_items import (
    mvp_core_flow_items,
    mvp_evaluation_items,
    mvp_observability_items,
    mvp_portfolio_items,
    mvp_safety_items,
)
from patchsmith.portfolio.mvp_progress_evidence import build_mvp_progress_evidence


def mvp_progress_items(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
    readiness: DemoReadinessReport,
    calibration: LiveCalibrationReport,
    failure_report: FailureArtifactReport,
) -> list[MvpProgressItem]:
    evidence = build_mvp_progress_evidence(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
        readiness=readiness,
        calibration=calibration,
        failure_report=failure_report,
    )
    return [
        *mvp_core_flow_items(evidence),
        *mvp_observability_items(evidence),
        *mvp_safety_items(evidence),
        *mvp_evaluation_items(evidence),
        *mvp_portfolio_items(evidence),
    ]


__all__ = ["mvp_progress_items"]
