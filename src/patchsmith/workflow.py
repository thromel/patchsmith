from __future__ import annotations

import subprocess
import time
from dataclasses import replace as dataclass_replace
from pathlib import Path

from patchsmith.analysis import analyze_repair_outcome
from patchsmith.deepagents_planner import DeepAgentsRepairPlanner
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RepairRunResult, RetrievedContext, RunRequest, new_id
from patchsmith.patch_quality import patch_quality_severity_from_runtime_trace
from patchsmith.planning import (
    HeuristicRepairPlanner,
    ModelBackedRepairPlanner,
    OpenAIResponsesModelClient,
    SeededFakeRepairModelClient,
)
from patchsmith.reporting import model_usage_from_trace, render_run_report
from patchsmith.runtime import (
    AgentlessRuntime,
    AgentRuntime,
    AgentTask,
    DeepAgentsRuntime,
    HeuristicRuntime,
)
from patchsmith.runtime.attempts import (
    attempted_target_old_span_hashes,
    attempted_target_paths,
    emit_agent_result_trace,
    feedback_attempt_record,
    ineffective_target_paths,
    issue_with_test_feedback,
    mounted_context_paths,
    retry_failure_class,
    retry_feedback_brief,
    retry_feedback_labels,
    run_sandbox_attempt,
    should_retry_with_test_feedback,
    test_feedback_retry_budget,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.tracing import RunTrace
from patchsmith.workflow_context import WorkflowContextSelector
from patchsmith.workspace_restore import WorkspaceRestorer

RETRY_CONTEXT_EXTRA_FILES = 3


class RepairRunner:
    def __init__(self, *, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.context_selector = WorkflowContextSelector()

    def run(self, request: RunRequest) -> RepairRunResult:
        run_id = new_id()
        run_dir = (self.artifacts_dir / "runs" / run_id).resolve()
        repo_path = run_dir / "repo"
        patches_dir = run_dir / "patches"
        logs_dir = run_dir / "logs"
        feedback_dir = run_dir / "feedback"
        report_path = run_dir / "report.md"
        trace_path = run_dir / "traces.jsonl"
        final_diff_path = run_dir / "final.diff"
        context_dir = run_dir / "context"
        for directory in (patches_dir, logs_dir, feedback_dir):
            directory.mkdir(parents=True, exist_ok=True)

        trace = RunTrace(run_id=run_id, trace_path=trace_path)
        trace.emit(
            node_name="run",
            event_type="lifecycle",
            status="created",
            input_summary=request.repo,
            output_summary="run workspace created",
        )

        status = "completed"
        try:
            started = time.perf_counter()
            snapshot = clone_or_copy_repository(
                request.repo,
                repo_path,
                commit=request.commit,
                branch=request.branch,
            )
            trace.time_event(
                node_name="ingest",
                event_type="repo_clone",
                status="completed",
                input_summary=request.repo,
                output_summary=f"{snapshot.file_count} indexed files",
                payload=snapshot.to_dict(),
                started=started,
            )

            started = time.perf_counter()
            repo_index = index_repository(repo_path)
            trace.time_event(
                node_name="index",
                event_type="file_index",
                status="completed",
                output_summary=f"{len(repo_index.files)} files",
                payload=repo_index.to_dict(),
                started=started,
            )

            context_selection = self.context_selector.select(
                request=request,
                repo_path=repo_path,
                repo_index=repo_index,
                artifact_dir=context_dir,
                trace=trace,
            )
            retrieved_context = context_selection.retrieved_context
            retry_context_limit = request.top_k + RETRY_CONTEXT_EXTRA_FILES
            retry_context_mount_limit = _retry_context_mount_limit(request)

            runtime = _runtime_for(request.runtime, request.planner)
            command = request.test_command or (
                snapshot.test_commands[0] if snapshot.test_commands else None
            )
            sandbox = create_sandbox_runner(
                mode=request.sandbox_mode,
                image=request.sandbox_image,
            )
            attempt_issue_text = request.issue_text
            attempt_retry_feedback_brief = ""
            used_model_responses = 0
            used_model_tokens = 0
            retry_attempt_history: list[dict[str, object]] = []
            deprioritized_context_paths: list[str] = []
            attempt = 0
            max_feedback_retries = test_feedback_retry_budget(request)
            workspace_restorer = WorkspaceRestorer.create(
                repo_path=repo_path,
                baseline_path=run_dir / ".retry_baseline_repo",
                enabled=max_feedback_retries > 0,
            )
            while True:
                attempt += 1
                if attempt > 1 and attempt_retry_feedback_brief:
                    refreshed_selection = self.context_selector.select(
                        request=dataclass_replace(
                            request,
                            issue_text=attempt_issue_text,
                            top_k=retry_context_limit,
                        ),
                        repo_path=repo_path,
                        repo_index=repo_index,
                        artifact_dir=context_dir / f"attempt_{attempt}",
                        trace=trace,
                    )
                    previous_paths = [context.path for context in retrieved_context]
                    refreshed_paths = [
                        context.path for context in refreshed_selection.retrieved_context
                    ]
                    deprioritized_context_paths = ineffective_target_paths(
                        retry_attempt_history
                    )
                    retrieved_context = _merge_retrieved_contexts(
                        retrieved_context,
                        refreshed_selection.retrieved_context,
                        limit=retry_context_limit,
                        deprioritized_paths=set(deprioritized_context_paths),
                    )
                    trace.emit(
                        node_name="context_refresh",
                        event_type="feedback_context_refresh",
                        status="completed",
                        input_summary=f"attempt={attempt}",
                        output_summary=", ".join(context.path for context in retrieved_context),
                        payload={
                            "attempt": attempt,
                            "limit": retry_context_limit,
                            "previous_context_paths": previous_paths,
                            "refreshed_context_paths": refreshed_paths,
                            "deprioritized_context_paths": deprioritized_context_paths,
                            "mounted_context_limit": retry_context_mount_limit,
                            "merged_context_paths": [
                                context.path for context in retrieved_context
                            ],
                        },
                    )
                runtime_config = {
                    **_runtime_config_with_resource_usage(
                        request.runtime_config,
                        used_model_responses=used_model_responses,
                        used_model_tokens=used_model_tokens,
                    ),
                    "planner": request.planner,
                    "max_retries": request.max_retries,
                    "workflow_attempt": attempt,
                    "test_feedback_retries": max_feedback_retries,
                }
                target_history_paths = _merge_path_lists(
                    attempted_target_paths(retry_attempt_history),
                    deprioritized_context_paths,
                )
                target_history_old_span_hashes = attempted_target_old_span_hashes(
                    retry_attempt_history
                )
                if attempt_retry_feedback_brief:
                    runtime_config["retry_feedback_brief"] = attempt_retry_feedback_brief
                    if "max_context_files" in request.runtime_config:
                        pinned_context_paths = mounted_context_paths(retry_attempt_history)
                        if pinned_context_paths:
                            runtime_config["context_selection_pinned_paths"] = (
                                pinned_context_paths
                            )
                    if retry_context_mount_limit > 0 and "max_context_files" not in runtime_config:
                        runtime_config["max_context_files"] = retry_context_mount_limit
                if target_history_paths:
                    runtime_config["target_history_paths"] = target_history_paths
                if target_history_old_span_hashes:
                    runtime_config["target_history_old_span_hashes"] = (
                        target_history_old_span_hashes
                    )
                if deprioritized_context_paths:
                    runtime_config["deprioritized_context_paths"] = deprioritized_context_paths
                agent_result = runtime.run(
                    AgentTask(
                        run_id=run_id,
                        repo_path=str(repo_path),
                        issue_text=attempt_issue_text,
                        retrieved_context=retrieved_context,
                        test_command=command,
                        runtime_config=runtime_config,
                    )
                )
                emit_agent_result_trace(
                    trace=trace,
                    request=request,
                    agent_result=agent_result,
                    attempt=attempt,
                )
                usage = model_usage_from_trace(trace.events)
                used_model_responses = _nonnegative_int_or_zero(
                    usage.get("response_count")
                )
                used_model_tokens = _nonnegative_int_or_zero(usage.get("total_tokens"))
                test_result = run_sandbox_attempt(
                    command=command,
                    sandbox=sandbox,
                    repo_path=repo_path,
                    logs_dir=logs_dir,
                    trace=trace,
                    request=request,
                    attempt=attempt,
                )
                final_diff = _workspace_diff(repo_path) or agent_result.final_diff
                repair_analysis = analyze_repair_outcome(
                    patch_status=agent_result.status,
                    final_diff=final_diff,
                    test_result=test_result,
                    patch_quality_severity=patch_quality_severity_from_runtime_trace(
                        agent_result.runtime_trace
                    ),
                )
                trace.emit(
                    node_name="analyze",
                    event_type="repair_outcome",
                    status=repair_analysis.status,
                    output_summary=repair_analysis.summary,
                    payload={
                        **repair_analysis.to_dict(),
                        "attempt": attempt,
                        "max_feedback_retries": max_feedback_retries,
                    },
                )
                if not should_retry_with_test_feedback(
                    request=request,
                    agent_result=agent_result,
                    test_result=test_result,
                    repair_analysis=repair_analysis,
                    attempt=attempt,
                    max_feedback_retries=max_feedback_retries,
                ):
                    break
                retry_budget_block = _retry_resource_budget_block(
                    request.runtime_config,
                    used_model_responses=used_model_responses,
                    used_model_tokens=used_model_tokens,
                )
                if retry_budget_block is not None:
                    trace.emit(
                        node_name="feedback_retry",
                        event_type="repair_retry",
                        status="blocked",
                        output_summary=(
                            "Skipped DeepAgents feedback retry because the configured "
                            "resource budget was exhausted or too low for another retry."
                        ),
                        payload={
                            "attempt": attempt,
                            "next_attempt": attempt + 1,
                            "max_feedback_retries": max_feedback_retries,
                            **retry_budget_block,
                        },
                    )
                    break
                retry_attempt_history.append(
                    feedback_attempt_record(
                        attempt=attempt,
                        agent_status=agent_result.status,
                        agent_summary=agent_result.summary,
                        test_result=test_result,
                        final_diff=final_diff,
                        runtime_trace=agent_result.runtime_trace,
                        repair_analysis=repair_analysis,
                        attempt_history=retry_attempt_history,
                    )
                )
                retry_class = retry_failure_class(
                    agent_status=agent_result.status,
                    test_result=test_result,
                    final_diff=final_diff,
                    repair_analysis=repair_analysis,
                    runtime_trace=agent_result.runtime_trace,
                    attempt_history=retry_attempt_history,
                )
                attempt_retry_feedback_brief = retry_feedback_brief(
                    agent_status=agent_result.status,
                    agent_summary=agent_result.summary,
                    test_result=test_result,
                    final_diff=final_diff,
                    attempt=attempt,
                    runtime_trace=agent_result.runtime_trace,
                    attempt_history=retry_attempt_history,
                    repair_analysis=repair_analysis,
                )
                retry_labels = retry_feedback_labels(
                    test_result=test_result,
                    agent_status=agent_result.status,
                    final_diff=final_diff,
                    repair_analysis=repair_analysis,
                    runtime_trace=agent_result.runtime_trace,
                    attempt_history=retry_attempt_history,
                )
                retry_feedback_path = (
                    feedback_dir / f"retry_feedback_attempt_{attempt}_to_{attempt + 1}.md"
                )
                retry_feedback_path.write_text(attempt_retry_feedback_brief, encoding="utf-8")
                trace.emit(
                    node_name="feedback_retry",
                    event_type="repair_retry",
                    status="scheduled",
                    output_summary=(
                        f"Scheduling DeepAgents feedback retry {attempt} of {max_feedback_retries}."
                    ),
                    payload={
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "max_feedback_retries": max_feedback_retries,
                        "test_exit_code": test_result.exit_code if test_result else None,
                        "repair_verdict": repair_analysis.verdict,
                        "patch_quality_severity": repair_analysis.patch_quality_severity,
                        "retry_failure_class": retry_class,
                        "retry_labels": list(retry_labels),
                        "retry_feedback_brief_chars": len(attempt_retry_feedback_brief),
                        "retry_feedback_path": str(retry_feedback_path),
                    },
                )
                attempt_issue_text = issue_with_test_feedback(
                    original_issue=request.issue_text,
                    agent_status=agent_result.status,
                    agent_summary=agent_result.summary,
                    test_result=test_result,
                    final_diff=final_diff,
                    attempt=attempt,
                    runtime_trace=agent_result.runtime_trace,
                    attempt_history=retry_attempt_history,
                    repair_analysis=repair_analysis,
                )
                started = time.perf_counter()
                workspace_restorer.restore()
                trace.time_event(
                    node_name="workspace_restore",
                    event_type="repair_retry_workspace",
                    status="completed",
                    output_summary="restored clean workspace before feedback retry",
                    payload={
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "baseline_path": str(workspace_restorer.baseline_path),
                    },
                    started=started,
                )
            final_diff_path.write_text(final_diff, encoding="utf-8")
            report = render_run_report(
                run_id=run_id,
                request=request,
                snapshot=snapshot,
                retrieved_context=retrieved_context,
                test_result=test_result,
                final_diff=final_diff,
                trace_events=trace.events,
                status=status,
                patch_status=agent_result.status,
                patch_summary=agent_result.summary,
                repair_analysis=repair_analysis,
            )
            report_path.write_text(report, encoding="utf-8")
            trace.emit(
                node_name="report",
                event_type="artifact_write",
                status="completed",
                output_summary=str(report_path),
                payload={"report_path": str(report_path), "final_diff_path": str(final_diff_path)},
            )
            workspace_restorer.cleanup()
        except Exception as error:
            status = "failed"
            trace.emit(
                node_name="run",
                event_type="lifecycle",
                status="failed",
                error=str(error),
                output_summary=type(error).__name__,
            )
            raise

        return RepairRunResult(
            run_id=run_id,
            status=status,
            run_dir=run_dir,
            repo_path=repo_path,
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            snapshot=snapshot,
            retrieved_context=retrieved_context,
            test_result=test_result,
            model_usage=model_usage_from_trace(trace.events),
        )


def _workspace_diff(repo_path: Path) -> str:
    if not (repo_path / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return ""
    return result.stdout


def _runtime_for(runtime_name: str, planner_name: str) -> AgentRuntime:
    if runtime_name == "deepagents":
        return DeepAgentsRuntime(planner=_planner_for(planner_name))
    if runtime_name == "heuristic":
        if planner_name != "heuristic":
            raise ValueError(
                "non-heuristic planners are currently supported only by the deepagents runtime"
            )
        return HeuristicRuntime()
    return AgentlessRuntime()


def _merge_retrieved_contexts(
    existing: list[RetrievedContext],
    refreshed: list[RetrievedContext],
    *,
    limit: int,
    deprioritized_paths: set[str] | None = None,
) -> list[RetrievedContext]:
    merged: list[RetrievedContext] = []
    seen_paths: set[str] = set()
    deprioritized = deprioritized_paths or set()
    reviewed_existing = [
        context
        for context in existing
        if "reviewed_source_hint" in context.matched_terms or "active_path" in context.matched_terms
    ]
    older_fallback = [
        context for context in existing if context not in reviewed_existing
    ]
    prioritized_reviewed = [
        context for context in reviewed_existing if context.path not in deprioritized
    ]
    delayed_contexts = [
        context
        for context in [*reviewed_existing, *refreshed, *older_fallback]
        if context.path in deprioritized
    ]
    prioritized_refreshed = [
        context for context in refreshed if context.path not in deprioritized
    ]
    prioritized_fallback = [
        context for context in older_fallback if context.path not in deprioritized
    ]
    for context in [
        *prioritized_reviewed,
        *prioritized_refreshed,
        *prioritized_fallback,
        *delayed_contexts,
    ]:
        if context.path in seen_paths:
            continue
        seen_paths.add(context.path)
        merged.append(dataclass_replace(context, rank=len(merged) + 1))
        if len(merged) >= limit:
            break
    return merged


def _retry_context_mount_limit(request: RunRequest) -> int:
    return request.top_k if request.top_k > 0 else 0


def _merge_path_lists(*path_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for path_list in path_lists:
        for path in path_list:
            if path not in merged:
                merged.append(path)
    return merged


def _runtime_config_with_resource_usage(
    runtime_config: dict[str, object],
    *,
    used_model_responses: int,
    used_model_tokens: int,
) -> dict[str, object]:
    copied = dict(runtime_config)
    resource_budget = copied.get("resource_budget")
    if not isinstance(resource_budget, dict):
        return copied
    updated_budget = dict(resource_budget)
    used_responses = max(0, used_model_responses)
    used_tokens = max(0, used_model_tokens)
    updated_budget["used_model_responses"] = used_responses
    updated_budget["used_model_tokens"] = used_tokens
    max_responses = _optional_nonnegative_int(
        updated_budget.get("max_model_responses")
    )
    if max_responses is not None:
        updated_budget["remaining_model_responses"] = max(
            0,
            max_responses - used_responses,
        )
    max_tokens = _optional_nonnegative_int(updated_budget.get("max_model_tokens"))
    if max_tokens is not None:
        updated_budget["remaining_model_tokens"] = max(0, max_tokens - used_tokens)
    copied["resource_budget"] = updated_budget
    return copied


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _nonnegative_int_or_zero(value: object) -> int:
    parsed = _optional_nonnegative_int(value)
    return parsed if parsed is not None else 0


def _retry_resource_budget_block(
    runtime_config: dict[str, object],
    *,
    used_model_responses: int,
    used_model_tokens: int,
) -> dict[str, object] | None:
    updated = _runtime_config_with_resource_usage(
        runtime_config,
        used_model_responses=used_model_responses,
        used_model_tokens=used_model_tokens,
    )
    resource_budget = updated.get("resource_budget")
    if not isinstance(resource_budget, dict):
        return None
    reasons: list[str] = []
    remaining_responses = _optional_nonnegative_int(
        resource_budget.get("remaining_model_responses")
    )
    if remaining_responses == 0:
        reasons.append("response_budget_exhausted")
    elif remaining_responses is not None and remaining_responses <= 4:
        reasons.append("response_budget_too_low_for_retry")
    remaining_tokens = _optional_nonnegative_int(
        resource_budget.get("remaining_model_tokens")
    )
    if remaining_tokens == 0:
        reasons.append("token_budget_exhausted")
    elif remaining_tokens is not None and remaining_tokens <= 100_000:
        reasons.append("token_budget_too_low_for_retry")
    if not reasons:
        return None
    reason = (
        "resource_budget_exhausted"
        if any(reason.endswith("_exhausted") for reason in reasons)
        else "resource_budget_insufficient_for_retry"
    )
    return {
        "reason": reason,
        "reasons": reasons,
        "resource_budget": resource_budget,
    }


def _planner_for(planner_name: str):
    if planner_name == "heuristic":
        return HeuristicRepairPlanner()
    if planner_name == "fake_model":
        return ModelBackedRepairPlanner(
            SeededFakeRepairModelClient(),
            name="fake_model_json_plan",
        )
    if planner_name == "openai":
        return ModelBackedRepairPlanner(
            OpenAIResponsesModelClient.from_env(),
            name="openai_json_plan",
        )
    if planner_name == "deepagents":
        return DeepAgentsRepairPlanner.from_env()
    raise ValueError(f"unsupported planner: {planner_name}")
