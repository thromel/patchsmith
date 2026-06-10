from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from patchsmith.context import (
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBundle,
    CtxhelmCliBroker,
    PatchSmithNativeBroker,
    retrieved_context_from_bundle,
)
from patchsmith.context_packing import summarize_context_pack
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext, RunRequest
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.workflow import RepairRunner


@dataclass(frozen=True)
class SeededTask:
    task_id: str
    task_dir: Path
    repo: Path
    issue_text: str
    test_command: str
    expected_touched_files: list[str]
    expected_related_tests: list[str]
    language: str
    failure_type: str


@dataclass(frozen=True)
class SeededTaskValidationResult:
    task_dir: str
    task_id: str | None
    status: str
    errors: list[str]
    warnings: list[str]
    issue_path: str | None
    repo_path: str | None
    expected_path: str | None
    expected_touched_files: list[str]
    expected_related_tests: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeededDatasetValidationSummary:
    dataset_dir: str
    task_count: int
    valid_tasks: int
    invalid_tasks: int
    warning_count: int
    error_count: int
    duplicate_task_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusEntryValidationResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    errors: list[str]
    warnings: list[str]
    language: str | None
    task_type: str | None
    state_at_capture: str | None
    expected_workflow: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusValidationSummary:
    corpus_path: str
    corpus_id: str | None
    entry_count: int
    valid_entries: int
    invalid_entries: int
    warning_count: int
    error_count: int
    repositories: list[str]
    languages: list[str]
    task_types: list[str]
    open_issue_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusRepoPreflightResult:
    repository: str
    repo_url: str
    status: str
    default_branch: str | None
    head_sha: str | None
    latency_ms: int
    error: str | None
    issue_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusRepoPreflightSummary:
    corpus_path: str
    repository_count: int
    reachable_repositories: int
    unreachable_repositories: int
    issue_count: int
    avg_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusContextPreviewResult:
    task_id: str
    repository: str
    issue_url: str
    status: str
    error: str | None
    repo_path: str | None
    commit_hash: str | None
    branch: str | None
    file_count: int
    language_summary: dict[str, int]
    package_manager: str | None
    test_commands: list[str]
    context_provider: str
    context_count: int
    retrieved_files: list[str]
    top_contexts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusContextPreviewSummary:
    corpus_path: str
    attempted_issues: int
    completed_issues: int
    failed_issues: int
    repository_count: int
    context_provider: str
    avg_context_count: float
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskResult:
    task_id: str
    repository: str
    issue_url: str
    status: str
    error: str | None
    task_dir: str | None
    manifest_path: str | None
    issue_path: str | None
    runbook_path: str | None
    repo_url: str
    commit_hash: str | None
    context_provider: str | None
    context_count: int
    retrieved_files: list[str]
    suggested_test_commands: list[str]
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskSummary:
    corpus_path: str
    context_preview_path: str
    output_dir: str
    attempted_issues: int
    materialized_tasks: int
    failed_tasks: int
    repository_count: int
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskValidationResult:
    task_id: str | None
    task_dir: str
    status: str
    errors: list[str]
    warnings: list[str]
    manifest_path: str | None
    issue_path: str | None
    runbook_path: str | None
    repository: str | None
    issue_url: str | None
    repo_path: str | None
    retrieved_files: list[str]
    suggested_commands: list[str]
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskValidationSummary:
    tasks_dir: str
    task_count: int
    valid_tasks: int
    invalid_tasks: int
    warning_count: int
    error_count: int
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvalResult:
    task_id: str
    context_provider: str
    status: str
    error: str | None
    retrieved_files: list[str]
    related_test_files: list[str]
    expected_touched_files: list[str]
    expected_related_tests: list[str]
    top1_touched_recall: float
    top3_touched_recall: float
    top5_touched_recall: float
    related_test_recall: float
    latency_ms: int
    context_count: int
    source_context_count: int
    test_context_count: int
    context_excerpt_chars: int
    context_approx_tokens: int
    fallback_used: bool
    source_text_logged: bool
    source_free_violation: bool
    raw_artifact_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvalSummary:
    provider: str
    attempted_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_top1_touched_recall: float
    avg_top3_touched_recall: float
    avg_top5_touched_recall: float
    avg_related_test_recall: float
    avg_latency_ms: float
    avg_context_count: float
    avg_source_context_count: float
    avg_test_context_count: float
    avg_context_excerpt_chars: float
    avg_context_approx_tokens: float
    fallback_count: int
    source_free_violation_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairEvalResult:
    task_id: str
    runtime: str
    planner: str
    context_provider: str
    status: str
    error: str | None
    patch_generated: bool
    targeted_tests_passed: bool
    test_exit_code: int | None
    report_path: str | None
    trace_path: str | None
    final_diff_path: str | None
    retrieved_files: list[str]
    latency_ms: int
    trace_event_count: int = 0
    runtime_node_count: int = 0
    failed_trace_event_count: int = 0
    retry_event_count: int = 0
    debuggability_score: float = 0.0
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairEvalSummary:
    runtime: str
    planner: str
    context_provider: str
    attempted_tasks: int
    completed_tasks: int
    patch_generated_rate: float
    targeted_test_pass_rate: float
    avg_latency_ms: float
    avg_trace_events: float = 0.0
    avg_runtime_nodes: float = 0.0
    failed_trace_event_count: int = 0
    avg_retry_events: float = 0.0
    avg_debuggability_score: float = 0.0
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScaffoldComparisonResult:
    scaffold: str
    runtime: str
    planner: str
    context_provider: str
    attempted_tasks: int
    completed_tasks: int
    patch_generated_rate: float
    targeted_test_pass_rate: float
    avg_latency_ms: float
    avg_trace_events: float
    avg_runtime_nodes: float
    failed_trace_event_count: int
    avg_retry_events: float
    avg_debuggability_score: float
    model_provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    repair_report_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScaffoldVariant:
    name: str
    runtime: str
    planner: str


SCAFFOLD_VARIANTS: dict[str, ScaffoldVariant] = {
    "agentless": ScaffoldVariant("agentless", "agentless", "heuristic"),
    "heuristic": ScaffoldVariant("heuristic", "heuristic", "heuristic"),
    "langgraph": ScaffoldVariant("langgraph", "langgraph", "heuristic"),
    "langgraph_fake_model": ScaffoldVariant("langgraph_fake_model", "langgraph", "fake_model"),
    "deepagents": ScaffoldVariant("deepagents", "deepagents", "heuristic"),
    "openai_agents": ScaffoldVariant("openai_agents", "openai_agents", "heuristic"),
}


@dataclass(frozen=True)
class PatchSearchCandidateResult:
    candidate_index: int
    name: str
    path: str | None
    status: str
    test_exit_code: int | None
    tests_passed: bool
    diff: str
    duration_ms: int
    risk_score: float
    reason: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchSearchEvalResult:
    task_id: str
    variant: str
    candidate_count: int
    status: str
    success_at_1: bool
    success_at_k: bool
    selected_candidate_index: int | None
    selected_candidate_name: str | None
    selected_candidate_passed: bool
    test_runs: int
    latency_ms: int
    candidate_results: list[PatchSearchCandidateResult]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchSearchEvalSummary:
    variant: str
    candidate_count: int
    attempted_tasks: int
    completed_tasks: int
    success_at_1_rate: float
    success_at_k_rate: float
    selected_success_rate: float
    avg_latency_ms: float
    avg_test_runs: float
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_seeded_tasks(dataset_dir: Path) -> list[SeededTask]:
    tasks: list[SeededTask] = []
    for task_dir in sorted(path for path in dataset_dir.iterdir() if path.is_dir()):
        expected_path = task_dir / "expected.json"
        issue_path = task_dir / "issue.md"
        repo_path = task_dir / "repo"
        if not expected_path.exists() or not issue_path.exists() or not repo_path.exists():
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        tasks.append(
            SeededTask(
                task_id=str(expected["task_id"]),
                task_dir=task_dir,
                repo=repo_path,
                issue_text=issue_path.read_text(encoding="utf-8"),
                test_command=str(expected["test_command"]),
                expected_touched_files=list(expected.get("expected_touched_files", [])),
                expected_related_tests=list(expected.get("expected_related_tests", [])),
                language=str(expected.get("language", "unknown")),
                failure_type=str(expected.get("failure_type", "unknown")),
            )
        )
    return tasks


