from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from patchsmith.models import PatchCandidate
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan, RepairPlanner
from patchsmith.runtime_core import (
    AgentResult,
    AgentTask,
    _no_patch_result,
    _plan_or_planner_metadata,
    _prepare_planner_for_task,
    _runtime_config_int,
)


class LangGraphRepairState(TypedDict, total=False):
    plan: RepairPlan | None
    trace: list[dict[str, Any]]
    attempt: int
    max_retries: int
    retry_decision: str
    last_error: str
    status: str
    summary: str
    generation_strategy: str
    final_diff: str
    files_changed: list[str]



class LangGraphRuntime:
    """LangGraph-backed repair runtime with a replaceable planner.

    The default planner is deterministic so tests and local evals do not require
    model credentials. The graph boundary is the important part: model planners
    can replace `HeuristicRepairPlanner` without changing workflow, sandbox,
    report, or eval code.
    """

    def __init__(self, planner: RepairPlanner | None = None) -> None:
        self.planner = planner or HeuristicRepairPlanner()

    def run(self, task: AgentTask) -> AgentResult:
        from langgraph.graph import END, StateGraph

        max_retries = _runtime_config_int(task.runtime_config, "max_retries", 0)
        _prepare_planner_for_task(self.planner, task)

        def triage_node(state: LangGraphRepairState) -> LangGraphRepairState:
            trace = list(state.get("trace", []))
            trace.append(
                {
                    "node": "triage",
                    "status": "completed",
                    "summary": f"{len(task.retrieved_context)} retrieved contexts",
                }
            )
            return {"trace": trace}

        def plan_node(state: LangGraphRepairState) -> LangGraphRepairState:
            plan = self.planner.plan(
                issue_text=task.issue_text,
                retrieved_context=task.retrieved_context,
            )
            trace = list(state.get("trace", []))
            attempt = int(state.get("attempt", 0)) + 1
            event: dict[str, Any] = {
                "node": "plan",
                "status": "completed" if plan else "no_match",
                "summary": plan.summary if plan else "No repair plan produced.",
                "attempt": attempt,
                "max_retries": max_retries,
            }
            metadata = _plan_or_planner_metadata(plan, self.planner)
            if metadata:
                event["metadata"] = metadata
            trace.append(event)
            return {"plan": plan, "trace": trace}

        def edit_node(state: LangGraphRepairState) -> LangGraphRepairState:
            plan = state.get("plan")
            trace = list(state.get("trace", []))
            attempt = int(state.get("attempt", 0)) + 1
            if not plan:
                trace.append(
                    {
                        "node": "edit",
                        "status": "skipped",
                        "summary": "No repair plan available to apply.",
                        "attempt": attempt,
                    }
                )
                return {
                    "status": "no_patch_generated",
                    "summary": "LangGraph planner produced no edit plan.",
                    "generation_strategy": "langgraph:no_plan",
                    "final_diff": "",
                    "files_changed": [],
                    "attempt": attempt,
                    "last_error": "no_plan",
                    "trace": trace,
                }

            try:
                edit = apply_text_replacement(
                    repo_path=Path(task.repo_path),
                    relative_path=plan.path,
                    old=plan.old,
                    new=plan.new,
                )
                trace.append(
                    {
                        "node": "edit",
                        "status": "completed",
                        "summary": f"Edited {plan.path}",
                        "attempt": attempt,
                    }
                )
                return {
                    "status": "patch_generated",
                    "summary": f"Applied repair plan `{plan.name}` to {plan.path}.",
                    "generation_strategy": f"langgraph:{plan.name}",
                    "final_diff": edit.diff,
                    "files_changed": [plan.path],
                    "attempt": attempt,
                    "last_error": "",
                    "trace": trace,
                }
            except PatchSafetyError as error:
                trace.append(
                    {
                        "node": "edit",
                        "status": "failed",
                        "summary": str(error),
                        "attempt": attempt,
                    }
                )
                return {
                    "status": "no_patch_generated",
                    "summary": str(error),
                    "generation_strategy": "langgraph:edit_failed",
                    "final_diff": "",
                    "files_changed": [],
                    "attempt": attempt,
                    "last_error": str(error),
                    "trace": trace,
                }

        def analyze_node(state: LangGraphRepairState) -> LangGraphRepairState:
            trace = list(state.get("trace", []))
            final_diff = state.get("final_diff", "")
            attempt = int(state.get("attempt", 0))
            status = "ready_for_test" if final_diff else "needs_retry_decision"
            summary = (
                "Patch candidate ready for workflow-level sandbox validation."
                if final_diff
                else f"No patch candidate after attempt {attempt}: {state.get('summary', '')}"
            )
            trace.append(
                {
                    "node": "analyze",
                    "status": status,
                    "summary": summary,
                    "attempt": attempt,
                    "last_error": str(state.get("last_error", "")),
                }
            )
            return {"trace": trace}

        def retry_node(state: LangGraphRepairState) -> LangGraphRepairState:
            trace = list(state.get("trace", []))
            attempt = int(state.get("attempt", 0))
            final_diff = state.get("final_diff", "")
            if final_diff:
                decision = "stop"
                status = "not_needed"
                summary = "Patch candidate exists; no retry needed."
            elif attempt <= max_retries:
                decision = "retry"
                status = "scheduled"
                summary = f"Retry {attempt} of {max_retries} scheduled."
            else:
                decision = "stop"
                status = "exhausted"
                summary = f"Retry budget exhausted after {attempt} attempt(s)."
            trace.append(
                {
                    "node": "retry",
                    "status": status,
                    "summary": summary,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "decision": decision,
                }
            )
            return {"retry_decision": decision, "trace": trace}

        def review_node(state: LangGraphRepairState) -> LangGraphRepairState:
            trace = list(state.get("trace", []))
            final_diff = state.get("final_diff", "")
            trace.append(
                {
                    "node": "review",
                    "status": str(state.get("status", "missing_result")),
                    "summary": "Generated one patch candidate." if final_diff else "No diff generated.",
                    "attempt": int(state.get("attempt", 0)),
                }
            )
            return {"trace": trace}

        def route_after_retry(state: LangGraphRepairState) -> str:
            return "retry" if state.get("retry_decision") == "retry" else "stop"

        graph = StateGraph(LangGraphRepairState)
        graph.add_node("triage", triage_node)
        graph.add_node("plan", plan_node)
        graph.add_node("edit", edit_node)
        graph.add_node("analyze", analyze_node)
        graph.add_node("retry", retry_node)
        graph.add_node("review", review_node)
        graph.set_entry_point("triage")
        graph.add_edge("triage", "plan")
        graph.add_edge("plan", "edit")
        graph.add_edge("edit", "analyze")
        graph.add_edge("analyze", "retry")
        graph.add_conditional_edges(
            "retry",
            route_after_retry,
            {
                "retry": "plan",
                "stop": "review",
            },
        )
        graph.add_edge("review", END)
        compiled = graph.compile()
        state = compiled.invoke(
            {
                "trace": [],
                "plan": None,
                "attempt": 0,
                "max_retries": max_retries,
                "retry_decision": "stop",
                "last_error": "",
                "status": "not_started",
                "summary": "",
                "generation_strategy": "langgraph:unknown",
                "final_diff": "",
                "files_changed": [],
            }
        )
        status = str(state.get("status", "no_patch_generated"))
        summary = str(state.get("summary", "LangGraph run finished without a result."))
        final_diff = str(state.get("final_diff", ""))
        generation_strategy = str(state.get("generation_strategy", "langgraph:unknown"))
        files_changed = list(state.get("files_changed", []))
        trace = list(state.get("trace", []))
        if final_diff:
            return AgentResult(
                status=status,
                summary=summary,
                final_diff=final_diff,
                patch_candidates=[
                    PatchCandidate(
                        candidate_id=f"{task.run_id}-candidate-1",
                        candidate_index=1,
                        generation_strategy=generation_strategy,
                        diff=final_diff,
                        files_changed=[str(path) for path in files_changed],
                        selected=True,
                        status="generated",
                        risk_notes=[
                            "LangGraph planner output applied through a bounded text replacement.",
                            "Review before using outside controlled fixtures.",
                        ],
                    )
                ],
                test_results=[],
                runtime_trace=trace,
            )
        return _no_patch_result(
            task=task,
            generation_strategy=generation_strategy,
            summary=summary,
            runtime_trace=trace,
        )
