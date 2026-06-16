from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.session.events import TranscriptEvent
from patchsmith.session.store import read_known_transcript_events


@dataclass(frozen=True)
class AgentSessionMetrics:
    task_count: int
    preflight_count: int
    preflight_passed_count: int
    run_preflight_count: int
    run_preflight_passed_count: int
    model_preflight_count: int
    model_preflight_passed_count: int
    model_preflight_blocked_count: int
    run_count: int
    validated_run_count: int
    run_error_count: int
    verify_count: int
    verify_passed_count: int
    diff_view_count: int
    diff_review_count: int
    diff_review_high_count: int
    current_diff_review_count: int
    current_diff_review_high_count: int
    apply_check_count: int
    apply_check_ready_count: int
    current_apply_check_ready_count: int
    apply_approval_count: int
    high_risk_apply_approval_count: int
    apply_rejection_count: int
    high_risk_apply_rejection_count: int
    apply_block_count: int
    apply_auto_deferred_count: int
    apply_attempt_count: int
    apply_success_count: int
    rewind_attempt_count: int
    rewind_success_count: int
    custom_command_count: int
    hook_run_count: int
    hook_block_count: int
    context_update_count: int
    permission_update_count: int
    model_update_count: int
    budget_update_count: int
    agent_profile_update_count: int
    instruction_update_count: int
    instruction_view_count: int
    memory_view_count: int
    plan_update_count: int
    plan_view_count: int
    feedback_update_count: int
    feedback_view_count: int
    session_gate_count: int
    session_gate_failure_count: int
    run_evidence_count: int
    checkpoint_count: int
    restore_count: int
    timeline_view_count: int
    next_view_count: int
    model_call_count: int
    model_response_count: int
    model_total_tokens: int
    estimated_cost_usd: float

    @property
    def validation_rate(self) -> float | None:
        return _rate(self.validated_run_count, self.run_count)

    @property
    def preflight_to_run_rate(self) -> float | None:
        return _rate(self.run_count, self.preflight_count)

    @property
    def apply_success_rate(self) -> float | None:
        return _rate(self.apply_success_count, self.apply_attempt_count)

    @property
    def rewind_success_rate(self) -> float | None:
        return _rate(self.rewind_success_count, self.rewind_attempt_count)

    @property
    def cost_per_validated_run_usd(self) -> float | None:
        if self.validated_run_count <= 0:
            return None
        return self.estimated_cost_usd / self.validated_run_count

    def to_dict(self) -> dict[str, object]:
        return {
            "task_count": self.task_count,
            "preflight_count": self.preflight_count,
            "preflight_passed_count": self.preflight_passed_count,
            "run_preflight_count": self.run_preflight_count,
            "run_preflight_passed_count": self.run_preflight_passed_count,
            "model_preflight_count": self.model_preflight_count,
            "model_preflight_passed_count": self.model_preflight_passed_count,
            "model_preflight_blocked_count": self.model_preflight_blocked_count,
            "run_count": self.run_count,
            "validated_run_count": self.validated_run_count,
            "run_error_count": self.run_error_count,
            "verify_count": self.verify_count,
            "verify_passed_count": self.verify_passed_count,
            "diff_view_count": self.diff_view_count,
            "diff_review_count": self.diff_review_count,
            "diff_review_high_count": self.diff_review_high_count,
            "current_diff_review_count": self.current_diff_review_count,
            "current_diff_review_high_count": self.current_diff_review_high_count,
            "apply_check_count": self.apply_check_count,
            "apply_check_ready_count": self.apply_check_ready_count,
            "current_apply_check_ready_count": self.current_apply_check_ready_count,
            "apply_approval_count": self.apply_approval_count,
            "high_risk_apply_approval_count": self.high_risk_apply_approval_count,
            "apply_rejection_count": self.apply_rejection_count,
            "high_risk_apply_rejection_count": self.high_risk_apply_rejection_count,
            "apply_block_count": self.apply_block_count,
            "apply_auto_deferred_count": self.apply_auto_deferred_count,
            "apply_attempt_count": self.apply_attempt_count,
            "apply_success_count": self.apply_success_count,
            "rewind_attempt_count": self.rewind_attempt_count,
            "rewind_success_count": self.rewind_success_count,
            "custom_command_count": self.custom_command_count,
            "hook_run_count": self.hook_run_count,
            "hook_block_count": self.hook_block_count,
            "context_update_count": self.context_update_count,
            "permission_update_count": self.permission_update_count,
            "model_update_count": self.model_update_count,
            "budget_update_count": self.budget_update_count,
            "agent_profile_update_count": self.agent_profile_update_count,
            "instruction_update_count": self.instruction_update_count,
            "instruction_view_count": self.instruction_view_count,
            "memory_view_count": self.memory_view_count,
            "plan_update_count": self.plan_update_count,
            "plan_view_count": self.plan_view_count,
            "feedback_update_count": self.feedback_update_count,
            "feedback_view_count": self.feedback_view_count,
            "session_gate_count": self.session_gate_count,
            "session_gate_failure_count": self.session_gate_failure_count,
            "run_evidence_count": self.run_evidence_count,
            "checkpoint_count": self.checkpoint_count,
            "restore_count": self.restore_count,
            "timeline_view_count": self.timeline_view_count,
            "next_view_count": self.next_view_count,
            "model_call_count": self.model_call_count,
            "model_response_count": self.model_response_count,
            "model_total_tokens": self.model_total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "validation_rate": self.validation_rate,
            "preflight_to_run_rate": self.preflight_to_run_rate,
            "apply_success_rate": self.apply_success_rate,
            "rewind_success_rate": self.rewind_success_rate,
            "cost_per_validated_run_usd": self.cost_per_validated_run_usd,
        }


