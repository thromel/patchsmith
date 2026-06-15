"""Execution of public issue repair attempt records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import (
    _optional_string,
    _patch_quality_from_trace,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_attempt_results import (
    public_issue_repair_attempt_result as _attempt_result,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_attempt_runner import (
    run_public_issue_repair_attempt,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    public_issue_repair_issue_text,
)
from patchsmith.evaluation_models import IssueCorpusPublicRepairAttemptResult
from patchsmith.patch_quality import assess_diff_quality
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files as _normalize_public_issue_fixture_files,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_source_hints as _normalize_public_issue_source_hints,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
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
    preflight_errors: list[str] | None = None,
    preflight_warnings: list[str] | None = None,
    preflight_evidence: list[str] | None = None,
    preflight_next_actions: list[str] | None = None,
    preflight_status: str = "not_applicable",
    preflight_gates: list[dict[str, str]] | None = None,
    attempt_index: int = 1,
    attempt_count: int = 1,
    deepagents_max_context_files: int | None = None,
    max_live_cost_usd: float | None = None,
    max_actual_model_responses: int | None = None,
    max_actual_model_tokens: int | None = None,
    deepagents_subagent_mode: str | None = None,
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
    errors.extend(preflight_errors or [])
    warnings = _string_list(record.get("warnings"))
    warnings.extend(preflight_warnings or [])
    evidence = _string_list(record.get("evidence"))
    evidence.extend(preflight_evidence or [])
    if deepagents_max_context_files is not None and deepagents_max_context_files > 0:
        evidence.append(
            f"DeepAgents max context files configured: {deepagents_max_context_files}"
        )
    next_actions = _string_list(record.get("next_actions"))
    next_actions.extend(preflight_next_actions or [])
    run_id: str | None = None
    run_status: str | None = None
    report_path: str | None = None
    trace_path: str | None = None
    final_diff_path: str | None = None
    test_exit_code: int | None = None
    patch_generated = False
    model_call_count: int | None = None
    model_response_count: int | None = None
    model_input_tokens: int | None = None
    model_output_tokens: int | None = None
    model_total_tokens: int | None = None
    estimated_model_cost_usd: float | None = None

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
            attempt_index=attempt_index,
            attempt_count=attempt_count,
            preflight_status=preflight_status,
            preflight_gates=preflight_gates,
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
            attempt_index=attempt_index,
            attempt_count=attempt_count,
            preflight_status=preflight_status,
            preflight_gates=preflight_gates,
        )

    assert runner is not None
    assert repo_path_value is not None
    assert issue_text is not None
    assert validation_command is not None
    try:
        run_outcome = run_public_issue_repair_attempt(
            runner=runner,
            repo_path=repo_path_value,
            issue_text=issue_text,
            issue_url=issue_url,
            validation_command=validation_command,
            validation_fixture_paths=validation_fixture_paths,
            validation_fixture_files=validation_fixture_files,
            validation_source_hints=validation_source_hints,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            max_retries=max_retries,
            deepagents_max_context_files=deepagents_max_context_files,
            max_actual_model_responses=max_actual_model_responses,
            max_actual_model_tokens=max_actual_model_tokens,
            deepagents_subagent_mode=deepagents_subagent_mode,
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
            attempt_index=attempt_index,
            attempt_count=attempt_count,
            preflight_status=preflight_status,
            preflight_gates=preflight_gates,
        )

    run_id = run_outcome.run_id
    run_status = run_outcome.run_status
    report_path = run_outcome.report_path
    trace_path = run_outcome.trace_path
    final_diff_path = run_outcome.final_diff_path
    test_exit_code = run_outcome.test_exit_code
    patch_generated = run_outcome.patch_generated
    model_call_count = run_outcome.model_call_count
    model_response_count = run_outcome.model_response_count
    model_input_tokens = run_outcome.model_input_tokens
    model_output_tokens = run_outcome.model_output_tokens
    model_total_tokens = run_outcome.model_total_tokens
    estimated_model_cost_usd = run_outcome.estimated_model_cost_usd
    patch_quality = _saved_patch_quality(
        trace_path=trace_path,
        final_diff_path=final_diff_path,
    )
    patch_quality_warning = bool(patch_quality.get("patch_quality_warning"))
    if patch_generated:
        evidence.append("PatchSmith generated a final diff")
    if estimated_model_cost_usd is not None:
        evidence.append(
            "Actual model usage: "
            f"{model_call_count or 0} calls, "
            f"{model_total_tokens or 0} tokens, "
            f"estimated cost ${estimated_model_cost_usd:.6f}."
        )
    if test_exit_code == 0 and patch_generated and not patch_quality_warning:
        status = "validated"
        evidence.append("repair validation command exited zero with acceptable patch quality")
        next_actions.append("review final diff and broaden validation before claims")
    elif test_exit_code == 0 and patch_generated:
        status = "failed"
        evidence.append("repair validation command exited zero")
        warnings.append("repair validation passed but final patch quality is high-risk")
        next_actions.append(
            "inspect or retry the high-risk final diff before claiming repair"
        )
    elif test_exit_code == 0:
        status = "failed"
        warnings.append("repair validation passed but no patch was generated")
        next_actions.append("inspect saved run artifacts before claiming repair")
    else:
        status = "failed"
        warnings.append(f"repair validation exit code is {test_exit_code}")
        next_actions.append("inspect saved run artifacts before retrying or claiming repair")
    if (
        max_live_cost_usd is not None
        and estimated_model_cost_usd is not None
        and estimated_model_cost_usd > max_live_cost_usd
    ):
        if status == "validated":
            status = "failed"
        warnings.append(
            "actual live model cost exceeded configured cap: "
            f"${estimated_model_cost_usd:.6f} > ${max_live_cost_usd:.6f}"
        )
        next_actions.append(
            "raise the live cost estimate/cap or reduce retries/context before "
            "claiming budget-compliant repair"
        )
    actual_usage_cap_warnings = _actual_usage_cap_warnings(
        model_response_count=model_response_count,
        model_total_tokens=model_total_tokens,
        max_actual_model_responses=max_actual_model_responses,
        max_actual_model_tokens=max_actual_model_tokens,
    )
    if actual_usage_cap_warnings:
        if status == "validated":
            status = "failed"
        warnings.extend(actual_usage_cap_warnings)
        next_actions.append(
            "ensure usage is recorded or reduce retries/context before claiming "
            "response/token-budget-compliant repair"
        )

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
        model_call_count=model_call_count,
        model_response_count=model_response_count,
        model_input_tokens=model_input_tokens,
        model_output_tokens=model_output_tokens,
        model_total_tokens=model_total_tokens,
        estimated_model_cost_usd=estimated_model_cost_usd,
        errors=errors,
        warnings=warnings,
        evidence=evidence,
        next_actions=next_actions,
        attempt_index=attempt_index,
        attempt_count=attempt_count,
        preflight_status=preflight_status,
        preflight_gates=preflight_gates,
    )


def _actual_usage_cap_warnings(
    *,
    model_response_count: int | None,
    model_total_tokens: int | None,
    max_actual_model_responses: int | None,
    max_actual_model_tokens: int | None,
) -> list[str]:
    warnings: list[str] = []
    if max_actual_model_responses is not None:
        if model_response_count is None:
            warnings.append(
                "actual model response cap was configured but response count was not recorded"
            )
        elif model_response_count > max_actual_model_responses:
            warnings.append(
                "actual model responses exceeded configured cap: "
                f"{model_response_count} > {max_actual_model_responses}"
            )
    if max_actual_model_tokens is not None:
        if model_total_tokens is None:
            warnings.append(
                "actual model token cap was configured but total tokens were not recorded"
            )
        elif model_total_tokens > max_actual_model_tokens:
            warnings.append(
                "actual model tokens exceeded configured cap: "
                f"{model_total_tokens} > {max_actual_model_tokens}"
            )
    return warnings


def _saved_patch_quality(
    *,
    trace_path: str | None,
    final_diff_path: str | None,
) -> dict[str, object]:
    trace_quality: dict[str, object] = (
        _patch_quality_from_trace(Path(trace_path))
        if trace_path and Path(trace_path).is_file()
        else {"patch_quality_severity": None, "patch_quality_warning": False}
    )
    diff_quality = _diff_patch_quality(final_diff_path)
    if diff_quality is None:
        return trace_quality
    trace_severity = trace_quality.get("patch_quality_severity")
    diff_severity = diff_quality.get("patch_quality_severity")
    return {
        "patch_quality_severity": _higher_severity(
            trace_severity if isinstance(trace_severity, str) else None,
            diff_severity if isinstance(diff_severity, str) else None,
        ),
        "patch_quality_warning": bool(trace_quality.get("patch_quality_warning"))
        or bool(diff_quality.get("patch_quality_warning")),
    }


def _diff_patch_quality(final_diff_path: str | None) -> dict[str, object] | None:
    if not final_diff_path:
        return None
    path = Path(final_diff_path)
    if not path.is_file():
        return None
    assessment = assess_diff_quality(path.read_text(encoding="utf-8"))
    if assessment.severity == "low" and not assessment.findings:
        return None
    return {
        "patch_quality_severity": assessment.severity,
        "patch_quality_warning": assessment.severity == "high",
    }


def _higher_severity(left: str | None, right: str | None) -> str | None:
    severities = [severity for severity in (left, right) if severity]
    if not severities:
        return None
    return max(severities, key=lambda severity: _severity_rank(severity))


def _severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity, -1)
