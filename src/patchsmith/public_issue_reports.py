from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
    IssueCorpusPublicReproductionPlanResult,
    IssueCorpusPublicReproductionPlanSummary,
    IssueCorpusPublicReproductionSpecValidationResult,
    IssueCorpusPublicReproductionSpecValidationSummary,
)
from patchsmith.public_issue_fixtures import public_issue_fixture_paths as _public_issue_fixture_paths


def _markdown_table_text(value: object) -> str:
    text = str(value).replace("|", "/").replace("\n", " ")
    return text[:500]


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
        log_paths = "; ".join(
            path
            for path in [result.stdout_path, result.stderr_path]
            if path
        )
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
            path
            for path in [result.stdout_path, result.stderr_path]
            if path is not None
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


def render_public_issue_repair_readiness_report(
    *,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
    summary: IssueCorpusPublicRepairReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Repair Readiness",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Materialized tasks directory: `{tasks_dir or 'not provided'}`",
        f"- Focused run path: `{focused_run_path}`",
        f"- Diagnosis path: `{diagnosis_path}`",
        f"- Setup validation path: `{setup_validation_path}`",
        f"- Reproduction execution path: `{reproduction_execution_path or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Repair-command tasks: `{summary.repair_command_tasks}`",
        f"- Passed focused tasks: `{summary.passed_focused_tasks}`",
        f"- Passed setup-validation tasks: `{summary.passed_setup_validation_tasks}`",
        f"- Reproduced tasks: `{summary.reproduced_tasks}`",
        f"- Missing reproduction tasks: `{summary.missing_reproduction_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Focused Run | Diagnosis | Setup Validation | "
            "Reproduction | Repair Command | Validation Command | Fixtures | Evidence | "
            "Blockers | Warnings | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.focused_run_status or 'missing')} | "
            f"{_markdown_table_text(result.diagnosis_category or 'missing')} | "
            f"{_markdown_table_text(result.setup_validation_status or 'missing')} | "
            f"{_markdown_table_text(result.reproduction_execution_status or 'missing')} | "
            f"{_markdown_table_text(result.repair_command or 'missing')} | "
            f"{_markdown_table_text(result.validation_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.validation_fixture_paths) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.evidence) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.blockers) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.warnings) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report gates readiness for a later PatchSmith public issue repair attempt.",
            "- `ready` means focused validation, setup validation, repository snapshot, and a saved repair command are available.",
            "- `warning` means repair can be attempted only with explicit caveats, usually because the saved pre-repair command passed and does not prove issue reproduction.",
            "- `blocked` means do not attempt a public issue repair until the listed prerequisite is fixed.",
            "- This report does not execute PatchSmith repair, generate a patch, call a live model provider, or prove public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_repair_attempt_report(
    *,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    summary: IssueCorpusPublicRepairAttemptSummary,
) -> str:
    lines = [
        "# Public Issue Repair Attempts",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Readiness path: `{readiness_path}`",
        f"- Materialized tasks directory: `{tasks_dir or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{summary.dry_run}`",
        f"- Allow warnings: `{summary.allow_warnings}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Max retries: `{summary.max_retries}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Validated tasks: `{summary.validated_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Reproduced-input tasks: `{summary.reproduced_input_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Readiness | Reproduction | Runtime | "
            "Validation | Fixtures | Test Exit | Patch | Run | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        run_refs = "; ".join(
            path
            for path in [result.report_path, result.trace_path, result.final_diff_path]
            if path is not None
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.readiness_status)} | "
            f"{_markdown_table_text(result.reproduction_execution_status or 'missing')} | "
            f"{_markdown_table_text(result.runtime + '/' + result.planner)} | "
            f"{_markdown_table_text(result.validation_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.validation_fixture_paths) or 'none')} | "
            f"{_markdown_table_text(str(result.test_exit_code) if result.test_exit_code is not None else 'not run')} | "
            f"{_markdown_table_text(str(result.patch_generated).lower())} | "
            f"{_markdown_table_text(run_refs or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This gate consumes public repair-readiness evidence before launching PatchSmith runs.",
            "- `blocked` rows were not run and must not be counted as repair attempts.",
            "- `dry_run` rows prove only readiness and configuration checks.",
            "- `validated` rows mean PatchSmith produced run artifacts and the configured validation command exited zero.",
            "- This report does not prove live LLM quality unless non-offline provider metadata is present in the saved run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)
