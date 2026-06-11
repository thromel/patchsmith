"""Observability package; public API facade for the split modules."""

from __future__ import annotations

from patchsmith.observability.failure import (
    build_failure_report,
    render_failure_report,
    write_failure_report,
)
from patchsmith.observability.index import (
    build_artifact_index,
    write_artifact_index,
    write_run_detail_pages,
)
from patchsmith.observability.models import (
    GENERATED_EXPERIMENT_DIR_NAMES,
    RECENT_RUN_LIMIT,
    REPORT_FILENAMES,
    RESULT_FILENAMES,
    SUMMARY_FILENAMES,
    ArtifactIndex,
    ExperimentArtifactIndexEntry,
    ExperimentMetricIndexEntry,
    FailureArtifactReport,
    FailureRunInsight,
    RunArtifactIndexEntry,
)
from patchsmith.observability.render_html import (
    render_artifact_dashboard,
    render_run_detail_page,
)
from patchsmith.observability.render_md import (
    render_artifact_index,
)

__all__ = [
    "GENERATED_EXPERIMENT_DIR_NAMES",
    "RECENT_RUN_LIMIT",
    "REPORT_FILENAMES",
    "RESULT_FILENAMES",
    "SUMMARY_FILENAMES",
    "ArtifactIndex",
    "ExperimentArtifactIndexEntry",
    "ExperimentMetricIndexEntry",
    "FailureArtifactReport",
    "FailureRunInsight",
    "RunArtifactIndexEntry",
    "build_artifact_index",
    "build_failure_report",
    "render_artifact_dashboard",
    "render_artifact_index",
    "render_failure_report",
    "render_run_detail_page",
    "write_artifact_index",
    "write_failure_report",
    "write_run_detail_pages",
]
