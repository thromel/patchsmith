"""Focused public issue setup readiness checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation_models import IssueCorpusFocusedTestSetupReadinessResult


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


__all__ = ["check_focused_test_setup_record"]
