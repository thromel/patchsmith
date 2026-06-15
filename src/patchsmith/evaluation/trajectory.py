"""Trace-derived metrics for agentic repair trajectories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgentTrajectoryMetrics:
    """Machine-readable signals for modern agent-loop behavior.

    These are intentionally derived from saved PatchSmith traces rather than
    prompt claims. A run gets credit only when the trace records a corresponding
    runtime node, contract, retry event, or patch diagnostic.
    """

    todo_planning: bool = False
    constrained_filesystem: bool = False
    specialist_review: bool = False
    guardrails: bool = False
    structured_output: bool = False
    retry_feedback: bool = False
    patch_diagnostics: bool = False
    contextual_verifier: bool = False
    process_quality_label: str = "unscored"
    process_quality_score: float = 0.0
    process_quality_flags: tuple[str, ...] = ()
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def agent_trajectory_metrics(events: list[dict[str, Any]]) -> AgentTrajectoryMetrics:
    runtime_payloads: list[dict[str, Any]] = []
    for event in events:
        if not _node_name(event).startswith("runtime."):
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            runtime_payloads.append(payload)
    node_names = {_node_name(event) for event in events}
    payload_nodes = {str(payload.get("node", "")) for payload in runtime_payloads}

    contracts = [
        contract
        for payload in runtime_payloads
        for contract in [_deepagents_contract(payload)]
        if contract is not None
    ]

    todo_planning = "runtime.todo" in node_names or "todo" in payload_nodes or any(
        _planning_policy(contract).get("todos_required") is True for contract in contracts
    )
    constrained_filesystem = any(
        bool(_filesystem_policy(contract).get("allowed_read_paths")) for contract in contracts
    )
    specialist_review = (
        "runtime.review" in node_names
        or "review" in payload_nodes
        or any(bool(contract.get("subagents")) for contract in contracts)
    )
    guardrails = (
        "runtime.guardrails" in node_names
        or any(_planning_policy(contract).get("one_bounded_replacement") is True for contract in contracts)
        or any(_has_patch_plan(payload) for payload in runtime_payloads)
    )
    structured_output = any(
        contract.get("response_format") or contract.get("response_schema") for contract in contracts
    )
    retry_feedback = any(
        _node_name(event) == "feedback_retry"
        or event.get("event_type") in {"repair_retry", "retry"}
        or _node_name(event) == "runtime.retry"
        for event in events
    )
    patch_diagnostics = any(_has_patch_plan(payload) for payload in runtime_payloads)
    contextual_verifier = any(_has_contextual_verifier(contract) for contract in contracts)
    process_quality_label, process_quality_score, process_quality_flags = (
        _process_quality(events)
    )

    score = _average_bool(
        [
            todo_planning,
            constrained_filesystem,
            specialist_review,
            guardrails,
            structured_output,
            retry_feedback,
            patch_diagnostics,
        ]
    )
    return AgentTrajectoryMetrics(
        todo_planning=todo_planning,
        constrained_filesystem=constrained_filesystem,
        specialist_review=specialist_review,
        guardrails=guardrails,
        structured_output=structured_output,
        retry_feedback=retry_feedback,
        patch_diagnostics=patch_diagnostics,
        contextual_verifier=contextual_verifier,
        process_quality_label=process_quality_label,
        process_quality_score=process_quality_score,
        process_quality_flags=process_quality_flags,
        score=score,
    )


def _node_name(event: dict[str, Any]) -> str:
    return str(event.get("node_name", ""))


def _deepagents_contract(payload: dict[str, Any]) -> dict[str, Any] | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    contract = metadata.get("deepagents_contract")
    return contract if isinstance(contract, dict) else None


def _planning_policy(contract: dict[str, Any]) -> dict[str, Any]:
    value = contract.get("planning_policy")
    return value if isinstance(value, dict) else {}


def _filesystem_policy(contract: dict[str, Any]) -> dict[str, Any]:
    value = contract.get("filesystem_policy")
    return value if isinstance(value, dict) else {}


def _has_patch_plan(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("patch_plan"), dict)


def _has_contextual_verifier(contract: dict[str, Any]) -> bool:
    if isinstance(contract.get("contextual_verifier"), dict):
        return True
    if contract.get("acceptance_rubric_manifest_path"):
        return True
    return _planning_policy(contract).get("acceptance_rubric_manifest_read_first") is True


def _process_quality(events: list[dict[str, Any]]) -> tuple[str, float, tuple[str, ...]]:
    if not events:
        return ("unscored", 0.0, ("missing_trace",))

    flags: list[str] = []
    if not _has_verification_event(events):
        flags.append("missing_verification")
    if _has_blind_feedback_retry(events):
        flags.append("blind_retry")
    if _failed_event_count(events) >= 3:
        flags.append("failed_event_churn")
    if _has_edit_after_successful_verification(events):
        flags.append("post_verification_edit")

    score = _process_quality_score(flags)
    if not flags:
        label = "solid"
    elif any(
        flag
        in {
            "missing_verification",
            "blind_retry",
            "post_verification_edit",
        }
        for flag in flags
    ):
        label = "risky"
    else:
        label = "watch"
    return (label, score, tuple(flags))


def _has_verification_event(events: list[dict[str, Any]]) -> bool:
    return any(
        _node_name(event) == "test"
        or str(event.get("event_type", "")) in {"sandbox_command", "repair_outcome"}
        for event in events
    )


def _has_blind_feedback_retry(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if _node_name(event) != "feedback_retry":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return True
        raw_labels = payload.get("retry_labels")
        has_label = isinstance(raw_labels, list) and any(
            isinstance(label, str) and bool(label) for label in raw_labels
        )
        has_failure_class = isinstance(payload.get("retry_failure_class"), str) and bool(
            payload["retry_failure_class"]
        )
        if not has_label and not has_failure_class:
            return True
    return False


def _failed_event_count(events: list[dict[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if str(event.get("status", "")).lower() in {"failed", "error"}
        or event.get("error") is not None
    )


def _has_edit_after_successful_verification(events: list[dict[str, Any]]) -> bool:
    successful_verification_seen = False
    for event in events:
        if _is_successful_verification(event):
            successful_verification_seen = True
            continue
        if successful_verification_seen and _node_name(event) in {
            "runtime.edit",
            "runtime.patch",
        }:
            return True
    return False


def _is_successful_verification(event: dict[str, Any]) -> bool:
    if _node_name(event) == "test":
        payload = event.get("payload")
        if isinstance(payload, dict) and payload.get("exit_code") == 0:
            return True
        return str(event.get("status", "")).lower() in {"passed", "validated"}
    if str(event.get("event_type", "")) != "repair_outcome":
        return False
    if str(event.get("status", "")).lower() == "validated":
        return True
    payload = event.get("payload")
    return isinstance(payload, dict) and payload.get("tests_passed") is True


def _process_quality_score(flags: list[str]) -> float:
    penalties = {
        "missing_verification": 0.35,
        "blind_retry": 0.30,
        "failed_event_churn": 0.20,
        "post_verification_edit": 0.35,
    }
    score = 1.0 - sum(penalties.get(flag, 0.10) for flag in flags)
    return max(0.0, round(score, 4))


def _average_bool(values: list[bool]) -> float:
    if not values:
        return 0.0
    return sum(1.0 if value else 0.0 for value in values) / len(values)
