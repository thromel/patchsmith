from __future__ import annotations

from importlib.util import find_spec
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypedDict

from patchsmith.models import CommandResult, PatchCandidate, RetrievedContext
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan, RepairPlanner


@dataclass(frozen=True)
class AgentTask:
    run_id: str
    repo_path: str
    issue_text: str
    retrieved_context: list[RetrievedContext]
    test_command: str | None
    runtime_config: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    status: str
    summary: str
    final_diff: str
    patch_candidates: list[PatchCandidate]
    test_results: list[CommandResult]
    runtime_trace: list[dict[str, Any]] = field(default_factory=list)


class AgentRuntime(Protocol):
    def run(self, task: AgentTask) -> AgentResult:
        """Run an issue-to-patch attempt behind a framework-neutral boundary."""


class AgentlessRuntime:
    """Deterministic baseline runtime used before model-backed patching is wired in."""

    def run(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            status="no_patch_generated",
            summary=(
                "Agentless scaffold inspected retrieved context but did not generate edits. "
                "This is the control runtime for ingestion, retrieval, sandbox, and report plumbing."
            ),
            final_diff="",
            patch_candidates=[
                PatchCandidate(
                    candidate_id=f"{task.run_id}-candidate-1",
                    candidate_index=1,
                    generation_strategy="agentless_noop",
                    diff="",
                    files_changed=[],
                    selected=True,
                    status="no_patch_generated",
                    risk_notes=["No code edits attempted."],
                )
            ],
            test_results=[],
        )


class HeuristicRuntime:
    """Deterministic repair baseline for seeded smoke tasks.

    This is not a replacement for the planned LangGraph runtime. It provides a
    bounded patch-attempt path so the rest of the product loop can be exercised
    before model calls are introduced.
    """

    def __init__(self, planner: RepairPlanner | None = None) -> None:
        self.planner = planner or HeuristicRepairPlanner()

    def run(self, task: AgentTask) -> AgentResult:
        repo_path = Path(task.repo_path)
        plan = self.planner.plan(issue_text=task.issue_text, retrieved_context=task.retrieved_context)
        if plan:
            try:
                return _apply_plan(
                    task=task,
                    repo_path=repo_path,
                    plan=plan,
                    generation_strategy=f"heuristic:{plan.name}",
                    risk_notes=[
                        "Deterministic seeded-task repair baseline.",
                        "Review before using outside controlled fixtures.",
                    ],
                    runtime_trace=[
                        {"node": "plan", "status": "completed", "summary": plan.summary},
                        {"node": "edit", "status": "completed", "summary": plan.path},
                        {"node": "review", "status": "completed", "summary": "single diff generated"},
                    ],
                )
            except PatchSafetyError:
                pass

        return AgentResult(
            status="no_patch_generated",
            summary="No heuristic repair rule matched the issue and retrieved source files.",
            final_diff="",
            patch_candidates=[
                PatchCandidate(
                    candidate_id=f"{task.run_id}-candidate-1",
                    candidate_index=1,
                    generation_strategy="heuristic:no_match",
                    diff="",
                    files_changed=[],
                    selected=True,
                    status="no_patch_generated",
                    risk_notes=["No heuristic edit attempted."],
                )
            ],
            test_results=[],
            runtime_trace=[
                {
                    "node": "plan",
                    "status": "no_match",
                    "summary": "No deterministic repair rule matched.",
                }
            ],
        )


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
            if plan and plan.metadata:
                event["metadata"] = plan.metadata
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


