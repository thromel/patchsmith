"""Focused public issue setup readiness and execution summaries."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
)


def summarize_focused_test_setup_readiness(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    docker_smoke_status: str,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
) -> IssueCorpusFocusedTestSetupReadinessSummary:
    return IssueCorpusFocusedTestSetupReadinessSummary(
        setup_plan_path=str(setup_plan_path),
        docker_smoke_path=str(docker_smoke_path),
        docker_smoke_status=docker_smoke_status,
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        network_required_tasks=sum(1 for result in results if result.requires_network),
        sandbox_required_tasks=sum(1 for result in results if result.sandbox_required),
    )


def summarize_focused_test_setup_execution(
    *,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    dry_run: bool,
    allow_warnings: bool,
    allow_dependency_installs: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestSetupExecutionSummary:
    return IssueCorpusFocusedTestSetupExecutionSummary(
        readiness_path=str(readiness_path),
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        allow_dependency_installs=allow_dependency_installs,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        completed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        skipped_tasks=sum(1 for result in results if result.status == "skipped"),
        command_count=sum(len(result.setup_commands) for result in results),
        attempted_commands=sum(
            1
            for result in results
            for command_result in result.command_results
            if command_result.status in {"passed", "failed", "timed_out"}
        ),
    )


__all__ = [
    "summarize_focused_test_setup_execution",
    "summarize_focused_test_setup_readiness",
]
