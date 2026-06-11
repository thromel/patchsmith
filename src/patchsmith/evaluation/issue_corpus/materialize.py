"""Evaluation issue corpus materialize (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty, write_json
from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _manifest_object,
    _manifest_string,
    _optional_string,
    _remove_artifact_dir,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.preview import _source_free_preview_contexts
from patchsmith.evaluation_models import (
    IssueCorpusMaterializedRunReadinessResult,
    IssueCorpusMaterializedRunReadinessSummary,
    IssueCorpusMaterializedTaskResult,
    IssueCorpusMaterializedTaskSummary,
    IssueCorpusMaterializedTaskValidationResult,
    IssueCorpusMaterializedTaskValidationSummary,
)
from patchsmith.evaluation_reports import (
    render_issue_corpus_materialized_task_report,
    render_materialized_issue_run_readiness_report,
    render_materialized_issue_task_validation_report,
)
from patchsmith.security import CommandPolicy


def materialize_issue_corpus_tasks(
    *,
    corpus_path: Path,
    output_dir: Path,
    context_preview_path: Path | None = None,
    max_issues: int | None = None,
) -> tuple[
    list[IssueCorpusMaterializedTaskResult],
    IssueCorpusMaterializedTaskSummary,
]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    context_preview_path = context_preview_path or output_dir / "context_preview_results.json"
    if not context_preview_path.exists():
        raise FileNotFoundError(f"context preview results do not exist: {context_preview_path}")

    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    issues = [issue for issue in payload["issues"] if isinstance(issue, dict)]
    if max_issues is not None:
        issues = issues[:max_issues]

    preview_payload = json.loads(context_preview_path.read_text(encoding="utf-8"))
    if not isinstance(preview_payload, list):
        raise ValueError("context preview results must contain a JSON list")
    previews_by_task = {
        str(item.get("task_id")): item
        for item in preview_payload
        if isinstance(item, dict) and item.get("task_id")
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = output_dir / "materialized_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results: list[IssueCorpusMaterializedTaskResult] = []
    corpus_id = payload.get("corpus_id") if isinstance(payload.get("corpus_id"), str) else None

    for issue in issues:
        task_id = str(issue.get("task_id", "unknown"))
        repository = str(issue.get("repository", "unknown"))
        issue_url = str(issue.get("issue_url", ""))
        repo_url = str(issue.get("repo_url", ""))
        task_dir = tasks_dir / _safe_artifact_name(task_id)
        try:
            preview = previews_by_task.get(task_id)
            if not isinstance(preview, dict) or preview.get("status") != "completed":
                raise ValueError(f"missing completed context preview for task: {task_id}")
            if task_dir.exists():
                _remove_artifact_dir(root=output_dir, target=task_dir)
            task_dir.mkdir(parents=True)
            issue_path = task_dir / "issue.md"
            manifest_path = task_dir / "task_manifest.json"
            runbook_path = task_dir / "RUNBOOK.md"
            manifest = _issue_corpus_task_manifest(
                issue=issue,
                preview=preview,
                corpus_id=corpus_id,
                task_dir=task_dir,
                issue_path=issue_path,
            )
            issue_path.write_text(
                _render_materialized_issue(issue=issue, preview=preview),
                encoding="utf-8",
            )
            write_json(manifest_path, manifest, trailing_newline=True)
            runbook_path.write_text(
                _render_materialized_task_runbook(manifest=manifest),
                encoding="utf-8",
            )
            test_commands = _materialized_test_commands(preview)
            source_free = _manifest_is_source_free(manifest)
            results.append(
                IssueCorpusMaterializedTaskResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="materialized",
                    error=None,
                    task_dir=str(task_dir),
                    manifest_path=str(manifest_path),
                    issue_path=str(issue_path),
                    runbook_path=str(runbook_path),
                    repo_url=repo_url,
                    commit_hash=_optional_string(preview.get("commit_hash")),
                    context_provider=_optional_string(preview.get("context_provider")),
                    context_count=int(preview.get("context_count") or 0),
                    retrieved_files=_string_list(preview.get("retrieved_files")),
                    suggested_test_commands=test_commands,
                    source_free=source_free,
                )
            )
        except Exception as error:
            results.append(
                IssueCorpusMaterializedTaskResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="failed",
                    error=str(error),
                    task_dir=str(task_dir),
                    manifest_path=None,
                    issue_path=None,
                    runbook_path=None,
                    repo_url=repo_url,
                    commit_hash=None,
                    context_provider=None,
                    context_count=0,
                    retrieved_files=[],
                    suggested_test_commands=[],
                    source_free=False,
                )
            )

    summary = summarize_issue_corpus_materialized_tasks(
        corpus_path=corpus_path,
        context_preview_path=context_preview_path,
        output_dir=output_dir,
        results=results,
    )
    write_issue_corpus_materialized_task_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        context_preview_path=context_preview_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_materialized_tasks(
    *,
    corpus_path: Path,
    context_preview_path: Path,
    output_dir: Path,
    results: list[IssueCorpusMaterializedTaskResult],
) -> IssueCorpusMaterializedTaskSummary:
    materialized = [result for result in results if result.status == "materialized"]
    return IssueCorpusMaterializedTaskSummary(
        corpus_path=str(corpus_path),
        context_preview_path=str(context_preview_path),
        output_dir=str(output_dir),
        attempted_issues=len(results),
        materialized_tasks=len(materialized),
        failed_tasks=sum(1 for result in results if result.status != "materialized"),
        repository_count=len({result.repository for result in results}),
        source_free=all(
            result.status == "materialized" and result.source_free for result in results
        ),
    )


def write_issue_corpus_materialized_task_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_task_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_task_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "materialized_task_results.csv").open(
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
                "error",
                "task_dir",
                "commit_hash",
                "context_provider",
                "context_count",
                "retrieved_files",
                "suggested_test_commands",
                "source_free",
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
                    "error": result.error,
                    "task_dir": result.task_dir,
                    "commit_hash": result.commit_hash,
                    "context_provider": result.context_provider,
                    "context_count": result.context_count,
                    "retrieved_files": ";".join(result.retrieved_files),
                    "suggested_test_commands": ";".join(result.suggested_test_commands),
                    "source_free": result.source_free,
                }
            )
    (output_dir / "materialized_task_report.md").write_text(
        render_issue_corpus_materialized_task_report(
            corpus_path=corpus_path,
            context_preview_path=context_preview_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def validate_materialized_issue_tasks(
    *,
    tasks_dir: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusMaterializedTaskValidationResult],
    IssueCorpusMaterializedTaskValidationSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [_validate_materialized_issue_task_dir(task_dir) for task_dir in task_dirs]
    duplicate_task_ids = _duplicate_materialized_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_materialized_validation_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]
    summary = summarize_materialized_issue_task_validation(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_task_validation_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_task_validation(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
) -> IssueCorpusMaterializedTaskValidationSummary:
    return IssueCorpusMaterializedTaskValidationSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        valid_tasks=sum(1 for result in results if result.status == "valid"),
        invalid_tasks=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        source_free=all(result.source_free for result in results),
    )


def write_materialized_issue_task_validation_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_task_validation_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_task_validation_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "materialized_task_validation_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())
    (output_dir / "materialized_task_validation_report.md").write_text(
        render_materialized_issue_task_validation_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def check_materialized_issue_run_readiness(
    *,
    tasks_dir: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusMaterializedRunReadinessResult],
    IssueCorpusMaterializedRunReadinessSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _check_materialized_issue_task_run_readiness(task_dir=task_dir, policy=policy)
        for task_dir in task_dirs
    ]
    summary = summarize_materialized_issue_run_readiness(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_run_readiness_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_run_readiness(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
) -> IssueCorpusMaterializedRunReadinessSummary:
    return IssueCorpusMaterializedRunReadinessSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        allowed_test_commands=sum(result.allowed_test_commands for result in results),
        blocked_test_commands=sum(result.blocked_test_commands for result in results),
    )


def write_materialized_issue_run_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
    summary: IssueCorpusMaterializedRunReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "materialized_run_readiness_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "materialized_run_readiness_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "materialized_run_readiness_results.csv").open(
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
                "repo_exists",
                "file_count",
                "package_manager",
                "allowed_test_commands",
                "blocked_test_commands",
                "risk_level",
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
                    "repo_exists": result.repo_exists,
                    "file_count": result.file_count,
                    "package_manager": result.package_manager,
                    "allowed_test_commands": result.allowed_test_commands,
                    "blocked_test_commands": result.blocked_test_commands,
                    "risk_level": result.risk_level,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "materialized_run_readiness_report.md").write_text(
        render_materialized_issue_run_readiness_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _validate_materialized_issue_task_dir(
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

    source_free = _manifest_is_source_free(manifest)
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


def _check_materialized_issue_task_run_readiness(
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

    risk_level, risk_notes = _materialized_run_risk(
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


def _issue_corpus_task_manifest(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
    corpus_id: str | None,
    task_dir: Path,
    issue_path: Path,
) -> dict[str, Any]:
    test_commands = _materialized_test_commands(preview)
    top_contexts = _source_free_preview_contexts(preview.get("top_contexts"))
    repo_ref = _optional_string(preview.get("repo_path")) or str(issue.get("repo_url", ""))
    manifest = {
        "task_manifest_version": 1,
        "task_id": str(issue.get("task_id", "unknown")),
        "source_corpus": corpus_id,
        "task_dir": str(task_dir),
        "issue_file": str(issue_path),
        "issue": {
            "source": issue.get("source"),
            "repository": issue.get("repository"),
            "repo_url": issue.get("repo_url"),
            "issue_url": issue.get("issue_url"),
            "issue_number": issue.get("issue_number"),
            "title": issue.get("title"),
            "language": issue.get("language"),
            "task_type": issue.get("task_type"),
            "state_at_capture": issue.get("state_at_capture"),
            "captured_at": issue.get("captured_at"),
            "selection_reason": issue.get("selection_reason"),
            "expected_workflow": _string_list(issue.get("expected_workflow")),
        },
        "repository_snapshot": {
            "repo_path": preview.get("repo_path"),
            "commit_hash": preview.get("commit_hash"),
            "branch": preview.get("branch"),
            "file_count": preview.get("file_count"),
            "language_summary": preview.get("language_summary") or {},
            "package_manager": preview.get("package_manager"),
            "test_commands": test_commands,
        },
        "retrieval_preview": {
            "context_provider": preview.get("context_provider"),
            "context_count": preview.get("context_count"),
            "retrieved_files": _string_list(preview.get("retrieved_files")),
            "top_contexts": top_contexts,
        },
        "suggested_commands": [
            (
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                f'--repo "{repo_ref}" '
                f'--issue-file "{issue_path}" '
                "--runtime langgraph "
                "--planner fake_model "
                "--context-provider native_hybrid "
                f'--test-command "{test_commands[0]}" '
                "--json"
            )
        ],
        "claim_boundary": [
            "This manifest prepares an external evaluation task.",
            "It does not prove issue reproduction, patch generation, or test success.",
            "It intentionally omits source excerpts and scraped issue body text.",
        ],
        "source_free": True,
    }
    manifest["source_free"] = _manifest_is_source_free(manifest)
    return manifest


def _render_materialized_issue(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
) -> str:
    workflow = _string_list(issue.get("expected_workflow"))
    retrieved_files = _string_list(preview.get("retrieved_files"))
    lines = [
        f"# {issue.get('title') or issue.get('task_id') or 'Public Issue Task'}",
        "",
        f"- Task ID: `{issue.get('task_id', 'unknown')}`",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Repository URL: `{issue.get('repo_url', 'unknown')}`",
        f"- Captured state: `{issue.get('state_at_capture', 'unknown')}`",
        f"- Task type: `{issue.get('task_type', 'unknown')}`",
        f"- Context provider: `{preview.get('context_provider', 'unknown')}`",
        f"- Commit: `{preview.get('commit_hash') or 'unknown'}`",
        "",
        "## Expected Workflow",
        "",
    ]
    lines.extend(f"- {item}" for item in workflow)
    lines.extend(
        [
            "",
            "## Retrieved File Hints",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in retrieved_files)
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This file contains curated public issue metadata and retrieved-file hints.",
            "- It intentionally omits source excerpts and scraped issue body text.",
            "- It is not evidence that PatchSmith reproduced or repaired the issue.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_materialized_task_runbook(*, manifest: dict[str, Any]) -> str:
    issue = dict_or_empty(manifest.get("issue"))
    snapshot = dict_or_empty(manifest.get("repository_snapshot"))
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    commands = _string_list(manifest.get("suggested_commands"))
    lines = [
        f"# {manifest.get('task_id', 'Public Issue Task')} Runbook",
        "",
        "## Inputs",
        "",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Local repository snapshot: `{snapshot.get('repo_path') or 'unknown'}`",
        f"- Commit: `{snapshot.get('commit_hash') or 'unknown'}`",
        f"- Context provider: `{retrieval.get('context_provider') or 'unknown'}`",
        f"- Retrieved files: `{', '.join(_string_list(retrieval.get('retrieved_files'))) or 'none'}`",
        "",
        "## Suggested Commands",
        "",
    ]
    for command in commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(
        [
            "## Claim Boundary",
            "",
            "- Run this task only after confirming dependency and sandbox expectations.",
            "- A generated manifest is setup evidence, not solved-run evidence.",
            "- Save normal PatchSmith run artifacts before making repair-quality claims.",
            "",
        ]
    )
    return "\n".join(lines)


def _materialized_test_commands(preview: dict[str, Any]) -> list[str]:
    commands = _string_list(preview.get("test_commands"))
    return commands or ["python3 -m pytest"]


def _materialized_run_risk(
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


def _manifest_is_source_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            key != "excerpt" and _manifest_is_source_free(child) for key, child in value.items()
        )
    if isinstance(value, list):
        return all(_manifest_is_source_free(item) for item in value)
    return True


def _is_materialized_test_candidate_path(path: str) -> bool:
    path_obj = Path(path)
    parts = path_obj.parts
    name = path_obj.name
    return (
        (bool(parts) and parts[0] in {"tests", "test", "testing"})
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _duplicate_materialized_task_ids(
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


def _with_materialized_validation_error(
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
