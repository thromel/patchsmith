"""Validation helpers for materialized issue tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import _manifest_object, _manifest_string, _string_list
from patchsmith.evaluation.issue_corpus.materialize_manifest import manifest_is_source_free
from patchsmith.evaluation_models import IssueCorpusMaterializedTaskValidationResult


def validate_materialized_issue_task_dir(
    task_dir: Path,
) -> IssueCorpusMaterializedTaskValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = task_dir / "task_manifest.json"
    issue_path = task_dir / "issue.md"
    runbook_path = task_dir / "RUNBOOK.md"
    manifest: dict[str, Any] = {}

    if not manifest_path.exists():
        errors.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                errors.append("task_manifest.json must contain a JSON object")
            else:
                manifest = parsed
        except json.JSONDecodeError as error:
            errors.append(f"task_manifest.json is invalid JSON: {error.msg}")

    if not issue_path.exists():
        errors.append("missing issue.md")
    elif not issue_path.read_text(encoding="utf-8").strip():
        errors.append("issue.md is empty")
    elif "Claim Boundary" not in issue_path.read_text(encoding="utf-8"):
        warnings.append("issue.md does not include a Claim Boundary section")

    if not runbook_path.exists():
        errors.append("missing RUNBOOK.md")
    elif not runbook_path.read_text(encoding="utf-8").strip():
        errors.append("RUNBOOK.md is empty")
    elif "Suggested Commands" not in runbook_path.read_text(encoding="utf-8"):
        warnings.append("RUNBOOK.md does not include suggested commands")

    task_id = _manifest_string(manifest, "task_id", errors)
    version = manifest.get("task_manifest_version")
    if version != 1:
        errors.append(f"unsupported task_manifest_version: {version}")
    if task_id and task_id != task_dir.name:
        warnings.append(f"task_id does not match directory name: {task_id} != {task_dir.name}")

    issue = _manifest_object(manifest, "issue", errors)
    repository = _manifest_string(issue, "repository", errors, field_name="issue.repository")
    repo_url = _manifest_string(issue, "repo_url", errors, field_name="issue.repo_url")
    issue_url = _manifest_string(issue, "issue_url", errors, field_name="issue.issue_url")
    language = _manifest_string(issue, "language", errors, field_name="issue.language")
    expected_workflow = _string_list(issue.get("expected_workflow"))

    if repository and "/" not in repository:
        errors.append(f"issue.repository must use owner/name format: {repository}")
    if repo_url and not repo_url.startswith("https://github.com/") and not Path(repo_url).exists():
        errors.append(f"issue.repo_url must be a GitHub URL or local fixture path: {repo_url}")
    if issue_url and not issue_url.startswith("https://github.com/"):
        errors.append(f"issue.issue_url must be a GitHub URL: {issue_url}")
    if repository and issue_url and repository.count("/") == 1:
        expected_prefix = f"https://github.com/{repository}/issues/"
        if not issue_url.startswith(expected_prefix) and not repository.startswith("local/"):
            errors.append(f"issue.issue_url does not match repository: {issue_url}")
    if language and language.lower() != "python":
        warnings.append(f"non-python materialized task language: {language}")
    if not expected_workflow:
        warnings.append("issue.expected_workflow is empty")

    snapshot = _manifest_object(manifest, "repository_snapshot", errors)
    repo_path_value = _manifest_string(
        snapshot, "repo_path", errors, field_name="repository_snapshot.repo_path"
    )
    commit_hash = _manifest_string(
        snapshot, "commit_hash", errors, field_name="repository_snapshot.commit_hash"
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    file_count = snapshot.get("file_count")
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if not repo_path.exists():
            errors.append(f"repository_snapshot.repo_path does not exist: {repo_path_value}")
        elif not repo_path.is_dir():
            errors.append(f"repository_snapshot.repo_path is not a directory: {repo_path_value}")
    if commit_hash and len(commit_hash) < 8:
        warnings.append("repository_snapshot.commit_hash is unusually short")
    if not isinstance(file_count, int) or file_count <= 0:
        errors.append("repository_snapshot.file_count must be a positive integer")
    if not test_commands:
        errors.append("repository_snapshot.test_commands must contain at least one command")
    elif not any("pytest" in command for command in test_commands):
        warnings.append("repository_snapshot.test_commands does not include pytest")

    retrieval = _manifest_object(manifest, "retrieval_preview", errors)
    context_provider = _manifest_string(
        retrieval, "context_provider", errors, field_name="retrieval_preview.context_provider"
    )
    context_count = retrieval.get("context_count")
    retrieved_files = _string_list(retrieval.get("retrieved_files"))
    top_contexts = retrieval.get("top_contexts")
    if context_provider not in {"native", "native_hybrid", "native_graph"}:
        errors.append(f"unsupported retrieval_preview.context_provider: {context_provider}")
    if not isinstance(context_count, int) or context_count <= 0:
        errors.append("retrieval_preview.context_count must be a positive integer")
    if not retrieved_files:
        errors.append("retrieval_preview.retrieved_files must not be empty")
    if not isinstance(top_contexts, list):
        errors.append("retrieval_preview.top_contexts must be a list")
    elif any(isinstance(context, dict) and "excerpt" in context for context in top_contexts):
        errors.append("retrieval_preview.top_contexts must be source-free")

    suggested_commands = _string_list(manifest.get("suggested_commands"))
    if not suggested_commands:
        errors.append("suggested_commands must contain at least one command")
    elif not any("patchsmith.cli run" in command for command in suggested_commands):
        errors.append("suggested_commands must include a patchsmith.cli run command")
    claim_boundary = _string_list(manifest.get("claim_boundary"))
    if not claim_boundary:
        errors.append("claim_boundary must not be empty")

    source_free = manifest_is_source_free(manifest)
    if manifest.get("source_free") is not True:
        errors.append("source_free must be true")
    if not source_free:
        errors.append("manifest contains non-source-free excerpt fields")

    return IssueCorpusMaterializedTaskValidationResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        manifest_path=str(manifest_path) if manifest_path.exists() else None,
        issue_path=str(issue_path) if issue_path.exists() else None,
        runbook_path=str(runbook_path) if runbook_path.exists() else None,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        retrieved_files=retrieved_files,
        suggested_commands=suggested_commands,
        source_free=source_free,
    )


def duplicate_materialized_task_ids(
    results: list[IssueCorpusMaterializedTaskValidationResult],
) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


def with_materialized_validation_error(
    result: IssueCorpusMaterializedTaskValidationResult,
    error: str,
) -> IssueCorpusMaterializedTaskValidationResult:
    return IssueCorpusMaterializedTaskValidationResult(
        task_id=result.task_id,
        task_dir=result.task_dir,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        manifest_path=result.manifest_path,
        issue_path=result.issue_path,
        runbook_path=result.runbook_path,
        repository=result.repository,
        issue_url=result.issue_url,
        repo_path=result.repo_path,
        retrieved_files=result.retrieved_files,
        suggested_commands=result.suggested_commands,
        source_free=result.source_free,
    )
