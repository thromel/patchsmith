"""Markdown rendering for project status reports."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _format_age_seconds, _markdown_cell
from patchsmith.portfolio.models import ProjectEvidenceFreshness, ProjectStatusReport


def render_project_status_report(report: ProjectStatusReport) -> str:
    lines = [
        "# PatchSmith Project Status Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Overall status: `{report.overall_status}`",
        f"- MVP progress: `{report.mvp_completion_percent:.1f}%` (`{report.mvp_status}`)",
        (
            f"- Delivery audit: `{report.delivery_completion_percent:.1f}%` "
            f"(`{report.delivery_status}`)"
        ),
        f"- Quality gate: `{report.quality_status}`",
        f"- Launch status: `{report.launch_status}`",
        f"- Release status: `{report.release_status}`",
        f"- Docker smoke: `{report.docker_smoke_status}`",
        f"- Environment readiness: `{report.environment_readiness_status}`",
        f"- Live calibration: `{report.live_calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- Indexed experiments: `{report.experiment_count}`",
        f"- Indexed runs: `{report.run_count}`",
        f"- Metric rows: `{report.metric_count}`",
        f"- Launch blockers: `{report.blocker_count}`",
        f"- Launch warnings: `{report.warning_count}`",
        (
            f"- Evidence freshness: `{report.evidence_freshness_status}` "
            f"(`{report.stale_source_count}` stale, "
            f"`{report.undated_source_count}` undated)"
        ),
        "",
        "## Status Surfaces",
        "",
        "| Surface | Status | Evidence | Source |",
        "|---|---|---|---|",
    ]
    for surface in report.surfaces:
        lines.append(
            "| "
            f"{surface.name} | "
            f"{surface.status} | "
            f"{_markdown_cell(surface.evidence)} | "
            f"`{surface.source}` |"
        )
    lines.extend(["", "## Missing Sources", ""])
    if report.missing_sources:
        lines.extend(f"- `{source}`" for source in report.missing_sources)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Evidence Freshness",
            "",
            "| Source | Status | Generated At | Age | Detail |",
            "|---|---|---|---|---|",
        ]
    )
    for freshness in report.evidence_freshness:
        lines.append(
            "| "
            f"`{freshness.source}` | "
            f"{freshness.status} | "
            f"{_project_freshness_generated_at(freshness)} | "
            f"{_project_freshness_age(freshness)} | "
            f"{_markdown_cell(freshness.detail)} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report summarizes saved evidence artifacts; it does not rerun checks.",
            "- Use `quality-gate` for executable verification.",
            "- Use `docker-smoke` for Docker sandbox evidence.",
            "- Use `live-calibration` for live model-provider evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _project_freshness_generated_at(freshness: ProjectEvidenceFreshness) -> str:
    if freshness.generated_at is None:
        return ""
    return f"`{freshness.generated_at}`"


def _project_freshness_age(freshness: ProjectEvidenceFreshness) -> str:
    if freshness.age_seconds is None:
        return ""
    return _format_age_seconds(freshness.age_seconds)


__all__ = ["render_project_status_report"]
