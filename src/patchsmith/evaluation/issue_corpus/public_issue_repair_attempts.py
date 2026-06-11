"""Execution of public issue repair attempt records."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _path_has_text,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    public_issue_repair_attempt_issue_text,
    public_issue_repair_issue_text,
    source_hint_file_paths,
)
from patchsmith.evaluation_models import IssueCorpusPublicRepairAttemptResult
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


def execute_public_issue_repair_record(
    *,
    record: dict[str, Any],
    manifest: dict[str, Any] | None,
    runner: Any,
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

    issue_text = public_issue_repair_issue_text(manifest)
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
        return _attempt_result(
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
            errors=errors,
            warnings=warnings,
            evidence=evidence,
            next_actions=[
                *next_actions,
                "resolve public repair-attempt blockers before execution",
            ],
        )

    if dry_run:
        return _attempt_result(
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
            warnings=warnings,
            evidence=[*evidence, "repair attempt passed dry-run gating"],
            next_actions=[*next_actions, "rerun with --execute to launch PatchSmith repair"],
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
    run_issue_text = public_issue_repair_attempt_issue_text(
        issue_text=issue_text,
        validation_command=validation_command,
        validation_fixture_paths=validation_fixture_paths,
        validation_fixture_files=validation_fixture_files,
        source_hints=source_hints,
    )
    context_paths = tuple(source_hint_file_paths(source_hints))
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
        return _attempt_result(
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
            errors=errors,
            warnings=warnings,
            evidence=evidence,
            next_actions=[*next_actions, "inspect the failed PatchSmith run before retrying"],
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

    return _attempt_result(
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
        errors=errors,
        warnings=warnings,
        evidence=evidence,
        next_actions=next_actions,
    )


def _attempt_result(
    *,
    task_id: str | None,
    repository: str | None,
    issue_url: str | None,
    status: str,
    readiness_status: str,
    repo_path: str | None,
    repo_exists: bool,
    repair_command: str | None,
    validation_command: str | None,
    validation_fixture_paths: list[str],
    reproduction_execution_status: str | None,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    dry_run: bool,
    run_id: str | None,
    run_status: str | None,
    report_path: str | None,
    trace_path: str | None,
    final_diff_path: str | None,
    test_exit_code: int | None,
    patch_generated: bool,
    errors: list[str],
    warnings: list[str],
    evidence: list[str],
    next_actions: list[str],
) -> IssueCorpusPublicRepairAttemptResult:
    return IssueCorpusPublicRepairAttemptResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        repo_path=repo_path,
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
