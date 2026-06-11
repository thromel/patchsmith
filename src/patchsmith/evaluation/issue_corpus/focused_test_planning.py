"""Planning helpers for materialized focused tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.evaluation._helpers import _string_list
from patchsmith.evaluation.issue_corpus.materialize import _is_materialized_test_candidate_path
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
)
from patchsmith.security import CommandPolicy


def summarize_materialized_issue_focused_test_plan(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
) -> IssueCorpusFocusedTestPlanSummary:
    return IssueCorpusFocusedTestPlanSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        fallback_tasks=sum(1 for result in results if result.status == "fallback"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
    )


def plan_materialized_issue_focused_test(
    *,
    task_dir: Path,
    policy: CommandPolicy,
    max_paths: int,
) -> IssueCorpusFocusedTestPlanResult:
    errors: list[str] = []
    warnings: list[str] = []
    risk_notes: list[str] = []
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
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    repository = issue.get("repository") if isinstance(issue.get("repository"), str) else None
    issue_url = issue.get("issue_url") if isinstance(issue.get("issue_url"), str) else None
    repo_path_value = (
        snapshot.get("repo_path") if isinstance(snapshot.get("repo_path"), str) else None
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    fallback_command = test_commands[0] if test_commands else None
    retrieved_files = _string_list(retrieval.get("retrieved_files"))
    focused_files = [
        path for path in retrieved_files if _is_materialized_test_candidate_path(path)
    ][: max(max_paths, 0)]

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

    if focused_files:
        missing_focused = [
            path for path in focused_files if repo_exists and not (workspace / path).is_file()
        ]
        if missing_focused:
            errors.append(f"focused test files do not exist: {', '.join(missing_focused)}")
        command = "python3 -m pytest " + " ".join(focused_files)
        status = "planned"
    elif fallback_command:
        command = fallback_command
        status = "fallback"
        warnings.append("no retrieved test-like file was available; using fallback test command")
    else:
        command = None
        status = "blocked"
        errors.append("no focused or fallback test command available")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"focused test command rejected by policy: {decision.reason}")

    if focused_files:
        risk_notes.append("focused command is derived from retrieved test-like files")
    if fallback_command and command == fallback_command:
        risk_notes.append("fallback command may run a broader test scope")
    if errors:
        status = "blocked"
    return IssueCorpusFocusedTestPlanResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status=status,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        focused_files=focused_files,
        command=command,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        fallback_command=fallback_command,
        risk_notes=risk_notes,
        errors=errors,
        warnings=warnings,
    )
