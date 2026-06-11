"""Public issue repair readiness and attempt output writers."""

from __future__ import annotations

import csv
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
)
from patchsmith.public_issue_reports import (
    render_public_issue_repair_attempt_report,
    render_public_issue_repair_readiness_report,
)


def write_public_issue_repair_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
    summary: IssueCorpusPublicRepairReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_repair_readiness_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_repair_readiness_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_repair_readiness_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "validation_fixture_paths",
                "focused_run_status",
                "diagnosis_category",
                "setup_validation_status",
                "setup_failure_category",
                "reproduction_execution_status",
                "reproduction_stdout_path",
                "reproduction_stderr_path",
                "matched_failure_signals",
                "sandbox_mode",
                "sandbox_network",
                "evidence",
                "blockers",
                "warnings",
                "next_actions",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "validation_fixture_paths": ";".join(result.validation_fixture_paths),
                    "focused_run_status": result.focused_run_status,
                    "diagnosis_category": result.diagnosis_category,
                    "setup_validation_status": result.setup_validation_status,
                    "setup_failure_category": result.setup_failure_category,
                    "reproduction_execution_status": result.reproduction_execution_status,
                    "reproduction_stdout_path": result.reproduction_stdout_path,
                    "reproduction_stderr_path": result.reproduction_stderr_path,
                    "matched_failure_signals": ";".join(result.matched_failure_signals),
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_network": result.sandbox_network,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_readiness_report.md").write_text(
        render_public_issue_repair_readiness_report(
            tasks_dir=tasks_dir,
            focused_run_path=focused_run_path,
            diagnosis_path=diagnosis_path,
            setup_validation_path=setup_validation_path,
            reproduction_execution_path=reproduction_execution_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_public_issue_repair_attempt_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    summary: IssueCorpusPublicRepairAttemptSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_repair_attempt_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_repair_attempt_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_repair_attempt_results.csv").open(
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
                "readiness_status",
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "validation_fixture_paths",
                "reproduction_execution_status",
                "runtime",
                "planner",
                "context_provider",
                "sandbox_mode",
                "sandbox_image",
                "dry_run",
                "run_id",
                "run_status",
                "report_path",
                "trace_path",
                "final_diff_path",
                "test_exit_code",
                "patch_generated",
                "errors",
                "warnings",
                "evidence",
                "next_actions",
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
                    "readiness_status": result.readiness_status,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "validation_fixture_paths": ";".join(result.validation_fixture_paths),
                    "reproduction_execution_status": result.reproduction_execution_status,
                    "runtime": result.runtime,
                    "planner": result.planner,
                    "context_provider": result.context_provider,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "dry_run": result.dry_run,
                    "run_id": result.run_id,
                    "run_status": result.run_status,
                    "report_path": result.report_path,
                    "trace_path": result.trace_path,
                    "final_diff_path": result.final_diff_path,
                    "test_exit_code": result.test_exit_code,
                    "patch_generated": result.patch_generated,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_attempt_report.md").write_text(
        render_public_issue_repair_attempt_report(
            readiness_path=readiness_path,
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )
