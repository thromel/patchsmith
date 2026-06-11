"""Portfolio delivery audit."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability import build_artifact_index
from patchsmith.portfolio._helpers import _utc_now
from patchsmith.portfolio.delivery_audit_items import _delivery_audit_items
from patchsmith.portfolio.delivery_audit_reports import render_delivery_audit_report
from patchsmith.portfolio.delivery_audit_support import (
    _delivery_completion_percent,
    _delivery_status,
)
from patchsmith.portfolio.models import DeliveryAuditReport


def build_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
) -> DeliveryAuditReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    items = _delivery_audit_items(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
    )
    status_counts = Counter(item.status for item in items)
    return DeliveryAuditReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        delivery_status=_delivery_status(items),
        completion_percent=_delivery_completion_percent(items),
        item_count=len(items),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        missing_count=status_counts.get("missing", 0),
        items=items,
    )


def write_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> DeliveryAuditReport:
    report = build_delivery_audit_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
    )
    write_markdown(output_path, render_delivery_audit_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


__all__ = [
    "build_delivery_audit_report",
    "render_delivery_audit_report",
    "write_delivery_audit_report",
]
