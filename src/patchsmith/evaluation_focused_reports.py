from __future__ import annotations

import json
from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestDiagnosisResult,
    IssueCorpusFocusedTestDiagnosisSummary,
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
    IssueCorpusFocusedTestRunResult,
    IssueCorpusFocusedTestRunSummary,
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupPlanResult,
    IssueCorpusFocusedTestSetupPlanSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
    IssueCorpusFocusedTestSetupValidationResult,
    IssueCorpusFocusedTestSetupValidationSummary,
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


def render_focused_test_setup_plan_report(
    *,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
    summary: IssueCorpusFocusedTestSetupPlanSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Plan",
        "",
        f"- Diagnosis path: `{diagnosis_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned setup tasks: `{summary.planned_tasks}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Manual review tasks: `{summary.manual_review_tasks}`",
        f"- Dependency setup tasks: `{summary.dependency_setup_tasks}`",
        f"- Environment setup tasks: `{summary.environment_setup_tasks}`",
        f"- Network-required tasks: `{summary.network_required_tasks}`",
        f"- Sandbox-required tasks: `{summary.sandbox_required_tasks}`",
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
            "| Task | Status | Profile | Setup Commands | Validation | Risk Notes |",
            "|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        setup_commands = "; ".join(result.setup_commands) if result.setup_commands else "none"
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(setup_commands)} | "
            f"{_markdown_table_text(result.validation_command or 'none')} | "
            f"{_markdown_table_text('; '.join(result.risk_notes) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans setup work from focused-test diagnosis categories.",
            "- Setup commands are not executed by this report and may require network access.",
            "- Run setup commands only in disposable, policy-approved sandboxes with no host secrets.",
            "- Passing setup does not prove public issue repair quality; it only prepares later reproduction and validation attempts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_readiness_report(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
    summary: IssueCorpusFocusedTestSetupReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Readiness",
        "",
        f"- Setup plan path: `{setup_plan_path}`",
        f"- Docker smoke path: `{docker_smoke_path}`",
        f"- Docker smoke status: `{summary.docker_smoke_status}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Network-required tasks: `{summary.network_required_tasks}`",
        f"- Sandbox-required tasks: `{summary.sandbox_required_tasks}`",
        "",
        "## Results",
        "",
        "| Task | Status | Profile | Repository Snapshot | Docker | Notes | Next Actions |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text('present' if result.repo_exists else result.repo_path or 'missing')} | "
            f"{_markdown_table_text(result.docker_smoke_status)} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report checks whether focused public issue setup plans are ready to execute.",
            "- It does not execute setup commands, install dependencies, or run validation tests.",
            "- `blocked` means setup should not be attempted until the listed safety or environment issue is fixed.",
            "- Public issue repair quality remains unproven until setup, reproduction, patching, and validation are saved as run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_execution_report(
    *,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    summary: IssueCorpusFocusedTestSetupExecutionSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Execution",
        "",
        f"- Readiness path: `{readiness_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Allow warnings: `{str(summary.allow_warnings).lower()}`",
        (f"- Allow dependency installs: `{str(summary.allow_dependency_installs).lower()}`"),
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Completed tasks: `{summary.completed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Skipped tasks: `{summary.skipped_tasks}`",
        f"- Setup commands: `{summary.command_count}`",
        f"- Attempted commands: `{summary.attempted_commands}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Readiness | Profile | Image | Network | Dependency Installs | "
            "Commands | Command Statuses | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        command_statuses = [
            f"{command.status}:{command.policy_reason or command.exit_code or 'n/a'}"
            for command in result.command_results
        ]
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.readiness_status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(result.sandbox_image)} | "
            f"{_markdown_table_text(result.sandbox_network)} | "
            f"{_markdown_table_text(str(result.allow_dependency_installs).lower())} | "
            f"{_markdown_table_text('; '.join(result.setup_commands) or 'none')} | "
            f"{_markdown_table_text('; '.join(command_statuses) or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Dry-run rows prove setup orchestration and command-policy checks, not dependency installation.",
            "- Blocked rows are stop conditions and must not be counted as public issue reproduction evidence.",
            "- Executed rows prove only setup command outcomes; repair quality still requires focused validation and normal run artifacts.",
            "- Commands must run only in disposable, policy-approved sandboxes with no host secrets.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_validation_report(
    *,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    summary: IssueCorpusFocusedTestSetupValidationSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Validation",
        "",
        f"- Setup execution path: `{setup_execution_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Skipped tasks: `{summary.skipped_tasks}`",
        f"- Failure categories: `{json.dumps(summary.failure_category_counts, sort_keys=True)}`",
        "",
        "## Results",
        "",
        "| Task | Status | Setup Status | Profile | Image | Validation Command | Command Status | Failure | Notes | Next Actions |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        command_status = (
            result.command_result.status if result.command_result is not None else "none"
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_execution_status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(result.sandbox_image)} | "
            f"{_markdown_table_text(result.validation_command or 'none')} | "
            f"{_markdown_table_text(command_status)} | "
            f"{_markdown_table_text(result.failure_category or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Dry-run rows prove validation command policy checks, not public issue reproduction.",
            "- Blocked rows mean setup has not reached a state where validation can run.",
            "- Passed validation proves the focused validation command runs after setup, not that a PatchSmith repair succeeded.",
            "- Repair-quality claims still require issue reproduction, patch generation, and saved normal PatchSmith run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:500]