def validate_seeded_dataset(
    *,
    dataset_dir: Path,
    output_dir: Path,
) -> tuple[list[SeededTaskValidationResult], SeededDatasetValidationSummary]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset directory does not exist: {dataset_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    task_dirs = sorted(path for path in dataset_dir.iterdir() if path.is_dir())
    results = [_validate_seeded_task_dir(task_dir) for task_dir in task_dirs]
    duplicate_task_ids = _duplicate_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_validation_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]

    summary = summarize_seeded_dataset_validation(
        dataset_dir=dataset_dir,
        results=results,
        duplicate_task_ids=duplicate_task_ids,
    )
    write_seeded_dataset_validation_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_seeded_dataset_validation(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    duplicate_task_ids: list[str] | None = None,
) -> SeededDatasetValidationSummary:
    return SeededDatasetValidationSummary(
        dataset_dir=str(dataset_dir),
        task_count=len(results),
        valid_tasks=sum(1 for result in results if result.status == "valid"),
        invalid_tasks=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        duplicate_task_ids=duplicate_task_ids or _duplicate_task_ids(results),
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
        _validate_issue_corpus_entry(entry, index)
        for index, entry in enumerate(entries_payload)
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
    repositories = sorted(
        {
            result.repository
            for result in results
            if result.repository
        }
    )
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
    (output_dir / "corpus_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "corpus_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
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


def preflight_issue_corpus_repositories(
    *,
    corpus_path: Path,
    output_dir: Path,
    timeout_seconds: int = 20,
) -> tuple[list[IssueCorpusRepoPreflightResult], IssueCorpusRepoPreflightSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    repositories = _issue_corpus_repositories(payload["issues"])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _preflight_issue_corpus_repository(
            repository=repository,
            repo_url=repo_url,
            issue_count=issue_count,
            timeout_seconds=timeout_seconds,
        )
        for repository, repo_url, issue_count in repositories
    ]
    summary = summarize_issue_corpus_repo_preflight(
        corpus_path=corpus_path,
        results=results,
    )
    write_issue_corpus_repo_preflight_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_repo_preflight(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
) -> IssueCorpusRepoPreflightSummary:
    latencies = [result.latency_ms for result in results if result.status == "reachable"]
    return IssueCorpusRepoPreflightSummary(
        corpus_path=str(corpus_path),
        repository_count=len(results),
        reachable_repositories=sum(1 for result in results if result.status == "reachable"),
        unreachable_repositories=sum(1 for result in results if result.status != "reachable"),
        issue_count=sum(result.issue_count for result in results),
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    )


def write_issue_corpus_repo_preflight_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repo_preflight_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "repo_preflight_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "repo_preflight_results.csv").open(
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
    (output_dir / "repo_preflight_report.md").write_text(
        render_issue_corpus_repo_preflight_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


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
        except Exception as error:  # noqa: BLE001 - report all corpus materialization failures.
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
            "excerpt" not in context
            for result in results
            for context in result.top_contexts
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
    (output_dir / "context_preview_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "context_preview_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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
        raise FileNotFoundError(
            f"context preview results do not exist: {context_preview_path}"
        )

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
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
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
        except Exception as error:  # noqa: BLE001 - keep materialization reports complete.
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
            result.status == "materialized" and result.source_free
            for result in results
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
    (output_dir / "materialized_task_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "materialized_task_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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
    (output_dir / "materialized_task_validation_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "materialized_task_validation_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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


def run_retrieval_evaluation(
    *,
    dataset_dir: Path,
    providers: list[str],
    output_dir: Path,
    top_k: int = 5,
) -> tuple[list[RetrievalEvalResult], list[RetrievalEvalSummary]]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[RetrievalEvalResult] = []

    for task in tasks:
        for provider in providers:
            result = evaluate_retrieval_task(
                task=task,
                provider=provider,
                output_dir=output_dir,
                top_k=top_k,
            )
            results.append(result)

    summaries = summarize_retrieval_results(results)
    write_retrieval_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summaries=summaries,
    )
    return results, summaries


def run_repair_evaluation(
    *,
    dataset_dir: Path,
    runtime: str,
    planner: str = "heuristic",
    max_retries: int = 0,
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> tuple[list[RepairEvalResult], RepairEvalSummary]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_artifacts_dir = output_dir / "run_artifacts"
    runner = RepairRunner(artifacts_dir=run_artifacts_dir)
    results: list[RepairEvalResult] = []

    for task in tasks:
        started = time.perf_counter()
        try:
            result = runner.run(
                RunRequest(
                    repo=str(task.repo),
                    issue_text=task.issue_text,
                    test_command=task.test_command,
                    runtime=runtime,
                    planner=planner,
                    max_retries=max_retries,
                    context_provider=context_provider,
                    retrieval_strategy=context_provider,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                )
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            final_diff = result.final_diff_path.read_text(encoding="utf-8")
            test_exit_code = result.test_result.exit_code if result.test_result else None
            usage = _model_usage_from_trace(result.trace_path)
            trace_metrics = _trace_metrics_from_trace(result.trace_path)
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status=result.status,
                    error=None,
                    patch_generated=bool(final_diff.strip()),
                    targeted_tests_passed=test_exit_code == 0,
                    test_exit_code=test_exit_code,
                    report_path=str(result.report_path),
                    trace_path=str(result.trace_path),
                    final_diff_path=str(result.final_diff_path),
                    retrieved_files=[context.path for context in result.retrieved_context],
                    latency_ms=latency_ms,
                    trace_event_count=trace_metrics["trace_event_count"],
                    runtime_node_count=trace_metrics["runtime_node_count"],
                    failed_trace_event_count=trace_metrics["failed_trace_event_count"],
                    retry_event_count=trace_metrics["retry_event_count"],
                    debuggability_score=trace_metrics["debuggability_score"],
                    model_provider=usage["model_provider"],
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                    estimated_cost_usd=usage["estimated_cost_usd"],
                )
            )
        except Exception as error:
            latency_ms = int((time.perf_counter() - started) * 1000)
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status="failed",
                    error=str(error),
                    patch_generated=False,
                    targeted_tests_passed=False,
                    test_exit_code=None,
                    report_path=None,
                    trace_path=None,
                    final_diff_path=None,
                    retrieved_files=[],
                    latency_ms=latency_ms,
                )
            )

    summary = summarize_repair_results(
        results,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
    )
    write_repair_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def run_scaffold_comparison(
    *,
    dataset_dir: Path,
    variants: list[str],
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> list[ScaffoldComparisonResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_variants = [_scaffold_variant(name) for name in variants]
    comparison_results: list[ScaffoldComparisonResult] = []

    for variant in selected_variants:
        variant_output_dir = output_dir / variant.name
        _repair_results, summary = run_repair_evaluation(
            dataset_dir=dataset_dir,
            runtime=variant.runtime,
            planner=variant.planner,
            context_provider=context_provider,
            output_dir=variant_output_dir,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
        )
        comparison_results.append(
            ScaffoldComparisonResult(
                scaffold=variant.name,
                runtime=summary.runtime,
                planner=summary.planner,
                context_provider=summary.context_provider,
                attempted_tasks=summary.attempted_tasks,
                completed_tasks=summary.completed_tasks,
                patch_generated_rate=summary.patch_generated_rate,
                targeted_test_pass_rate=summary.targeted_test_pass_rate,
                avg_latency_ms=summary.avg_latency_ms,
                avg_trace_events=summary.avg_trace_events,
                avg_runtime_nodes=summary.avg_runtime_nodes,
                failed_trace_event_count=summary.failed_trace_event_count,
                avg_retry_events=summary.avg_retry_events,
                avg_debuggability_score=summary.avg_debuggability_score,
                model_provider=summary.model_provider,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                total_tokens=summary.total_tokens,
                estimated_cost_usd=summary.estimated_cost_usd,
                repair_report_path=str(variant_output_dir / "repair_report.md"),
            )
        )

    write_scaffold_comparison_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=comparison_results,
    )
    return comparison_results


def run_patch_search_evaluation(
    *,
    dataset_dir: Path,
    candidate_counts: list[int],
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> tuple[list[PatchSearchEvalResult], list[PatchSearchEvalSummary]]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[PatchSearchEvalResult] = []

    for candidate_count in candidate_counts:
        if candidate_count < 1:
            raise ValueError("candidate counts must be positive")
        variant = f"candidates_{candidate_count}"
        for task in tasks:
            results.append(
                evaluate_patch_search_task(
                    task=task,
                    variant=variant,
                    candidate_count=candidate_count,
                    context_provider=context_provider,
                    output_dir=output_dir,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                )
            )

    summaries = summarize_patch_search_results(results)
    write_patch_search_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summaries=summaries,
    )
    return results, summaries


def summarize_repair_results(
    results: list[RepairEvalResult],
    *,
    runtime: str,
    planner: str,
    context_provider: str,
) -> RepairEvalSummary:
    completed = [result for result in results if result.status == "completed"]
    providers = sorted(
        {result.model_provider for result in completed if result.model_provider is not None}
    )
    return RepairEvalSummary(
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        attempted_tasks=len(results),
        completed_tasks=len(completed),
        patch_generated_rate=_average(
            1.0 if result.patch_generated else 0.0 for result in completed
        ),
        targeted_test_pass_rate=_average(
            1.0 if result.targeted_tests_passed else 0.0 for result in completed
        ),
        avg_latency_ms=_average(result.latency_ms for result in completed),
        avg_trace_events=_average(result.trace_event_count for result in completed),
        avg_runtime_nodes=_average(result.runtime_node_count for result in completed),
        failed_trace_event_count=sum(result.failed_trace_event_count for result in completed),
        avg_retry_events=_average(result.retry_event_count for result in completed),
        avg_debuggability_score=_average(result.debuggability_score for result in completed),
        model_provider=",".join(providers) if providers else None,
        input_tokens=_sum_optional(result.input_tokens for result in completed),
        output_tokens=_sum_optional(result.output_tokens for result in completed),
        total_tokens=_sum_optional(result.total_tokens for result in completed),
        estimated_cost_usd=_sum_optional_float(result.estimated_cost_usd for result in completed),
    )


def evaluate_retrieval_task(
    *,
    task: SeededTask,
    provider: str,
    output_dir: Path,
    top_k: int,
) -> RetrievalEvalResult:
    started = time.perf_counter()
    provider_artifacts = output_dir / "context_artifacts" / task.task_id / provider
    provider_artifacts.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix=f"patchsmith-eval-{task.task_id}-") as tmp_dir:
            repo_path = Path(tmp_dir) / "repo"
            snapshot = clone_or_copy_repository(str(task.repo), repo_path)
            if provider == "ctxhelm_cli":
                _ensure_git_repo(snapshot.repo_path)

            repo_index = index_repository(snapshot.repo_path)
            native_contexts = KeywordRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )
            hybrid_contexts = HybridRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )
            graph_contexts = GraphRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )

            if provider == "native":
                bundle = PatchSmithNativeBroker().prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = native_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "native_hybrid":
                bundle = PatchSmithNativeBroker(
                    HybridRetriever(), provider_name="patchsmith_native_hybrid"
                ).prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = hybrid_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "native_graph":
                bundle = PatchSmithNativeBroker(
                    GraphRetriever(), provider_name="patchsmith_native_graph"
                ).prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = graph_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "ctxhelm_cli":
                bundle = CtxhelmCliBroker().prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = retrieved_context_from_bundle(
                    bundle=bundle,
                    repo_path=snapshot.repo_path,
                    fallback_contexts=[],
                    top_k=top_k,
                )
                related_tests = _related_tests_from_bundle(bundle)
            else:
                raise ValueError(f"unsupported context provider: {provider}")

            latency_ms = int((time.perf_counter() - started) * 1000)
            retrieved_files = [context.path for context in contexts]
            packing = summarize_context_pack(contexts)
            return RetrievalEvalResult(
                task_id=task.task_id,
                context_provider=provider,
                status="completed",
                error=None,
                retrieved_files=retrieved_files,
                related_test_files=related_tests,
                expected_touched_files=task.expected_touched_files,
                expected_related_tests=task.expected_related_tests,
                top1_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 1),
                top3_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 3),
                top5_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 5),
                related_test_recall=recall(related_tests, task.expected_related_tests),
                latency_ms=latency_ms,
                context_count=packing.context_count,
                source_context_count=packing.source_context_count,
                test_context_count=packing.test_context_count,
                context_excerpt_chars=packing.excerpt_char_count,
                context_approx_tokens=packing.approx_token_count,
                fallback_used=bundle.fallback_used,
                source_text_logged=bundle.source_text_logged,
                source_free_violation=bundle.source_text_logged,
                raw_artifact_path=bundle.raw_artifact_path,
            )
    except (ContextBrokerError, ValueError, OSError, subprocess.CalledProcessError) as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalEvalResult(
            task_id=task.task_id,
            context_provider=provider,
            status="failed",
            error=str(error),
            retrieved_files=[],
            related_test_files=[],
            expected_touched_files=task.expected_touched_files,
            expected_related_tests=task.expected_related_tests,
            top1_touched_recall=0.0,
            top3_touched_recall=0.0,
            top5_touched_recall=0.0,
            related_test_recall=0.0,
            latency_ms=latency_ms,
            context_count=0,
            source_context_count=0,
            test_context_count=0,
            context_excerpt_chars=0,
            context_approx_tokens=0,
            fallback_used=False,
            source_text_logged=False,
            source_free_violation=False,
            raw_artifact_path=None,
        )