def session_usage_payload(transcript_path: Path) -> dict[str, object]:
    return _session_usage_payload(read_known_transcript_events(transcript_path))


def _session_usage_payload(events: list[TranscriptEvent]) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_count": 0,
        "run_count": 0,
        "validated_run_count": 0,
        "run_error_count": 0,
        "model_call_count": 0,
        "model_response_count": 0,
        "model_total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    for row in events:
        event = row.event
        row_payload = row.payload
        if event == "user_task":
            payload["task_count"] = _increment_int(payload["task_count"])
        elif event == "run_result":
            payload["run_count"] = _increment_int(payload["run_count"])
            if row_payload.get("test_exit_code") == 0:
                payload["validated_run_count"] = _increment_int(
                    payload["validated_run_count"]
                )
            _add_usage(payload, row_payload)
        elif event == "run_error":
            payload["run_error_count"] = _increment_int(payload["run_error_count"])
    return payload


def session_metrics(transcript_path: Path) -> AgentSessionMetrics:
    rows = read_known_transcript_events(transcript_path)
    usage = _session_usage_payload(rows)
    preflight_count = 0
    preflight_passed_count = 0
    run_preflight_count = 0
    run_preflight_passed_count = 0
    model_preflight_count = 0
    model_preflight_passed_count = 0
    model_preflight_blocked_count = 0
    apply_attempt_count = 0
    apply_success_count = 0
    verify_count = 0
    verify_passed_count = 0
    diff_view_count = 0
    diff_review_count = 0
    diff_review_high_count = 0
    apply_check_count = 0
    apply_check_ready_count = 0
    apply_approval_count = 0
    high_risk_apply_approval_count = 0
    apply_rejection_count = 0
    high_risk_apply_rejection_count = 0
    apply_block_count = 0
    apply_auto_deferred_count = 0
    rewind_attempt_count = 0
    rewind_success_count = 0
    custom_command_count = 0
    hook_run_count = 0
    hook_block_count = 0
    context_update_count = 0
    permission_update_count = 0
    model_update_count = 0
    budget_update_count = 0
    agent_profile_update_count = 0
    instruction_update_count = 0
    instruction_view_count = 0
    memory_view_count = 0
    plan_update_count = 0
    plan_view_count = 0
    feedback_update_count = 0
    feedback_view_count = 0
    session_gate_count = 0
    session_gate_failure_count = 0
    run_evidence_count = 0
    checkpoint_count = 0
    restore_count = 0
    timeline_view_count = 0
    next_view_count = 0
    for row in rows:
        event = row.event
        payload = row.payload
        if event == "preflight":
            preflight_count += 1
            if payload.get("status") == "passed":
                preflight_passed_count += 1
        elif event == "run_preflight":
            run_preflight_count += 1
            run_preflight = payload.get("preflight")
            if isinstance(run_preflight, dict) and run_preflight.get("status") == "passed":
                run_preflight_passed_count += 1
        elif event == "model_preflight":
            model_preflight_count += 1
            if payload.get("available") is True:
                model_preflight_passed_count += 1
            else:
                model_preflight_blocked_count += 1
        elif event == "run_result":
            run_apply = payload.get("apply")
            if isinstance(run_apply, dict):
                apply_attempt_count += 1
                if run_apply.get("applied") is True:
                    apply_success_count += 1
        elif event == "apply_result":
            apply_attempt_count += 1
            if payload.get("applied") is True:
                apply_success_count += 1
        elif event == "verify_result":
            verify_count += 1
            if payload.get("status") == "passed":
                verify_passed_count += 1
        elif event == "diff_view":
            diff_view_count += 1
        elif event == "diff_review":
            diff_review_count += 1
            if payload.get("risk_level") == "high":
                diff_review_high_count += 1
        elif event == "apply_check_result":
            apply_check_count += 1
            if payload.get("status") == "ready":
                apply_check_ready_count += 1
        elif event == "apply_approval":
            apply_approval_count += 1
            if payload.get("risk_level") == "high":
                high_risk_apply_approval_count += 1
        elif event == "apply_rejection":
            apply_rejection_count += 1
            if payload.get("risk_level") == "high":
                high_risk_apply_rejection_count += 1
        elif event == "apply_blocked":
            apply_block_count += 1
        elif event == "apply_auto_deferred":
            apply_auto_deferred_count += 1
        elif event == "rewind_result":
            rewind_attempt_count += 1
            if payload.get("applied") is True:
                rewind_success_count += 1
        elif event == "custom_command":
            custom_command_count += 1
        elif event == "hook_result":
            hook_run_count += 1
            if payload.get("status") == "blocked":
                hook_block_count += 1
        elif event == "context_update":
            context_update_count += 1
        elif event == "config_update":
            field = payload.get("field")
            if field == "permissions":
                permission_update_count += 1
            elif field == "deepagents_model":
                model_update_count += 1
            elif field == "resource_budget":
                budget_update_count += 1
            elif field == "agent_profile":
                agent_profile_update_count += 1
            elif field == "project_instructions":
                instruction_update_count += 1
        elif event == "instruction_view":
            instruction_view_count += 1
        elif event == "memory_view":
            memory_view_count += 1
        elif event == "plan_update":
            plan_update_count += 1
        elif event == "plan_view":
            plan_view_count += 1
        elif event == "feedback_update":
            feedback_update_count += 1
        elif event == "feedback_view":
            feedback_view_count += 1
        elif event == "session_gate":
            session_gate_count += 1
            gate = payload.get("gate")
            if isinstance(gate, dict) and gate.get("status") == "failed":
                session_gate_failure_count += 1
        elif event == "run_evidence":
            run_evidence_count += 1
        elif event == "session_checkpoint":
            checkpoint_count += 1
        elif event == "session_restore":
            restore_count += 1
        elif event == "session_timeline":
            timeline_view_count += 1
        elif event == "session_next":
            next_view_count += 1
    current = _current_session_quality_window(rows)
    return AgentSessionMetrics(
        task_count=_int_field(usage, "task_count"),
        preflight_count=preflight_count,
        preflight_passed_count=preflight_passed_count,
        run_preflight_count=run_preflight_count,
        run_preflight_passed_count=run_preflight_passed_count,
        model_preflight_count=model_preflight_count,
        model_preflight_passed_count=model_preflight_passed_count,
        model_preflight_blocked_count=model_preflight_blocked_count,
        run_count=_int_field(usage, "run_count"),
        validated_run_count=_int_field(usage, "validated_run_count"),
        run_error_count=_int_field(usage, "run_error_count"),
        verify_count=verify_count,
        verify_passed_count=verify_passed_count,
        diff_view_count=diff_view_count,
        diff_review_count=diff_review_count,
        diff_review_high_count=diff_review_high_count,
        current_diff_review_count=current["diff_review_count"],
        current_diff_review_high_count=current["diff_review_high_count"],
        apply_check_count=apply_check_count,
        apply_check_ready_count=apply_check_ready_count,
        current_apply_check_ready_count=current["apply_check_ready_count"],
        apply_approval_count=apply_approval_count,
        high_risk_apply_approval_count=high_risk_apply_approval_count,
        apply_rejection_count=apply_rejection_count,
        high_risk_apply_rejection_count=high_risk_apply_rejection_count,
        apply_block_count=apply_block_count,
        apply_auto_deferred_count=apply_auto_deferred_count,
        apply_attempt_count=apply_attempt_count,
        apply_success_count=apply_success_count,
        rewind_attempt_count=rewind_attempt_count,
        rewind_success_count=rewind_success_count,
        custom_command_count=custom_command_count,
        hook_run_count=hook_run_count,
        hook_block_count=hook_block_count,
        context_update_count=context_update_count,
        permission_update_count=permission_update_count,
        model_update_count=model_update_count,
        budget_update_count=budget_update_count,
        agent_profile_update_count=agent_profile_update_count,
        instruction_update_count=instruction_update_count,
        instruction_view_count=instruction_view_count,
        memory_view_count=memory_view_count,
        plan_update_count=plan_update_count,
        plan_view_count=plan_view_count,
        feedback_update_count=feedback_update_count,
        feedback_view_count=feedback_view_count,
        session_gate_count=session_gate_count,
        session_gate_failure_count=session_gate_failure_count,
        run_evidence_count=run_evidence_count,
        checkpoint_count=checkpoint_count,
        restore_count=restore_count,
        timeline_view_count=timeline_view_count,
        next_view_count=next_view_count,
        model_call_count=_int_field(usage, "model_call_count"),
        model_response_count=_int_field(usage, "model_response_count"),
        model_total_tokens=_int_field(usage, "model_total_tokens"),
        estimated_cost_usd=_float_field(usage, "estimated_cost_usd"),
    )


