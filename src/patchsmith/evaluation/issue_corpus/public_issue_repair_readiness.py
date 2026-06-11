"""Readiness checks for public issue repair attempts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    first_manifest_repair_command,
)
from patchsmith.evaluation_models import IssueCorpusPublicRepairReadinessResult
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files as _normalize_public_issue_fixture_files,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_source_hints as _normalize_public_issue_source_hints,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
)


def check_public_issue_repair_readiness_record(
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
    repair_command = first_manifest_repair_command(manifest)

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
