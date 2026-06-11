"""Evaluation runners patch search (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from patchsmith.context import SupportsRetrieve
from patchsmith.evaluation._helpers import _average
from patchsmith.evaluation.seeded import load_seeded_tasks
from patchsmith.evaluation_models import (
    PatchSearchCandidateResult,
    PatchSearchEvalResult,
    PatchSearchEvalSummary,
    SeededTask,
)
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan
from patchsmith.repair_reports import (
    render_patch_search_eval_report,
)
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.sandbox import create_sandbox_runner


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
                    1.0 if result.selected_candidate_passed else 0.0 for result in completed
                ),
                avg_latency_ms=_average(result.latency_ms for result in completed),
                avg_test_runs=_average(result.test_runs for result in completed),
            )
        )
    return summaries


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
        fieldnames = (
            [key for key in results[0].to_dict() if key != "candidate_results"] if results else []
        )
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


def _retrieve_for_patch_search(
    *,
    repo_path: Path,
    repo_index: Any,
    issue_text: str,
    context_provider: str,
) -> list[RetrievedContext]:
    retriever: SupportsRetrieve
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
