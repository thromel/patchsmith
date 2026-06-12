"""Portfolio release hygiene (split from portfolio.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import (
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.models import (
    ReleaseHygieneCheck,
    ReleaseHygieneReport,
)
from patchsmith.portfolio.release_hygiene_checks import (
    release_hygiene_checks as _release_hygiene_checks,
)
from patchsmith.portfolio.release_hygiene_project_checks import (
    _run_git as _run_git,
)


def build_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    checks = _release_hygiene_checks(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        readiness=readiness,
    )
    status_counts = Counter(check.status for check in checks)
    return ReleaseHygieneReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        release_status=_release_status(checks),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        checks=checks,
        review_artifacts=[
            "artifacts/experiments/index.html",
            "artifacts/experiments/failure_report.md",
            "artifacts/experiments/demo_readiness.md",
            "artifacts/experiments/calibration_readiness.md",
            "artifacts/experiments/launch_blockers.md",
            "artifacts/experiments/demo_script.md",
            "artifacts/experiments/demo_media.svg",
            "artifacts/experiments/demo_media.png",
            "artifacts/experiments/quality_gate.md",
            "artifacts/experiments/project_status.md",
            "artifacts/experiments/final_evaluation.md",
            "artifacts/experiments/delivery_audit.md",
            "artifacts/experiments/release_hygiene.md",
        ],
    )


def write_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    report = build_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    write_markdown(output_path, render_release_hygiene_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_release_hygiene_report(report: ReleaseHygieneReport) -> str:
    lines = [
        "# PatchSmith Release Hygiene Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Release status: `{report.release_status}`",
        f"- Passed checks: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            _release_decision(report),
        ]
    )
    return "\n".join(lines) + "\n"


def _release_status(checks: list[ReleaseHygieneCheck]) -> str:
    statuses = {check.status for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _release_decision(report: ReleaseHygieneReport) -> str:
    if report.release_status == "ready":
        return "Release hygiene is clean for the current scoped portfolio launch."
    if report.release_status == "ready_with_warnings":
        return (
            "Release hygiene has warnings. The offline demo can proceed if each warning "
            "is disclosed or deliberately deferred."
        )
    return (
        "Release hygiene is blocked. Resolve blocked checks before claiming a stable "
        "public or tagged release."
    )
