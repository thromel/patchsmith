"""Evaluation issue corpus focused tests."""

from __future__ import annotations

import json
from pathlib import Path

from patchsmith.evaluation._helpers import _docker_smoke_status_from_file
from patchsmith.evaluation.issue_corpus.focused_diagnosis import diagnose_focused_test_run_record
from patchsmith.evaluation.issue_corpus.focused_test_outputs import (
    write_focused_test_diagnosis_outputs,
    write_focused_test_setup_execution_outputs,
    write_focused_test_setup_readiness_outputs,
    write_materialized_issue_focused_test_plan_outputs,
)
from patchsmith.evaluation.issue_corpus.focused_test_planning import (
    plan_materialized_issue_focused_test,
    summarize_materialized_issue_focused_test_plan,
)
from patchsmith.evaluation.issue_corpus.focused_test_setup import (
    check_focused_test_setup_record,
    execute_focused_test_setup_record,
    summarize_focused_test_setup_execution,
    summarize_focused_test_setup_readiness,
)
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestDiagnosisResult,
    IssueCorpusFocusedTestDiagnosisSummary,
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy, FocusedSetupCommandPolicy


def plan_materialized_issue_focused_tests(
    *,
    tasks_dir: Path,
    output_dir: Path,
    max_paths: int = 2,
) -> tuple[list[IssueCorpusFocusedTestPlanResult], IssueCorpusFocusedTestPlanSummary]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        plan_materialized_issue_focused_test(
            task_dir=task_dir,
            policy=policy,
            max_paths=max_paths,
        )
        for task_dir in task_dirs
    ]
    summary = summarize_materialized_issue_focused_test_plan(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_focused_test_plan_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def diagnose_focused_test_runs(
    *,
    results_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestDiagnosisResult],
    IssueCorpusFocusedTestDiagnosisSummary,
]:
    records = _load_record_list(results_path, label="focused test run results")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [diagnose_focused_test_run_record(record=record) for record in records]
    summary = summarize_focused_test_diagnosis(
        results_path=results_path,
        results=results,
    )
    write_focused_test_diagnosis_outputs(
        output_dir=output_dir,
        results_path=results_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_diagnosis(
    *,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
) -> IssueCorpusFocusedTestDiagnosisSummary:
    category_counts: dict[str, int] = {}
    for result in results:
        category_counts[result.category] = category_counts.get(result.category, 0) + 1
    return IssueCorpusFocusedTestDiagnosisSummary(
        run_results_path=str(results_path),
        task_count=len(results),
        passed_tasks=sum(1 for result in results if result.category == "focused_test_passed"),
        environment_issue_tasks=sum(1 for result in results if result.severity == "environment"),
        dependency_issue_tasks=sum(1 for result in results if result.severity == "dependency"),
        timeout_tasks=sum(1 for result in results if result.category == "timeout"),
        blocked_tasks=sum(1 for result in results if result.severity == "blocked"),
        unknown_failure_tasks=sum(1 for result in results if result.category == "nonzero_exit"),
        category_counts=dict(sorted(category_counts.items())),
    )


def check_focused_test_setup_readiness(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestSetupReadinessResult],
    IssueCorpusFocusedTestSetupReadinessSummary,
]:
    records = _load_record_list(setup_plan_path, label="focused test setup plan")
    docker_smoke_status = _docker_smoke_status_from_file(docker_smoke_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        check_focused_test_setup_record(
            record=record,
            docker_smoke_status=docker_smoke_status,
        )
        for record in records
    ]
    summary = summarize_focused_test_setup_readiness(
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        docker_smoke_status=docker_smoke_status,
        results=results,
    )
    write_focused_test_setup_readiness_outputs(
        output_dir=output_dir,
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        results=results,
        summary=summary,
    )
    return results, summary


def execute_focused_test_setups(
    *,
    readiness_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
    allow_warnings: bool = False,
    allow_dependency_installs: bool = False,
) -> tuple[
    list[IssueCorpusFocusedTestSetupExecutionResult],
    IssueCorpusFocusedTestSetupExecutionSummary,
]:
    records = _load_record_list(readiness_path, label="focused test setup readiness")
    if allow_dependency_installs and sandbox_mode != "docker":
        raise ValueError("--allow-dependency-installs requires --sandbox-mode docker")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_setup_execution"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    policy = FocusedSetupCommandPolicy() if allow_dependency_installs else CommandPolicy()
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            policy=policy,
            network=sandbox_network,
        )
    )
    results = [
        execute_focused_test_setup_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            allow_warnings=allow_warnings,
            allow_dependency_installs=allow_dependency_installs,
        )
        for record in selected_records
    ]
    summary = summarize_focused_test_setup_execution(
        readiness_path=readiness_path,
        results=results,
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        allow_dependency_installs=allow_dependency_installs,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_focused_test_setup_execution_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        results=results,
        summary=summary,
    )
    return results, summary


def _load_record_list(path: Path, *, label: str) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError(f"{label} records must be JSON objects")
    return records


__all__ = [
    "check_focused_test_setup_readiness",
    "diagnose_focused_test_runs",
    "execute_focused_test_setups",
    "plan_materialized_issue_focused_tests",
    "summarize_focused_test_diagnosis",
    "summarize_focused_test_setup_execution",
    "summarize_focused_test_setup_readiness",
    "summarize_materialized_issue_focused_test_plan",
]