def format_session_metrics(metrics: AgentSessionMetrics) -> str:
    return "\n".join(
        [
            "Session metrics:",
            f"- Tasks: {metrics.task_count}",
            f"- Preflights: {metrics.preflight_count}",
            f"- Passed preflights: {metrics.preflight_passed_count}",
            f"- Run preflights: {metrics.run_preflight_count}",
            f"- Passed run preflights: {metrics.run_preflight_passed_count}",
            f"- Model preflights: {metrics.model_preflight_count}",
            f"- Passed model preflights: {metrics.model_preflight_passed_count}",
            f"- Blocked model preflights: {metrics.model_preflight_blocked_count}",
            f"- Runs: {metrics.run_count}",
            f"- Validated runs: {metrics.validated_run_count}",
            f"- Run errors: {metrics.run_error_count}",
            f"- Verify runs: {metrics.verify_count}",
            f"- Passed verify runs: {metrics.verify_passed_count}",
            f"- Diff views: {metrics.diff_view_count}",
            f"- Diff reviews: {metrics.diff_review_count}",
            f"- High-risk diff reviews: {metrics.diff_review_high_count}",
            f"- Current diff reviews: {metrics.current_diff_review_count}",
            f"- Current high-risk diff reviews: {metrics.current_diff_review_high_count}",
            f"- Apply checks: {metrics.apply_check_count}",
            f"- Ready apply checks: {metrics.apply_check_ready_count}",
            f"- Current ready apply checks: {metrics.current_apply_check_ready_count}",
            f"- Apply approvals: {metrics.apply_approval_count}",
            f"- High-risk apply approvals: {metrics.high_risk_apply_approval_count}",
            f"- Apply rejections: {metrics.apply_rejection_count}",
            f"- High-risk apply rejections: {metrics.high_risk_apply_rejection_count}",
            f"- Blocked applies: {metrics.apply_block_count}",
            f"- Deferred auto applies: {metrics.apply_auto_deferred_count}",
            f"- Validation rate: {_format_rate(metrics.validation_rate)}",
            f"- Preflight-to-run rate: {_format_rate(metrics.preflight_to_run_rate)}",
            f"- Apply attempts: {metrics.apply_attempt_count}",
            f"- Applied diffs: {metrics.apply_success_count}",
            f"- Apply success rate: {_format_rate(metrics.apply_success_rate)}",
            f"- Rewind attempts: {metrics.rewind_attempt_count}",
            f"- Reverted diffs: {metrics.rewind_success_count}",
            f"- Rewind success rate: {_format_rate(metrics.rewind_success_rate)}",
            f"- Custom commands: {metrics.custom_command_count}",
            f"- Hook runs: {metrics.hook_run_count}",
            f"- Hook blocks: {metrics.hook_block_count}",
            f"- Context updates: {metrics.context_update_count}",
            f"- Permission updates: {metrics.permission_update_count}",
            f"- Model updates: {metrics.model_update_count}",
            f"- Budget updates: {metrics.budget_update_count}",
            f"- Agent profile updates: {metrics.agent_profile_update_count}",
            f"- Instruction updates: {metrics.instruction_update_count}",
            f"- Instruction views: {metrics.instruction_view_count}",
            f"- Memory views: {metrics.memory_view_count}",
            f"- Plan updates: {metrics.plan_update_count}",
            f"- Plan views: {metrics.plan_view_count}",
            f"- Feedback updates: {metrics.feedback_update_count}",
            f"- Feedback views: {metrics.feedback_view_count}",
            f"- Session gates: {metrics.session_gate_count}",
            f"- Failed session gates: {metrics.session_gate_failure_count}",
            f"- Run evidence views: {metrics.run_evidence_count}",
            f"- Checkpoints: {metrics.checkpoint_count}",
            f"- Restores: {metrics.restore_count}",
            f"- Timeline views: {metrics.timeline_view_count}",
            f"- Next recommendations: {metrics.next_view_count}",
            f"- Model responses: {metrics.model_response_count}",
            f"- Model tokens: {metrics.model_total_tokens}",
            f"- Estimated cost: {_format_cost(metrics.estimated_cost_usd)}",
            (
                "- Cost per validated run: "
                f"{_format_cost(metrics.cost_per_validated_run_usd)}"
            ),
        ]
    )


