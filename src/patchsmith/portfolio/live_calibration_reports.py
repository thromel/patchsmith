"""Markdown rendering for live calibration reports."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _markdown_cell, _provider_summary
from patchsmith.portfolio.models import (
    LiveCalibrationPlanReport,
    LiveCalibrationReport,
)


def render_live_calibration_report(report: LiveCalibrationReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Readiness",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- Model providers: `{_provider_summary(report.model_providers)}`",
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
    lines.extend(["", "## Smoke Commands", ""])
    for command in report.smoke_commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(["## Decision", "", _live_calibration_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def render_live_calibration_plan_report(report: LiveCalibrationPlanReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Plan",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Plan status: `{report.plan_status}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- Credentials configured: `{str(report.credentials_configured).lower()}`",
        f"- Model: `{report.model}`",
        f"- Cost rates configured: `{str(report.cost_rates_configured).lower()}`",
        "",
        "## Prerequisites",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.prerequisites:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Planned Runs",
            "",
            "| Run | Stage | Status | Runtime | Planner | Context | Credentials | Output | Success Evidence | Claim Boundary |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in report.runs:
        lines.append(
            "| "
            f"{run.name} | "
            f"{run.stage} | "
            f"{run.status} | "
            f"{run.runtime} | "
            f"{run.planner} | "
            f"{run.context_provider} | "
            f"{str(run.requires_credentials).lower()} | "
            f"{_markdown_cell(run.output_path)} | "
            f"{_markdown_cell(run.success_evidence)} | "
            f"{_markdown_cell(run.claim_boundary)} |"
        )
    lines.extend(["", "## Commands", ""])
    for run in report.runs:
        lines.extend([f"### {run.name}", "", "```bash", run.command, "```", ""])
    lines.extend(["## Claim Boundary", ""])
    for claim in report.claim_boundary:
        lines.append(f"- {claim}")
    lines.extend(["", "## Decision", "", _live_calibration_plan_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def _live_calibration_plan_decision(report: LiveCalibrationPlanReport) -> str:
    if report.plan_status == "calibrated":
        return "Live-provider evidence already exists; rerun only when recalibrating a new model or scaffold."
    if report.plan_status == "ready_to_run":
        return "Run the required single-task smoke first, then regenerate `live-calibration` before broader evals."
    return (
        "Live calibration is planned but blocked by missing prerequisites. Do not claim "
        "live LLM execution until a required run saves non-offline provider metadata."
    )


def _live_calibration_decision(report: LiveCalibrationReport) -> str:
    if report.calibration_status == "calibrated":
        return (
            "Saved non-offline provider evidence exists. Report it with token and cost "
            "metadata before making live-provider claims."
        )
    if report.calibration_status == "ready_to_run":
        return (
            "The environment appears ready for a live OpenAI smoke run, but saved "
            "live-provider artifacts are still missing."
        )
    if report.calibration_status == "not_configured":
        return (
            "Live calibration is not configured. Keep current public claims scoped to "
            "offline seeded-suite evidence."
        )
    return (
        "Live calibration needs review before publishable claims. Resolve warning checks "
        "and preserve the resulting run artifacts."
    )
