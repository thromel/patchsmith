from __future__ import annotations

import subprocess
import time
from pathlib import Path

from patchsmith.analysis import analyze_repair_outcome
from patchsmith.context import (
    ContextBrokerError,
    ContextBrokerRequest,
    CtxhelmCliBroker,
    PatchSmithNativeBroker,
    fallback_bundle,
    promote_active_context_targets,
    retrieved_context_from_bundle,
)
from patchsmith.deepagents_planner import DeepAgentsRepairPlanner
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RepairRunResult, RunRequest, new_id
from patchsmith.planning import (
    HeuristicRepairPlanner,
    ModelBackedRepairPlanner,
    OpenAIResponsesModelClient,
    SeededFakeRepairModelClient,
)
from patchsmith.reporting import render_run_report
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.runtime import (
    AgentlessRuntime,
    AgentRuntime,
    AgentTask,
    DeepAgentsRuntime,
    HeuristicRuntime,
    LangGraphRuntime,
    OpenAIAgentsRuntime,
)
from patchsmith.runtime.attempts import (
    emit_agent_result_trace,
    issue_with_test_feedback,
    run_sandbox_attempt,
    should_retry_with_test_feedback,
    test_feedback_retry_budget,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.tracing import RunTrace


class RepairRunner:
    def __init__(self, *, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.retriever = KeywordRetriever()
        self.native_broker = PatchSmithNativeBroker(self.retriever)
        self.hybrid_retriever = HybridRetriever()
        self.hybrid_broker = PatchSmithNativeBroker(
            self.hybrid_retriever, provider_name="patchsmith_native_hybrid"
        )
        self.graph_retriever = GraphRetriever()
        self.graph_broker = PatchSmithNativeBroker(
            self.graph_retriever, provider_name="patchsmith_native_graph"
        )
        self.ctxhelm_broker = CtxhelmCliBroker()

    def run(self, request: RunRequest) -> RepairRunResult:
        run_id = new_id()
        run_dir = (self.artifacts_dir / "runs" / run_id).resolve()
        repo_path = run_dir / "repo"
        patches_dir = run_dir / "patches"
        logs_dir = run_dir / "logs"
        report_path = run_dir / "report.md"
        trace_path = run_dir / "traces.jsonl"
        final_diff_path = run_dir / "final.diff"
        context_dir = run_dir / "context"
        for directory in (patches_dir, logs_dir):
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

            started = time.perf_counter()
            native_context = self.retriever.retrieve(
                repo_path=repo_path,
                repo_index=repo_index,
                issue_text=request.issue_text,
                top_k=request.top_k,
            )
            hybrid_context = self.hybrid_retriever.retrieve(
                repo_path=repo_path,
                repo_index=repo_index,
                issue_text=request.issue_text,
                top_k=request.top_k,
            )
            graph_context = self.graph_retriever.retrieve(
                repo_path=repo_path,
                repo_index=repo_index,
                issue_text=request.issue_text,
                top_k=request.top_k,
            )
            trace.time_event(
                node_name="retrieve",
                event_type="keyword_search",
                status="completed",
                input_summary=request.issue_text[:160],
                output_summary=(
                    ", ".join(context.path for context in native_context) or "no matches"
                ),
                payload={"contexts": [context.to_dict() for context in native_context]},
                started=started,
            )

            broker_request = ContextBrokerRequest(
                repo_path=repo_path,
                task=request.issue_text,
                active_paths=request.context_paths,
            )
            native_bundle = self.native_broker.prepare(
                broker_request,
                repo_index=repo_index,
                artifact_dir=context_dir,
            )
            context_bundle = native_bundle
            fallback_contexts = native_context
            if request.context_provider == "native_hybrid":
                context_bundle = self.hybrid_broker.prepare(
                    broker_request,
                    repo_index=repo_index,
                    artifact_dir=context_dir,
                )
                fallback_contexts = hybrid_context
            if request.context_provider == "native_graph":
                context_bundle = self.graph_broker.prepare(
                    broker_request,
                    repo_index=repo_index,
                    artifact_dir=context_dir,
                )
                fallback_contexts = graph_context
            if request.context_provider in {"ctxhelm_cli", "auto"}:
                try:
                    context_bundle = self.ctxhelm_broker.prepare(
                        broker_request,
                        repo_index=repo_index,
                        artifact_dir=context_dir,
                    )
                except ContextBrokerError as error:
                    context_bundle = fallback_bundle(
                        provider="ctxhelm_cli",
                        reason=str(error),
                        native_bundle=native_bundle,
                    )
                if not context_bundle.targets:
                    context_bundle = fallback_bundle(
                        provider="ctxhelm_cli",
                        reason="ctxhelm returned no target files; using native keyword contexts",
                        native_bundle=native_bundle,
                    )
            context_bundle = promote_active_context_targets(
                bundle=context_bundle,
                repo_path=repo_path,
                active_paths=request.context_paths,
            )

            trace.emit(
                node_name="context_broker",
                event_type="context_broker_call",
                status="fallback" if context_bundle.fallback_used else "completed",
                input_summary=request.context_provider,
                output_summary=(
                    f"{context_bundle.provider} targets={len(context_bundle.targets)} "
                    f"tests={len(context_bundle.related_tests)}"
                ),
                payload=context_bundle.to_dict(),
                latency_ms=context_bundle.latency_ms,
            )

            retrieved_context = retrieved_context_from_bundle(
                bundle=context_bundle,
                repo_path=repo_path,
                fallback_contexts=fallback_contexts,
                top_k=request.top_k,
            )

            runtime = _runtime_for(request.runtime, request.planner)
            command = request.test_command or (
                snapshot.test_commands[0] if snapshot.test_commands else None
            )
            sandbox = create_sandbox_runner(
                mode=request.sandbox_mode,
                image=request.sandbox_image,
            )
            attempt_issue_text = request.issue_text
            attempt = 0
            max_feedback_retries = test_feedback_retry_budget(request)
            while True:
                attempt += 1
                agent_result = runtime.run(
                    AgentTask(
                        run_id=run_id,
                        repo_path=str(repo_path),
                        issue_text=attempt_issue_text,
                        retrieved_context=retrieved_context,
                        test_command=command,
                        runtime_config={
                            "planner": request.planner,
                            "max_retries": request.max_retries,
                            "workflow_attempt": attempt,
                            "test_feedback_retries": max_feedback_retries,
                        },
                    )
                )
                emit_agent_result_trace(
                    trace=trace,
                    request=request,
                    agent_result=agent_result,
                    attempt=attempt,
                )
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
                    attempt=attempt,
                    max_feedback_retries=max_feedback_retries,
                ):
                    break
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
                    },
                )
                attempt_issue_text = issue_with_test_feedback(
                    original_issue=request.issue_text,
                    agent_status=agent_result.status,
                    agent_summary=agent_result.summary,
                    test_result=test_result,
                    final_diff=final_diff,
                    attempt=attempt,
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
    if runtime_name == "langgraph":
        return LangGraphRuntime(planner=_planner_for(planner_name))
    if runtime_name == "deepagents":
        return DeepAgentsRuntime(planner=_planner_for(planner_name))
    if runtime_name == "openai_agents":
        return OpenAIAgentsRuntime(planner=_planner_for(planner_name))
    if runtime_name == "heuristic":
        if planner_name != "heuristic":
            raise ValueError(
                "non-heuristic planners are currently supported only by langgraph "
                "deepagents, and openai_agents runtimes"
            )
        return HeuristicRuntime()
    return AgentlessRuntime()


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
