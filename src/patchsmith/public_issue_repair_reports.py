"""Public issue repair report renderers."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
)
from patchsmith.public_issue_report_helpers import _markdown_table_text


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
        f"- Repeat count: `{summary.repeat_count}`",
        f"- Stop on validated: `{summary.stop_on_validated}`",
        f"- Unique task count: `{summary.unique_task_count}`",
        f"- Dry run: `{summary.dry_run}`",
        f"- Allow warnings: `{summary.allow_warnings}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Max retries: `{summary.max_retries}`",
        f"- DeepAgents max context files: `{summary.deepagents_max_context_files or 'not set'}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Validated tasks: `{summary.validated_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Reproduced-input tasks: `{summary.reproduced_input_tasks}`",
        f"- Tasks with validated attempt: `{summary.tasks_with_validated_attempt}`",
        f"- Tasks with failed attempts only: `{summary.tasks_with_failed_attempts_only}`",
        f"- Validated task pass@N rate: `{summary.validated_task_pass_at_n_rate:.3f}`",
        f"- Model calls: `{summary.model_call_count if summary.model_call_count is not None else 'n/a'}`",
        f"- Model responses: `{summary.model_response_count if summary.model_response_count is not None else 'n/a'}`",
        f"- Model total tokens: `{summary.model_total_tokens if summary.model_total_tokens is not None else 'n/a'}`",
        f"- Estimated model cost: `{_format_optional_cost(summary.estimated_model_cost_usd)}`",
        f"- Max actual model responses: `{summary.max_actual_model_responses if summary.max_actual_model_responses is not None else 'not set'}`",
        f"- Max actual model tokens: `{summary.max_actual_model_tokens if summary.max_actual_model_tokens is not None else 'not set'}`",
        "",
        "## Results",
        "",
        (
            "| Task | Attempt | Status | Repository | Readiness | Reproduction | Runtime | "
            "Preflight | Validation | Fixtures | Test Exit | Patch | Cost | Run | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
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
            f"{_markdown_table_text(f'{result.attempt_index}/{result.attempt_count}')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.readiness_status)} | "
            f"{_markdown_table_text(result.reproduction_execution_status or 'missing')} | "
            f"{_markdown_table_text(result.runtime + '/' + result.planner)} | "
            f"{_markdown_table_text(_preflight_summary(result))} | "
            f"{_markdown_table_text(result.validation_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.validation_fixture_paths) or 'none')} | "
            f"{_markdown_table_text(str(result.test_exit_code) if result.test_exit_code is not None else 'not run')} | "
            f"{_markdown_table_text(str(result.patch_generated).lower())} | "
            f"{_markdown_table_text(_model_cost_summary(result))} | "
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
            "- `validated` rows mean PatchSmith produced run artifacts, the configured validation command exited zero, and saved patch-quality evidence did not mark the final patch high-risk.",
            "- Rows with passing tests but high-risk final patch quality are counted as `failed` until the final diff is reviewed or retried.",
            "- Pass@N counts a task as validated when at least one repeated attempt is cleanly validated.",
            "- This report does not prove live LLM quality unless non-offline provider metadata is present in the saved run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def _preflight_summary(result: IssueCorpusPublicRepairAttemptResult) -> str:
    if not result.preflight_gates:
        return result.preflight_status
    gates = "; ".join(
        f"{gate.get('name', 'gate')}:{gate.get('status', 'unknown')}"
        for gate in result.preflight_gates
    )
    return f"{result.preflight_status} ({gates})"


def _model_cost_summary(result: IssueCorpusPublicRepairAttemptResult) -> str:
    if result.model_call_count is None and result.estimated_model_cost_usd is None:
        return "n/a"
    parts: list[str] = []
    if result.model_call_count is not None:
        parts.append(f"{result.model_call_count} calls")
    if result.model_total_tokens is not None:
        parts.append(f"{result.model_total_tokens} tokens")
    if result.estimated_model_cost_usd is not None:
        parts.append(f"${result.estimated_model_cost_usd:.6f}")
    return ", ".join(parts) if parts else "n/a"


def _format_optional_cost(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.6f}"


__all__ = [
    "render_public_issue_repair_attempt_report",
    "render_public_issue_repair_readiness_report",
]
