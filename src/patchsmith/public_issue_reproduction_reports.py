"""Public issue reproduction report renderers."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
    IssueCorpusPublicReproductionPlanResult,
    IssueCorpusPublicReproductionPlanSummary,
    IssueCorpusPublicReproductionSpecValidationResult,
    IssueCorpusPublicReproductionSpecValidationSummary,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
)
from patchsmith.public_issue_report_helpers import _markdown_table_text


def render_public_issue_reproduction_plan_report(
    *,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
    summary: IssueCorpusPublicReproductionPlanSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Plan",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Focused plan path: `{focused_plan_path or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned tasks: `{summary.planned_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Manual-spec-required tasks: `{summary.manual_spec_required_tasks}`",
        f"- Candidate commands: `{summary.command_count}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        f"- Fixture files: `{summary.fixture_file_count}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Command Source | Command | Fixtures | "
            "Expected Failure Signals | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.blockers, *result.warnings]
        fixture_paths = "; ".join(_public_issue_fixture_paths(result.fixture_files))
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.command_source)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(fixture_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'manual spec required')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans public issue reproduction checks before repair attempts.",
            "- `planned` means an explicit expected failing signal is encoded and the command is policy-allowed.",
            "- `warning` means a candidate command exists but a reviewer still needs to encode the expected failing signal.",
            "- `blocked` means the reproduction command should not be run until the listed prerequisite is fixed.",
            "- Fixture files are written only to disposable execution workspaces; they do not modify source snapshots.",
            "- This report does not run tests, prove issue reproduction, generate patches, or call a live model provider.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_reproduction_spec_validation_report(
    *,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
    summary: IssueCorpusPublicReproductionSpecValidationSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Spec Validation",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Specs path: `{specs_path}`",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Focused plan path: `{focused_plan_path or 'not provided'}`",
        f"- Task rows: `{summary.task_count}`",
        f"- Spec count: `{summary.spec_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Missing-spec tasks: `{summary.missing_spec_tasks}`",
        f"- Empty-signal tasks: `{summary.empty_signal_tasks}`",
        f"- Policy-blocked tasks: `{summary.policy_blocked_tasks}`",
        f"- Extra-spec tasks: `{summary.extra_spec_tasks}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        f"- Fixture files: `{summary.fixture_file_count}`",
        f"- Unsafe-fixture tasks: `{summary.unsafe_fixture_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Spec | Repository | Command Source | Command | "
            "Fixtures | Expected Failure Signals | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        fixture_paths = "; ".join(_public_issue_fixture_paths(result.fixture_files))
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text('present' if result.spec_present else 'missing')} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.command_source)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(fixture_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'missing')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report validates reviewed reproduction criteria before execution.",
            "- `ready` means a spec exists, the merged command is policy-allowed, and expected failure signals are non-empty.",
            "- `warning` means the spec can be reviewed further before execution.",
            "- `blocked` means the spec should not be used for reproduction execution until fixed.",
            "- Fixture files must be repository-relative, traversal-free, and are applied only to disposable execution workspaces.",
            "- This report does not execute reproduction commands or prove public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_failure_signal_discovery_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> str:
    lines = [
        "# Public Issue Failure Signal Discovery",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Reproduction plan path: `{plan_path}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Sandbox: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Observed-failure tasks: `{summary.observed_failure_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Candidate-signal tasks: `{summary.candidate_signal_tasks}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Command | Exit Code | Candidate "
            "Signals | Fixtures | Logs | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        log_paths = "; ".join(path for path in [result.stdout_path, result.stderr_path] if path)
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(str(result.exit_code) if result.exit_code is not None else 'not run')} | "
            f"{_markdown_table_text('; '.join(result.candidate_failure_signals) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.fixture_paths) or 'none')} | "
            f"{_markdown_table_text(log_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report discovers candidate failure text for human review.",
            "- `observed_failure` means the candidate command failed and logs were saved; it does not prove issue reproduction.",
            "- Only `execute-public-issue-reproductions` with reviewed expected failure signals can count a task as reproduced.",
            "- `passed` means the candidate command did not expose a pre-repair failure and likely needs a more specific reproduction.",
            "- Fixture files, when present, are applied to a disposable copy before the candidate command runs.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_reproduction_execution_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Execution",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Reproduction plan path: `{plan_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{summary.dry_run}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Reproduced tasks: `{summary.reproduced_tasks}`",
        f"- Not-reproduced tasks: `{summary.not_reproduced_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Manual-spec-required tasks: `{summary.manual_spec_required_tasks}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Plan Status | Command | Expected Signals | "
            "Matched Signals | Fixtures | Exit | Logs | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        log_paths = "; ".join(
            path for path in [result.stdout_path, result.stderr_path] if path is not None
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.reproduction_plan_status)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.matched_failure_signals) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.fixture_paths) or 'none')} | "
            f"{_markdown_table_text(str(result.exit_code) if result.exit_code is not None else 'not run')} | "
            f"{_markdown_table_text(log_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report only executes commands from the public issue reproduction plan.",
            "- `blocked` means the command was not run because required safety or expected-failure criteria were missing.",
            "- `dry_run` means the command and expected failure signal passed preflight, but no repository code was executed.",
            "- `reproduced` means an executed command failed nonzero and all configured expected failure signals appeared in saved stdout/stderr.",
            "- Fixture files, when present, are applied to a disposable copy before the reproduction command runs.",
            "- This report does not generate patches, prove repair quality, or call a live model provider.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "render_public_issue_failure_signal_discovery_report",
    "render_public_issue_reproduction_execution_report",
    "render_public_issue_reproduction_plan_report",
    "render_public_issue_reproduction_spec_validation_report",
]
