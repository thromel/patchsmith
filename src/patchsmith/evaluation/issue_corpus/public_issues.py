"""Evaluation issue corpus public issues (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty, write_json
from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _load_json_record_list,
    _optional_string,
    _path_has_text,
    _records_by_task_id,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.materialize import _is_materialized_test_candidate_path
from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
    IssueCorpusPublicReproductionPlanResult,
    IssueCorpusPublicReproductionPlanSummary,
    IssueCorpusPublicReproductionSpecValidationResult,
    IssueCorpusPublicReproductionSpecValidationSummary,
)
from patchsmith.ingest import clone_or_copy_repository
from patchsmith.models import RunRequest
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files as _normalize_public_issue_fixture_files,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_source_hints as _normalize_public_issue_source_hints,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_source_hints as _public_issue_fixture_source_hints,
)
from patchsmith.public_issue_fixtures import (
    write_public_issue_fixture_files as _write_public_issue_fixture_files,
)
from patchsmith.public_issue_reports import (
    render_public_issue_failure_signal_discovery_report,
    render_public_issue_repair_attempt_report,
    render_public_issue_repair_readiness_report,
    render_public_issue_reproduction_execution_report,
    render_public_issue_reproduction_plan_report,
    render_public_issue_reproduction_spec_validation_report,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy
from patchsmith.workflow import RepairRunner


def plan_public_issue_reproductions(
    *,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
    reproduction_specs_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionPlanResult],
    IssueCorpusPublicReproductionPlanSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    focused_records = (
        _load_json_record_list(focused_plan_path, label="focused test plan results")
        if focused_plan_path is not None and focused_plan_path.exists()
        else []
    )
    focused_by_task = _records_by_task_id(focused_records)
    reproduction_specs_by_task = (
        _load_public_issue_reproduction_specs(reproduction_specs_path)
        if reproduction_specs_path is not None
        else {}
    )
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _plan_public_issue_reproduction_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=reproduction_specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    summary = summarize_public_issue_reproduction_plan(
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
    )
    write_public_issue_reproduction_plan_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_plan(
    *,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> IssueCorpusPublicReproductionPlanSummary:
    return IssueCorpusPublicReproductionPlanSummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(1 for result in results if result.manual_spec_required),
        command_count=sum(1 for result in results if result.reproduction_command),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
    )


def write_public_issue_reproduction_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
    summary: IssueCorpusPublicReproductionPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_plan_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_plan_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_specs_template.json",
        _public_issue_reproduction_specs_template(results),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_plan_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "focused_files",
                "fixture_paths",
                "expected_failure_signals",
                "manual_spec_required",
                "evidence",
                "blockers",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "focused_files": ";".join(result.focused_files),
                    "fixture_paths": ";".join(_public_issue_fixture_paths(result.fixture_files)),
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_plan_report.md").write_text(
        render_public_issue_reproduction_plan_report(
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def validate_public_issue_reproduction_specs(
    *,
    specs_path: Path,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionSpecValidationResult],
    IssueCorpusPublicReproductionSpecValidationSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    focused_records = (
        _load_json_record_list(focused_plan_path, label="focused test plan results")
        if focused_plan_path is not None and focused_plan_path.exists()
        else []
    )
    focused_by_task = _records_by_task_id(focused_records)
    specs_by_task = _load_public_issue_reproduction_specs(specs_path)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    task_ids = {task_dir.name for task_dir in task_dirs}
    results = [
        _validate_public_issue_reproduction_spec_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    for extra_task_id in sorted(set(specs_by_task) - task_ids):
        results.append(
            IssueCorpusPublicReproductionSpecValidationResult(
                task_id=extra_task_id,
                repository=_optional_string(specs_by_task[extra_task_id].get("repository")),
                issue_url=_optional_string(specs_by_task[extra_task_id].get("issue_url")),
                status="blocked",
                spec_present=True,
                repo_path=None,
                repo_exists=False,
                reproduction_command=_optional_string(specs_by_task[extra_task_id].get("command")),
                command_source="reproduction_spec",
                policy_allowed=False,
                policy_reason=None,
                fixture_files=_normalize_public_issue_fixture_files(
                    specs_by_task[extra_task_id].get("fixture_files")
                )[0],
                source_hints=_normalize_public_issue_source_hints(
                    specs_by_task[extra_task_id].get("source_hints")
                )[0],
                expected_failure_signals=_string_list(
                    specs_by_task[extra_task_id].get("expected_failure_signals")
                ),
                errors=["reproduction spec task_id has no materialized task"],
                warnings=[],
                evidence=["reviewed reproduction spec found"],
                next_actions=[
                    "remove the extra spec or materialize the matching public issue task"
                ],
            )
        )
    summary = summarize_public_issue_reproduction_spec_validation(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        spec_count=len(specs_by_task),
        results=results,
    )
    write_public_issue_reproduction_spec_validation_outputs(
        output_dir=output_dir,
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_spec_validation(
    *,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    spec_count: int,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
) -> IssueCorpusPublicReproductionSpecValidationSummary:
    return IssueCorpusPublicReproductionSpecValidationSummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        specs_path=str(specs_path),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        spec_count=spec_count,
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        missing_spec_tasks=sum(1 for result in results if not result.spec_present),
        empty_signal_tasks=sum(1 for result in results if not result.expected_failure_signals),
        policy_blocked_tasks=sum(
            1 for result in results if result.reproduction_command and not result.policy_allowed
        ),
        extra_spec_tasks=sum(
            1
            for result in results
            if "reproduction spec task_id has no materialized task" in result.errors
        ),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
        unsafe_fixture_tasks=sum(
            1 for result in results if any("fixture_files" in error for error in result.errors)
        ),
    )


def write_public_issue_reproduction_spec_validation_outputs(
    *,
    output_dir: Path,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
    summary: IssueCorpusPublicReproductionSpecValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_spec_validation_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_spec_validation_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_spec_validation_results.csv").open(
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
                "spec_present",
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "fixture_paths",
                "expected_failure_signals",
                "errors",
                "warnings",
                "evidence",
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
                    "spec_present": result.spec_present,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fixture_paths": ";".join(_public_issue_fixture_paths(result.fixture_files)),
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_spec_validation_report.md").write_text(
        render_public_issue_reproduction_spec_validation_report(
            specs_path=specs_path,
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def discover_public_issue_failure_signals(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicFailureSignalDiscoveryResult],
    IssueCorpusPublicFailureSignalDiscoverySummary,
]:
    records = _load_json_record_list(path=plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            network=sandbox_network,
        )
    )
    policy = CommandPolicy()
    run_logs_dir = output_dir / "public_issue_failure_signal_discovery_logs"
    results = [
        _discover_public_issue_failure_signal_record(
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
    summary = summarize_public_issue_failure_signal_discovery(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_failure_signal_discovery_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_failure_signal_discovery(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicFailureSignalDiscoverySummary:
    return IssueCorpusPublicFailureSignalDiscoverySummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"observed_failure", "passed", "timed_out", "failed"}
        ),
        observed_failure_tasks=sum(1 for result in results if result.status == "observed_failure"),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        candidate_signal_tasks=sum(1 for result in results if result.candidate_failure_signals),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def write_public_issue_failure_signal_discovery_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_failure_signal_discovery_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_failure_signal_discovery_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_failure_signal_discovery_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "candidate_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "candidate_failure_signals": ";".join(result.candidate_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_failure_signal_discovery_report.md").write_text(
        render_public_issue_failure_signal_discovery_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _public_issue_reproduction_specs_template(
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "claim_boundary": [
            "This template is for reviewed public issue reproduction criteria.",
            "Do not count a task as reproduced until execute-public-issue-reproductions records a nonzero exit and matches every expected failure signal.",
            "Keep commands within the normal PatchSmith command policy, such as python3 -m pytest.",
        ],
        "specs": [
            {
                "task_id": result.task_id,
                "repository": result.repository,
                "issue_url": result.issue_url,
                "command": result.reproduction_command,
                "fixture_files": [],
                "expected_failure_signals": [],
                "review_notes": (
                    "Fill after reviewing the issue-specific failing traceback, "
                    "assertion, or behavior mismatch."
                ),
            }
            for result in results
        ],
    }


def execute_public_issue_reproductions(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicReproductionExecutionResult],
    IssueCorpusPublicReproductionExecutionSummary,
]:
    records = _load_json_record_list(plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "public_issue_reproductions"
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
        _execute_public_issue_reproduction_record(
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
    summary = summarize_public_issue_reproduction_execution(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_reproduction_execution_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_execution(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicReproductionExecutionSummary:
    return IssueCorpusPublicReproductionExecutionSummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"reproduced", "not_reproduced", "failed", "timed_out"}
        ),
        reproduced_tasks=sum(1 for result in results if result.status == "reproduced"),
        not_reproduced_tasks=sum(1 for result in results if result.status == "not_reproduced"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(1 for result in results if result.manual_spec_required),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def write_public_issue_reproduction_execution_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_execution_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_execution_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_execution_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "expected_failure_signals",
                "manual_spec_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "matched_failure_signals",
                "missing_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "matched_failure_signals": ";".join(result.matched_failure_signals),
                    "missing_failure_signals": ";".join(result.missing_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_execution_report.md").write_text(
        render_public_issue_reproduction_execution_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def check_public_issue_repair_readiness(
    *,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    reproduction_execution_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicRepairReadinessResult],
    IssueCorpusPublicRepairReadinessSummary,
]:
    focused_records = _load_json_record_list(focused_run_path, label="focused test run results")
    diagnosis_records = _load_json_record_list(
        diagnosis_path, label="focused test diagnosis results"
    )
    setup_validation_records = _load_json_record_list(
        setup_validation_path, label="focused test setup validation results"
    )
    reproduction_execution_records = (
        _load_json_record_list(
            reproduction_execution_path,
            label="public issue reproduction execution results",
        )
        if reproduction_execution_path is not None and reproduction_execution_path.exists()
        else []
    )
    manifests = _load_public_issue_task_manifests(tasks_dir)
    diagnosis_by_task = _records_by_task_id(diagnosis_records)
    setup_validation_by_task = _records_by_task_id(setup_validation_records)
    reproduction_execution_by_task = _records_by_task_id(reproduction_execution_records)
    results = [
        _check_public_issue_repair_readiness_record(
            focused_record=record,
            diagnosis_record=diagnosis_by_task.get(_optional_string(record.get("task_id")) or ""),
            setup_validation_record=setup_validation_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            reproduction_execution_record=reproduction_execution_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
        )
        for record in focused_records
    ]
    summary = summarize_public_issue_repair_readiness(
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path if reproduction_execution_records else None
        ),
        results=results,
    )
    write_public_issue_repair_readiness_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path if reproduction_execution_records else None
        ),
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_repair_readiness(
    *,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
) -> IssueCorpusPublicRepairReadinessSummary:
    return IssueCorpusPublicRepairReadinessSummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        focused_run_path=str(focused_run_path),
        diagnosis_path=str(diagnosis_path),
        setup_validation_path=str(setup_validation_path),
        reproduction_execution_path=(
            str(reproduction_execution_path) if reproduction_execution_path is not None else None
        ),
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        repair_command_tasks=sum(1 for result in results if result.repair_command),
        passed_focused_tasks=sum(1 for result in results if result.focused_run_status == "passed"),
        passed_setup_validation_tasks=sum(
            1 for result in results if result.setup_validation_status == "passed"
        ),
        reproduced_tasks=sum(
            1 for result in results if result.reproduction_execution_status == "reproduced"
        ),
        missing_reproduction_tasks=sum(
            1 for result in results if result.reproduction_execution_status != "reproduced"
        ),
    )


def write_public_issue_repair_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
    summary: IssueCorpusPublicRepairReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_repair_readiness_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_repair_readiness_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_repair_readiness_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "validation_fixture_paths",
                "focused_run_status",
                "diagnosis_category",
                "setup_validation_status",
                "setup_failure_category",
                "reproduction_execution_status",
                "reproduction_stdout_path",
                "reproduction_stderr_path",
                "matched_failure_signals",
                "sandbox_mode",
                "sandbox_network",
                "evidence",
                "blockers",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "validation_fixture_paths": ";".join(result.validation_fixture_paths),
                    "focused_run_status": result.focused_run_status,
                    "diagnosis_category": result.diagnosis_category,
                    "setup_validation_status": result.setup_validation_status,
                    "setup_failure_category": result.setup_failure_category,
                    "reproduction_execution_status": (result.reproduction_execution_status),
                    "reproduction_stdout_path": result.reproduction_stdout_path,
                    "reproduction_stderr_path": result.reproduction_stderr_path,
                    "matched_failure_signals": ";".join(result.matched_failure_signals),
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_network": result.sandbox_network,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_readiness_report.md").write_text(
        render_public_issue_repair_readiness_report(
            tasks_dir=tasks_dir,
            focused_run_path=focused_run_path,
            diagnosis_path=diagnosis_path,
            setup_validation_path=setup_validation_path,
            reproduction_execution_path=reproduction_execution_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def execute_public_issue_repairs(
    *,
    readiness_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    runtime: str = "langgraph",
    planner: str = "fake_model",
    context_provider: str = "native_hybrid",
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    max_retries: int = 0,
    max_tasks: int | None = None,
    dry_run: bool = True,
    allow_warnings: bool = False,
) -> tuple[
    list[IssueCorpusPublicRepairAttemptResult],
    IssueCorpusPublicRepairAttemptSummary,
]:
    records = _load_json_record_list(
        readiness_path,
        label="public issue repair readiness results",
    )
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    manifests = _load_public_issue_task_manifests(tasks_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None if dry_run else RepairRunner(artifacts_dir=output_dir / "public_issue_repair_attempts")
    )
    results = [
        _execute_public_issue_repair_record(
            record=record,
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
            runner=runner,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            max_retries=max_retries,
            dry_run=dry_run,
            allow_warnings=allow_warnings,
        )
        for record in selected_records
    ]
    summary = summarize_public_issue_repair_attempts(
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        max_retries=max_retries,
    )
    write_public_issue_repair_attempt_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_repair_attempts(
    *,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    dry_run: bool,
    allow_warnings: bool,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    max_retries: int,
) -> IssueCorpusPublicRepairAttemptSummary:
    return IssueCorpusPublicRepairAttemptSummary(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        readiness_path=str(readiness_path),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        max_retries=max_retries,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(1 for result in results if result.status in {"validated", "failed"}),
        validated_tasks=sum(1 for result in results if result.status == "validated"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        reproduced_input_tasks=sum(
            1 for result in results if result.reproduction_execution_status == "reproduced"
        ),
    )


def write_public_issue_repair_attempt_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    summary: IssueCorpusPublicRepairAttemptSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_repair_attempt_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_repair_attempt_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_repair_attempt_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "validation_fixture_paths",
                "reproduction_execution_status",
                "runtime",
                "planner",
                "context_provider",
                "sandbox_mode",
                "sandbox_image",
                "dry_run",
                "run_id",
                "run_status",
                "report_path",
                "trace_path",
                "final_diff_path",
                "test_exit_code",
                "patch_generated",
                "errors",
                "warnings",
                "evidence",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "validation_fixture_paths": ";".join(result.validation_fixture_paths),
                    "reproduction_execution_status": (result.reproduction_execution_status),
                    "runtime": result.runtime,
                    "planner": result.planner,
                    "context_provider": result.context_provider,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "dry_run": result.dry_run,
                    "run_id": result.run_id,
                    "run_status": result.run_status,
                    "report_path": result.report_path,
                    "trace_path": result.trace_path,
                    "final_diff_path": result.final_diff_path,
                    "test_exit_code": result.test_exit_code,
                    "patch_generated": result.patch_generated,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_attempt_report.md").write_text(
        render_public_issue_repair_attempt_report(
            readiness_path=readiness_path,
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _plan_public_issue_reproduction_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionPlanResult:
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []
    next_actions: list[str] = []

    if not manifest_path.exists():
        blockers.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            blockers.append(f"task_manifest.json is invalid JSON: {error.msg}")
        else:
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                blockers.append("task_manifest.json must contain a JSON object")

    task_id = _optional_string(manifest.get("task_id")) or task_dir.name
    issue = dict_or_empty(manifest.get("issue"))
    snapshot = dict_or_empty(manifest.get("repository_snapshot"))
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    reproduction = dict_or_empty(manifest.get("reproduction"))
    spec_reproduction = reproduction_spec if isinstance(reproduction_spec, dict) else {}
    repository = _optional_string(issue.get("repository"))
    issue_url = _optional_string(issue.get("issue_url"))
    repo_path = _optional_string(snapshot.get("repo_path")) or (
        _optional_string(focused_record.get("repo_path")) if focused_record else None
    )
    focused_files = _string_list(focused_record.get("focused_files")) if focused_record else []
    if not focused_files:
        focused_files = [
            path
            for path in _string_list(retrieval.get("retrieved_files"))
            if _is_materialized_test_candidate_path(path)
        ][:2]
    spec_command = _optional_string(spec_reproduction.get("command"))
    explicit_command = _optional_string(reproduction.get("command"))
    focused_command = _optional_string(focused_record.get("command")) if focused_record else None
    test_commands = _string_list(snapshot.get("test_commands"))
    if spec_command:
        command = spec_command
        command_source = "reproduction_spec"
        evidence.append("reproduction spec provides an explicit command")
    elif explicit_command:
        command = explicit_command
        command_source = "manifest_reproduction"
        evidence.append("manifest contains an explicit reproduction command")
    elif focused_command:
        command = focused_command
        command_source = "focused_test_plan"
        evidence.append("focused test plan provides the reproduction candidate command")
    elif test_commands:
        command = test_commands[0]
        command_source = "repository_test_command"
        warnings.append("using broad repository test command as reproduction candidate")
    else:
        command = None
        command_source = "missing"
        blockers.append("no reproduction or focused test command is available")

    spec_failure_signals = _string_list(spec_reproduction.get("expected_failure_signals"))
    manifest_failure_signals = _string_list(reproduction.get("expected_failure_signals"))
    expected_failure_signals = spec_failure_signals or manifest_failure_signals
    if "fixture_files" in spec_reproduction:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            spec_reproduction.get("fixture_files")
        )
        fixture_source = "reproduction spec"
    else:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            reproduction.get("fixture_files")
        )
        fixture_source = "task manifest"
    if fixture_errors:
        blockers.extend(fixture_errors)
    elif fixture_files:
        evidence.append(f"{fixture_source} provides {len(fixture_files)} temporary fixture file(s)")
    source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        spec_reproduction.get("source_hints")
    )
    if source_hint_errors:
        blockers.extend(source_hint_errors)
    elif source_hints:
        evidence.append(f"reproduction spec provides {len(source_hints)} reviewed source hint(s)")
    manual_spec_required = not expected_failure_signals
    if expected_failure_signals:
        if spec_failure_signals:
            evidence.append("expected failing signal is encoded in the reproduction spec")
        else:
            evidence.append("expected failing signal is encoded in the task manifest")
    else:
        warnings.append("expected failing signal is not encoded")
        next_actions.append(
            "add issue-specific expected failure text, assertion, traceback, or exit criteria"
        )

    workspace = Path.cwd()
    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if repo_exists:
            workspace = repo
            evidence.append("repository snapshot exists")
        else:
            blockers.append(f"repository snapshot is missing: {repo_path}")
    else:
        blockers.append("repository_snapshot.repo_path is missing")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if decision.allowed:
            evidence.append("reproduction command is allowed by command policy")
        else:
            blockers.append(f"reproduction command rejected by policy: {decision.reason}")

    if focused_record is None and command_source not in {
        "manifest_reproduction",
        "reproduction_spec",
    }:
        warnings.append("focused test plan record is missing")
        next_actions.append("regenerate `plan-materialized-focused-tests` before execution")
    if command and not blockers and not manual_spec_required:
        next_actions.append("execute reproduction command and save failing stdout/stderr evidence")
    elif command and not blockers:
        next_actions.append("review and encode the expected failing signal before execution")

    status = "blocked" if blockers else "warning" if warnings else "planned"
    return IssueCorpusPublicReproductionPlanResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        reproduction_command=command,
        command_source=command_source,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        focused_files=focused_files,
        fixture_files=fixture_files,
        source_hints=source_hints,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        evidence=_dedupe_preserve_order(evidence),
        blockers=_dedupe_preserve_order(blockers),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _validate_public_issue_reproduction_spec_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionSpecValidationResult:
    planned = _plan_public_issue_reproduction_record(
        task_dir=task_dir,
        focused_record=focused_record,
        reproduction_spec=reproduction_spec,
        policy=policy,
    )
    errors = list(planned.blockers)
    warnings = list(planned.warnings)
    evidence = list(planned.evidence)
    next_actions = list(planned.next_actions)
    spec_present = reproduction_spec is not None

    if spec_present:
        evidence.append("reviewed reproduction spec found")
    else:
        errors.append("reviewed reproduction spec is missing")
        next_actions.append(
            "fill public_issue_reproduction_specs_template.json and rerun validation"
        )

    if not planned.expected_failure_signals:
        errors.append("expected_failure_signals is empty")
        next_actions.append(
            "encode at least one exact failing assertion, traceback, or behavior signal"
        )

    if not planned.reproduction_command:
        errors.append("reproduction command is missing")
    elif not planned.policy_allowed:
        errors.append(
            f"reproduction command rejected by policy: {planned.policy_reason or 'unknown'}"
        )

    if planned.command_source != "reproduction_spec":
        warnings.append(
            "reproduction spec does not override the command; using planned fallback command"
        )

    status = "blocked" if errors else "warning" if warnings else "ready"
    return IssueCorpusPublicReproductionSpecValidationResult(
        task_id=planned.task_id,
        repository=planned.repository,
        issue_url=planned.issue_url,
        status=status,
        spec_present=spec_present,
        repo_path=planned.repo_path,
        repo_exists=planned.repo_exists,
        reproduction_command=planned.reproduction_command,
        command_source=planned.command_source,
        policy_allowed=planned.policy_allowed,
        policy_reason=planned.policy_reason,
        fixture_files=planned.fixture_files,
        source_hints=planned.source_hints,
        expected_failure_signals=planned.expected_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _discover_public_issue_failure_signal_record(
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
) -> IssueCorpusPublicFailureSignalDiscoveryResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    _source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        record.get("source_hints")
    )
    errors.extend(fixture_errors)
    errors.extend(source_hint_errors)
    policy_allowed = False
    policy_reason: str | None = None
    workspace: Path | None = None

    if plan_status == "blocked":
        errors.append("reproduction plan is blocked")
    elif plan_status not in {"planned", "warning"}:
        warnings.append(f"reproduction plan status is {plan_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("reproduction plan record has no repo_path")

    if not command:
        errors.append("reproduction command is missing")
    elif workspace is not None:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"reproduction command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve discovery blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "rerun with --execute to observe candidate failure logs",
                ]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_files:
            with tempfile.TemporaryDirectory(prefix="patchsmith-public-repro-fixtures-") as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(str(workspace), fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=fixture_files,
                )
                command_result = runner.run(
                    command=command,
                    workspace=snapshot.repo_path,
                    timeout_seconds=timeout_seconds,
                )
        else:
            command_result = runner.run(
                command=command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
    except (OSError, ValueError) as error:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(
                [*errors, f"failed to prepare fixture workspace: {error}"]
            ),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve fixture workspace preparation before execution"]
            ),
        )
    stdout_file = run_dir / "stdout.txt"
    stderr_file = run_dir / "stderr.txt"
    stdout_file.write_text(command_result.stdout, encoding="utf-8")
    stderr_file.write_text(command_result.stderr, encoding="utf-8")
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    candidate_failure_signals = _candidate_failure_signals_from_logs(combined_logs)
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason

    if not policy_allowed:
        status = "blocked"
        errors.append(f"reproduction command rejected by policy: {policy_reason or 'unknown'}")
        next_actions.append("resolve command-policy blockers before discovery")
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"candidate command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif command_result.exit_code == 0:
        status = "passed"
        warnings.append("candidate command passed; no failure signal was observed")
        next_actions.append(
            "write or select a more specific issue reproduction before repair attempts"
        )
    elif candidate_failure_signals:
        status = "observed_failure"
        next_actions.append(
            "review candidate_failure_signals and copy exact issue-specific signals into reviewed specs"
        )
    else:
        status = "failed"
        warnings.append("candidate command failed but no concise failure signal was extracted")
        next_actions.append("inspect saved stdout/stderr and choose reviewed failure signals")

    return IssueCorpusPublicFailureSignalDiscoveryResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=str(stdout_file),
        stderr_path=str(stderr_file),
        fixture_paths=fixture_paths,
        candidate_failure_signals=candidate_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_public_issue_reproduction_record(
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
) -> IssueCorpusPublicReproductionExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    expected_failure_signals = _string_list(record.get("expected_failure_signals"))
    manual_spec_required = record.get("manual_spec_required") is True or not (
        expected_failure_signals
    )
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        record.get("source_hints")
    )
    errors.extend(fixture_errors)
    errors.extend(source_hint_errors)

    exit_code: int | None = None
    timed_out = False
    duration_ms = 0
    policy_allowed = False
    policy_reason: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    matched_failure_signals: list[str] = []
    missing_failure_signals = list(expected_failure_signals)

    workspace: Path | None = None
    if plan_status == "blocked":
        errors.append("reproduction plan is blocked")
    elif plan_status not in {"planned", "warning"}:
        warnings.append(f"reproduction plan status is {plan_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("reproduction plan record has no repo_path")

    if not command:
        errors.append("reproduction command is missing")
    elif workspace is not None:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"reproduction command rejected by policy: {decision.reason}")

    if manual_spec_required:
        errors.append("expected failing signal is not encoded")
        next_actions.append(
            "encode an issue-specific expected failure signal before executing reproduction"
        )

    if errors:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve reproduction blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute to save failing reproduction logs"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_files:
            with tempfile.TemporaryDirectory(prefix="patchsmith-public-repro-fixtures-") as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(str(workspace), fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=fixture_files,
                )
                command_result = runner.run(
                    command=command,
                    workspace=snapshot.repo_path,
                    timeout_seconds=timeout_seconds,
                )
        else:
            command_result = runner.run(
                command=command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
    except (OSError, ValueError) as error:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=_dedupe_preserve_order(
                [*errors, f"failed to prepare fixture workspace: {error}"]
            ),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve fixture workspace preparation before execution"]
            ),
        )
    stdout_file = run_dir / "stdout.txt"
    stderr_file = run_dir / "stderr.txt"
    stdout_file.write_text(command_result.stdout, encoding="utf-8")
    stderr_file.write_text(command_result.stderr, encoding="utf-8")

    exit_code = command_result.exit_code
    timed_out = command_result.timed_out
    duration_ms = command_result.duration_ms
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason
    stdout_path = str(stdout_file)
    stderr_path = str(stderr_file)
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    matched_failure_signals = _matched_expected_failure_signals(
        combined_logs,
        expected_failure_signals,
    )
    matched_set = set(matched_failure_signals)
    missing_failure_signals = [
        signal for signal in expected_failure_signals if signal not in matched_set
    ]

    if not policy_allowed:
        status = "blocked"
        errors.append(f"reproduction command rejected by policy: {policy_reason or 'unknown'}")
        next_actions.append("resolve command-policy blockers before execution")
    elif timed_out:
        status = "timed_out"
        warnings.append(f"reproduction command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif exit_code == 0:
        status = "not_reproduced"
        warnings.append("reproduction command passed; expected pre-repair failure was absent")
        next_actions.append(
            "confirm whether the issue is already fixed or update the reproduction command"
        )
    elif missing_failure_signals:
        status = "failed"
        warnings.append("reproduction command failed without all expected failure signals")
        next_actions.append(
            "inspect saved stdout/stderr and update expected failure criteria if appropriate"
        )
    else:
        status = "reproduced"
        next_actions.append("use the saved failing logs as pre-repair reproduction evidence")

    return IssueCorpusPublicReproductionExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        fixture_files=fixture_files,
        fixture_paths=fixture_paths,
        source_hints=source_hints,
        matched_failure_signals=matched_failure_signals,
        missing_failure_signals=missing_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _check_public_issue_repair_readiness_record(
    *,
    focused_record: dict[str, Any],
    diagnosis_record: dict[str, Any] | None,
    setup_validation_record: dict[str, Any] | None,
    reproduction_execution_record: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> IssueCorpusPublicRepairReadinessResult:
    task_id = _optional_string(focused_record.get("task_id"))
    repository = _optional_string(focused_record.get("repository"))
    issue_url = _optional_string(focused_record.get("issue_url"))
    repo_path = _optional_string(focused_record.get("repo_path"))
    focused_status = _optional_string(focused_record.get("status"))
    focused_command = _optional_string(focused_record.get("command"))
    diagnosis_category = (
        _optional_string(diagnosis_record.get("category")) if diagnosis_record is not None else None
    )
    diagnosis_severity = (
        _optional_string(diagnosis_record.get("severity")) if diagnosis_record is not None else None
    )
    setup_status = (
        _optional_string(setup_validation_record.get("status"))
        if setup_validation_record is not None
        else None
    )
    setup_failure_category = (
        _optional_string(setup_validation_record.get("failure_category"))
        if setup_validation_record is not None
        else None
    )
    setup_validation_command = (
        _optional_string(setup_validation_record.get("validation_command"))
        if setup_validation_record is not None
        else focused_command
    )
    sandbox_mode = (
        _optional_string(setup_validation_record.get("sandbox_mode"))
        if setup_validation_record is not None
        else None
    )
    sandbox_network = (
        _optional_string(setup_validation_record.get("sandbox_network"))
        if setup_validation_record is not None
        else None
    )
    reproduction_execution_status = (
        _optional_string(reproduction_execution_record.get("status"))
        if reproduction_execution_record is not None
        else None
    )
    reproduction_stdout_path = (
        _optional_string(reproduction_execution_record.get("stdout_path"))
        if reproduction_execution_record is not None
        else None
    )
    reproduction_stderr_path = (
        _optional_string(reproduction_execution_record.get("stderr_path"))
        if reproduction_execution_record is not None
        else None
    )
    matched_failure_signals = (
        _string_list(reproduction_execution_record.get("matched_failure_signals"))
        if reproduction_execution_record is not None
        else []
    )
    reproduction_command = (
        _optional_string(reproduction_execution_record.get("reproduction_command"))
        if reproduction_execution_record is not None
        else None
    )
    validation_fixture_files, fixture_errors = (
        _normalize_public_issue_fixture_files(reproduction_execution_record.get("fixture_files"))
        if reproduction_execution_record is not None
        else ([], [])
    )
    validation_fixture_paths = _public_issue_fixture_paths(validation_fixture_files)
    validation_source_hints, source_hint_errors = (
        _normalize_public_issue_source_hints(reproduction_execution_record.get("source_hints"))
        if reproduction_execution_record is not None
        else ([], [])
    )
    validation_command = (
        reproduction_command
        if reproduction_execution_status == "reproduced" and reproduction_command
        else setup_validation_command
    )
    repair_command = _first_manifest_repair_command(manifest)

    evidence: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []
    blockers.extend(fixture_errors)
    blockers.extend(source_hint_errors)

    if not task_id:
        blockers.append("focused run record has no task_id")
    if repo_path:
        repo_exists = Path(repo_path).is_dir()
        if repo_exists:
            evidence.append("repository snapshot exists")
        else:
            blockers.append(f"repository snapshot is missing: {repo_path}")
    else:
        repo_exists = False
        blockers.append("focused run record has no repo_path")

    if focused_status == "passed":
        evidence.append("focused validation command passed before repair")
        if reproduction_execution_status == "reproduced":
            evidence.append("separate reproduction execution provides failing pre-repair evidence")
        else:
            warnings.append(
                "pre-repair focused command passed; issue reproduction is not proven by saved evidence"
            )
            next_actions.append(
                "record an issue-specific failing reproduction or keep repair-quality claims scoped"
            )
    elif focused_status in {"failed", "timed_out"}:
        if diagnosis_category == "nonzero_exit":
            evidence.append("focused command failed with an unclassified nonzero exit")
            warnings.append(
                "focused command failed; confirm the failure reproduces the public issue before repair"
            )
            next_actions.append(
                "capture the expected failing assertion or traceback before using this as a repair target"
            )
        else:
            blockers.append(f"focused run status is {focused_status}")
            next_actions.append("resolve focused test execution before repair attempts")
    else:
        blockers.append(f"focused run status is {focused_status or 'missing'}")

    if diagnosis_record is None:
        blockers.append("focused diagnosis record is missing")
    elif diagnosis_category == "focused_test_passed":
        evidence.append("focused diagnosis confirms runnable validation")
    elif diagnosis_severity in {"dependency", "environment", "blocked"}:
        blockers.append(
            f"focused diagnosis is {diagnosis_category or 'unknown'} with {diagnosis_severity} severity"
        )
    else:
        warnings.append(f"focused diagnosis is {diagnosis_category or 'unknown'}")

    if setup_validation_record is None:
        blockers.append("setup validation record is missing")
    elif setup_status == "passed":
        evidence.append("post-setup validation command passed")
    elif setup_status == "dry_run":
        blockers.append("setup validation was only dry-run")
        next_actions.append("execute setup validation before repair attempts")
    else:
        blockers.append(f"setup validation status is {setup_status or 'missing'}")
        if setup_failure_category:
            blockers.append(f"setup validation failure category is {setup_failure_category}")

    if reproduction_execution_record is None:
        warnings.append("public issue reproduction execution record is missing")
        next_actions.append("run `execute-public-issue-reproductions` before repair attempts")
    elif reproduction_execution_status == "reproduced":
        evidence.append("public issue reproduction execution saved failing evidence")
        if reproduction_command:
            evidence.append("issue-specific reproduction command selected for repair validation")
        if validation_fixture_paths:
            evidence.append(
                "repair validation fixtures selected: " + ", ".join(validation_fixture_paths)
            )
        if validation_source_hints:
            evidence.append("reviewed source hints selected: " + ", ".join(validation_source_hints))
        if reproduction_stdout_path:
            evidence.append(f"reproduction stdout saved: {reproduction_stdout_path}")
        if reproduction_stderr_path:
            evidence.append(f"reproduction stderr saved: {reproduction_stderr_path}")
        if matched_failure_signals:
            evidence.append("matched reproduction signal: " + "; ".join(matched_failure_signals))
    elif reproduction_execution_status == "dry_run":
        warnings.append("public issue reproduction execution is only dry-run")
        next_actions.append("rerun reproduction execution with --execute after review")
    elif reproduction_execution_status == "blocked":
        warnings.append("public issue reproduction execution is blocked")
        next_actions.append("resolve reproduction execution blockers before repair attempts")
    elif reproduction_execution_status == "not_reproduced":
        warnings.append("public issue reproduction command did not fail as expected")
        next_actions.append("confirm whether the issue is already fixed or update reproduction")
    else:
        warnings.append(
            f"public issue reproduction execution status is {reproduction_execution_status or 'missing'}"
        )
        next_actions.append("inspect reproduction execution logs before repair attempts")

    if repair_command:
        evidence.append("saved PatchSmith repair command is available")
    else:
        blockers.append("saved PatchSmith repair command is missing")
        next_actions.append("regenerate materialized public issue tasks with suggested commands")

    if validation_command:
        if validation_command == reproduction_command:
            evidence.append("issue-specific validation command is available")
        else:
            evidence.append("focused validation command is available")
    else:
        blockers.append("validation command is missing")

    if sandbox_mode == "docker":
        evidence.append(f"setup validation used Docker network {sandbox_network or 'unknown'}")
    if sandbox_network == "bridge":
        warnings.append("repair validation depends on Docker bridge networking")

    if not blockers and not next_actions:
        next_actions.append("run a bounded PatchSmith repair attempt and save normal run artifacts")
    elif not blockers:
        next_actions.append("run repair only after accepting the listed caveats")

    status = "blocked" if blockers else "warning" if warnings else "ready"
    return IssueCorpusPublicRepairReadinessResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        repair_command=repair_command,
        validation_command=validation_command,
        validation_fixture_files=validation_fixture_files,
        validation_fixture_paths=validation_fixture_paths,
        validation_source_hints=validation_source_hints,
        focused_run_status=focused_status,
        diagnosis_category=diagnosis_category,
        setup_validation_status=setup_status,
        setup_failure_category=setup_failure_category,
        reproduction_execution_status=reproduction_execution_status,
        reproduction_stdout_path=reproduction_stdout_path,
        reproduction_stderr_path=reproduction_stderr_path,
        matched_failure_signals=matched_failure_signals,
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        evidence=_dedupe_preserve_order(evidence),
        blockers=_dedupe_preserve_order(blockers),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_public_issue_repair_record(
    *,
    record: dict[str, Any],
    manifest: dict[str, Any] | None,
    runner: RepairRunner | None,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    max_retries: int,
    dry_run: bool,
    allow_warnings: bool,
) -> IssueCorpusPublicRepairAttemptResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    readiness_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    repair_command = _optional_string(record.get("repair_command"))
    validation_command = _optional_string(record.get("validation_command"))
    validation_fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("validation_fixture_files")
    )
    validation_fixture_paths = _public_issue_fixture_paths(validation_fixture_files)
    validation_source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        record.get("validation_source_hints")
    )
    reproduction_execution_status = _optional_string(record.get("reproduction_execution_status"))
    errors = _string_list(record.get("blockers"))
    errors.extend(fixture_errors)
    errors.extend(source_hint_errors)
    warnings = _string_list(record.get("warnings"))
    evidence = _string_list(record.get("evidence"))
    next_actions = _string_list(record.get("next_actions"))
    run_id: str | None = None
    run_status: str | None = None
    report_path: str | None = None
    trace_path: str | None = None
    final_diff_path: str | None = None
    test_exit_code: int | None = None
    patch_generated = False

    repo_exists = False
    if repo_path_value:
        repo_path = Path(repo_path_value)
        repo_exists = repo_path.exists() and repo_path.is_dir()
        if not repo_exists:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("repair-readiness record has no repo_path")

    issue_text = _public_issue_repair_issue_text(manifest)
    if not issue_text:
        errors.append("materialized issue text is missing")
    if not repair_command:
        errors.append("repair command is missing")
    if not validation_command:
        errors.append("validation command is missing")
    if reproduction_execution_status != "reproduced":
        errors.append("public issue reproduction has not been proven")
        next_actions.append("execute reproduction and save failing logs before repair")
    if readiness_status == "blocked":
        errors.append("repair readiness is blocked")
    elif readiness_status == "warning" and not allow_warnings:
        errors.append("repair readiness is warning and --allow-warnings was not set")
    elif readiness_status not in {"ready", "warning"}:
        warnings.append(f"repair readiness status is {readiness_status}")

    if errors:
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            validation_fixture_paths=validation_fixture_paths,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status=run_status,
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order(evidence),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve public repair-attempt blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            validation_fixture_paths=validation_fixture_paths,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status=run_status,
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order([*evidence, "repair attempt passed dry-run gating"]),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute to launch PatchSmith repair"]
            ),
        )

    assert runner is not None
    assert repo_path_value is not None
    assert issue_text is not None
    run_repo = repo_path_value
    source_hints = _dedupe_preserve_order(
        [
            *validation_source_hints,
            *_public_issue_fixture_source_hints(
                repo_path=Path(repo_path_value),
                fixture_files=validation_fixture_files,
            ),
        ]
    )
    run_issue_text = _public_issue_repair_attempt_issue_text(
        issue_text=issue_text,
        validation_command=validation_command,
        validation_fixture_paths=validation_fixture_paths,
        validation_fixture_files=validation_fixture_files,
        source_hints=source_hints,
    )
    context_paths = tuple(_source_hint_file_paths(source_hints))
    try:
        if validation_fixture_files:
            with tempfile.TemporaryDirectory(
                prefix="patchsmith-public-repair-fixtures-"
            ) as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(repo_path_value, fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=validation_fixture_files,
                )
                run_repo = str(snapshot.repo_path)
                run_result = runner.run(
                    RunRequest(
                        repo=run_repo,
                        issue_text=run_issue_text,
                        issue_url=issue_url,
                        test_command=validation_command,
                        runtime=runtime,
                        planner=planner,
                        max_retries=max_retries,
                        context_provider=context_provider,
                        sandbox_mode=sandbox_mode,
                        sandbox_image=sandbox_image,
                        context_paths=context_paths,
                    )
                )
        else:
            run_result = runner.run(
                RunRequest(
                    repo=run_repo,
                    issue_text=run_issue_text,
                    issue_url=issue_url,
                    test_command=validation_command,
                    runtime=runtime,
                    planner=planner,
                    max_retries=max_retries,
                    context_provider=context_provider,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                    context_paths=context_paths,
                )
            )
    except Exception as error:
        errors.append(f"PatchSmith repair run failed: {error}")
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="failed",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            validation_fixture_paths=validation_fixture_paths,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status="failed",
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order(evidence),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "inspect the failed PatchSmith run before retrying"]
            ),
        )

    run_id = run_result.run_id
    run_status = run_result.status
    report_path = str(run_result.report_path)
    trace_path = str(run_result.trace_path)
    final_diff_path = str(run_result.final_diff_path)
    test_exit_code = (
        run_result.test_result.exit_code if run_result.test_result is not None else None
    )
    patch_generated = _path_has_text(run_result.final_diff_path)
    if patch_generated:
        evidence.append("PatchSmith generated a final diff")
    if test_exit_code == 0 and patch_generated:
        status = "validated"
        evidence.append("repair validation command exited zero")
        next_actions.append("review final diff and broaden validation before claims")
    elif test_exit_code == 0:
        status = "failed"
        warnings.append("repair validation passed but no patch was generated")
        next_actions.append("inspect saved run artifacts before claiming repair")
    else:
        status = "failed"
        warnings.append(f"repair validation exit code is {test_exit_code}")
        next_actions.append("inspect saved run artifacts before retrying or claiming repair")

    return IssueCorpusPublicRepairAttemptResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        repo_path=repo_path_value,
        repo_exists=repo_exists,
        repair_command=repair_command,
        validation_command=validation_command,
        validation_fixture_paths=validation_fixture_paths,
        reproduction_execution_status=reproduction_execution_status,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        dry_run=dry_run,
        run_id=run_id,
        run_status=run_status,
        report_path=report_path,
        trace_path=trace_path,
        final_diff_path=final_diff_path,
        test_exit_code=test_exit_code,
        patch_generated=patch_generated,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _first_manifest_repair_command(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    commands = _string_list(manifest.get("suggested_commands"))
    return commands[0] if commands else None


def _public_issue_repair_issue_text(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    issue_file = _optional_string(manifest.get("issue_file"))
    if issue_file:
        path = Path(issue_file)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    issue = dict_or_empty(manifest.get("issue"))
    parts = [
        _optional_string(issue.get("title")),
        _optional_string(issue.get("task_type")),
        _optional_string(issue.get("selection_reason")),
    ]
    workflow = _string_list(issue.get("expected_workflow"))
    text = "\n".join(part for part in [*parts, *workflow] if part)
    return text or None


def _public_issue_repair_attempt_issue_text(
    *,
    issue_text: str,
    validation_command: str | None,
    validation_fixture_paths: list[str],
    validation_fixture_files: list[dict[str, str]],
    source_hints: list[str],
) -> str:
    sections = [issue_text.rstrip()]
    details: list[str] = []
    if validation_command:
        details.append(f"Validation command: `{validation_command}`")
    if validation_fixture_paths:
        details.append(
            "Fixture files already added to the disposable repair workspace: "
            + ", ".join(f"`{path}`" for path in validation_fixture_paths)
        )
    if source_hints:
        details.append(
            "Reviewed source files and fixture import hints: "
            + ", ".join(f"`{path}`" for path in source_hints)
        )
    if details:
        sections.extend(["", "## Reviewed Reproduction", "", *details])
    for fixture in validation_fixture_files[:3]:
        path = fixture.get("path", "fixture")
        content = fixture.get("content", "")
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        excerpt = content[:4000]
        sections.extend(
            [
                "",
                f"### Fixture `{path}`",
                "",
                "```python",
                excerpt,
                "```",
            ]
        )
    return "\n".join(sections)


def _source_hint_file_paths(source_hints: list[str]) -> list[str]:
    return _dedupe_preserve_order(
        [
            Path(hint.partition("#")[0]).as_posix()
            for hint in source_hints
            if isinstance(hint, str) and hint.partition("#")[0].strip()
        ]
    )


def _load_public_issue_reproduction_specs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"public issue reproduction specs do not exist: {path}")
    if not path.is_file():
        raise ValueError(f"public issue reproduction specs path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict) and isinstance(parsed.get("specs"), list):
        raw_records = parsed["specs"]
    elif isinstance(parsed, list):
        raw_records = parsed
    elif isinstance(parsed, dict):
        raw_records = []
        for task_id, record in parsed.items():
            if not isinstance(record, dict):
                raise ValueError(
                    "task-id keyed reproduction specs must map every task id to an object"
                )
            raw_records.append({**record, "task_id": task_id})
    else:
        raise ValueError("public issue reproduction specs must contain an object or list")

    specs: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            raise ValueError(f"reproduction spec #{index} must be a JSON object")
        task_id = _optional_string(raw_record.get("task_id"))
        if task_id is None:
            raise ValueError(f"reproduction spec #{index} is missing task_id")
        if task_id in specs:
            raise ValueError(f"duplicate reproduction spec for task_id: {task_id}")
        specs[task_id] = raw_record
    return specs


def _load_public_issue_task_manifests(tasks_dir: Path | None) -> dict[str, dict[str, Any]]:
    if tasks_dir is None or not tasks_dir.exists() or not tasks_dir.is_dir():
        return {}
    manifests: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(tasks_dir.glob("*/task_manifest.json")):
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        task_id = _optional_string(parsed.get("task_id")) or manifest_path.parent.name
        manifests[task_id] = parsed
    return manifests


def _matching_lines(text: str, patterns: list[str], *, limit: int) -> list[str]:
    matches: list[str] = []
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered_line = stripped.lower()
        if any(pattern in lowered_line for pattern in lowered_patterns):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return matches


def _matched_expected_failure_signals(text: str, patterns: list[str]) -> list[str]:
    matched: list[str] = []
    lowered_text = text.lower()
    for pattern in patterns:
        if pattern.lower() in lowered_text:
            matched.append(pattern)
    return matched


def _candidate_failure_signals_from_logs(text: str, *, limit: int = 8) -> list[str]:
    exception_markers = (
        "assertionerror",
        "modulenotfounderror",
        "importerror",
        "nameerror",
        "typeerror",
        "valueerror",
        "no such file or directory",
    )
    matches: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if (
            lowered.startswith(("failed ", "error ", "e   ", "traceback"))
            or "error:" in lowered
            or any(marker in lowered for marker in exception_markers)
        ):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return _dedupe_preserve_order(matches)


def _last_nonempty_lines(text: str, *, limit: int) -> list[str]:
    lines = [line.strip()[:240] for line in text.splitlines() if line.strip()]
    return lines[-limit:]
