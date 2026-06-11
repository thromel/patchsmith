"""Observability package; public API facade for the split modules.

Index entry models and shared constants live in
``patchsmith.observability.models``.
"""

from __future__ import annotations

from patchsmith.observability.failure import (
    build_failure_report,
    write_failure_report,
)
from patchsmith.observability.index import (
    build_artifact_index,
    write_artifact_index,
)
from patchsmith.observability.models import (
    ArtifactIndex,
    ExperimentMetricIndexEntry,
    FailureArtifactReport,
)
from patchsmith.observability.render_html import (
    render_artifact_dashboard,
    render_run_detail_page,
)
from patchsmith.observability.render_md import (
    render_artifact_index,
)

__all__ = [
    "ArtifactIndex",
    "ExperimentMetricIndexEntry",
    "FailureArtifactReport",
    "build_artifact_index",
    "build_failure_report",
    "render_artifact_dashboard",
    "render_artifact_index",
    "render_run_detail_page",
    "write_artifact_index",
    "write_failure_report",
]