def _current_session_quality_window(
    rows: list[TranscriptEvent],
) -> dict[str, int]:
    latest_run_index = _latest_event_index(rows, "run_result")
    if latest_run_index < 0:
        return {
            "diff_review_count": 0,
            "diff_review_high_count": 0,
            "apply_check_ready_count": 0,
        }
    diff_reviews: list[tuple[int, dict[str, object]]] = []
    for index, row in enumerate(rows[latest_run_index + 1 :], start=latest_run_index + 1):
        if row.event != "diff_review":
            continue
        diff_reviews.append((index, row.payload))
    if not diff_reviews:
        return {
            "diff_review_count": 0,
            "diff_review_high_count": 0,
            "apply_check_ready_count": 0,
        }
    latest_review_index, latest_review_payload = diff_reviews[-1]
    ready_apply_checks = 0
    for row in rows[latest_review_index + 1 :]:
        if row.event != "apply_check_result":
            continue
        if row.payload.get("status") == "ready":
            ready_apply_checks += 1
    return {
        "diff_review_count": len(diff_reviews),
        "diff_review_high_count": (
            1 if latest_review_payload.get("risk_level") == "high" else 0
        ),
        "apply_check_ready_count": ready_apply_checks,
    }


def _latest_event_index(rows: list[TranscriptEvent], event: str) -> int:
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].event == event:
            return index
    return -1


def _int_field(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else 0


def _float_field(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else 0.0


def _increment_int(value: object) -> int:
    return value + 1 if isinstance(value, int) else 1


def _add_usage(
    target: dict[str, object],
    run_payload: dict[str, object],
) -> None:
    target["model_call_count"] = _sum_int(
        target["model_call_count"],
        run_payload.get("model_call_count"),
    )
    target["model_response_count"] = _sum_int(
        target["model_response_count"],
        run_payload.get("model_response_count"),
    )
    target["model_total_tokens"] = _sum_int(
        target["model_total_tokens"],
        run_payload.get("model_total_tokens"),
    )
    target["estimated_cost_usd"] = _sum_float(
        target["estimated_cost_usd"],
        run_payload.get("estimated_cost_usd"),
    )


def _sum_int(left: object, right: object) -> int:
    left_value = left if isinstance(left, int) else 0
    right_value = right if isinstance(right, int) else 0
    return left_value + right_value


def _sum_float(left: object, right: object) -> float:
    left_value = float(left) if isinstance(left, int | float) else 0.0
    right_value = float(right) if isinstance(right, int | float) else 0.0
    return left_value + right_value


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _format_rate(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.2%}"


def _format_cost(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"${float(value):.6f}"
