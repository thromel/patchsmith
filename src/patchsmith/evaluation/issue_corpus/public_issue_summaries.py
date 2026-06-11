from __future__ import annotations

from datetime import UTC, datetime
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


def summarize_public_issue_reproduction_plan(
    *,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> IssueCorpusPublicReproductionPlanSummary:
    return IssueCorpusPublicReproductionPlanSummary(
        generated_at=_generated_at(),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(1 for result in results if result.manual_spec_required),
        command_count=sum(1 for result in results if result.reproduction_command),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
    )


def summarize_public_issue_reproduction_spec_validation(
    *,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    spec_count: int,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
) -> IssueCorpusPublicReproductionSpecValidationSummary:
    return IssueCorpusPublicReproductionSpecValidationSummary(
        generated_at=_generated_at(),
        specs_path=str(specs_path),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        spec_count=spec_count,
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        missing_spec_tasks=sum(1 for result in results if not result.spec_present),
        empty_signal_tasks=sum(1 for result in results if not result.expected_failure_signals),
        policy_blocked_tasks=sum(
            1 for result in results if result.reproduction_command and not result.policy_allowed
        ),
        extra_spec_tasks=sum(
            1
            for result in results
            if "reproduction spec task_id has no materialized task" in result.errors
        ),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
        unsafe_fixture_tasks=sum(
            1 for result in results if any("fixture_files" in error for error in result.errors)
        ),
    )


def summarize_public_issue_failure_signal_discovery(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicFailureSignalDiscoverySummary:
    return IssueCorpusPublicFailureSignalDiscoverySummary(
        generated_at=_generated_at(),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"observed_failure", "passed", "timed_out", "failed"}
        ),
        observed_failure_tasks=sum(1 for result in results if result.status == "observed_failure"),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        candidate_signal_tasks=sum(1 for result in results if result.candidate_failure_signals),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def summarize_public_issue_reproduction_execution(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicReproductionExecutionSummary:
    return IssueCorpusPublicReproductionExecutionSummary(
        generated_at=_generated_at(),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"reproduced", "not_reproduced", "failed", "timed_out"}
        ),
        reproduced_tasks=sum(1 for result in results if result.status == "reproduced"),
        not_reproduced_tasks=sum(1 for result in results if result.status == "not_reproduced"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(1 for result in results if result.manual_spec_required),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def summarize_public_issue_repair_readiness(
    *,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
) -> IssueCorpusPublicRepairReadinessSummary:
    return IssueCorpusPublicRepairReadinessSummary(
        generated_at=_generated_at(),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        focused_run_path=str(focused_run_path),
        diagnosis_path=str(diagnosis_path),
        setup_validation_path=str(setup_validation_path),
        reproduction_execution_path=(
            str(reproduction_execution_path) if reproduction_execution_path is not None else None
        ),
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        repair_command_tasks=sum(1 for result in results if result.repair_command),
        passed_focused_tasks=sum(1 for result in results if result.focused_run_status == "passed"),
        passed_setup_validation_tasks=sum(
            1 for result in results if result.setup_validation_status == "passed"
        ),
        reproduced_tasks=sum(
            1 for result in results if result.reproduction_execution_status == "reproduced"
        ),
        missing_reproduction_tasks=sum(
            1 for result in results if result.reproduction_execution_status != "reproduced"
        ),
    )


def summarize_public_issue_repair_attempts(
    *,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    dry_run: bool,
    allow_warnings: bool,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    max_retries: int,
) -> IssueCorpusPublicRepairAttemptSummary:
    return IssueCorpusPublicRepairAttemptSummary(
        generated_at=_generated_at(),
        readiness_path=str(readiness_path),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        max_retries=max_retries,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(1 for result in results if result.status in {"validated", "failed"}),
        validated_tasks=sum(1 for result in results if result.status == "validated"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        reproduced_input_tasks=sum(
            1 for result in results if result.reproduction_execution_status == "reproduced"
        ),
    )


def _generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