def evaluate_patch_search_task(
    *,
    task: SeededTask,
    variant: str,
    candidate_count: int,
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> PatchSearchEvalResult:
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix=f"patchsmith-search-{task.task_id}-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            retrieval_repo = tmp_path / "retrieval_repo"
            snapshot = clone_or_copy_repository(str(task.repo), retrieval_repo)
            repo_index = index_repository(snapshot.repo_path)
            contexts = _retrieve_for_patch_search(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                context_provider=context_provider,
            )
            plan = HeuristicRepairPlanner().plan(
                issue_text=task.issue_text,
                retrieved_context=contexts,
            )
            if plan is None:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return PatchSearchEvalResult(
                    task_id=task.task_id,
                    variant=variant,
                    candidate_count=candidate_count,
                    status="no_plan",
                    success_at_1=False,
                    success_at_k=False,
                    selected_candidate_index=None,
                    selected_candidate_name=None,
                    selected_candidate_passed=False,
                    test_runs=0,
                    latency_ms=latency_ms,
                    candidate_results=[],
                    error="no heuristic repair plan",
                )

            candidate_plans = _patch_search_candidates(plan, candidate_count)
            candidate_results: list[PatchSearchCandidateResult] = []
            sandbox = create_sandbox_runner(mode=sandbox_mode, image=sandbox_image)
            for candidate_index, candidate_plan, risk_score, reason in candidate_plans:
                candidate_repo = tmp_path / f"candidate_{candidate_index}"
                clone_or_copy_repository(str(task.repo), candidate_repo)
                candidate_started = time.perf_counter()
                try:
                    edit = apply_text_replacement(
                        repo_path=candidate_repo,
                        relative_path=candidate_plan.path,
                        old=candidate_plan.old,
                        new=candidate_plan.new,
                    )
                    test_result = sandbox.run(
                        command=task.test_command,
                        workspace=candidate_repo,
                        timeout_seconds=60,
                    )
                    tests_passed = test_result.exit_code == 0
                    status = "tests_passed" if tests_passed else "tests_failed"
                    candidate_results.append(
                        PatchSearchCandidateResult(
                            candidate_index=candidate_index,
                            name=candidate_plan.name,
                            path=candidate_plan.path,
                            status=status,
                            test_exit_code=test_result.exit_code,
                            tests_passed=tests_passed,
                            diff=edit.diff,
                            duration_ms=int((time.perf_counter() - candidate_started) * 1000),
                            risk_score=risk_score,
                            reason=reason,
                        )
                    )
                except PatchSafetyError as error:
                    candidate_results.append(
                        PatchSearchCandidateResult(
                            candidate_index=candidate_index,
                            name=candidate_plan.name,
                            path=candidate_plan.path,
                            status="patch_rejected",
                            test_exit_code=None,
                            tests_passed=False,
                            diff="",
                            duration_ms=int((time.perf_counter() - candidate_started) * 1000),
                            risk_score=risk_score,
                            reason=reason,
                            error=str(error),
                        )
                    )

            selected = next(
                (candidate for candidate in candidate_results if candidate.tests_passed),
                None,
            )
            success_at_1 = bool(candidate_results and candidate_results[0].tests_passed)
            success_at_k = any(candidate.tests_passed for candidate in candidate_results)
            latency_ms = int((time.perf_counter() - started) * 1000)
            _write_patch_search_task_artifact(
                output_dir=output_dir,
                task_id=task.task_id,
                variant=variant,
                candidate_results=candidate_results,
            )
            return PatchSearchEvalResult(
                task_id=task.task_id,
                variant=variant,
                candidate_count=candidate_count,
                status="completed",
                success_at_1=success_at_1,
                success_at_k=success_at_k,
                selected_candidate_index=selected.candidate_index if selected else None,
                selected_candidate_name=selected.name if selected else None,
                selected_candidate_passed=bool(selected and selected.tests_passed),
                test_runs=sum(
                    1 for candidate in candidate_results if candidate.status != "patch_rejected"
                ),
                latency_ms=latency_ms,
                candidate_results=candidate_results,
            )
    except Exception as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return PatchSearchEvalResult(
            task_id=task.task_id,
            variant=variant,
            candidate_count=candidate_count,
            status="failed",
            success_at_1=False,
            success_at_k=False,
            selected_candidate_index=None,
            selected_candidate_name=None,
            selected_candidate_passed=False,
            test_runs=0,
            latency_ms=latency_ms,
            candidate_results=[],
            error=str(error),
        )


def summarize_retrieval_results(
    results: list[RetrievalEvalResult],
) -> list[RetrievalEvalSummary]:
    summaries: list[RetrievalEvalSummary] = []
    providers = sorted({result.context_provider for result in results})
    for provider in providers:
        provider_results = [result for result in results if result.context_provider == provider]
        completed = [result for result in provider_results if result.status == "completed"]
        summaries.append(
            RetrievalEvalSummary(
                provider=provider,
                attempted_tasks=len(provider_results),
                completed_tasks=len(completed),
                failed_tasks=len(provider_results) - len(completed),
                avg_top1_touched_recall=_average(
                    result.top1_touched_recall for result in completed
                ),
                avg_top3_touched_recall=_average(
                    result.top3_touched_recall for result in completed
                ),
                avg_top5_touched_recall=_average(
                    result.top5_touched_recall for result in completed
                ),
                avg_related_test_recall=_average(
                    result.related_test_recall for result in completed
                ),
                avg_latency_ms=_average(result.latency_ms for result in completed),
                avg_context_count=_average(result.context_count for result in completed),
                avg_source_context_count=_average(
                    result.source_context_count for result in completed
                ),
                avg_test_context_count=_average(
                    result.test_context_count for result in completed
                ),
                avg_context_excerpt_chars=_average(
                    result.context_excerpt_chars for result in completed
                ),
                avg_context_approx_tokens=_average(
                    result.context_approx_tokens for result in completed
                ),
                fallback_count=sum(1 for result in provider_results if result.fallback_used),
                source_free_violation_count=sum(
                    1 for result in provider_results if result.source_free_violation
                ),
            )
        )
    return summaries


def summarize_patch_search_results(
    results: list[PatchSearchEvalResult],
) -> list[PatchSearchEvalSummary]:
    summaries: list[PatchSearchEvalSummary] = []
    variants = sorted({result.variant for result in results})
    for variant in variants:
        variant_results = [result for result in results if result.variant == variant]
        completed = [result for result in variant_results if result.status == "completed"]
        candidate_count = max((result.candidate_count for result in variant_results), default=0)
        summaries.append(
            PatchSearchEvalSummary(
                variant=variant,
                candidate_count=candidate_count,
                attempted_tasks=len(variant_results),
                completed_tasks=len(completed),
                success_at_1_rate=_average(
                    1.0 if result.success_at_1 else 0.0 for result in completed
                ),
                success_at_k_rate=_average(
                    1.0 if result.success_at_k else 0.0 for result in completed
                ),
                selected_success_rate=_average(
                    1.0 if result.selected_candidate_passed else 0.0
                    for result in completed
                ),
                avg_latency_ms=_average(result.latency_ms for result in completed),
                avg_test_runs=_average(result.test_runs for result in completed),
            )
        )
    return summaries


def write_retrieval_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> None:
    results_json = output_dir / "results.json"
    results_csv = output_dir / "results.csv"
    summary_json = output_dir / "summary.json"
    report_path = output_dir / "report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].to_dict()) if results else [])
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retrieved_files"] = ";".join(result.retrieved_files)
                row["related_test_files"] = ";".join(result.related_test_files)
                row["expected_touched_files"] = ";".join(result.expected_touched_files)
                row["expected_related_tests"] = ";".join(result.expected_related_tests)
                writer.writerow(row)

    report_path.write_text(
        render_retrieval_eval_report(
            dataset_dir=dataset_dir,
            results=results,
            summaries=summaries,
        ),
        encoding="utf-8",
    )


def write_repair_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> None:
    results_json = output_dir / "repair_results.json"
    results_csv = output_dir / "repair_results.csv"
    summary_json = output_dir / "repair_summary.json"
    report_path = output_dir / "repair_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retrieved_files"] = ";".join(result.retrieved_files)
                writer.writerow(row)

    report_path.write_text(
        render_repair_eval_report(dataset_dir=dataset_dir, results=results, summary=summary),
        encoding="utf-8",
    )


