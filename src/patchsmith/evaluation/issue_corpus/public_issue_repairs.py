"""Public issue repair readiness and attempt workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from patchsmith.deepagents_config import deepagents_config_from_env
from patchsmith.evaluation._helpers import (
    _load_json_record_list,
    _optional_string,
    _records_by_task_id,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_attempts import (
    execute_public_issue_repair_record,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    load_public_issue_task_manifests,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_outputs import (
    write_public_issue_repair_attempt_outputs,
    write_public_issue_repair_readiness_outputs,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_readiness import (
    check_public_issue_repair_readiness_record,
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
from patchsmith.model_preflight import (
    ModelPreflightResult,
    openai_model_preflight_from_env,
)
from patchsmith.sandbox import check_docker_sandbox_availability
from patchsmith.workflow import RepairRunner


@dataclass(frozen=True)
class PublicRepairSandboxPreflight:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    gates: tuple[dict[str, str], ...] = ()


PublicRepairSandboxPreflightFunc = Callable[
    [str, str],
    PublicRepairSandboxPreflight,
]
PublicRepairModelPreflightFunc = Callable[[str], ModelPreflightResult]


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
    manifests = load_public_issue_task_manifests(tasks_dir)
    diagnosis_by_task = _records_by_task_id(diagnosis_records)
    setup_validation_by_task = _records_by_task_id(setup_validation_records)
    reproduction_execution_by_task = _records_by_task_id(reproduction_execution_records)
    results = [
        check_public_issue_repair_readiness_record(
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


def execute_public_issue_repairs(
    *,
    readiness_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    runtime: str = "deepagents",
    planner: str = "fake_model",
    context_provider: str = "native_hybrid",
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    max_retries: int = 0,
    max_tasks: int | None = None,
    task_ids: list[str] | None = None,
    repeats: int = 1,
    stop_on_validated: bool = False,
    dry_run: bool = True,
    allow_warnings: bool = False,
    sandbox_preflight: PublicRepairSandboxPreflightFunc | None = None,
    model_preflight: PublicRepairModelPreflightFunc | None = None,
    max_live_cost_usd: float | None = None,
    estimated_cost_per_attempt_usd: float | None = None,
    deepagents_max_context_files: int | None = None,
    max_actual_model_responses: int | None = None,
    max_actual_model_tokens: int | None = None,
    deepagents_subagent_mode: str | None = None,
) -> tuple[
    list[IssueCorpusPublicRepairAttemptResult],
    IssueCorpusPublicRepairAttemptSummary,
]:
    if max_actual_model_responses is not None and max_actual_model_responses < 0:
        raise ValueError("max_actual_model_responses must be non-negative")
    if max_actual_model_tokens is not None and max_actual_model_tokens < 0:
        raise ValueError("max_actual_model_tokens must be non-negative")
    if deepagents_subagent_mode not in {None, "full", "auto", "inline"}:
        raise ValueError("deepagents_subagent_mode must be full, auto, or inline")
    records = _load_json_record_list(
        readiness_path,
        label="public issue repair readiness results",
    )
    selected_records = records
    if task_ids:
        wanted = {task_id.strip() for task_id in task_ids if task_id.strip()}
        selected_records = [
            record
            for record in selected_records
            if (_optional_string(record.get("task_id")) or "") in wanted
        ]
    if max_tasks is not None and max_tasks > 0:
        selected_records = selected_records[:max_tasks]
    repeat_count = max(1, repeats)
    manifests = load_public_issue_task_manifests(tasks_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight = _public_repair_sandbox_preflight(
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_preflight=sandbox_preflight,
    )
    model_preflight_result = (
        _public_repair_model_preflight(
            planner=planner,
            dry_run=dry_run,
            model_preflight=model_preflight,
        )
        if not preflight.errors
        else PublicRepairSandboxPreflight()
    )
    preflight = _merge_preflights(preflight, model_preflight_result)
    budget_preflight_result = (
        _public_repair_budget_preflight(
            planner=planner,
            dry_run=dry_run,
            selected_record_count=len(selected_records),
            repeat_count=repeat_count,
            max_retries=max_retries,
            max_live_cost_usd=max_live_cost_usd,
            estimated_cost_per_attempt_usd=estimated_cost_per_attempt_usd,
        )
        if not preflight.errors
        else PublicRepairSandboxPreflight()
    )
    preflight = _merge_preflights(preflight, budget_preflight_result)
    runner = (
        None
        if dry_run or preflight.errors
        else RepairRunner(artifacts_dir=output_dir / "public_issue_repair_attempts")
    )
    results: list[IssueCorpusPublicRepairAttemptResult] = []
    for record in selected_records:
        for attempt_index in range(1, repeat_count + 1):
            result = execute_public_issue_repair_record(
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
                preflight_errors=list(preflight.errors),
                preflight_warnings=list(preflight.warnings),
                preflight_evidence=list(preflight.evidence),
                preflight_next_actions=list(preflight.next_actions),
                preflight_status=_preflight_status(preflight),
                preflight_gates=list(preflight.gates),
                attempt_index=attempt_index,
                attempt_count=repeat_count,
                deepagents_max_context_files=deepagents_max_context_files,
                max_live_cost_usd=max_live_cost_usd,
                max_actual_model_responses=max_actual_model_responses,
                max_actual_model_tokens=max_actual_model_tokens,
                deepagents_subagent_mode=deepagents_subagent_mode,
            )
            results.append(result)
            if stop_on_validated and result.status == "validated":
                break
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
        stop_on_validated=stop_on_validated,
        repeat_count=repeat_count,
        deepagents_max_context_files=deepagents_max_context_files,
        max_actual_model_responses=max_actual_model_responses,
        max_actual_model_tokens=max_actual_model_tokens,
    )
    write_public_issue_repair_attempt_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def _public_repair_sandbox_preflight(
    *,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_preflight: PublicRepairSandboxPreflightFunc | None,
) -> PublicRepairSandboxPreflight:
    if sandbox_preflight is not None:
        return sandbox_preflight(sandbox_mode, sandbox_image)
    if sandbox_mode != "docker":
        return PublicRepairSandboxPreflight(
            evidence=(f"sandbox preflight skipped for {sandbox_mode} mode",),
            gates=(
                _preflight_gate(
                    name="sandbox",
                    status="skipped",
                    detail=f"sandbox preflight skipped for {sandbox_mode} mode",
                    mode=sandbox_mode,
                ),
            ),
        )
    availability = check_docker_sandbox_availability(image=sandbox_image)
    if not availability.available:
        return PublicRepairSandboxPreflight(
            errors=tuple(
                f"Docker sandbox preflight failed: {error}" for error in availability.errors
            ),
            evidence=availability.evidence,
            next_actions=availability.next_actions,
            gates=(
                _preflight_gate(
                    name="sandbox",
                    status="blocked",
                    detail="; ".join(availability.errors) or "docker sandbox unavailable",
                    mode=sandbox_mode,
                    image=sandbox_image,
                ),
            ),
        )
    return PublicRepairSandboxPreflight(
        evidence=availability.evidence,
        gates=(
            _preflight_gate(
                name="sandbox",
                status="passed",
                detail="docker sandbox available",
                mode=sandbox_mode,
                image=sandbox_image,
            ),
        ),
    )


def _public_repair_model_preflight(
    *,
    planner: str,
    dry_run: bool,
    model_preflight: PublicRepairModelPreflightFunc | None,
) -> PublicRepairSandboxPreflight:
    if dry_run:
        return PublicRepairSandboxPreflight(
            gates=(
                _preflight_gate(
                    name="model",
                    status="skipped",
                    detail="model preflight skipped for dry run",
                    provider="openai_models",
                ),
            ),
        )
    if planner not in {"openai", "deepagents"}:
        return PublicRepairSandboxPreflight(
            gates=(
                _preflight_gate(
                    name="model",
                    status="skipped",
                    detail=f"model preflight skipped for {planner} planner",
                    provider="openai_models",
                ),
            ),
        )
    result = (
        model_preflight(planner)
        if model_preflight is not None
        else openai_model_preflight_from_env(model=_model_for_planner(planner))
    )
    if result.available:
        return PublicRepairSandboxPreflight(
            evidence=(
                f"OpenAI model preflight passed for `{result.model}` "
                f"({result.available_model_count or 0} visible models).",
            ),
            gates=(
                _model_preflight_gate(
                    result=result,
                    status="passed",
                    detail=(
                        f"model visible in provider catalog; "
                        f"{result.available_model_count or 0} models returned"
                    ),
                ),
            ),
        )
    next_actions = ["Set OPENAI_API_KEY and PATCHSMITH_OPENAI_MODEL before live repair."]
    if result.suggestions:
        next_actions.append("Available nearby models: " + ", ".join(result.suggestions))
    return PublicRepairSandboxPreflight(
        errors=(
            "OpenAI model preflight failed for "
            f"`{result.model}` ({result.status}): {result.error or 'model unavailable'}",
        ),
        next_actions=tuple(next_actions),
        gates=(
            _model_preflight_gate(
                result=result,
                status="blocked",
                detail=result.error or "model unavailable",
            ),
        ),
    )


def _public_repair_budget_preflight(
    *,
    planner: str,
    dry_run: bool,
    selected_record_count: int,
    repeat_count: int,
    max_retries: int,
    max_live_cost_usd: float | None,
    estimated_cost_per_attempt_usd: float | None,
) -> PublicRepairSandboxPreflight:
    if dry_run:
        return PublicRepairSandboxPreflight(
            gates=(
                _preflight_gate(
                    name="budget",
                    status="skipped",
                    detail="live cost budget preflight skipped for dry run",
                ),
            ),
        )
    if planner not in {"openai", "deepagents"}:
        return PublicRepairSandboxPreflight(
            gates=(
                _preflight_gate(
                    name="budget",
                    status="skipped",
                    detail=f"live cost budget preflight skipped for {planner} planner",
                ),
            ),
        )
    if max_live_cost_usd is None:
        return PublicRepairSandboxPreflight(
            gates=(
                _preflight_gate(
                    name="budget",
                    status="skipped",
                    detail="live cost budget cap was not configured",
                ),
            ),
        )
    if max_live_cost_usd < 0:
        return PublicRepairSandboxPreflight(
            errors=("Live cost budget preflight failed: max_live_cost_usd must be non-negative.",),
            next_actions=("Set --max-live-cost-usd to a non-negative value.",),
            gates=(
                _budget_preflight_gate(
                    status="blocked",
                    detail="max_live_cost_usd must be non-negative",
                    max_live_cost_usd=max_live_cost_usd,
                    estimated_cost_per_attempt_usd=estimated_cost_per_attempt_usd,
                    selected_record_count=selected_record_count,
                    repeat_count=repeat_count,
                    max_retries=max_retries,
                ),
            ),
        )
    if estimated_cost_per_attempt_usd is None or estimated_cost_per_attempt_usd <= 0:
        return PublicRepairSandboxPreflight(
            errors=(
                "Live cost budget preflight failed: estimated_cost_per_attempt_usd "
                "must be positive when a live budget cap is set.",
            ),
            next_actions=("Set --estimated-cost-per-attempt-usd to a positive estimate.",),
            gates=(
                _budget_preflight_gate(
                    status="blocked",
                    detail="estimated_cost_per_attempt_usd must be positive",
                    max_live_cost_usd=max_live_cost_usd,
                    estimated_cost_per_attempt_usd=estimated_cost_per_attempt_usd,
                    selected_record_count=selected_record_count,
                    repeat_count=repeat_count,
                    max_retries=max_retries,
                ),
            ),
        )
    projected_model_attempts = _projected_model_attempts(
        selected_record_count=selected_record_count,
        repeat_count=repeat_count,
        max_retries=max_retries,
    )
    projected_cost = projected_model_attempts * estimated_cost_per_attempt_usd
    if projected_cost > max_live_cost_usd:
        return PublicRepairSandboxPreflight(
            errors=(
                "Live cost budget preflight failed: projected maximum cost "
                f"${projected_cost:.6f} exceeds cap ${max_live_cost_usd:.6f}.",
            ),
            next_actions=(
                "Reduce --max-tasks, --repeats, --max-retries, or raise --max-live-cost-usd.",
            ),
            gates=(
                _budget_preflight_gate(
                    status="blocked",
                    detail="projected maximum live cost exceeds configured cap",
                    max_live_cost_usd=max_live_cost_usd,
                    estimated_cost_per_attempt_usd=estimated_cost_per_attempt_usd,
                    selected_record_count=selected_record_count,
                    repeat_count=repeat_count,
                    max_retries=max_retries,
                    projected_model_attempts=projected_model_attempts,
                    projected_cost_usd=projected_cost,
                ),
            ),
        )
    return PublicRepairSandboxPreflight(
        evidence=(
            "Live cost budget preflight passed: projected maximum cost "
            f"${projected_cost:.6f} within cap ${max_live_cost_usd:.6f}.",
        ),
        gates=(
            _budget_preflight_gate(
                status="passed",
                detail="projected maximum live cost is within configured cap",
                max_live_cost_usd=max_live_cost_usd,
                estimated_cost_per_attempt_usd=estimated_cost_per_attempt_usd,
                selected_record_count=selected_record_count,
                repeat_count=repeat_count,
                max_retries=max_retries,
                projected_model_attempts=projected_model_attempts,
                projected_cost_usd=projected_cost,
            ),
        ),
    )


def _model_for_planner(planner: str) -> str | None:
    if planner == "deepagents":
        return deepagents_config_from_env().model
    return None


def _merge_preflights(
    left: PublicRepairSandboxPreflight,
    right: PublicRepairSandboxPreflight,
) -> PublicRepairSandboxPreflight:
    return PublicRepairSandboxPreflight(
        errors=(*left.errors, *right.errors),
        warnings=(*left.warnings, *right.warnings),
        evidence=(*left.evidence, *right.evidence),
        next_actions=(*left.next_actions, *right.next_actions),
        gates=(*left.gates, *right.gates),
    )


def _preflight_status(preflight: PublicRepairSandboxPreflight) -> str:
    if preflight.errors:
        return "blocked"
    statuses = {gate.get("status", "") for gate in preflight.gates}
    if "passed" in statuses:
        return "passed"
    if "skipped" in statuses:
        return "skipped"
    return "not_applicable"


def _preflight_gate(
    *,
    name: str,
    status: str,
    detail: str,
    **metadata: str,
) -> dict[str, str]:
    gate = {
        "name": name,
        "status": status,
        "detail": detail,
    }
    gate.update({key: value for key, value in metadata.items() if value})
    return gate


def _model_preflight_gate(
    *,
    result: ModelPreflightResult,
    status: str,
    detail: str,
) -> dict[str, str]:
    gate = _preflight_gate(
        name="model",
        status=status,
        detail=detail,
        provider=result.provider,
        model=result.model,
        endpoint=result.endpoint,
        provider_status=result.status,
    )
    if result.available_model_count is not None:
        gate["available_model_count"] = str(result.available_model_count)
    if result.suggestions:
        gate["suggestions"] = ",".join(result.suggestions)
    return gate


def _projected_model_attempts(
    *,
    selected_record_count: int,
    repeat_count: int,
    max_retries: int,
) -> int:
    return max(0, selected_record_count) * max(1, repeat_count) * (max(0, max_retries) + 1)


def _budget_preflight_gate(
    *,
    status: str,
    detail: str,
    max_live_cost_usd: float,
    estimated_cost_per_attempt_usd: float | None,
    selected_record_count: int,
    repeat_count: int,
    max_retries: int,
    projected_model_attempts: int | None = None,
    projected_cost_usd: float | None = None,
) -> dict[str, str]:
    gate = _preflight_gate(
        name="budget",
        status=status,
        detail=detail,
        max_live_cost_usd=f"{max_live_cost_usd:.6f}",
        selected_record_count=str(max(0, selected_record_count)),
        repeat_count=str(max(1, repeat_count)),
        max_retries=str(max(0, max_retries)),
    )
    if estimated_cost_per_attempt_usd is not None:
        gate["estimated_cost_per_attempt_usd"] = f"{estimated_cost_per_attempt_usd:.6f}"
    if projected_model_attempts is not None:
        gate["projected_model_attempts"] = str(projected_model_attempts)
    if projected_cost_usd is not None:
        gate["projected_cost_usd"] = f"{projected_cost_usd:.6f}"
    return gate


__all__ = [
    "PublicRepairSandboxPreflight",
    "RepairRunner",
    "check_public_issue_repair_readiness",
    "execute_public_issue_repairs",
]
