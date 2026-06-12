from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from patchsmith.models import CommandResult, PatchCandidate, RetrievedContext
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan, RepairPlanner
from patchsmith.runtime.plan_diagnostics import repair_plan_diagnostics


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
        plan = self.planner.plan(
            issue_text=task.issue_text, retrieved_context=task.retrieved_context
        )
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
                        {
                            "node": "plan",
                            "status": "completed",
                            "summary": plan.summary,
                            "patch_plan": repair_plan_diagnostics(
                                plan,
                                repo_path=repo_path,
                            ),
                        },
                        {"node": "edit", "status": "completed", "summary": plan.path},
                        {
                            "node": "review",
                            "status": "completed",
                            "summary": "single diff generated",
                        },
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


def _plan_or_planner_metadata(
    plan: RepairPlan | None,
    planner: RepairPlanner,
) -> dict[str, Any] | None:
    if plan and plan.metadata:
        return plan.metadata
    planner_metadata = getattr(planner, "last_plan_metadata", None)
    if isinstance(planner_metadata, dict) and planner_metadata:
        return planner_metadata
    model_metadata = getattr(planner, "last_model_metadata", None)
    to_dict = getattr(model_metadata, "to_dict", None)
    if callable(to_dict):
        return {"model_call": to_dict()}
    return None


def _prepare_planner_for_task(planner: RepairPlanner, task: AgentTask) -> None:
    prepare_task = getattr(planner, "prepare_task", None)
    if callable(prepare_task):
        prepare_task(task)


def _plan_for_task(planner: RepairPlanner, task: AgentTask) -> RepairPlan | None:
    plan_for_task = getattr(planner, "plan_for_task", None)
    if callable(plan_for_task):
        return plan_for_task(task=task)
    _prepare_planner_for_task(planner, task)
    return planner.plan(
        issue_text=task.issue_text,
        retrieved_context=task.retrieved_context,
    )
