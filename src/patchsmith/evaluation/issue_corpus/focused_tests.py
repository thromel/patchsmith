"""Evaluation issue corpus focused tests (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
import tomllib
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _docker_smoke_status_from_file,
    _fixture_listing_command,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.materialize import _is_materialized_test_candidate_path
from patchsmith.evaluation.issue_corpus.public_issues import _last_nonempty_lines, _matching_lines
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestDiagnosisResult,
    IssueCorpusFocusedTestDiagnosisSummary,
    IssueCorpusFocusedTestPlanResult,
    IssueCorpusFocusedTestPlanSummary,
    IssueCorpusFocusedTestRunResult,
    IssueCorpusFocusedTestRunSummary,
    IssueCorpusFocusedTestSetupCommandResult,
    IssueCorpusFocusedTestSetupExecutionResult,
    IssueCorpusFocusedTestSetupExecutionSummary,
    IssueCorpusFocusedTestSetupPlanResult,
    IssueCorpusFocusedTestSetupPlanSummary,
    IssueCorpusFocusedTestSetupReadinessResult,
    IssueCorpusFocusedTestSetupReadinessSummary,
    IssueCorpusFocusedTestSetupValidationResult,
    IssueCorpusFocusedTestSetupValidationSummary,
)
from patchsmith.evaluation_reports import (
    render_focused_test_diagnosis_report,
    render_focused_test_setup_execution_report,
    render_focused_test_setup_plan_report,
    render_focused_test_setup_readiness_report,
    render_focused_test_setup_validation_report,
    render_materialized_issue_focused_test_plan_report,
    render_materialized_issue_focused_test_run_report,
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
        _plan_materialized_issue_focused_test(
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


def summarize_materialized_issue_focused_test_plan(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
) -> IssueCorpusFocusedTestPlanSummary:
    return IssueCorpusFocusedTestPlanSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        fallback_tasks=sum(1 for result in results if result.status == "fallback"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
    )


def write_materialized_issue_focused_test_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
    summary: IssueCorpusFocusedTestPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_plan_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_plan_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_plan_results.csv").open(
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
                "focused_files",
                "command",
                "policy_allowed",
                "policy_reason",
                "fallback_command",
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
                    "focused_files": ";".join(result.focused_files),
                    "command": result.command,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fallback_command": result.fallback_command,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "focused_test_plan_report.md").write_text(
        render_materialized_issue_focused_test_plan_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def run_materialized_issue_focused_tests(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
    sandbox_network: str = "none",
    timeout_seconds: int = 60,
    max_tasks: int | None = None,
) -> tuple[list[IssueCorpusFocusedTestRunResult], IssueCorpusFocusedTestRunSummary]:
    if not plan_path.exists():
        raise FileNotFoundError(f"focused test plan does not exist: {plan_path}")
    if not plan_path.is_file():
        raise ValueError(f"focused test plan path is not a file: {plan_path}")
    parsed = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test plan must contain a JSON list")
    plan_records = [record for record in parsed if isinstance(record, dict)]
    if len(plan_records) != len(parsed):
        raise ValueError("focused test plan records must be JSON objects")
    selected_records = plan_records
    if max_tasks is not None and max_tasks > 0:
        selected_records = plan_records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_runs"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    runner = create_sandbox_runner(
        mode=sandbox_mode,
        image=sandbox_image,
        network=sandbox_network,
    )
    results = [
        _run_materialized_issue_focused_test_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            timeout_seconds=timeout_seconds,
        )
        for record in selected_records
    ]
    summary = summarize_materialized_issue_focused_test_runs(
        plan_path=plan_path,
        results=results,
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_materialized_issue_focused_test_run_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_focused_test_runs(
    *,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    sandbox_mode: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestRunSummary:
    return IssueCorpusFocusedTestRunSummary(
        plan_path=str(plan_path),
        task_count=len(results),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )


def write_materialized_issue_focused_test_run_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    summary: IssueCorpusFocusedTestRunSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_run_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_run_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_run_results.csv").open(
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
                "command",
                "repo_path",
                "focused_files",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
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
                    "command": result.command,
                    "repo_path": result.repo_path,
                    "focused_files": ";".join(result.focused_files),
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "focused_test_run_report.md").write_text(
        render_materialized_issue_focused_test_run_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def diagnose_focused_test_runs(
    *,
    results_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestDiagnosisResult],
    IssueCorpusFocusedTestDiagnosisSummary,
]:
    if not results_path.exists():
        raise FileNotFoundError(f"focused test run results do not exist: {results_path}")
    if not results_path.is_file():
        raise ValueError(f"focused test run results path is not a file: {results_path}")
    parsed = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test run results must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test run result records must be JSON objects")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_diagnose_focused_test_run_record(record=record) for record in records]
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


def write_focused_test_diagnosis_outputs(
    *,
    output_dir: Path,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
    summary: IssueCorpusFocusedTestDiagnosisSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_diagnosis_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_diagnosis_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_diagnosis_results.csv").open(
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
                "run_status",
                "command",
                "repo_path",
                "focused_files",
                "category",
                "severity",
                "summary",
                "evidence",
                "suggested_next_actions",
                "stdout_path",
                "stderr_path",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "run_status": result.run_status,
                    "command": result.command,
                    "repo_path": result.repo_path,
                    "focused_files": ";".join(result.focused_files),
                    "category": result.category,
                    "severity": result.severity,
                    "summary": result.summary,
                    "evidence": ";".join(result.evidence),
                    "suggested_next_actions": ";".join(result.suggested_next_actions),
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                }
            )
    (output_dir / "focused_test_diagnosis_report.md").write_text(
        render_focused_test_diagnosis_report(
            results_path=results_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def plan_focused_test_setups(
    *,
    diagnosis_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestSetupPlanResult],
    IssueCorpusFocusedTestSetupPlanSummary,
]:
    if not diagnosis_path.exists():
        raise FileNotFoundError(f"focused test diagnosis does not exist: {diagnosis_path}")
    if not diagnosis_path.is_file():
        raise ValueError(f"focused test diagnosis path is not a file: {diagnosis_path}")
    parsed = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test diagnosis must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test diagnosis records must be JSON objects")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_plan_focused_test_setup(record=record) for record in records]
    summary = summarize_focused_test_setup_plan(
        diagnosis_path=diagnosis_path,
        results=results,
    )
    write_focused_test_setup_plan_outputs(
        output_dir=output_dir,
        diagnosis_path=diagnosis_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_plan(
    *,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
) -> IssueCorpusFocusedTestSetupPlanSummary:
    category_counts: dict[str, int] = {}
    for result in results:
        category_counts[result.category] = category_counts.get(result.category, 0) + 1
    return IssueCorpusFocusedTestSetupPlanSummary(
        diagnosis_path=str(diagnosis_path),
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        manual_review_tasks=sum(1 for result in results if result.status == "manual_review"),
        dependency_setup_tasks=sum(1 for result in results if result.severity == "dependency"),
        environment_setup_tasks=sum(1 for result in results if result.severity == "environment"),
        network_required_tasks=sum(1 for result in results if result.requires_network),
        sandbox_required_tasks=sum(1 for result in results if result.sandbox_required),
        category_counts=dict(sorted(category_counts.items())),
    )


def write_focused_test_setup_plan_outputs(
    *,
    output_dir: Path,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
    summary: IssueCorpusFocusedTestSetupPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_plan_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_plan_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_plan_results.csv").open(
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
                "category",
                "severity",
                "repo_path",
                "setup_profile",
                "setup_commands",
                "validation_command",
                "focused_files",
                "requires_network",
                "sandbox_required",
                "evidence",
                "risk_notes",
                "suggested_next_actions",
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
                    "category": result.category,
                    "severity": result.severity,
                    "repo_path": result.repo_path,
                    "setup_profile": result.setup_profile,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "focused_files": ";".join(result.focused_files),
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "evidence": ";".join(result.evidence),
                    "risk_notes": ";".join(result.risk_notes),
                    "suggested_next_actions": ";".join(result.suggested_next_actions),
                }
            )
    (output_dir / "focused_test_setup_plan_report.md").write_text(
        render_focused_test_setup_plan_report(
            diagnosis_path=diagnosis_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
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
    if not setup_plan_path.exists():
        raise FileNotFoundError(f"focused test setup plan does not exist: {setup_plan_path}")
    if not setup_plan_path.is_file():
        raise ValueError(f"focused test setup plan path is not a file: {setup_plan_path}")
    parsed = json.loads(setup_plan_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup plan must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup plan records must be JSON objects")

    docker_smoke_status = _docker_smoke_status_from_file(docker_smoke_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _check_focused_test_setup_record(
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


def summarize_focused_test_setup_readiness(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    docker_smoke_status: str,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
) -> IssueCorpusFocusedTestSetupReadinessSummary:
    return IssueCorpusFocusedTestSetupReadinessSummary(
        setup_plan_path=str(setup_plan_path),
        docker_smoke_path=str(docker_smoke_path),
        docker_smoke_status=docker_smoke_status,
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        network_required_tasks=sum(1 for result in results if result.requires_network),
        sandbox_required_tasks=sum(1 for result in results if result.sandbox_required),
    )


def write_focused_test_setup_readiness_outputs(
    *,
    output_dir: Path,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
    summary: IssueCorpusFocusedTestSetupReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_readiness_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_readiness_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_readiness_results.csv").open(
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
                "setup_profile",
                "repo_path",
                "repo_exists",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "docker_smoke_status",
                "errors",
                "warnings",
                "next_actions",
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
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "docker_smoke_status": result.docker_smoke_status,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_readiness_report.md").write_text(
        render_focused_test_setup_readiness_report(
            setup_plan_path=setup_plan_path,
            docker_smoke_path=docker_smoke_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


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
    if not readiness_path.exists():
        raise FileNotFoundError(f"focused test setup readiness does not exist: {readiness_path}")
    if not readiness_path.is_file():
        raise ValueError(f"focused test setup readiness path is not a file: {readiness_path}")
    parsed = json.loads(readiness_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup readiness must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup readiness records must be JSON objects")
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
        _execute_focused_test_setup_record(
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


def summarize_focused_test_setup_execution(
    *,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    dry_run: bool,
    allow_warnings: bool,
    allow_dependency_installs: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestSetupExecutionSummary:
    return IssueCorpusFocusedTestSetupExecutionSummary(
        readiness_path=str(readiness_path),
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        allow_dependency_installs=allow_dependency_installs,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        completed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        skipped_tasks=sum(1 for result in results if result.status == "skipped"),
        command_count=sum(len(result.setup_commands) for result in results),
        attempted_commands=sum(
            1
            for result in results
            for command_result in result.command_results
            if command_result.status in {"passed", "failed", "timed_out"}
        ),
    )


def write_focused_test_setup_execution_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    summary: IssueCorpusFocusedTestSetupExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_execution_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_execution_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_execution_results.csv").open(
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
                "readiness_status",
                "setup_profile",
                "repo_path",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "allow_dependency_installs",
                "command_results",
                "errors",
                "warnings",
                "next_actions",
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
                    "readiness_status": result.readiness_status,
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "allow_dependency_installs": result.allow_dependency_installs,
                    "command_results": json.dumps(
                        [command.to_dict() for command in result.command_results],
                        sort_keys=True,
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_execution_report.md").write_text(
        render_focused_test_setup_execution_report(
            readiness_path=readiness_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def validate_focused_test_setups(
    *,
    setup_execution_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusFocusedTestSetupValidationResult],
    IssueCorpusFocusedTestSetupValidationSummary,
]:
    if not setup_execution_path.exists():
        raise FileNotFoundError(
            f"focused test setup execution does not exist: {setup_execution_path}"
        )
    if not setup_execution_path.is_file():
        raise ValueError(f"focused test setup execution path is not a file: {setup_execution_path}")
    parsed = json.loads(setup_execution_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup execution must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup execution records must be JSON objects")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_setup_validation"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
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
        _validate_focused_test_setup_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )
        for record in selected_records
    ]
    summary = summarize_focused_test_setup_validation(
        setup_execution_path=setup_execution_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_focused_test_setup_validation_outputs(
        output_dir=output_dir,
        setup_execution_path=setup_execution_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_validation(
    *,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestSetupValidationSummary:
    failure_category_counts: dict[str, int] = {}
    for result in results:
        if result.failure_category:
            failure_category_counts[result.failure_category] = (
                failure_category_counts.get(result.failure_category, 0) + 1
            )
    return IssueCorpusFocusedTestSetupValidationSummary(
        setup_execution_path=str(setup_execution_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        skipped_tasks=sum(1 for result in results if result.status == "skipped"),
        failure_category_counts=failure_category_counts,
    )


def write_focused_test_setup_validation_outputs(
    *,
    output_dir: Path,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    summary: IssueCorpusFocusedTestSetupValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_validation_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_validation_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_validation_results.csv").open(
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
                "setup_execution_status",
                "setup_profile",
                "repo_path",
                "validation_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "failure_category",
                "failure_summary",
                "failure_evidence",
                "command_result",
                "errors",
                "warnings",
                "next_actions",
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
                    "setup_execution_status": result.setup_execution_status,
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "validation_command": result.validation_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "failure_category": result.failure_category,
                    "failure_summary": result.failure_summary,
                    "failure_evidence": ";".join(result.failure_evidence),
                    "command_result": (
                        json.dumps(result.command_result.to_dict(), sort_keys=True)
                        if result.command_result is not None
                        else None
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_validation_report.md").write_text(
        render_focused_test_setup_validation_report(
            setup_execution_path=setup_execution_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _plan_materialized_issue_focused_test(
    *,
    task_dir: Path,
    policy: CommandPolicy,
    max_paths: int,
) -> IssueCorpusFocusedTestPlanResult:
    errors: list[str] = []
    warnings: list[str] = []
    risk_notes: list[str] = []
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
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    repository = issue.get("repository") if isinstance(issue.get("repository"), str) else None
    issue_url = issue.get("issue_url") if isinstance(issue.get("issue_url"), str) else None
    repo_path_value = (
        snapshot.get("repo_path") if isinstance(snapshot.get("repo_path"), str) else None
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    fallback_command = test_commands[0] if test_commands else None
    retrieved_files = _string_list(retrieval.get("retrieved_files"))
    focused_files = [
        path for path in retrieved_files if _is_materialized_test_candidate_path(path)
    ][: max(max_paths, 0)]

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

    if focused_files:
        missing_focused = [
            path for path in focused_files if repo_exists and not (workspace / path).is_file()
        ]
        if missing_focused:
            errors.append(f"focused test files do not exist: {', '.join(missing_focused)}")
        command = "python3 -m pytest " + " ".join(focused_files)
        status = "planned"
    elif fallback_command:
        command = fallback_command
        status = "fallback"
        warnings.append("no retrieved test-like file was available; using fallback test command")
    else:
        command = None
        status = "blocked"
        errors.append("no focused or fallback test command available")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"focused test command rejected by policy: {decision.reason}")

    if focused_files:
        risk_notes.append("focused command is derived from retrieved test-like files")
    if fallback_command and command == fallback_command:
        risk_notes.append("fallback command may run a broader test scope")
    if errors:
        status = "blocked"
    return IssueCorpusFocusedTestPlanResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status=status,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        focused_files=focused_files,
        command=command,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        fallback_command=fallback_command,
        risk_notes=risk_notes,
        errors=errors,
        warnings=warnings,
    )


def _run_materialized_issue_focused_test_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestRunResult:
    errors: list[str] = []
    warnings: list[str] = []
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    command = _optional_string(record.get("command"))
    repo_path_value = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    plan_policy_allowed = bool(record.get("policy_allowed"))
    plan_policy_reason = _optional_string(record.get("policy_reason"))

    workspace: Path | None = None
    if not command:
        errors.append("focused test plan has no command")
    if not plan_policy_allowed:
        errors.append(
            "focused test plan command was not policy-allowed"
            + (f": {plan_policy_reason}" if plan_policy_reason else "")
        )
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("focused test plan has no repo_path")

    if errors:
        return IssueCorpusFocusedTestRunResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            command=command,
            repo_path=repo_path_value,
            focused_files=focused_files,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=False,
            policy_reason=plan_policy_reason,
            stdout_path=None,
            stderr_path=None,
            errors=errors,
            warnings=warnings,
        )

    assert command is not None
    assert workspace is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    command_result = runner.run(
        command=command,
        workspace=workspace,
        timeout_seconds=timeout_seconds,
    )
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(command_result.stdout, encoding="utf-8")
    stderr_path.write_text(command_result.stderr, encoding="utf-8")
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason
    if not policy_allowed:
        status = "blocked"
        errors.append(f"focused test command rejected by policy: {policy_reason}")
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"focused test command timed out after {timeout_seconds}s")
    elif command_result.exit_code is None:
        status = "blocked"
        errors.append("focused test command did not return an exit code")
    elif command_result.exit_code == 0:
        status = "passed"
    else:
        status = "failed"
        warnings.append(f"focused test command exited {command_result.exit_code}")

    return IssueCorpusFocusedTestRunResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        command=command,
        repo_path=repo_path_value,
        focused_files=focused_files,
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        errors=errors,
        warnings=warnings,
    )


def _diagnose_focused_test_run_record(
    *,
    record: dict[str, Any],
) -> IssueCorpusFocusedTestDiagnosisResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    run_status = _optional_string(record.get("status"))
    command = _optional_string(record.get("command"))
    repo_path = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    stdout_path = _optional_string(record.get("stdout_path"))
    stderr_path = _optional_string(record.get("stderr_path"))
    logs = _focused_test_log_text(stdout_path=stdout_path, stderr_path=stderr_path)

    if run_status == "passed":
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="focused_test_passed",
            severity="info",
            summary="Focused test command passed in the saved run.",
            evidence=[],
            suggested_next_actions=[
                "Use the focused command as targeted validation input for a later repair attempt.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if run_status == "timed_out":
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="timeout",
            severity="environment",
            summary="Focused test command timed out in the saved run.",
            evidence=_matching_lines(logs, ["timed out", "timeout"], limit=2),
            suggested_next_actions=[
                "Run the focused command in a stricter isolated environment with an explicit timeout budget.",
                "Reduce the command to issue-specific tests before using it as repair validation.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if run_status == "blocked":
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="execution_blocked",
            severity="blocked",
            summary="Focused test command was blocked before meaningful test execution.",
            evidence=_string_list(record.get("errors"))
            or _matching_lines(logs, ["blocked", "policy", "exit code"], limit=3),
            suggested_next_actions=[
                "Fix the focused test plan or sandbox availability before running public issue repairs.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "_pytest._version" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="missing_generated_version_metadata",
            severity="dependency",
            summary="Pytest snapshot failed before collection because generated version metadata is missing.",
            evidence=_matching_lines(logs, ["_pytest._version", "ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Prepare the repository in an isolated environment using its documented build step before running tests.",
                "Record the setup command separately from repair validation; do not treat this as a patch failure.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "recursive dependency involving fixture" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="pytest_fixture_dependency_error",
            severity="environment",
            summary="Pytest fixture setup failed before issue-specific assertions could run.",
            evidence=_matching_lines(
                logs,
                ["recursive dependency involving fixture", "ERROR at setup"],
                limit=4,
            ),
            suggested_next_actions=[
                "Install or configure upstream test fixtures in an isolated environment.",
                "Prefer narrower issue-specific tests that avoid service fixtures when possible.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "ModuleNotFoundError" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="missing_python_module",
            severity="dependency",
            summary="Focused test command failed because Python import dependencies are missing.",
            evidence=_matching_lines(logs, ["ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Resolve repository test dependencies in a sandbox before interpreting repair quality.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "ERROR at setup" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="pytest_setup_error",
            severity="environment",
            summary="Focused test command reached pytest but failed during setup.",
            evidence=_matching_lines(logs, ["ERROR at setup"], limit=4),
            suggested_next_actions=[
                "Inspect fixture and service requirements before attempting automated repair.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if not logs.strip():
        evidence = _string_list(record.get("errors")) or _string_list(record.get("warnings"))
        category = "missing_logs" if not evidence else "nonzero_exit"
        summary = (
            "Focused test command did not produce saved logs."
            if category == "missing_logs"
            else "Focused test command failed without a classified log signature."
        )
        return IssueCorpusFocusedTestDiagnosisResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category=category,
            severity="environment" if category == "missing_logs" else "unknown",
            summary=summary,
            evidence=evidence,
            suggested_next_actions=[
                "Rerun the focused command and capture stdout/stderr before interpreting failure quality.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    return IssueCorpusFocusedTestDiagnosisResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        run_status=run_status,
        command=command,
        repo_path=repo_path,
        focused_files=focused_files,
        category="nonzero_exit",
        severity="unknown",
        summary="Focused test command failed without a known readiness signature.",
        evidence=_last_nonempty_lines(logs, limit=4),
        suggested_next_actions=[
            "Inspect the saved stdout/stderr and add a narrower diagnosis before repair-quality claims.",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def _plan_focused_test_setup(
    *,
    record: dict[str, Any],
) -> IssueCorpusFocusedTestSetupPlanResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    category = _optional_string(record.get("category")) or "unknown"
    severity = _optional_string(record.get("severity")) or "unknown"
    command = _optional_string(record.get("command"))
    repo_path = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    evidence = _string_list(record.get("evidence"))
    diagnosis_next_actions = _string_list(record.get("suggested_next_actions"))
    validation_command = command

    setup_profile = "manual_review"
    setup_commands: list[str] = []
    status = "manual_review"
    requires_network = False
    sandbox_required = True
    risk_notes = [
        "setup planning only; commands are not executed by this report",
        "run setup only in a disposable sandbox with no host secrets",
    ]
    suggested_next_actions = [
        "review the focused diagnosis and repository setup docs before executing setup",
    ]

    if category == "focused_test_passed":
        setup_profile = "no_setup_required"
        status = "ready"
        sandbox_required = False
        risk_notes = ["focused command already passed in the saved run"]
        suggested_next_actions = [
            "use the focused command as targeted validation for a later repair attempt",
        ]
    elif category == "missing_generated_version_metadata":
        setup_profile = "python_editable_install_build_metadata"
        status = "planned"
        requires_network = True
        setup_commands = [
            "python3 -m pip install -e .",
            "python3 -m pytest --version",
        ]
        suggested_next_actions = [
            "prepare generated package metadata in an isolated Python environment",
            "rerun the focused validation command after setup succeeds",
        ]
    elif category == "pytest_fixture_dependency_error":
        setup_profile = "pytest_fixture_environment"
        status = "planned"
        requires_network = True
        setup_commands = [
            _focused_test_dependency_install_command(repo_path),
            _fixture_listing_command(focused_files),
        ]
        risk_notes.append("fixture setup may require optional test dependencies or local services")
        suggested_next_actions = [
            "install upstream test extras in an isolated Python environment",
            "prefer narrower issue-specific tests that avoid service fixtures when possible",
        ]
    elif category == "missing_python_module":
        setup_profile = "python_dependency_install"
        status = "planned"
        requires_network = True
        setup_commands = ["python3 -m pip install -e ."]
        suggested_next_actions = [
            "install repository dependencies in an isolated Python environment",
            "rerun focused validation before repair attempts",
        ]
    elif category == "pytest_setup_error":
        setup_profile = "pytest_setup_environment"
        status = "planned"
        requires_network = True
        setup_commands = [_focused_test_dependency_install_command(repo_path)]
        suggested_next_actions = [
            "inspect fixture and service requirements before automated repair",
            "rerun focused validation after setup changes",
        ]
    elif category == "timeout":
        setup_profile = "scope_timeout_review"
        suggested_next_actions = [
            "reduce the focused command scope or raise timeout only after cost review",
        ]
    elif category == "execution_blocked":
        setup_profile = "policy_or_sandbox_review"
        suggested_next_actions = [
            "fix command policy, repo snapshot, or sandbox availability before running setup",
        ]
    elif category == "missing_logs":
        setup_profile = "rerun_with_log_capture"
        suggested_next_actions = [
            "rerun the focused command with stdout and stderr capture before setup planning",
        ]
    elif diagnosis_next_actions:
        suggested_next_actions = diagnosis_next_actions

    return IssueCorpusFocusedTestSetupPlanResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        category=category,
        severity=severity,
        repo_path=repo_path,
        setup_profile=setup_profile,
        setup_commands=setup_commands,
        validation_command=validation_command,
        focused_files=focused_files,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        evidence=evidence,
        risk_notes=risk_notes,
        suggested_next_actions=suggested_next_actions,
    )


def _check_focused_test_setup_record(
    *,
    record: dict[str, Any],
    docker_smoke_status: str,
) -> IssueCorpusFocusedTestSetupReadinessResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    setup_status = _optional_string(record.get("status")) or "unknown"
    repo_path = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if not repo_exists:
            errors.append(f"repository snapshot is not available: {repo_path}")
            next_actions.append("rerun public issue context preview or materialization")
    else:
        errors.append("setup plan is missing repo_path")
        next_actions.append("regenerate focused diagnosis and setup plan from run results")

    if setup_status == "manual_review":
        errors.append("setup plan requires manual review before execution")
    elif setup_status == "ready":
        if setup_commands:
            warnings.append("ready setup task unexpectedly includes setup commands")
    elif setup_status != "planned":
        warnings.append(f"setup plan status is {setup_status}")

    if setup_status == "planned" and not setup_commands:
        errors.append("planned setup task has no setup commands")
    if setup_status == "planned" and not validation_command:
        errors.append("planned setup task has no validation command")

    if sandbox_required and docker_smoke_status != "passed":
        errors.append(f"Docker sandbox smoke is {docker_smoke_status}")
        next_actions.append("start Docker, build the smoke image, and rerun docker-smoke")
    if requires_network:
        warnings.append("setup requires network access; use a controlled disposable build step")
        next_actions.append("review network access and dependency trust before setup execution")
    if sandbox_required:
        next_actions.append("execute setup only inside a disposable sandbox with no host secrets")

    status = "blocked" if errors else "warning" if warnings else "ready"
    if not next_actions and status == "ready":
        next_actions.append("run setup commands in the approved sandbox, then rerun validation")
    return IssueCorpusFocusedTestSetupReadinessResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        setup_profile=setup_profile,
        repo_path=repo_path,
        repo_exists=repo_exists,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        docker_smoke_status=docker_smoke_status,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_focused_test_setup_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any | None,
    policy: CommandPolicy,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
    dry_run: bool,
    allow_warnings: bool,
    allow_dependency_installs: bool,
) -> IssueCorpusFocusedTestSetupExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    readiness_status = _optional_string(record.get("status")) or "unknown"
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors = _string_list(record.get("errors"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    command_results: list[IssueCorpusFocusedTestSetupCommandResult] = []

    workspace: Path | None = None
    if readiness_status == "blocked":
        errors.append("setup readiness is blocked")
    elif readiness_status == "warning" and not allow_warnings:
        errors.append("setup readiness is warning and --allow-warnings was not set")
    elif readiness_status not in {"ready", "warning"}:
        warnings.append(f"setup readiness status is {readiness_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("setup readiness record has no repo_path")

    if sandbox_required and sandbox_mode != "docker":
        warnings.append("setup requested Docker isolation but a non-Docker sandbox was selected")
    if requires_network and sandbox_mode == "docker":
        warnings.append(
            f"setup requires network access; Docker sandbox network is {sandbox_network}"
        )
        if not dry_run and sandbox_network == "none":
            errors.append("setup requires network but Docker sandbox network is none")

    if not setup_commands:
        status = "blocked" if errors else "skipped"
        if status == "skipped":
            next_actions.append("no setup commands were required; rerun focused validation")
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status=status,
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(next_actions),
        )

    if workspace is not None:
        for command in setup_commands:
            decision = policy.evaluate(command, workspace=workspace)
            command_results.append(
                IssueCorpusFocusedTestSetupCommandResult(
                    command=command,
                    status="dry_run" if decision.allowed else "policy_blocked",
                    exit_code=None,
                    timed_out=False,
                    duration_ms=0,
                    policy_allowed=decision.allowed,
                    policy_reason=decision.reason,
                    stdout_path=None,
                    stderr_path=None,
                )
            )
            if not decision.allowed:
                errors.append(f"setup command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "resolve setup-readiness and command-policy blockers before execution",
                ]
            ),
        )

    if dry_run:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute after reviewing dry-run evidence"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    command_results = []
    status = "passed"
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    for index, command in enumerate(setup_commands, start=1):
        command_result = runner.run(
            command=command,
            workspace=workspace,
            timeout_seconds=timeout_seconds,
        )
        command_dir = run_dir / f"command_{index:02d}"
        command_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = command_dir / "stdout.txt"
        stderr_path = command_dir / "stderr.txt"
        stdout_path.write_text(command_result.stdout, encoding="utf-8")
        stderr_path.write_text(command_result.stderr, encoding="utf-8")
        if not command_result.policy_decision.allowed:
            command_status = "policy_blocked"
            status = "blocked"
            errors.append(
                f"setup command rejected by policy: {command_result.policy_decision.reason}"
            )
        elif command_result.timed_out:
            command_status = "timed_out"
            status = "timed_out"
            warnings.append(f"setup command timed out after {timeout_seconds}s")
        elif command_result.exit_code == 0:
            command_status = "passed"
        else:
            command_status = "failed"
            status = "failed"
            warnings.append(f"setup command exited {command_result.exit_code}")
        command_results.append(
            IssueCorpusFocusedTestSetupCommandResult(
                command=command,
                status=command_status,
                exit_code=command_result.exit_code,
                timed_out=command_result.timed_out,
                duration_ms=command_result.duration_ms,
                policy_allowed=command_result.policy_decision.allowed,
                policy_reason=command_result.policy_decision.reason,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )
        )
        if command_status != "passed":
            break

    return IssueCorpusFocusedTestSetupExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        setup_profile=setup_profile,
        repo_path=repo_path_value,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        allow_dependency_installs=allow_dependency_installs,
        command_results=command_results,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(
            [*next_actions, "rerun focused validation command after successful setup"]
        ),
    )


def _classify_focused_test_setup_validation_failure(
    *,
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
) -> tuple[str | None, str | None, list[str], list[str]]:
    if status in {"passed", "dry_run", "skipped"}:
        return None, None, [], []
    if status == "timed_out":
        return (
            "validation_timeout",
            "validation command timed out before producing a stable setup signal",
            [],
            ["raise or split the timeout only after confirming the command scope is focused"],
        )
    if status == "blocked":
        return (
            "validation_policy_or_setup_blocker",
            "validation command could not run because setup or command policy blocked it",
            [],
            ["resolve setup and command-policy blockers before interpreting validation output"],
        )

    combined = "\n".join(part for part in [stderr, stdout] if part)
    combined_lower = combined.lower()
    if "minversion" in combined_lower and "actual pytest-" in combined_lower:
        return (
            "pytest_in_tree_version_metadata",
            "pytest validation imported the repository development version below pyproject minversion",
            _diagnostic_lines(
                combined,
                ["minversion", "actual pytest-"],
            ),
            [
                "refresh the pytest setup recipe to run through the repository's supported tox/nox workflow or generated version metadata",
            ],
        )
    if "recursive dependency involving fixture 'httpbin'" in combined_lower:
        return (
            "missing_httpbin_fixture_provider",
            "requests validation requires an external httpbin fixture provider instead of the recursive local fixture alias",
            _diagnostic_lines(
                combined,
                ["recursive dependency involving fixture 'httpbin'", "tests/conftest.py"],
            ),
            [
                "narrow requests validation to issue-specific tests that do not require httpbin or add a controlled httpbin fixture provider",
            ],
        )
    if "no module named" in combined_lower:
        return (
            "missing_python_dependency",
            "validation failed because a required Python dependency was not importable",
            _diagnostic_lines(combined, ["no module named"]),
            ["extend the disposable setup recipe with the missing dependency only after review"],
        )
    if "file or directory not found" in combined_lower or "not found:" in combined_lower:
        return (
            "invalid_validation_target",
            "validation command references a test path or selector that pytest cannot find",
            _diagnostic_lines(combined, ["file or directory not found", "not found:"]),
            ["regenerate the focused validation command from current repository paths"],
        )
    if exit_code is not None:
        return (
            "unknown_validation_failure",
            f"validation command exited {exit_code} without a recognized setup diagnostic",
            _diagnostic_lines(combined, ["error", "failed", "traceback"]),
            ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
        )
    return (
        "unknown_validation_failure",
        "validation command failed without an exit code or recognized setup diagnostic",
        _diagnostic_lines(combined, ["error", "failed", "traceback"]),
        ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
    )


def _diagnostic_lines(text: str, patterns: list[str], *, limit: int = 3) -> list[str]:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    evidence: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            evidence.append(stripped[:240])
        if len(evidence) >= limit:
            break
    return evidence


def _validate_focused_test_setup_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any | None,
    policy: CommandPolicy,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
    dry_run: bool,
) -> IssueCorpusFocusedTestSetupValidationResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    setup_status = _optional_string(record.get("status")) or "unknown"
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    validation_command = _optional_string(record.get("validation_command"))
    errors: list[str] = []
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    command_result_payload: IssueCorpusFocusedTestSetupCommandResult | None = None

    workspace: Path | None = None
    if setup_status not in {"passed", "skipped"}:
        errors.append(f"setup execution status is {setup_status}")
        next_actions.append("complete setup execution before running validation")
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("setup execution record has no repo_path")
    if not validation_command:
        errors.append("setup execution record has no validation command")

    if workspace is not None and validation_command:
        decision = policy.evaluate(validation_command, workspace=workspace)
        command_result_payload = IssueCorpusFocusedTestSetupCommandResult(
            command=validation_command,
            status="dry_run" if decision.allowed else "policy_blocked",
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=decision.allowed,
            policy_reason=decision.reason,
            stdout_path=None,
            stderr_path=None,
        )
        if not decision.allowed:
            errors.append(f"validation command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusFocusedTestSetupValidationResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            setup_execution_status=setup_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            validation_command=validation_command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            failure_category="validation_policy_or_setup_blocker",
            failure_summary=(
                "validation command could not run because setup or command policy blocked it"
            ),
            failure_evidence=_dedupe_preserve_order(errors),
            command_result=command_result_payload,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "resolve setup and command-policy blockers before interpreting validation output",
                ]
            ),
        )

    if dry_run:
        return IssueCorpusFocusedTestSetupValidationResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            setup_execution_status=setup_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            validation_command=validation_command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            failure_category=None,
            failure_summary=None,
            failure_evidence=[],
            command_result=command_result_payload,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute after reviewing validation dry-run evidence"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert validation_command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    command_result = runner.run(
        command=validation_command,
        workspace=workspace,
        timeout_seconds=timeout_seconds,
    )
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(command_result.stdout, encoding="utf-8")
    stderr_path.write_text(command_result.stderr, encoding="utf-8")

    if not command_result.policy_decision.allowed:
        status = "blocked"
        errors.append(
            f"validation command rejected by policy: {command_result.policy_decision.reason}"
        )
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"validation command timed out after {timeout_seconds}s")
    elif command_result.exit_code == 0:
        status = "passed"
    else:
        status = "failed"
        warnings.append(f"validation command exited {command_result.exit_code}")
    failure_category, failure_summary, failure_evidence, failure_next_actions = (
        _classify_focused_test_setup_validation_failure(
            status=status,
            stdout=command_result.stdout,
            stderr=command_result.stderr,
            exit_code=command_result.exit_code,
        )
    )
    if failure_summary:
        warnings.append(failure_summary)

    command_result_payload = IssueCorpusFocusedTestSetupCommandResult(
        command=validation_command,
        status=status if status in {"passed", "failed", "timed_out"} else "policy_blocked",
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=command_result.policy_decision.allowed,
        policy_reason=command_result.policy_decision.reason,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
    return IssueCorpusFocusedTestSetupValidationResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        setup_execution_status=setup_status,
        setup_profile=setup_profile,
        repo_path=repo_path_value,
        validation_command=validation_command,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        failure_category=failure_category,
        failure_summary=failure_summary,
        failure_evidence=failure_evidence,
        command_result=command_result_payload,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(
            [
                *next_actions,
                *failure_next_actions,
                "use validation result as setup-readiness evidence only",
            ]
        ),
    )


def _focused_test_dependency_install_command(repo_path: str | None) -> str:
    pyproject_path = Path(repo_path) / "pyproject.toml" if repo_path else None
    if pyproject_path is not None and pyproject_path.exists():
        try:
            parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            parsed = {}
        dependency_groups = parsed.get("dependency-groups")
        if isinstance(dependency_groups, dict) and "test" in dependency_groups:
            return "python3 -m pip install -e . --group test"
    return 'python3 -m pip install -e ".[test]"'


def _focused_test_log_text(*, stdout_path: str | None, stderr_path: str | None) -> str:
    parts: list[str] = []
    for path_value in [stdout_path, stderr_path]:
        if not path_value:
            continue
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)
