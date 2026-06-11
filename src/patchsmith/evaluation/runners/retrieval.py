"""Evaluation runners retrieval (split from evaluation.py)."""

from __future__ import annotations

import csv
import subprocess
import tempfile
import time
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.context import (
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBundle,
    CtxhelmCliBroker,
    PatchSmithNativeBroker,
    retrieved_context_from_bundle,
)
from patchsmith.context_packing import summarize_context_pack
from patchsmith.evaluation._helpers import _average, _ensure_git_repo
from patchsmith.evaluation.metrics import recall, top_k_recall
from patchsmith.evaluation.seeded import load_seeded_tasks
from patchsmith.evaluation_models import (
    RetrievalEvalResult,
    RetrievalEvalSummary,
    SeededTask,
)
from patchsmith.evaluation_reports import (
    render_retrieval_eval_report,
)
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever


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
                avg_test_context_count=_average(result.test_context_count for result in completed),
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

    write_json(results_json, [result.to_dict() for result in results])
    write_json(summary_json, [summary.to_dict() for summary in summaries])

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
