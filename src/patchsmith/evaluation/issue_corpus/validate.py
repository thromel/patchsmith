"""Evaluation issue corpus validate (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import _entry_string_list, _required_entry_string
from patchsmith.evaluation_models import (
    IssueCorpusEntryValidationResult,
    IssueCorpusValidationSummary,
)
from patchsmith.evaluation_reports import (
    render_issue_corpus_validation_report,
)


def validate_issue_corpus(
    *,
    corpus_path: Path,
    output_dir: Path,
) -> tuple[list[IssueCorpusEntryValidationResult], IssueCorpusValidationSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"issue corpus is invalid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ValueError("issue corpus must contain a JSON object")
    entries_payload = payload.get("issues")
    if not isinstance(entries_payload, list):
        raise ValueError("issue corpus missing list field: issues")
    results = [
        _validate_issue_corpus_entry(entry, index) for index, entry in enumerate(entries_payload)
    ]
    duplicate_task_ids = _duplicate_issue_corpus_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_issue_corpus_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]
    summary = summarize_issue_corpus_validation(
        corpus_path=corpus_path,
        corpus_id=payload.get("corpus_id") if isinstance(payload.get("corpus_id"), str) else None,
        results=results,
    )
    write_issue_corpus_validation_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_validation(
    *,
    corpus_path: Path,
    corpus_id: str | None,
    results: list[IssueCorpusEntryValidationResult],
) -> IssueCorpusValidationSummary:
    repositories = sorted({result.repository for result in results if result.repository})
    languages = sorted({result.language for result in results if result.language})
    task_types = sorted({result.task_type for result in results if result.task_type})
    return IssueCorpusValidationSummary(
        corpus_path=str(corpus_path),
        corpus_id=corpus_id,
        entry_count=len(results),
        valid_entries=sum(1 for result in results if result.status == "valid"),
        invalid_entries=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        repositories=repositories,
        languages=languages,
        task_types=task_types,
        open_issue_count=sum(1 for result in results if result.state_at_capture == "open"),
    )


def write_issue_corpus_validation_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusEntryValidationResult],
    summary: IssueCorpusValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "corpus_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(output_dir / "corpus_summary.json", summary.to_dict(), trailing_newline=True)
    with (output_dir / "corpus_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "errors",
                "warnings",
                "language",
                "task_type",
                "state_at_capture",
                "expected_workflow",
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
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "language": result.language,
                    "task_type": result.task_type,
                    "state_at_capture": result.state_at_capture,
                    "expected_workflow": ";".join(result.expected_workflow),
                }
            )
    (output_dir / "corpus_report.md").write_text(
        render_issue_corpus_validation_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _validate_issue_corpus_entry(
    entry: Any,
    index: int,
) -> IssueCorpusEntryValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(entry, dict):
        return IssueCorpusEntryValidationResult(
            task_id=None,
            repository=None,
            issue_url=None,
            status="invalid",
            errors=[f"issues[{index}] must be an object"],
            warnings=[],
            language=None,
            task_type=None,
            state_at_capture=None,
            expected_workflow=[],
        )

    task_id = _required_entry_string(entry, "task_id", errors)
    repository = _required_entry_string(entry, "repository", errors)
    repo_url = _required_entry_string(entry, "repo_url", errors)
    issue_url = _required_entry_string(entry, "issue_url", errors)
    title = _required_entry_string(entry, "title", errors)
    language = _required_entry_string(entry, "language", errors)
    task_type = _required_entry_string(entry, "task_type", errors)
    state_at_capture = _required_entry_string(entry, "state_at_capture", errors)
    captured_at = _required_entry_string(entry, "captured_at", errors)
    expected_workflow = _entry_string_list(entry, "expected_workflow", errors)
    selection_reason = _required_entry_string(entry, "selection_reason", errors)

    if task_id and not task_id.replace("_", "").replace("-", "").isalnum():
        errors.append(f"task_id contains unsafe characters: {task_id}")
    if repository and "/" not in repository:
        errors.append(f"repository must use owner/name format: {repository}")
    if repo_url and not repo_url.startswith("https://github.com/"):
        errors.append(f"repo_url must be a GitHub URL: {repo_url}")
    if issue_url and not issue_url.startswith("https://github.com/"):
        errors.append(f"issue_url must be a GitHub URL: {issue_url}")
    if repository and issue_url:
        expected_prefix = f"https://github.com/{repository}/issues/"
        if not issue_url.startswith(expected_prefix):
            errors.append(f"issue_url does not match repository: {issue_url}")
    if repo_url and issue_url and "/issues/" in repo_url:
        errors.append("repo_url should point to the repository, not an issue")
    if state_at_capture and state_at_capture not in {"open", "closed"}:
        warnings.append(f"unexpected state_at_capture: {state_at_capture}")
    if language and language.lower() != "python":
        warnings.append(f"non-python issue corpus entry: {language}")
    if title and len(title) < 8:
        warnings.append("title is very short")
    if captured_at and "T" not in captured_at:
        warnings.append(f"captured_at should be an ISO timestamp: {captured_at}")
    if not selection_reason:
        warnings.append("selection_reason is empty")

    return IssueCorpusEntryValidationResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        language=language,
        task_type=task_type,
        state_at_capture=state_at_capture,
        expected_workflow=expected_workflow,
    )


def _duplicate_issue_corpus_task_ids(
    results: list[IssueCorpusEntryValidationResult],
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


def _with_issue_corpus_error(
    result: IssueCorpusEntryValidationResult,
    error: str,
) -> IssueCorpusEntryValidationResult:
    return IssueCorpusEntryValidationResult(
        task_id=result.task_id,
        repository=result.repository,
        issue_url=result.issue_url,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        language=result.language,
        task_type=result.task_type,
        state_at_capture=result.state_at_capture,
        expected_workflow=result.expected_workflow,
    )
