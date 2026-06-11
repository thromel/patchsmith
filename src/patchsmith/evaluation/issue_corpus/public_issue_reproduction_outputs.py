"""Output writers for public issue reproduction workflows."""

from __future__ import annotations

import csv
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
)
from patchsmith.public_issue_reports import (
    render_public_issue_failure_signal_discovery_report,
    render_public_issue_reproduction_execution_report,
)


def write_public_issue_failure_signal_discovery_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_failure_signal_discovery_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_failure_signal_discovery_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_failure_signal_discovery_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "candidate_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "candidate_failure_signals": ";".join(result.candidate_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_failure_signal_discovery_report.md").write_text(
        render_public_issue_failure_signal_discovery_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def write_public_issue_reproduction_execution_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_execution_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_execution_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_execution_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "expected_failure_signals",
                "manual_spec_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "matched_failure_signals",
                "missing_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "matched_failure_signals": ";".join(result.matched_failure_signals),
                    "missing_failure_signals": ";".join(result.missing_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_execution_report.md").write_text(
        render_public_issue_reproduction_execution_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )
