"""Evaluation issue corpus preview (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import _remove_artifact_dir, _string_list
from patchsmith.evaluation_models import (
    IssueCorpusContextPreviewResult,
    IssueCorpusContextPreviewSummary,
)
from patchsmith.evaluation_reports import (
    render_issue_corpus_context_preview_report,
)
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever


def preview_issue_corpus_context(
    *,
    corpus_path: Path,
    output_dir: Path,
    context_provider: str = "native_hybrid",
    top_k: int = 5,
    max_issues: int | None = None,
) -> tuple[list[IssueCorpusContextPreviewResult], IssueCorpusContextPreviewSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    issues = [issue for issue in payload["issues"] if isinstance(issue, dict)]
    if max_issues is not None:
        issues = issues[:max_issues]
    output_dir.mkdir(parents=True, exist_ok=True)
    repositories_dir = output_dir / "repositories"
    repositories_dir.mkdir(parents=True, exist_ok=True)
    snapshots: dict[str, Any] = {}
    indexes: dict[str, Any] = {}
    results: list[IssueCorpusContextPreviewResult] = []

    for issue in issues:
        task_id = str(issue.get("task_id", "unknown"))
        repository = str(issue.get("repository", "unknown"))
        issue_url = str(issue.get("issue_url", ""))
        repo_url = str(issue.get("repo_url", ""))
        try:
            if repository not in snapshots:
                repo_dir = repositories_dir / _safe_artifact_name(repository)
                if repo_dir.exists():
                    _remove_artifact_dir(root=output_dir, target=repo_dir)
                snapshot = clone_or_copy_repository(repo_url, repo_dir)
                snapshots[repository] = snapshot
                indexes[repository] = index_repository(snapshot.repo_path)
            snapshot = snapshots[repository]
            repo_index = indexes[repository]
            retriever = _issue_corpus_retriever(context_provider)
            contexts = retriever.retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=_issue_corpus_issue_text(issue),
                top_k=top_k,
            )
            contexts = _supplement_context_preview_source_neighbors(
                contexts=contexts,
                repo_index=repo_index,
                top_k=top_k,
                context_provider=context_provider,
            )
            results.append(
                IssueCorpusContextPreviewResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="completed",
                    error=None,
                    repo_path=str(snapshot.repo_path),
                    commit_hash=snapshot.commit_hash,
                    branch=snapshot.branch,
                    file_count=snapshot.file_count,
                    language_summary=snapshot.language_summary,
                    package_manager=snapshot.package_manager,
                    test_commands=snapshot.test_commands,
                    context_provider=context_provider,
                    context_count=len(contexts),
                    retrieved_files=[context.path for context in contexts],
                    top_contexts=[_source_free_context(context) for context in contexts],
                )
            )
        except Exception as error:
            results.append(
                IssueCorpusContextPreviewResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="failed",
                    error=str(error),
                    repo_path=None,
                    commit_hash=None,
                    branch=None,
                    file_count=0,
                    language_summary={},
                    package_manager=None,
                    test_commands=[],
                    context_provider=context_provider,
                    context_count=0,
                    retrieved_files=[],
                    top_contexts=[],
                )
            )

    summary = summarize_issue_corpus_context_preview(
        corpus_path=corpus_path,
        results=results,
        context_provider=context_provider,
    )
    write_issue_corpus_context_preview_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_context_preview(
    *,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    context_provider: str,
) -> IssueCorpusContextPreviewSummary:
    completed = [result for result in results if result.status == "completed"]
    return IssueCorpusContextPreviewSummary(
        corpus_path=str(corpus_path),
        attempted_issues=len(results),
        completed_issues=len(completed),
        failed_issues=sum(1 for result in results if result.status != "completed"),
        repository_count=len({result.repository for result in results}),
        context_provider=context_provider,
        avg_context_count=(
            round(sum(result.context_count for result in completed) / len(completed), 1)
            if completed
            else 0.0
        ),
        source_free=all(
            "excerpt" not in context for result in results for context in result.top_contexts
        ),
    )


def write_issue_corpus_context_preview_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    summary: IssueCorpusContextPreviewSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "context_preview_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "context_preview_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "context_preview_results.csv").open(
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
                "commit_hash",
                "branch",
                "file_count",
                "package_manager",
                "test_commands",
                "context_provider",
                "context_count",
                "retrieved_files",
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
                    "commit_hash": result.commit_hash,
                    "branch": result.branch,
                    "file_count": result.file_count,
                    "package_manager": result.package_manager,
                    "test_commands": ";".join(result.test_commands),
                    "context_provider": result.context_provider,
                    "context_count": result.context_count,
                    "retrieved_files": ";".join(result.retrieved_files),
                }
            )
    (output_dir / "context_preview_report.md").write_text(
        render_issue_corpus_context_preview_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _issue_corpus_retriever(context_provider: str):
    if context_provider == "native":
        return KeywordRetriever()
    if context_provider == "native_hybrid":
        return HybridRetriever()
    if context_provider == "native_graph":
        return GraphRetriever()
    raise ValueError(f"unsupported issue-corpus context provider: {context_provider}")


def _issue_corpus_issue_text(issue: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in ("title", "task_type", "selection_reason"):
        value = issue.get(key)
        if isinstance(value, str):
            fields.append(value)
    workflow = issue.get("expected_workflow")
    if isinstance(workflow, list):
        fields.extend(item for item in workflow if isinstance(item, str))
    return "\n".join(fields)


def _source_free_context(context: RetrievedContext) -> dict[str, Any]:
    return {
        "path": context.path,
        "rank": context.rank,
        "score": context.score,
        "method": context.method,
        "matched_terms": context.matched_terms,
    }


def _source_free_preview_contexts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    contexts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        contexts.append(
            {
                "path": item.get("path"),
                "rank": item.get("rank"),
                "score": item.get("score"),
                "method": item.get("method"),
                "matched_terms": _string_list(item.get("matched_terms")),
            }
        )
    return contexts


def _supplement_context_preview_source_neighbors(
    *,
    contexts: list[RetrievedContext],
    repo_index: Any,
    top_k: int,
    context_provider: str,
) -> list[RetrievedContext]:
    if top_k <= 0 or not contexts:
        return []
    existing_paths = {context.path for context in contexts}
    source_paths = {
        file.path
        for file in repo_index.files
        if isinstance(getattr(file, "path", None), str)
        and not _is_issue_corpus_test_path(file.path)
    }
    supplements: list[RetrievedContext] = []
    for context in contexts:
        if not _is_issue_corpus_test_path(context.path):
            continue
        for candidate in _source_neighbor_candidates(context.path, source_paths):
            if candidate in existing_paths:
                continue
            existing_paths.add(candidate)
            supplements.append(
                RetrievedContext(
                    path=candidate,
                    rank=0,
                    score=max(context.score - 0.001, 0.0),
                    method=f"{context_provider}_source_neighbor",
                    matched_terms=["source_neighbor", f"test:{context.path}"],
                    excerpt="",
                )
            )
            break
    if not supplements:
        return _rerank_contexts(contexts)

    if len(contexts) + len(supplements) <= top_k:
        return _rerank_contexts([*contexts, *supplements])

    non_test_contexts = [
        context for context in contexts if not _is_issue_corpus_test_path(context.path)
    ]
    if not non_test_contexts:
        kept_originals = contexts[: max(top_k - len(supplements), 0)]
        return _rerank_contexts([*kept_originals, *supplements[:top_k]])[:top_k]
    return _rerank_contexts(contexts[:top_k])


def _source_neighbor_candidates(test_path: str, source_paths: set[str]) -> list[str]:
    path = Path(test_path)
    stem = path.stem
    normalized_stem = stem
    if normalized_stem.startswith("test_"):
        normalized_stem = normalized_stem[len("test_") :]
    if normalized_stem.endswith("_test"):
        normalized_stem = normalized_stem[: -len("_test")]

    stripped_parts = [
        part for part in path.parts if part not in {"tests", "test", "unit", "integration"}
    ]
    if stripped_parts:
        stripped_parts[-1] = f"{normalized_stem}{path.suffix}"
    relative_guess = Path(*stripped_parts) if stripped_parts else Path(f"{normalized_stem}.py")

    candidates = [
        f"src/{relative_guess.as_posix()}",
        f"lib/{relative_guess.as_posix()}",
        relative_guess.as_posix(),
        f"src/{normalized_stem}{path.suffix}",
        f"lib/{normalized_stem}{path.suffix}",
        f"{normalized_stem}{path.suffix}",
    ]
    candidates.extend(
        sorted(
            source_path for source_path in source_paths if Path(source_path).stem == normalized_stem
        )
    )
    deduped: list[str] = []
    for candidate in candidates:
        if candidate in source_paths and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _is_issue_corpus_test_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name
    return (
        "tests" in parts or "test" in parts or name.startswith("test_") or name.endswith("_test.py")
    )


def _rerank_contexts(contexts: list[RetrievedContext]) -> list[RetrievedContext]:
    return [replace(context, rank=index + 1) for index, context in enumerate(contexts)]
