"""Output writers for materialized public issue task workflows."""

from __future__ import annotations

import csv
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusMaterializedRunReadinessResult,
    IssueCorpusMaterializedRunReadinessSummary,
    IssueCorpusMaterializedTaskResult,
    IssueCorpusMaterializedTaskSummary,
    IssueCorpusMaterializedTaskValidationResult,
    IssueCorpusMaterializedTaskValidationSummary,
)
from patchsmith.evaluation_reports import (
    render_issue_corpus_materialized_task_report,
    render_materialized_issue_run_readiness_report,
    render_materialized_issue_task_validation_report,
)


def write_issue_corpus_materialized_task_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_task_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_task_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "materialized_task_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "error",
                "task_dir",
                "commit_hash",
                "context_provider",
                "context_count",
                "retrieved_files",
                "suggested_test_commands",
                "source_free",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "error": result.error,
                    "task_dir": result.task_dir,
                    "commit_hash": result.commit_hash,
                    "context_provider": result.context_provider,
                    "context_count": result.context_count,
                    "retrieved_files": ";".join(result.retrieved_files),
                    "suggested_test_commands": ";".join(result.suggested_test_commands),
                    "source_free": result.source_free,
                }
            )
    (output_dir / "materialized_task_report.md").write_text(
        render_issue_corpus_materialized_task_report(
            corpus_path=corpus_path,
            context_preview_path=context_preview_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_materialized_issue_task_validation_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_task_validation_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_task_validation_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "materialized_task_validation_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())
    (output_dir / "materialized_task_validation_report.md").write_text(
        render_materialized_issue_task_validation_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_materialized_issue_run_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
    summary: IssueCorpusMaterializedRunReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_run_readiness_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_run_readiness_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "materialized_run_readiness_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "repo_exists",
                "file_count",
                "package_manager",
                "allowed_test_commands",
                "blocked_test_commands",
                "risk_level",
                "risk_notes",
                "errors",
                "warnings",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "repo_exists": result.repo_exists,
                    "file_count": result.file_count,
                    "package_manager": result.package_manager,
                    "allowed_test_commands": result.allowed_test_commands,
                    "blocked_test_commands": result.blocked_test_commands,
                    "risk_level": result.risk_level,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "materialized_run_readiness_report.md").write_text(
        render_materialized_issue_run_readiness_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )
