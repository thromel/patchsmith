"""Portfolio launch blockers (split from portfolio.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import (
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.launch_blocker_items import launch_blocker_items
from patchsmith.portfolio.models import LaunchBlockerItem, LaunchBlockerReport


def build_launch_blocker_report(*, artifacts_dir: Path) -> LaunchBlockerReport:
    artifacts_dir = artifacts_dir.resolve()
    items = launch_blocker_items(artifacts_dir)
    status_counts = Counter(item.status for item in items)
    return LaunchBlockerReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        launch_status=_launch_blocker_status(items),
        item_count=len(items),
        blocked_count=status_counts.get("blocked", 0),
        warning_count=status_counts.get("warning", 0),
        ready_count=status_counts.get("ready", 0),
        items=items,
    )


def write_launch_blocker_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> LaunchBlockerReport:
    report = build_launch_blocker_report(artifacts_dir=artifacts_dir)
    write_markdown(output_path, render_launch_blocker_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_launch_blocker_report(report: LaunchBlockerReport) -> str:
    lines = [
        "# PatchSmith Launch Blocker Backlog",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Launch status: `{report.launch_status}`",
        f"- Items: `{report.item_count}`",
        f"- Blocked: `{report.blocked_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Ready: `{report.ready_count}`",
        "",
        "## Prioritized Items",
        "",
        "| ID | Status | Severity | Area | Summary | Evidence | Next Action | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            f"{item.blocker_id} | "
            f"{item.status} | "
            f"{item.severity} | "
            f"{item.area} | "
            f"{_markdown_cell(item.summary)} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.next_action)} | "
            f"`{item.source_artifact}` |"
        )
    lines.extend(["", "## Dependency Chain", ""])
    for item in report.items:
        dependencies = ", ".join(f"`{dependency}`" for dependency in item.dependencies)
        lines.append(
            f"- `{item.blocker_id}`: "
            f"{dependencies if dependencies else 'no upstream blocker dependency'}"
        )
    lines.extend(["", "## Remediation Commands", ""])
    for item in report.items:
        lines.append(f"### `{item.blocker_id}`")
        lines.append("")
        if item.remediation_commands:
            lines.append("```bash")
            lines.extend(item.remediation_commands)
            lines.append("```")
        else:
            lines.append("No command needed.")
        lines.append("")
    lines.extend(["## Decision", "", _launch_blocker_decision(report)])
    return "\n".join(lines) + "\n"


def _launch_blocker_status(items: list[LaunchBlockerItem]) -> str:
    statuses = {item.status for item in items}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _launch_blocker_decision(report: LaunchBlockerReport) -> str:
    if report.launch_status == "ready":
        return "No launch blockers are present in the current readiness artifacts."
    if report.launch_status == "ready_with_warnings":
        return (
            "Launch can proceed only with the listed caveats and without live-provider "
            "or unsupported sandbox claims."
        )
    return (
        "Launch is blocked by readiness evidence. Resolve P0 items before claiming "
        "public or tagged release readiness."
    )
