"""Portfolio mvp progress (split from portfolio.py)."""

from __future__ import annotations

from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability import (
    build_artifact_index,
    build_failure_report,
)
from patchsmith.portfolio._helpers import (
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.live_calibration import build_live_calibration_report
from patchsmith.portfolio.models import (
    MvpProgressCategory,
    MvpProgressItem,
    MvpProgressReport,
)
from patchsmith.portfolio.mvp_progress_items import mvp_progress_items


def build_mvp_progress_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> MvpProgressReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    calibration = build_live_calibration_report(artifacts_dir=artifacts_dir)
    failure_report = build_failure_report(
        artifacts_dir=artifacts_dir,
        max_runs=max_failure_runs,
    )
    items = mvp_progress_items(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
        readiness=readiness,
        calibration=calibration,
        failure_report=failure_report,
    )
    categories = _mvp_progress_categories(items)
    passed_count = sum(1 for item in items if item.status == "passed")
    warning_count = sum(1 for item in items if item.status == "warning")
    blocked_count = sum(1 for item in items if item.status == "blocked")
    missing_count = sum(1 for item in items if item.status == "missing")
    completion_percent = _mvp_completion_percent(items)
    status = _mvp_progress_status(
        completion_percent=completion_percent,
        warning_count=warning_count,
        blocked_count=blocked_count,
        missing_count=missing_count,
    )
    return MvpProgressReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        completion_percent=completion_percent,
        status=status,
        item_count=len(items),
        passed_count=passed_count,
        warning_count=warning_count,
        blocked_count=blocked_count,
        missing_count=missing_count,
        categories=categories,
        items=items,
    )


def write_mvp_progress_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> MvpProgressReport:
    report = build_mvp_progress_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    write_markdown(output_path, render_mvp_progress_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_mvp_progress_report(report: MvpProgressReport) -> str:
    lines = [
        "# PatchSmith MVP Progress Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Status: `{report.status}`",
        f"- Evidence-weighted completion: `{report.completion_percent:.1f}%`",
        f"- Items: `{report.item_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        f"- Missing: `{report.missing_count}`",
        "",
        "## Category Summary",
        "",
        "| Category | Completion | Passed | Warnings | Blockers | Missing | Items |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category in report.categories:
        lines.append(
            "| "
            f"{category.name} | "
            f"{category.completion_percent:.1f}% | "
            f"{category.passed_count} | "
            f"{category.warning_count} | "
            f"{category.blocked_count} | "
            f"{category.missing_count} | "
            f"{category.item_count} |"
        )
    lines.extend(
        [
            "",
            "## Checklist Evidence",
            "",
            "| Category | Item | Status | Evidence | Next Action |",
            "|---|---|---|---|---|",
        ]
    )
    for item in report.items:
        lines.append(
            "| "
            f"{item.category} | "
            f"{item.item} | "
            f"{item.status} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Scoring",
            "",
            "- Passed items count as 1.0.",
            "- Warning items count as 0.5 because evidence exists but is incomplete.",
            "- Blocked and missing items count as 0.0.",
            "- This is an evidence report, not a substitute for rerunning verification gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _mvp_completion_percent(items: list[MvpProgressItem]) -> float:
    if not items:
        return 0.0
    return round((sum(item.score for item in items) / len(items)) * 100, 1)


def _mvp_progress_status(
    *,
    completion_percent: float,
    warning_count: int,
    blocked_count: int,
    missing_count: int,
) -> str:
    if blocked_count or missing_count:
        return "in_progress"
    if warning_count:
        return "ready_with_caveats" if completion_percent >= 80 else "in_progress"
    return "complete"


def _mvp_progress_categories(items: list[MvpProgressItem]) -> list[MvpProgressCategory]:
    categories: list[MvpProgressCategory] = []
    for category_name in dict.fromkeys(item.category for item in items):
        category_items = [item for item in items if item.category == category_name]
        categories.append(
            MvpProgressCategory(
                name=category_name,
                item_count=len(category_items),
                passed_count=sum(1 for item in category_items if item.status == "passed"),
                warning_count=sum(1 for item in category_items if item.status == "warning"),
                blocked_count=sum(1 for item in category_items if item.status == "blocked"),
                missing_count=sum(1 for item in category_items if item.status == "missing"),
                completion_percent=_mvp_completion_percent(category_items),
            )
        )
    return categories
