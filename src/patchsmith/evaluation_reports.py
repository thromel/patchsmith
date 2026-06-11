from __future__ import annotations

import json
from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusContextPreviewResult,
    IssueCorpusContextPreviewSummary,
    IssueCorpusEntryValidationResult,
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
    IssueCorpusMaterializedRunReadinessResult,
    IssueCorpusMaterializedRunReadinessSummary,
    IssueCorpusMaterializedTaskResult,
    IssueCorpusMaterializedTaskSummary,
    IssueCorpusMaterializedTaskValidationResult,
    IssueCorpusMaterializedTaskValidationSummary,
    IssueCorpusRepoPreflightResult,
    IssueCorpusRepoPreflightSummary,
    IssueCorpusValidationSummary,
    RetrievalEvalResult,
    RetrievalEvalSummary,
    SeededDatasetValidationSummary,
    SeededTaskValidationResult,
)


def render_retrieval_eval_report(
    *,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{len({result.task_id for result in results})}`",
        f"- Lane count: `{len({result.context_provider for result in results})}`",
        "- Model cost: `$0.00` (retrieval-only evaluation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Provider | Attempted | Completed | Top-1 | Top-3 | Top-5 | Related Tests | "
            "Avg Ctx | Avg Src | Avg Test | Avg Tokens | Avg Latency ms | Fallbacks | "
            "Source-Free Violations |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.provider} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.avg_top1_touched_recall:.2f} | "
            f"{summary.avg_top3_touched_recall:.2f} | "
            f"{summary.avg_top5_touched_recall:.2f} | "
            f"{summary.avg_related_test_recall:.2f} | "
            f"{summary.avg_context_count:.1f} | "
            f"{summary.avg_source_context_count:.1f} | "
            f"{summary.avg_test_context_count:.1f} | "
            f"{summary.avg_context_approx_tokens:.0f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.fallback_count} | "
            f"{summary.source_free_violation_count} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Provider | Status | Top-1 | Top-3 | Top-5 | Related Tests | "
                "Ctx | Tokens | Retrieved Files | Error |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.context_provider} | "
            f"{result.status} | "
            f"{result.top1_touched_recall:.2f} | "
            f"{result.top3_touched_recall:.2f} | "
            f"{result.top5_touched_recall:.2f} | "
            f"{result.related_test_recall:.2f} | "
            f"{result.context_count} | "
            f"{result.context_approx_tokens} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures localization evidence only; it does not claim patch success.",
            "- Context providers are compared under the same task and repository snapshot.",
            "- Context token counts are approximate and use packed excerpt characters, not a model-specific tokenizer.",
            "- Source-bearing raw artifacts are kept under the experiment output directory and not copied into this public summary.",
            "",
        ]
    )
    return "\n".join(lines)


def render_seeded_dataset_validation_report(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> str:
    lines = [
        "# Seeded Dataset Validation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        (
            f"- Duplicate task IDs: `{', '.join(summary.duplicate_task_ids)}`"
            if summary.duplicate_task_ids
            else "- Duplicate task IDs: `none`"
        ),
        "",
        "## Results",
        "",
        "| Task | Status | Errors | Warnings | Expected Source | Expected Tests |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_touched_files) or 'none'} | "
            f"{', '.join(result.expected_related_tests) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            (
                "- Dataset validation checks metadata shape, required files, non-empty "
                "issues, and expected paths."
            ),
            (
                "- A valid dataset is required before retrieval or repair eval metrics are "
                "release evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_validation_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusEntryValidationResult],
    summary: IssueCorpusValidationSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Validation Report",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Corpus ID: `{summary.corpus_id or 'unknown'}`",
        f"- Entry count: `{summary.entry_count}`",
        f"- Valid entries: `{summary.valid_entries}`",
        f"- Invalid entries: `{summary.invalid_entries}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Repositories: `{', '.join(summary.repositories) or 'none'}`",
        f"- Languages: `{', '.join(summary.languages) or 'none'}`",
        f"- Task types: `{', '.join(summary.task_types) or 'none'}`",
        f"- Open issues at capture: `{summary.open_issue_count}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Issue | Status | Errors | Warnings | Workflow |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or 'unknown'} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_workflow) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This corpus proves that public issue candidates have been curated and validated.",
            "- It does not prove PatchSmith solved these issues until run artifacts exist for them.",
            "- Use this corpus as the next real-world evaluation lane after seeded-suite gates.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_repo_preflight_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Repository Preflight",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Repository count: `{summary.repository_count}`",
        f"- Reachable repositories: `{summary.reachable_repositories}`",
        f"- Unreachable repositories: `{summary.unreachable_repositories}`",
        f"- Issue count: `{summary.issue_count}`",
        f"- Average reachable latency: `{summary.avg_latency_ms:.1f}ms`",
        "",
        "## Results",
        "",
        "| Repository | Status | Default Branch | HEAD | Issues | Latency ms | Error |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.repository} | "
            f"{result.status} | "
            f"{result.default_branch or 'unknown'} | "
            f"{result.head_sha or 'unknown'} | "
            f"{result.issue_count} | "
            f"{result.latency_ms} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preflight proves repository reachability and records current HEAD metadata.",
            "- It does not clone source or run repair tasks.",
            "- Use this before converting public issue candidates into executable eval tasks.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_context_preview_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    summary: IssueCorpusContextPreviewSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Context Preview",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Completed issues: `{summary.completed_issues}`",
        f"- Failed issues: `{summary.failed_issues}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Average context count: `{summary.avg_context_count:.1f}`",
        f"- Source-free summary: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Files | Contexts | Retrieved Files | Error |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.file_count} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preview proves repository clone/index/retrieval plumbing on public issue candidates.",
            "- Retrieved source excerpts are intentionally omitted from this summary.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_materialized_task_report(
    *,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Materialized Tasks",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Context preview: `{context_preview_path}`",
        f"- Output: `{summary.output_dir}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Materialized tasks: `{summary.materialized_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Contexts | Retrieved Files | Task Dir | Error |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.task_dir or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This materialization creates external-evaluation task manifests and runbooks.",
            "- Manifests intentionally omit source excerpts and issue body scraping.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_task_validation_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> str:
    lines = [
        "# Public Issue Materialized Task Validation",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Issue | Retrieved Files | Errors | Warnings |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            "- This gate validates manifest shape, source-free context summaries, task files, local repository snapshots, and suggested run commands.",
            "- A valid manifest set is external-evaluation setup evidence, not repair-quality evidence.",
            "- Public issue reproduction and repair claims still require normal PatchSmith run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_run_readiness_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
    summary: IssueCorpusMaterializedRunReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Materialized Run Readiness",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Allowed test commands: `{summary.allowed_test_commands}`",
        f"- Blocked test commands: `{summary.blocked_test_commands}`",
        "",
        "## Results",
        "",
        "| Task | Status | Risk | Repository | Files | Allowed Tests | Blocked Tests | Notes |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for result in results:
        notes = [*result.risk_notes, *result.errors, *result.warnings]
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.risk_level} | "
            f"{result.repository or 'unknown'} | "
            f"{result.file_count if result.file_count is not None else 'unknown'} | "
            f"{result.allowed_test_commands} | "
            f"{result.blocked_test_commands} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report checks run readiness without executing public repository tests.",
            "- `warning` means the task is runnable by policy but has cost, dependency, or scope risk.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


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
                path
                for path in [result.stdout_path, result.stderr_path]
                if path is not None
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
        (
            "- Allow dependency installs: "
            f"`{str(summary.allow_dependency_installs).lower()}`"
        ),
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
            result.command_result.status
            if result.command_result is not None
            else "none"
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
