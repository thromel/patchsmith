"""Run-readiness checks for materialized issue tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.evaluation._helpers import _string_list
from patchsmith.evaluation_models import IssueCorpusMaterializedRunReadinessResult
from patchsmith.security import CommandPolicy


def check_materialized_issue_task_run_readiness(
    *,
    task_dir: Path,
    policy: CommandPolicy,
) -> IssueCorpusMaterializedRunReadinessResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.exists():
        errors.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                errors.append("task_manifest.json must contain a JSON object")
        except json.JSONDecodeError as error:
            errors.append(f"task_manifest.json is invalid JSON: {error.msg}")

    task_id = manifest.get("task_id") if isinstance(manifest.get("task_id"), str) else None
    issue = dict_or_empty(manifest.get("issue"))
    snapshot = dict_or_empty(manifest.get("repository_snapshot"))
    repository = issue.get("repository") if isinstance(issue.get("repository"), str) else None
    issue_url = issue.get("issue_url") if isinstance(issue.get("issue_url"), str) else None
    repo_path_value = (
        snapshot.get("repo_path") if isinstance(snapshot.get("repo_path"), str) else None
    )
    package_manager = (
        snapshot.get("package_manager")
        if isinstance(snapshot.get("package_manager"), str)
        else None
    )
    file_count = snapshot.get("file_count") if isinstance(snapshot.get("file_count"), int) else None
    test_commands = _string_list(snapshot.get("test_commands"))
    suggested_commands = _string_list(manifest.get("suggested_commands"))
    repo_exists = False
    workspace = Path.cwd()
    if repo_path_value:
        repo_path = Path(repo_path_value)
        repo_exists = repo_path.exists() and repo_path.is_dir()
        if repo_exists:
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("repository_snapshot.repo_path is missing")

    if not test_commands:
        errors.append("no test commands available")
    command_checks: list[dict[str, Any]] = []
    for command in test_commands:
        decision = policy.evaluate(command, workspace=workspace)
        command_checks.append(
            {
                "command": command,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "tokens": list(decision.tokens),
            }
        )
        if not decision.allowed:
            errors.append(f"test command rejected by policy: {command} ({decision.reason})")

    if not suggested_commands:
        warnings.append("no suggested patchsmith run command recorded")

    risk_level, risk_notes = materialized_run_risk(
        file_count=file_count,
        test_commands=test_commands,
        package_manager=package_manager,
    )
    allowed_count = sum(1 for check in command_checks if check["allowed"])
    blocked_count = sum(1 for check in command_checks if not check["allowed"])
    status = "blocked" if errors else "warning" if warnings or risk_notes else "ready"
    return IssueCorpusMaterializedRunReadinessResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status=status,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        repo_exists=repo_exists,
        file_count=file_count,
        package_manager=package_manager,
        test_commands=test_commands,
        allowed_test_commands=allowed_count,
        blocked_test_commands=blocked_count,
        command_checks=command_checks,
        suggested_commands=suggested_commands,
        risk_level=risk_level,
        risk_notes=risk_notes,
        errors=errors,
        warnings=warnings,
    )


def materialized_run_risk(
    *,
    file_count: int | None,
    test_commands: list[str],
    package_manager: str | None,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    level = "low"
    if file_count is None:
        notes.append("repository size is unknown")
        level = "medium"
    elif file_count >= 500:
        notes.append(f"large repository snapshot with {file_count} indexed files")
        level = "high"
    elif file_count >= 100:
        notes.append(f"medium repository snapshot with {file_count} indexed files")
        level = "medium"

    full_suite_commands = [
        command
        for command in test_commands
        if command.strip() in {"pytest", "python -m pytest", "python3 -m pytest"}
    ]
    if full_suite_commands:
        notes.append("suggested test command runs the full pytest suite")
        if level == "low":
            level = "medium"
    if package_manager is None:
        notes.append("package manager detection is unavailable")
        if level == "low":
            level = "medium"
    return level, notes