def write_scaffold_comparison_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> None:
    results_json = output_dir / "scaffold_results.json"
    results_csv = output_dir / "scaffold_results.csv"
    report_path = output_dir / "scaffold_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())

    report_path.write_text(
        render_scaffold_comparison_report(dataset_dir=dataset_dir, results=results),
        encoding="utf-8",
    )


def write_patch_search_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[PatchSearchEvalResult],
    summaries: list[PatchSearchEvalSummary],
) -> None:
    results_json = output_dir / "patch_search_results.json"
    results_csv = output_dir / "patch_search_results.csv"
    summary_json = output_dir / "patch_search_summary.json"
    report_path = output_dir / "patch_search_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            key for key in results[0].to_dict() if key != "candidate_results"
        ] if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row.pop("candidate_results", None)
                writer.writerow(row)

    report_path.write_text(
        render_patch_search_eval_report(
            dataset_dir=dataset_dir,
            results=results,
            summaries=summaries,
        ),
        encoding="utf-8",
    )


def write_seeded_dataset_validation_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> None:
    results_json = output_dir / "validation_results.json"
    results_csv = output_dir / "validation_results.csv"
    summary_json = output_dir / "validation_summary.json"
    report_path = output_dir / "validation_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["errors"] = ";".join(result.errors)
                row["warnings"] = ";".join(result.warnings)
                row["expected_touched_files"] = ";".join(result.expected_touched_files)
                row["expected_related_tests"] = ";".join(result.expected_related_tests)
                writer.writerow(row)

    report_path.write_text(
        render_seeded_dataset_validation_report(
            dataset_dir=dataset_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def render_retrieval_eval_report(
    *,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{len({result.task_id for result in results})}`",
        f"- Lane count: `{len({result.context_provider for result in results})}`",
        "- Model cost: `$0.00` (retrieval-only evaluation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Provider | Attempted | Completed | Top-1 | Top-3 | Top-5 | Related Tests | "
            "Avg Ctx | Avg Src | Avg Test | Avg Tokens | Avg Latency ms | Fallbacks | "
            "Source-Free Violations |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.provider} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.avg_top1_touched_recall:.2f} | "
            f"{summary.avg_top3_touched_recall:.2f} | "
            f"{summary.avg_top5_touched_recall:.2f} | "
            f"{summary.avg_related_test_recall:.2f} | "
            f"{summary.avg_context_count:.1f} | "
            f"{summary.avg_source_context_count:.1f} | "
            f"{summary.avg_test_context_count:.1f} | "
            f"{summary.avg_context_approx_tokens:.0f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.fallback_count} | "
            f"{summary.source_free_violation_count} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Provider | Status | Top-1 | Top-3 | Top-5 | Related Tests | "
                "Ctx | Tokens | Retrieved Files | Error |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.context_provider} | "
            f"{result.status} | "
            f"{result.top1_touched_recall:.2f} | "
            f"{result.top3_touched_recall:.2f} | "
            f"{result.top5_touched_recall:.2f} | "
            f"{result.related_test_recall:.2f} | "
            f"{result.context_count} | "
            f"{result.context_approx_tokens} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures localization evidence only; it does not claim patch success.",
            "- Context providers are compared under the same task and repository snapshot.",
            "- Context token counts are approximate and use packed excerpt characters, not a model-specific tokenizer.",
            "- Source-bearing raw artifacts are kept under the experiment output directory and not copied into this public summary.",
            "",
        ]
    )
    return "\n".join(lines)


def render_seeded_dataset_validation_report(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> str:
    lines = [
        "# Seeded Dataset Validation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        (
            f"- Duplicate task IDs: `{', '.join(summary.duplicate_task_ids)}`"
            if summary.duplicate_task_ids
            else "- Duplicate task IDs: `none`"
        ),
        "",
        "## Results",
        "",
        "| Task | Status | Errors | Warnings | Expected Source | Expected Tests |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_touched_files) or 'none'} | "
            f"{', '.join(result.expected_related_tests) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            (
                "- Dataset validation checks metadata shape, required files, non-empty "
                "issues, and expected paths."
            ),
            (
                "- A valid dataset is required before retrieval or repair eval metrics are "
                "release evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_validation_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusEntryValidationResult],
    summary: IssueCorpusValidationSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Validation Report",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Corpus ID: `{summary.corpus_id or 'unknown'}`",
        f"- Entry count: `{summary.entry_count}`",
        f"- Valid entries: `{summary.valid_entries}`",
        f"- Invalid entries: `{summary.invalid_entries}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Repositories: `{', '.join(summary.repositories) or 'none'}`",
        f"- Languages: `{', '.join(summary.languages) or 'none'}`",
        f"- Task types: `{', '.join(summary.task_types) or 'none'}`",
        f"- Open issues at capture: `{summary.open_issue_count}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Issue | Status | Errors | Warnings | Workflow |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or 'unknown'} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_workflow) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This corpus proves that public issue candidates have been curated and validated.",
            "- It does not prove PatchSmith solved these issues until run artifacts exist for them.",
            "- Use this corpus as the next real-world evaluation lane after seeded-suite gates.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_repo_preflight_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Repository Preflight",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Repository count: `{summary.repository_count}`",
        f"- Reachable repositories: `{summary.reachable_repositories}`",
        f"- Unreachable repositories: `{summary.unreachable_repositories}`",
        f"- Issue count: `{summary.issue_count}`",
        f"- Average reachable latency: `{summary.avg_latency_ms:.1f}ms`",
        "",
        "## Results",
        "",
        "| Repository | Status | Default Branch | HEAD | Issues | Latency ms | Error |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.repository} | "
            f"{result.status} | "
            f"{result.default_branch or 'unknown'} | "
            f"{result.head_sha or 'unknown'} | "
            f"{result.issue_count} | "
            f"{result.latency_ms} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preflight proves repository reachability and records current HEAD metadata.",
            "- It does not clone source or run repair tasks.",
            "- Use this before converting public issue candidates into executable eval tasks.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_context_preview_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    summary: IssueCorpusContextPreviewSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Context Preview",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Completed issues: `{summary.completed_issues}`",
        f"- Failed issues: `{summary.failed_issues}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Average context count: `{summary.avg_context_count:.1f}`",
        f"- Source-free summary: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Files | Contexts | Retrieved Files | Error |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.file_count} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preview proves repository clone/index/retrieval plumbing on public issue candidates.",
            "- Retrieved source excerpts are intentionally omitted from this summary.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_materialized_task_report(
    *,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Materialized Tasks",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Context preview: `{context_preview_path}`",
        f"- Output: `{summary.output_dir}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Materialized tasks: `{summary.materialized_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Contexts | Retrieved Files | Task Dir | Error |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.task_dir or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This materialization creates external-evaluation task manifests and runbooks.",
            "- Manifests intentionally omit source excerpts and issue body scraping.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_task_validation_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> str:
    lines = [
        "# Public Issue Materialized Task Validation",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Issue | Retrieved Files | Errors | Warnings |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            "- This gate validates manifest shape, source-free context summaries, task files, local repository snapshots, and suggested run commands.",
            "- A valid manifest set is external-evaluation setup evidence, not repair-quality evidence.",
            "- Public issue reproduction and repair claims still require normal PatchSmith run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_repair_eval_report(
    *,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> str:
    input_tokens = summary.input_tokens if summary.input_tokens is not None else "n/a"
    output_tokens = summary.output_tokens if summary.output_tokens is not None else "n/a"
    total_tokens = summary.total_tokens if summary.total_tokens is not None else "n/a"
    lines = [
        "# Repair Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Completed tasks: `{summary.completed_tasks}`",
        f"- Model provider: `{summary.model_provider or 'none'}`",
        f"- Input tokens: `{input_tokens}`",
        f"- Output tokens: `{output_tokens}`",
        f"- Total tokens: `{total_tokens}`",
        f"- Estimated model cost: `{_format_cost(summary.estimated_cost_usd)}`",
        "",
        "## Summary",
        "",
        (
            "| Runtime | Planner | Context | Patch Generated | Targeted Tests Passed | "
            "Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | Failed Trace Events | "
            "Avg Retries | Debug Score | Input Tokens | Output Tokens | Est Cost |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| "
        f"{summary.runtime} | "
        f"{summary.planner} | "
        f"{summary.context_provider} | "
        f"{summary.patch_generated_rate:.2f} | "
        f"{summary.targeted_test_pass_rate:.2f} | "
        f"{summary.avg_latency_ms:.0f} | "
        f"{summary.avg_trace_events:.1f} | "
        f"{summary.avg_runtime_nodes:.1f} | "
        f"{summary.failed_trace_event_count} | "
        f"{summary.avg_retry_events:.1f} | "
        f"{summary.avg_debuggability_score:.1f} | "
        f"{summary.input_tokens if summary.input_tokens is not None else ''} | "
        f"{summary.output_tokens if summary.output_tokens is not None else ''} | "
        f"{_format_cost(summary.estimated_cost_usd)} |",
        "",
        "## Per-Task Results",
        "",
        (
            "| Task | Planner | Model Provider | Status | Patch Generated | Tests Passed | "
            "Exit Code | Trace Events | Runtime Nodes | Failed Trace Events | Retries | "
            "Debug Score | Tokens | Est Cost | Retrieved Files | Report | Error |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.planner} | "
            f"{result.model_provider or ''} | "
            f"{result.status} | "
            f"{int(result.patch_generated)} | "
            f"{int(result.targeted_tests_passed)} | "
            f"{result.test_exit_code if result.test_exit_code is not None else ''} | "
            f"{result.trace_event_count} | "
            f"{result.runtime_node_count} | "
            f"{result.failed_trace_event_count} | "
            f"{result.retry_event_count} | "
            f"{result.debuggability_score:.1f} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.report_path or ''} | "
            f"{(result.error or '').replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures seeded-task patch smoke behavior.",
            (
                "- Heuristic and fake-model planners should not be presented as autonomous "
                "coding-agent quality."
            ),
            (
                "- Use this runner to validate artifacts and gates before enabling a live "
                "model provider."
            ),
            "- Estimated cost is reported only when provider usage and configured rates exist.",
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "",
        ]
    )
    if summary.runtime == "deepagents":
        lines.insert(
            -1,
            (
                "- The `deepagents` runtime row is dependency-gated adapter evidence; "
                "local runs use offline compatibility mode unless the optional "
                "`deepagents` extra and live model provider are configured."
            ),
        )
    if summary.runtime == "openai_agents":
        lines.insert(
            -1,
            (
                "- The `openai_agents` runtime row is dependency-gated adapter evidence; "
                "local runs use offline compatibility mode unless the optional "
                "`openai-agents` extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def render_scaffold_comparison_report(
    *,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> str:
    lines = [
        "# Scaffold Comparison Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Scaffold count: `{len(results)}`",
        f"- Model cost: `{_format_cost(_sum_optional_float(result.estimated_cost_usd for result in results))}`",
        "",
        "## Summary",
        "",
        (
            "| Scaffold | Runtime | Planner | Context | Completed | Patch Generated | "
            "Targeted Tests Passed | Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | "
            "Failed Trace Events | Avg Retries | Debug Score | Model Provider | Tokens | Est Cost | Repair Report |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.scaffold} | "
            f"{result.runtime} | "
            f"{result.planner} | "
            f"{result.context_provider} | "
            f"{result.completed_tasks}/{result.attempted_tasks} | "
            f"{result.patch_generated_rate:.2f} | "
            f"{result.targeted_test_pass_rate:.2f} | "
            f"{result.avg_latency_ms:.0f} | "
            f"{result.avg_trace_events:.1f} | "
            f"{result.avg_runtime_nodes:.1f} | "
            f"{result.failed_trace_event_count} | "
            f"{result.avg_retry_events:.1f} | "
            f"{result.avg_debuggability_score:.1f} | "
            f"{result.model_provider or ''} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{result.repair_report_path} |"
        )

    best_resolved = max((result.targeted_test_pass_rate for result in results), default=0.0)
    best_scaffolds = [
        result.scaffold for result in results if result.targeted_test_pass_rate == best_resolved
    ]
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            (
                f"- Best targeted-test pass rate in this run: `{best_resolved:.2f}` "
                f"from `{', '.join(best_scaffolds) or 'none'}`."
            ),
            "- Agentless is the no-edit baseline and should not be treated as a repair scaffold.",
            (
                "- Heuristic and fake-model planners are deterministic seeded-task baselines; "
                "they do not prove autonomous coding-agent quality."
            ),
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "- Compare repair report traces before making a default-runtime decision.",
            "",
        ]
    )
    if any(result.scaffold == "deepagents" for result in results):
        lines.insert(
            -1,
            (
                "- The `deepagents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `deepagents` "
                "extra and live model provider are configured."
            ),
        )
    if any(result.scaffold == "openai_agents" for result in results):
        lines.insert(
            -1,
            (
                "- The `openai_agents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `openai-agents` "
                "extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def render_patch_search_eval_report(
    *,
    dataset_dir: Path,
    results: list[PatchSearchEvalResult],
    summaries: list[PatchSearchEvalSummary],
) -> str:
    lines = [
        "# Patch Search Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Variant count: `{len(summaries)}`",
        "- Model cost: `$0.00` (deterministic candidate generation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Variant | Candidates | Attempted | Completed | Success@1 | Success@k | "
            "Selected Success | Avg Latency ms | Avg Test Runs | Est Cost |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.variant} | "
            f"{summary.candidate_count} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.success_at_1_rate:.2f} | "
            f"{summary.success_at_k_rate:.2f} | "
            f"{summary.selected_success_rate:.2f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.avg_test_runs:.1f} | "
            f"{_format_cost(summary.estimated_cost_usd)} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Variant | Status | Success@1 | Success@k | Selected Candidate | "
                "Selected Passed | Test Runs | Latency ms | Error |"
            ),
            "|---|---|---|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for result in results:
        selected = (
            f"{result.selected_candidate_index}:{result.selected_candidate_name}"
            if result.selected_candidate_index is not None
            else "none"
        )
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.variant} | "
            f"{result.status} | "
            f"{int(result.success_at_1)} | "
            f"{int(result.success_at_k)} | "
            f"{selected} | "
            f"{int(result.selected_candidate_passed)} | "
            f"{result.test_runs} | "
            f"{result.latency_ms} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures deterministic patch-search infrastructure, not model diversity.",
            "- Each candidate is applied and tested in an isolated copy of the task repository.",
            "- The selector chooses the first candidate whose targeted tests pass.",
            "- Cost is zero because this lane currently uses heuristic candidate generation.",
            "",
        ]
    )
    return "\n".join(lines)


def top_k_recall(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    return recall(retrieved[:k], expected)


def recall(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    retrieved_set = set(retrieved)
    expected_set = set(expected)
    return len(retrieved_set & expected_set) / len(expected_set)


def _related_tests_from_contexts(
    contexts: list[RetrievedContext], expected_related_tests: list[str]
) -> list[str]:
    expected = set(expected_related_tests)
    return [context.path for context in contexts if context.path in expected]


def _related_tests_from_bundle(bundle: ContextBundle) -> list[str]:
    paths: list[str] = []
    for item in bundle.related_tests:
        path = item.get("path")
        if isinstance(path, str) and path not in paths:
            paths.append(path)
    return paths


def _retrieve_for_patch_search(
    *,
    repo_path: Path,
    repo_index: Any,
    issue_text: str,
    context_provider: str,
) -> list[RetrievedContext]:
    if context_provider == "native_graph":
        retriever = GraphRetriever()
    elif context_provider == "native_hybrid":
        retriever = HybridRetriever()
    else:
        retriever = KeywordRetriever()
    return retriever.retrieve(
        repo_path=repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
        top_k=5,
    )


def _patch_search_candidates(
    base_plan: RepairPlan,
    candidate_count: int,
) -> list[tuple[int, RepairPlan, float, str]]:
    candidates: list[tuple[int, RepairPlan, float, str]] = [
        (
            1,
            base_plan,
            0.2,
            "primary heuristic repair plan",
        )
    ]
    if candidate_count >= 2:
        candidates.append(
            (
                2,
                RepairPlan(
                    name=f"{base_plan.name}_noop_control",
                    path=base_plan.path,
                    old=base_plan.old,
                    new=base_plan.old,
                    summary="No-op control candidate for patch-search selection.",
                ),
                0.7,
                "no-op control candidate",
            )
        )
    if candidate_count >= 3:
        candidates.append(
            (
                3,
                RepairPlan(
                    name=f"{base_plan.name}_delete_control",
                    path=base_plan.path,
                    old=base_plan.old,
                    new="",
                    summary="Deletion control candidate for patch-search selection.",
                ),
                0.9,
                "high-risk deletion control candidate",
            )
        )
    while len(candidates) < candidate_count:
        next_index = len(candidates) + 1
        candidates.append(
            (
                next_index,
                RepairPlan(
                    name=f"{base_plan.name}_noop_control_{next_index}",
                    path=base_plan.path,
                    old=base_plan.old,
                    new=base_plan.old,
                    summary="Extra no-op control candidate for patch-search selection.",
                ),
                0.8,
                "extra no-op control candidate",
            )
        )
    return candidates[:candidate_count]


def _write_patch_search_task_artifact(
    *,
    output_dir: Path,
    task_id: str,
    variant: str,
    candidate_results: list[PatchSearchCandidateResult],
) -> None:
    task_dir = output_dir / "task_artifacts" / variant
    task_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = task_dir / f"{task_id}.json"
    artifact_path.write_text(
        json.dumps([candidate.to_dict() for candidate in candidate_results], indent=2),
        encoding="utf-8",
    )


def _ensure_git_repo(repo_path: Path) -> None:
    if (repo_path / ".git").exists():
        return
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=PatchSmith",
            "-c",
            "user.email=patchsmith@example.local",
            "commit",
            "-q",
            "-m",
            "seeded task snapshot",
        ],
        cwd=repo_path,
        check=True,
    )


def _validate_seeded_task_dir(task_dir: Path) -> SeededTaskValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    expected_path = task_dir / "expected.json"
    issue_path = task_dir / "issue.md"
    repo_path = task_dir / "repo"
    expected: dict[str, Any] = {}

    if not expected_path.exists():
        errors.append("missing expected.json")
    else:
        try:
            parsed = json.loads(expected_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                errors.append("expected.json must contain a JSON object")
            else:
                expected = parsed
        except json.JSONDecodeError as error:
            errors.append(f"expected.json is invalid JSON: {error.msg}")

    if not issue_path.exists():
        errors.append("missing issue.md")
    elif not issue_path.read_text(encoding="utf-8").strip():
        errors.append("issue.md is empty")

    if not repo_path.exists():
        errors.append("missing repo directory")
    elif not repo_path.is_dir():
        errors.append("repo path is not a directory")

    task_id = _expected_string(expected, "task_id", errors)
    test_command = _expected_string(expected, "test_command", errors)
    language = _expected_string(expected, "language", errors)
    failure_type = _expected_string(expected, "failure_type", errors)
    expected_touched_files = _expected_string_list(expected, "expected_touched_files", errors)
    expected_related_tests = _expected_string_list(expected, "expected_related_tests", errors)

    if task_id and task_id != task_dir.name:
        warnings.append(f"task_id does not match directory name: {task_id} != {task_dir.name}")
    if test_command and "pytest" not in test_command:
        warnings.append(f"test command is not the current seeded-suite default: {test_command}")
    if language and language.lower() != "python":
        warnings.append(f"non-python seeded task language: {language}")
    if repo_path.exists() and repo_path.is_dir():
        for relative_path in expected_touched_files:
            _validate_expected_repo_file(repo_path, relative_path, "expected_touched_files", errors)
        for relative_path in expected_related_tests:
            _validate_expected_repo_file(repo_path, relative_path, "expected_related_tests", errors)
        if not any(repo_path.rglob("test_*.py")):
            warnings.append("repo has no Python test files matching test_*.py")

    return SeededTaskValidationResult(
        task_dir=str(task_dir),
        task_id=task_id,
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        issue_path=str(issue_path) if issue_path.exists() else None,
        repo_path=str(repo_path) if repo_path.exists() else None,
        expected_path=str(expected_path) if expected_path.exists() else None,
        expected_touched_files=expected_touched_files,
        expected_related_tests=expected_related_tests,
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


def _issue_corpus_repositories(issues: list[Any]) -> list[tuple[str, str, int]]:
    repo_urls: dict[str, str] = {}
    issue_counts: dict[str, int] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        repository = issue.get("repository")
        repo_url = issue.get("repo_url")
        if not isinstance(repository, str) or not repository.strip():
            continue
        if not isinstance(repo_url, str) or not repo_url.strip():
            continue
        repository = repository.strip()
        repo_urls[repository] = repo_url.strip()
        issue_counts[repository] = issue_counts.get(repository, 0) + 1
    return [
        (repository, repo_urls[repository], issue_counts[repository])
        for repository in sorted(repo_urls)
    ]


def _preflight_issue_corpus_repository(
    *,
    repository: str,
    repo_url: str,
    issue_count: int,
    timeout_seconds: int,
) -> IssueCorpusRepoPreflightResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=None,
            head_sha=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(error),
            issue_count=issue_count,
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    default_branch, head_sha = _parse_ls_remote_head(completed.stdout)
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "git ls-remote failed"
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=default_branch,
            head_sha=head_sha,
            latency_ms=latency_ms,
            error=error,
            issue_count=issue_count,
        )
    return IssueCorpusRepoPreflightResult(
        repository=repository,
        repo_url=repo_url,
        status="reachable",
        default_branch=default_branch,
        head_sha=head_sha,
        latency_ms=latency_ms,
        error=None,
        issue_count=issue_count,
    )


def _parse_ls_remote_head(output: str) -> tuple[str | None, str | None]:
    default_branch: str | None = None
    head_sha: str | None = None
    for line in output.splitlines():
        if line.startswith("ref:") and "\tHEAD" in line:
            ref = line.split()[1] if len(line.split()) >= 2 else ""
            prefix = "refs/heads/"
            default_branch = ref[len(prefix) :] if ref.startswith(prefix) else ref or None
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD":
            head_sha = parts[0]
    return default_branch, head_sha


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
                f"--repo \"{repo_ref}\" "
                f"--issue-file \"{issue_path}\" "
                "--runtime langgraph "
                "--planner fake_model "
                "--context-provider native_hybrid "
                f"--test-command \"{test_commands[0]}\" "
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
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    snapshot = (
        manifest.get("repository_snapshot")
        if isinstance(manifest.get("repository_snapshot"), dict)
        else {}
    )
    retrieval = (
        manifest.get("retrieval_preview")
        if isinstance(manifest.get("retrieval_preview"), dict)
        else {}
    )
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


def _manifest_is_source_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            key != "excerpt" and _manifest_is_source_free(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return all(_manifest_is_source_free(item) for item in value)
    return True


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


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
    name = path.name
    stem = path.stem
    normalized_stem = stem
    if normalized_stem.startswith("test_"):
        normalized_stem = normalized_stem[len("test_") :]
    if normalized_stem.endswith("_test"):
        normalized_stem = normalized_stem[: -len("_test")]

    stripped_parts = [
        part
        for part in path.parts
        if part not in {"tests", "test", "unit", "integration"}
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
            source_path
            for source_path in source_paths
            if Path(source_path).stem == normalized_stem
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
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _rerank_contexts(contexts: list[RetrievedContext]) -> list[RetrievedContext]:
    return [replace(context, rank=index + 1) for index, context in enumerate(contexts)]


def _safe_artifact_name(value: str) -> str:
    sanitized = "".join(character if character.isalnum() else "_" for character in value)
    sanitized = "_".join(part for part in sanitized.split("_") if part)
    return sanitized or "unknown"


def _remove_artifact_dir(*, root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError(f"refusing to remove path outside artifact root: {target}") from error
    if target == root:
        raise ValueError("refusing to remove artifact root")
    shutil.rmtree(target)


def _required_entry_string(entry: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"entry missing non-empty string field: {key}")
        return None
    return value.strip()


def _entry_string_list(entry: dict[str, Any], key: str, errors: list[str]) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"entry missing non-empty string list field: {key}")
        return []
    results: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"entry field {key}[{index}] must be a non-empty string")
            continue
        results.append(item.strip())
    return results


def _expected_string(expected: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = expected.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"expected.json missing non-empty string field: {key}")
        return None
    return value.strip()


def _expected_string_list(
    expected: dict[str, Any],
    key: str,
    errors: list[str],
) -> list[str]:
    value = expected.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"expected.json missing non-empty string list field: {key}")
        return []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"expected.json field {key}[{index}] must be a non-empty string")
            continue
        paths.append(item.strip())
    return paths


def _manifest_string(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    field_name: str | None = None,
) -> str | None:
    value = manifest.get(key)
    name = field_name or key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return None
    return value.strip()


def _manifest_object(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _validate_expected_repo_file(
    repo_path: Path,
    relative_path: str,
    field_name: str,
    errors: list[str],
) -> None:
    if relative_path.startswith("/") or relative_path.startswith("../") or "/../" in relative_path:
        errors.append(f"{field_name} contains unsafe path: {relative_path}")
        return
    target = (repo_path / relative_path).resolve()
    try:
        target.relative_to(repo_path.resolve())
    except ValueError:
        errors.append(f"{field_name} escapes repo: {relative_path}")
        return
    if not target.is_file():
        errors.append(f"{field_name} path does not exist: {relative_path}")


def _duplicate_task_ids(results: list[SeededTaskValidationResult]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


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


def _with_validation_error(
    result: SeededTaskValidationResult,
    error: str,
) -> SeededTaskValidationResult:
    return SeededTaskValidationResult(
        task_dir=result.task_dir,
        task_id=result.task_id,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        issue_path=result.issue_path,
        repo_path=result.repo_path,
        expected_path=result.expected_path,
        expected_touched_files=result.expected_touched_files,
        expected_related_tests=result.expected_related_tests,
    )


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


def _model_usage_from_trace(trace_path: Path) -> dict[str, Any]:
    providers: list[str] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    total_tokens: list[int] = []
    estimated_costs: list[float] = []

    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event, dict) else None
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            continue
        model_call = metadata.get("model_call")
        if not isinstance(model_call, dict):
            continue
        provider = model_call.get("provider")
        if isinstance(provider, str) and provider not in providers:
            providers.append(provider)
        _append_int(input_tokens, model_call.get("input_tokens"))
        _append_int(output_tokens, model_call.get("output_tokens"))
        _append_int(total_tokens, model_call.get("total_tokens"))
        _append_float(estimated_costs, model_call.get("estimated_cost_usd"))

    return {
        "model_provider": ",".join(providers) if providers else None,
        "input_tokens": sum(input_tokens) if input_tokens else None,
        "output_tokens": sum(output_tokens) if output_tokens else None,
        "total_tokens": sum(total_tokens) if total_tokens else None,
        "estimated_cost_usd": sum(estimated_costs) if estimated_costs else None,
    }


def _trace_metrics_from_trace(trace_path: Path) -> dict[str, Any]:
    events = _trace_events(trace_path)
    node_names = {
        str(event.get("node_name"))
        for event in events
        if isinstance(event.get("node_name"), str)
    }
    event_types = {
        str(event.get("event_type"))
        for event in events
        if isinstance(event.get("event_type"), str)
    }
    runtime_node_count = sum(
        1 for event in events if str(event.get("node_name", "")).startswith("runtime.")
    )
    failed_event_count = sum(
        1
        for event in events
        if str(event.get("status", "")).lower() in {"failed", "error"}
        or event.get("error") is not None
    )
    retry_event_count = sum(
        1
        for event in events
        if str(event.get("node_name", "")) == "runtime.retry"
        or str(event.get("event_type", "")) == "retry"
    )
    debuggability_score = 0.0
    if events:
        debuggability_score += 1.0
    if "retrieve" in node_names or "context_broker" in node_names:
        debuggability_score += 1.0
    if runtime_node_count:
        debuggability_score += 1.0
    if "test" in node_names:
        debuggability_score += 1.0
    if "repair_outcome" in event_types:
        debuggability_score += 1.0

    return {
        "trace_event_count": len(events),
        "runtime_node_count": runtime_node_count,
        "failed_trace_event_count": failed_event_count,
        "retry_event_count": retry_event_count,
        "debuggability_score": debuggability_score,
    }


def _trace_events(trace_path: Path) -> list[dict[str, Any]]:
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _scaffold_variant(name: str) -> ScaffoldVariant:
    try:
        return SCAFFOLD_VARIANTS[name]
    except KeyError as error:
        supported = ", ".join(sorted(SCAFFOLD_VARIANTS))
        raise ValueError(f"unsupported scaffold variant: {name}; supported: {supported}") from error


def _append_int(values: list[int], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        values.append(value)


def _append_float(values: list[float], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        values.append(float(value))


def _sum_optional(values: Any) -> int | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return sum(values_list)


def _sum_optional_float(values: Any) -> float | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return float(sum(values_list))


def _format_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "$0.00"
    return f"${value:.6f}"


def _average(values: Any) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)
