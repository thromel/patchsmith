"""Focused public issue test plan, run, and diagnosis report renderers."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_focused_report_helpers import _markdown_table_text
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestDiagnosisResult,
    IssueCorpusFocusedTestDiagnosisSummary,
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
    IssueCorpusFocusedTestRunResult,
    IssueCorpusFocusedTestRunSummary,
)


def render_materialized_issue_focused_test_plan_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
    summary: IssueCorpusFocusedTestPlanSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Plan",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned focused tasks: `{summary.planned_tasks}`",
        f"- Fallback tasks: `{summary.fallback_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Focused Files | Command | Policy | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.risk_notes, *result.errors, *result.warnings]
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"{', '.join(result.focused_files) or 'none'} | "
            f"`{result.command or 'none'}` | "
            f"{'allowed' if result.policy_allowed else result.policy_reason or 'not checked'} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans narrower pytest commands from retrieved test-like files.",
            "- Commands are policy-checked but not executed.",
            "- Passing these commands would still be targeted evidence, not full public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_focused_test_run_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    summary: IssueCorpusFocusedTestRunSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Run",
        "",
        f"- Plan path: `{plan_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Command | Exit | Duration | Logs | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        logs = "none"
        if result.stdout_path or result.stderr_path:
            logs = ", ".join(
                path for path in [result.stdout_path, result.stderr_path] if path is not None
            )
        exit_code = result.exit_code if result.exit_code is not None else "n/a"
        lines.append(
            "| "
            f"{result.task_id or 'unknown'} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"`{result.command or 'none'}` | "
            f"{exit_code} | "
            f"{result.duration_ms}ms | "
            f"{logs} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report executes the focused commands selected by the public issue task plan.",
            "- Passing tasks prove only that the planned focused test command is runnable in the current snapshot.",
            "- Failed or timed-out tasks are dependency, environment, or upstream-suite readiness signals unless paired with issue reproduction evidence.",
            "- This report does not prove issue reproduction, patch generation, or end-to-end repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_diagnosis_report(
    *,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
    summary: IssueCorpusFocusedTestDiagnosisSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Diagnosis",
        "",
        f"- Run results path: `{results_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Environment issue tasks: `{summary.environment_issue_tasks}`",
        f"- Dependency issue tasks: `{summary.dependency_issue_tasks}`",
        f"- Timeout tasks: `{summary.timeout_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Unknown failure tasks: `{summary.unknown_failure_tasks}`",
        "",
        "## Category Counts",
        "",
    ]
    if summary.category_counts:
        for category, count in summary.category_counts.items():
            lines.append(f"- `{category}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Task | Run Status | Category | Severity | Summary | Evidence | Next Actions |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.run_status or 'unknown')} | "
            f"{_markdown_table_text(result.category)} | "
            f"{_markdown_table_text(result.severity)} | "
            f"{_markdown_table_text(result.summary)} | "
            f"{_markdown_table_text('; '.join(result.evidence) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.suggested_next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report classifies focused test execution failures from saved stdout/stderr logs.",
            "- It is a dependency and environment readiness aid, not a patch-quality score.",
            "- Suggested actions must be executed only inside an approved sandbox and should not bypass command policy.",
            "- Public issue repair quality remains unproven until issue reproduction, patch generation, and passing validation are saved.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "render_focused_test_diagnosis_report",
    "render_materialized_issue_focused_test_plan_report",
    "render_materialized_issue_focused_test_run_report",
]
