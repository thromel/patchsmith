"""Markdown rendering for Docker smoke reports."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _markdown_cell
from patchsmith.portfolio.models import DockerSmokeReport


def render_docker_smoke_report(report: DockerSmokeReport) -> str:
    lines = [
        "# PatchSmith Docker Smoke Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Smoke status: `{report.smoke_status}`",
        f"- Docker binary: `{report.docker_binary}`",
        f"- Image: `{report.image}`",
        f"- Task directory: `{report.task_dir}`",
        f"- Test command: `{report.test_command}`",
        f"- Runtime: `{report.runtime}`",
        f"- Context provider: `{report.context_provider}`",
        f"- Run ID: `{report.run_id or 'n/a'}`",
        f"- Test exit code: `{report.test_exit_code if report.test_exit_code is not None else 'n/a'}`",
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
    lines.extend(
        [
            "",
            "## Environment",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
    )
    for key, value in report.environment.items():
        lines.append(f"| {key} | {_markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "Diagnostic and remediation commands:",
            "",
            "```bash",
            *report.remediation_commands,
            "```",
            "",
            "Build the seeded smoke image:",
            "",
            "```bash",
            report.build_command,
            "```",
            "",
            "Run the smoke:",
            "",
            "```bash",
            report.smoke_command,
            "```",
        ]
    )
    if report.run_report_path or report.run_trace_path:
        lines.extend(["", "## Run Artifacts", ""])
        if report.run_report_path:
            lines.append(f"- Report: `{report.run_report_path}`")
        if report.run_trace_path:
            lines.append(f"- Trace: `{report.run_trace_path}`")
    lines.extend(["", "## Decision", "", _docker_smoke_decision(report)])
    return "\n".join(lines) + "\n"


def _docker_smoke_decision(report: DockerSmokeReport) -> str:
    if report.smoke_status == "passed":
        return "Docker sandbox smoke passed. The MVP Docker-sandbox evidence can be cited."
    if report.smoke_status == "failed":
        return "Docker sandbox smoke ran but failed. Inspect the run artifacts before claiming Docker readiness."
    if report.smoke_status == "skipped":
        return "Docker preflight passed but the executable seeded run was skipped."
    return "Docker sandbox smoke is not available in this environment. Keep Docker readiness as a caveat."


__all__ = ["render_docker_smoke_report"]
