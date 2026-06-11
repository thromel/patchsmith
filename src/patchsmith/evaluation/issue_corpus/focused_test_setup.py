"""Focused public issue setup readiness and execution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestSetupCommandResult,
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
)
from patchsmith.security import CommandPolicy


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


def check_focused_test_setup_record(
    *,
    record: dict[str, Any],
    docker_smoke_status: str,
) -> IssueCorpusFocusedTestSetupReadinessResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    setup_status = _optional_string(record.get("status")) or "unknown"
    repo_path = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if not repo_exists:
            errors.append(f"repository snapshot is not available: {repo_path}")
            next_actions.append("rerun public issue context preview or materialization")
    else:
        errors.append("setup plan is missing repo_path")
        next_actions.append("regenerate focused diagnosis and setup plan from run results")

    if setup_status == "manual_review":
        errors.append("setup plan requires manual review before execution")
    elif setup_status == "ready":
        if setup_commands:
            warnings.append("ready setup task unexpectedly includes setup commands")
    elif setup_status != "planned":
        warnings.append(f"setup plan status is {setup_status}")

    if setup_status == "planned" and not setup_commands:
        errors.append("planned setup task has no setup commands")
    if setup_status == "planned" and not validation_command:
        errors.append("planned setup task has no validation command")

    if sandbox_required and docker_smoke_status != "passed":
        errors.append(f"Docker sandbox smoke is {docker_smoke_status}")
        next_actions.append("start Docker, build the smoke image, and rerun docker-smoke")
    if requires_network:
        warnings.append("setup requires network access; use a controlled disposable build step")
        next_actions.append("review network access and dependency trust before setup execution")
    if sandbox_required:
        next_actions.append("execute setup only inside a disposable sandbox with no host secrets")

    status = "blocked" if errors else "warning" if warnings else "ready"
    if not next_actions and status == "ready":
        next_actions.append("run setup commands in the approved sandbox, then rerun validation")
    return IssueCorpusFocusedTestSetupReadinessResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        setup_profile=setup_profile,
        repo_path=repo_path,
        repo_exists=repo_exists,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        docker_smoke_status=docker_smoke_status,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def execute_focused_test_setup_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any | None,
    policy: CommandPolicy,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
    dry_run: bool,
    allow_warnings: bool,
    allow_dependency_installs: bool,
) -> IssueCorpusFocusedTestSetupExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    readiness_status = _optional_string(record.get("status")) or "unknown"
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors = _string_list(record.get("errors"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    command_results: list[IssueCorpusFocusedTestSetupCommandResult] = []

    workspace: Path | None = None
    if readiness_status == "blocked":
        errors.append("setup readiness is blocked")
    elif readiness_status == "warning" and not allow_warnings:
        errors.append("setup readiness is warning and --allow-warnings was not set")
    elif readiness_status not in {"ready", "warning"}:
        warnings.append(f"setup readiness status is {readiness_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("setup readiness record has no repo_path")

    if sandbox_required and sandbox_mode != "docker":
        warnings.append("setup requested Docker isolation but a non-Docker sandbox was selected")
    if requires_network and sandbox_mode == "docker":
        warnings.append(
            f"setup requires network access; Docker sandbox network is {sandbox_network}"
        )
        if not dry_run and sandbox_network == "none":
            errors.append("setup requires network but Docker sandbox network is none")

    if not setup_commands:
        status = "blocked" if errors else "skipped"
        if status == "skipped":
            next_actions.append("no setup commands were required; rerun focused validation")
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status=status,
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(next_actions),
        )

    if workspace is not None:
        for command in setup_commands:
            decision = policy.evaluate(command, workspace=workspace)
            command_results.append(
                IssueCorpusFocusedTestSetupCommandResult(
                    command=command,
                    status="dry_run" if decision.allowed else "policy_blocked",
                    exit_code=None,
                    timed_out=False,
                    duration_ms=0,
                    policy_allowed=decision.allowed,
                    policy_reason=decision.reason,
                    stdout_path=None,
                    stderr_path=None,
                )
            )
            if not decision.allowed:
                errors.append(f"setup command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "resolve setup-readiness and command-policy blockers before execution",
                ]
            ),
        )

    if dry_run:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute after reviewing dry-run evidence"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    command_results = []
    status = "passed"
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    for index, command in enumerate(setup_commands, start=1):
        command_result = runner.run(
            command=command,
            workspace=workspace,
            timeout_seconds=timeout_seconds,
        )
        command_dir = run_dir / f"command_{index:02d}"
        command_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = command_dir / "stdout.txt"
        stderr_path = command_dir / "stderr.txt"
        stdout_path.write_text(command_result.stdout, encoding="utf-8")
        stderr_path.write_text(command_result.stderr, encoding="utf-8")
        if not command_result.policy_decision.allowed:
            command_status = "policy_blocked"
            status = "blocked"
            errors.append(
                f"setup command rejected by policy: {command_result.policy_decision.reason}"
            )
        elif command_result.timed_out:
            command_status = "timed_out"
            status = "timed_out"
            warnings.append(f"setup command timed out after {timeout_seconds}s")
        elif command_result.exit_code == 0:
            command_status = "passed"
        else:
            command_status = "failed"
            status = "failed"
            warnings.append(f"setup command exited {command_result.exit_code}")
        command_results.append(
            IssueCorpusFocusedTestSetupCommandResult(
                command=command,
                status=command_status,
                exit_code=command_result.exit_code,
                timed_out=command_result.timed_out,
                duration_ms=command_result.duration_ms,
                policy_allowed=command_result.policy_decision.allowed,
                policy_reason=command_result.policy_decision.reason,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )
        )
        if command_status != "passed":
            break

    return IssueCorpusFocusedTestSetupExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        setup_profile=setup_profile,
        repo_path=repo_path_value,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        allow_dependency_installs=allow_dependency_installs,
        command_results=command_results,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(
            [*next_actions, "rerun focused validation command after successful setup"]
        ),
    )