class DeepAgentsRuntime:
    """Dependency-gated DeepAgents adapter behind the shared runtime boundary.

    The real `deepagents` package is optional. Local seeded evals use the same
    bounded planner/edit contract as other runtimes while emitting DeepAgents
    scaffold events for comparison. This keeps the adapter measurable without
    requiring live model credentials or installing the package globally.
    """

    def __init__(self, planner: RepairPlanner | None = None) -> None:
        self.planner = planner or HeuristicRepairPlanner()

    def run(self, task: AgentTask) -> AgentResult:
        repo_path = Path(task.repo_path)
        package_available = find_spec("deepagents") is not None
        mode = "package_available" if package_available else "compatibility_mode"
        trace: list[dict[str, Any]] = [
            {
                "node": "harness",
                "status": mode,
                "summary": (
                    "DeepAgents package is importable; using bounded PatchSmith edit contract."
                    if package_available
                    else "DeepAgents package is not installed; using offline adapter compatibility mode."
                ),
                "framework": "deepagents",
            },
            {
                "node": "todo",
                "status": "completed",
                "summary": "Created repair todo from issue, retrieved context, and test command.",
                "todo_count": 3 if task.test_command else 2,
            },
            {
                "node": "context",
                "status": "completed",
                "summary": f"{len(task.retrieved_context)} retrieved contexts available to scaffold.",
                "context_paths": [context.path for context in task.retrieved_context],
            },
        ]
        plan = self.planner.plan(
            issue_text=task.issue_text,
            retrieved_context=task.retrieved_context,
        )
        trace.append(
            {
                "node": "plan",
                "status": "completed" if plan else "no_match",
                "summary": (
                    plan.summary
                    if plan
                    else "DeepAgents adapter produced no bounded repair plan."
                ),
            }
        )
        if not plan:
            trace.append(
                {
                    "node": "review",
                    "status": "no_patch_generated",
                    "summary": "No patch candidate generated by DeepAgents adapter.",
                }
            )
            return _no_patch_result(
                task=task,
                generation_strategy="deepagents:no_plan",
                summary="DeepAgents adapter produced no bounded repair plan.",
                runtime_trace=trace,
            )
        try:
            result = _apply_plan(
                task=task,
                repo_path=repo_path,
                plan=plan,
                generation_strategy=f"deepagents:{plan.name}",
                risk_notes=[
                    "DeepAgents adapter uses PatchSmith's bounded text replacement safety gate.",
                    (
                        "Real deepagents package was available."
                        if package_available
                        else "Offline compatibility mode; install optional deepagents extra for live harness work."
                    ),
                    "Review before using outside controlled fixtures.",
                ],
                runtime_trace=[
                    *trace,
                    {"node": "edit", "status": "completed", "summary": f"Edited {plan.path}"},
                    {
                        "node": "review",
                        "status": "patch_generated",
                        "summary": "DeepAgents adapter generated one bounded patch candidate.",
                    },
                ],
            )
        except PatchSafetyError as error:
            trace.extend(
                [
                    {
                        "node": "edit",
                        "status": "failed",
                        "summary": str(error),
                    },
                    {
                        "node": "review",
                        "status": "no_patch_generated",
                        "summary": "Patch safety gate rejected DeepAgents adapter edit.",
                    },
                ]
            )
            return _no_patch_result(
                task=task,
                generation_strategy="deepagents:edit_failed",
                summary=str(error),
                runtime_trace=trace,
            )
        return result


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


def _apply_plan(
    *,
    task: AgentTask,
    repo_path: Path,
    plan: RepairPlan,
    generation_strategy: str,
    risk_notes: list[str],
    runtime_trace: list[dict[str, Any]],
) -> AgentResult:
    edit = apply_text_replacement(
        repo_path=repo_path,
        relative_path=plan.path,
        old=plan.old,
        new=plan.new,
    )
    return AgentResult(
        status="patch_generated",
        summary=f"Applied repair plan `{plan.name}` to {plan.path}.",
        final_diff=edit.diff,
        patch_candidates=[
            PatchCandidate(
                candidate_id=f"{task.run_id}-candidate-1",
                candidate_index=1,
                generation_strategy=generation_strategy,
                diff=edit.diff,
                files_changed=[plan.path],
                selected=True,
                status="generated",
                risk_notes=risk_notes,
            )
        ],
        test_results=[],
        runtime_trace=runtime_trace,
    )


def _no_patch_result(
    *,
    task: AgentTask,
    generation_strategy: str,
    summary: str,
    runtime_trace: list[dict[str, Any]],
) -> AgentResult:
    return AgentResult(
        status="no_patch_generated",
        summary=summary,
        final_diff="",
        patch_candidates=[
            PatchCandidate(
                candidate_id=f"{task.run_id}-candidate-1",
                candidate_index=1,
                generation_strategy=generation_strategy,
                diff="",
                files_changed=[],
                selected=True,
                status="no_patch_generated",
                risk_notes=["No code edits attempted."],
            )
        ],
        test_results=[],
        runtime_trace=runtime_trace,
    )


def _runtime_config_int(config: dict[str, object], key: str, default: int) -> int:
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return max(0, value)
    return default
