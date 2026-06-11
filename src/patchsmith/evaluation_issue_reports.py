from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusContextPreviewResult,
    IssueCorpusContextPreviewSummary,
    IssueCorpusEntryValidationResult,
    IssueCorpusMaterializedRunReadinessResult,
    IssueCorpusMaterializedRunReadinessSummary,
    IssueCorpusMaterializedTaskResult,
    IssueCorpusMaterializedTaskSummary,
    IssueCorpusMaterializedTaskValidationResult,
    IssueCorpusMaterializedTaskValidationSummary,
    IssueCorpusRepoPreflightResult,
    IssueCorpusRepoPreflightSummary,
    IssueCorpusValidationSummary,
)


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
