"""Output writers for focused public issue test workflows."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestDiagnosisResult,
    IssueCorpusFocusedTestDiagnosisSummary,
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
)
from patchsmith.evaluation_reports import (
    render_focused_test_diagnosis_report,
    render_focused_test_setup_execution_report,
    render_focused_test_setup_readiness_report,
    render_materialized_issue_focused_test_plan_report,
)


def write_materialized_issue_focused_test_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
    summary: IssueCorpusFocusedTestPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_plan_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_plan_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "focused_test_plan_results.csv").open(
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
                "focused_files",
                "command",
                "policy_allowed",
                "policy_reason",
                "fallback_command",
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
                    "focused_files": ";".join(result.focused_files),
                    "command": result.command,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fallback_command": result.fallback_command,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "focused_test_plan_report.md").write_text(
        render_materialized_issue_focused_test_plan_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_focused_test_diagnosis_outputs(
    *,
    output_dir: Path,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
    summary: IssueCorpusFocusedTestDiagnosisSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_diagnosis_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_diagnosis_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "focused_test_diagnosis_results.csv").open(
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
                "run_status",
                "command",
                "repo_path",
                "focused_files",
                "category",
                "severity",
                "summary",
                "evidence",
                "suggested_next_actions",
                "stdout_path",
                "stderr_path",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "run_status": result.run_status,
                    "command": result.command,
                    "repo_path": result.repo_path,
                    "focused_files": ";".join(result.focused_files),
                    "category": result.category,
                    "severity": result.severity,
                    "summary": result.summary,
                    "evidence": ";".join(result.evidence),
                    "suggested_next_actions": ";".join(result.suggested_next_actions),
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                }
            )
    (output_dir / "focused_test_diagnosis_report.md").write_text(
        render_focused_test_diagnosis_report(
            results_path=results_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_focused_test_setup_readiness_outputs(
    *,
    output_dir: Path,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
    summary: IssueCorpusFocusedTestSetupReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_setup_readiness_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_setup_readiness_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "focused_test_setup_readiness_results.csv").open(
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
                "setup_profile",
                "repo_path",
                "repo_exists",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "docker_smoke_status",
                "errors",
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
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "docker_smoke_status": result.docker_smoke_status,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_readiness_report.md").write_text(
        render_focused_test_setup_readiness_report(
            setup_plan_path=setup_plan_path,
            docker_smoke_path=docker_smoke_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_focused_test_setup_execution_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    summary: IssueCorpusFocusedTestSetupExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_setup_execution_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_setup_execution_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "focused_test_setup_execution_results.csv").open(
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
                "setup_profile",
                "repo_path",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "allow_dependency_installs",
                "command_results",
                "errors",
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
                    "readiness_status": result.readiness_status,
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "allow_dependency_installs": result.allow_dependency_installs,
                    "command_results": json.dumps(
                        [command.to_dict() for command in result.command_results],
                        sort_keys=True,
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_execution_report.md").write_text(
        render_focused_test_setup_execution_report(
            readiness_path=readiness_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )
