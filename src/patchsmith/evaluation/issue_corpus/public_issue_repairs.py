"""Public issue repair readiness and attempt workflows."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty, write_json
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _load_json_record_list,
    _optional_string,
    _path_has_text,
    _records_by_task_id,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_repair_attempts,
    summarize_public_issue_repair_readiness,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
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
    render_public_issue_repair_attempt_report,
    render_public_issue_repair_readiness_report,
)
from patchsmith.workflow import RepairRunner


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
