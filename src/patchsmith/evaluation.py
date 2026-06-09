from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
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
from patchsmith.sandbox import LocalSandboxRunner
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
            sandbox = LocalSandboxRunner()
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
