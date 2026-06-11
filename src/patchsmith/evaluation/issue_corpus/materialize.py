"""Evaluation issue corpus materialize (split from evaluation.py)."""

from __future__ import annotations

import json
from pathlib import Path

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _optional_string,
    _remove_artifact_dir,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.materialize_manifest import (
    issue_corpus_task_manifest,
    manifest_is_source_free,
    materialized_test_commands,
    render_materialized_issue,
    render_materialized_task_runbook,
)
from patchsmith.evaluation.issue_corpus.materialize_outputs import (
    write_issue_corpus_materialized_task_outputs,
    write_materialized_issue_run_readiness_outputs,
    write_materialized_issue_task_validation_outputs,
)
from patchsmith.evaluation.issue_corpus.materialize_readiness import (
    check_materialized_issue_task_run_readiness,
)
from patchsmith.evaluation.issue_corpus.materialize_utils import (
    is_materialized_test_candidate_path,
)
from patchsmith.evaluation.issue_corpus.materialize_validation import (
    duplicate_materialized_task_ids,
    validate_materialized_issue_task_dir,
    with_materialized_validation_error,
)
from patchsmith.evaluation_models import (
    IssueCorpusMaterializedRunReadinessResult,
    IssueCorpusMaterializedRunReadinessSummary,
    IssueCorpusMaterializedTaskResult,
    IssueCorpusMaterializedTaskSummary,
    IssueCorpusMaterializedTaskValidationResult,
    IssueCorpusMaterializedTaskValidationSummary,
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
            manifest = issue_corpus_task_manifest(
                issue=issue,
                preview=preview,
                corpus_id=corpus_id,
                task_dir=task_dir,
                issue_path=issue_path,
            )
            issue_path.write_text(
                render_materialized_issue(issue=issue, preview=preview),
                encoding="utf-8",
            )
            write_json(manifest_path, manifest, trailing_newline=True)
            runbook_path.write_text(
                render_materialized_task_runbook(manifest=manifest),
                encoding="utf-8",
            )
            test_commands = materialized_test_commands(preview)
            source_free = manifest_is_source_free(manifest)
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
    results = [validate_materialized_issue_task_dir(task_dir) for task_dir in task_dirs]
    duplicate_task_ids = duplicate_materialized_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            with_materialized_validation_error(result, "duplicate task_id")
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
        check_materialized_issue_task_run_readiness(task_dir=task_dir, policy=policy)
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


def _is_materialized_test_candidate_path(path: str) -> bool:
    return is_materialized_test_candidate_path(path)
