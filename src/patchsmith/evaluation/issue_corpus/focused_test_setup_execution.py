"""Focused public issue setup command execution."""

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
)
from patchsmith.security import CommandPolicy


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


__all__ = ["execute_focused_test_setup_record"]
