from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.session.events import TranscriptEvent
from patchsmith.session.metrics import session_metrics
from patchsmith.session.store import read_known_transcript_events


@dataclass(frozen=True)
class AgentSessionRecommendation:
    action: str
    reason: str
    commands: tuple[str, ...]
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "commands": list(self.commands),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class AgentRepeatedFailure:
    count: int
    signature: str
    latest_run_id: str
    patch_generated: object
    retrieved_files: tuple[str, ...]


def session_recommendation(transcript_path: Path) -> AgentSessionRecommendation:
    rows = read_known_transcript_events(transcript_path)
    metrics = session_metrics(transcript_path)
    last_run = _latest_payload(rows, "run_result")
    last_error = _latest_payload(rows, "run_error")
    last_preflight = _latest_payload(rows, "preflight")
    latest_config = _latest_config(rows) or {}
    latest_run_index = _latest_event_index(rows, "run_result")
    latest_evidence_index = _latest_event_index(rows, "run_evidence")
    latest_gate_index = _latest_event_index(rows, "session_gate")
    latest_diff_view_index = _latest_event_index(rows, "diff_view")
    latest_diff_review = _latest_payload(rows, "diff_review")
    latest_diff_review_index = _latest_event_index(rows, "diff_review")
    latest_apply_check = _latest_payload(rows, "apply_check_result")
    latest_apply_check_index = _latest_event_index(rows, "apply_check_result")
    latest_apply_approval_index = _latest_event_index(rows, "apply_approval")
    latest_apply_rejection = _latest_payload(rows, "apply_rejection")
    latest_apply_rejection_index = _latest_event_index(rows, "apply_rejection")
    latest_apply_index = _latest_event_index(rows, "apply_result")
    latest_verify_index = _latest_event_index(rows, "verify_result")
    latest_checkpoint_index = _latest_event_index(rows, "session_checkpoint")
    latest_preflight_index = _latest_event_index(rows, "preflight")
    pending_plan = _pending_planned_task(rows)
    repeated_failure = _latest_repeated_failure(rows)

    if pending_plan is not None:
        pending_planned_task, pending_plan_index = pending_plan
        if (
            last_preflight is None
            or latest_preflight_index < pending_plan_index
            or last_preflight.get("status") != "passed"
        ):
            return AgentSessionRecommendation(
                action="Fix readiness or cancel the pending planned task.",
                reason=(
                    "Plan mode has a pending task, but the latest preflight "
                    "did not pass."
                ),
                commands=(
                    "/doctor",
                    f"/preflight {pending_planned_task}",
                    "/cancel plan",
                ),
                evidence=(
                    f"pending_task={_compact_text(pending_planned_task, limit=80)}",
                    "latest_preflight=missing"
                    if last_preflight is None
                    else f"latest_preflight={_plain_text(last_preflight.get('status'))}",
                ),
            )
        return AgentSessionRecommendation(
            action="Approve or cancel the pending planned task.",
            reason=(
                "Plan mode preflighted a task and is waiting for an explicit "
                "run or cancel decision."
            ),
            commands=("/run", "/cancel plan", "/mode act"),
            evidence=(
                f"pending_task={_compact_text(pending_planned_task, limit=80)}",
                "plan_mode=pending",
            ),
        )

    if metrics.run_count == 0:
        if last_preflight is not None and last_preflight.get("status") != "passed":
            return AgentSessionRecommendation(
                action="Fix readiness before spending model tokens.",
                reason=(
                    "The transcript has no completed runs and the latest "
                    "preflight is blocked."
                ),
                commands=("/doctor", "/preflight <task>"),
                evidence=(
                    f"latest_preflight={_plain_text(last_preflight.get('status'))}",
                    f"run_count={metrics.run_count}",
                ),
            )
        return AgentSessionRecommendation(
            action="Run a bounded preflight, then start the first repair run.",
            reason="The transcript has no completed runs yet.",
            commands=("/preflight <task>", "/run <task>"),
            evidence=(f"run_count={metrics.run_count}",),
        )

    if _latest_event_is(rows, "run_error") and last_error is not None:
        return AgentSessionRecommendation(
            action="Inspect local readiness before retrying the agent.",
            reason="The most recent run attempt ended in an error.",
            commands=("/doctor", "/timeline 20"),
            evidence=(
                f"error={_plain_text(last_error.get('error_type'))}",
                _compact_text(last_error.get("message"), limit=80),
            ),
        )

    if last_run is None:
        return AgentSessionRecommendation(
            action="Inspect the transcript before continuing.",
            reason="The session has run metrics but no readable run payload.",
            commands=("/timeline 20", "/status"),
            evidence=(f"run_count={metrics.run_count}",),
        )

    if repeated_failure is not None:
        return AgentSessionRecommendation(
            action="Break the repeated failure loop before another run.",
            reason=(
                "The latest runs reached the same unresolved outcome without "
                "a strategy-changing transcript event between them."
            ),
            commands=(
                "/trace",
                "/feedback add <what changed after reviewing the failure>",
                "/context add <path[#symbol]>",
            ),
            evidence=(
                f"repeat_count={repeated_failure.count}",
                f"failure={repeated_failure.signature}",
                f"patch_generated={_plain_text(repeated_failure.patch_generated)}",
                "retrieved_files="
                + _compact_text(
                    ", ".join(repeated_failure.retrieved_files),
                    limit=80,
                ),
            ),
        )

    budget_pressure = _latest_budget_pressure(last_run, latest_config)
    if budget_pressure is not None:
        return AgentSessionRecommendation(
            action="Adjust budget, model, or context strategy before retrying.",
            reason=(
                "The latest run produced no patch and exhausted the configured "
                "model budget."
            ),
            commands=(
                "/trace",
                "/budget set <responses> <tokens>",
                "/model <id>",
                "/feedback add <budget-aware retry plan>",
            ),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                *budget_pressure,
                f"failure={_plain_text(last_run.get('repair_failure_category'))}",
            ),
        )

    test_exit_code = last_run.get("test_exit_code")
    if test_exit_code != 0:
        return AgentSessionRecommendation(
            action="Review run evidence and capture retry guidance.",
            reason="The latest run is not validated by its test command.",
            commands=("/trace", "/feedback add <retry guidance>", "/run <task>"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                f"test_exit_code={_plain_text(test_exit_code)}",
            ),
        )

    if latest_evidence_index < latest_run_index:
        return AgentSessionRecommendation(
            action="Inspect the latest validated run artifacts.",
            reason=(
                "The latest run passed validation but has not been reviewed "
                "with /trace."
            ),
            commands=("/trace", "/gate clean"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                "trace_review=missing_after_latest_run",
            ),
        )

    if latest_gate_index < latest_run_index:
        return AgentSessionRecommendation(
            action="Gate the latest validated run before promotion.",
            reason=(
                "The latest run passed validation but no session gate was "
                "recorded after it."
            ),
            commands=("/gate clean", "/checkpoint validated"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                "session_gate=missing_after_latest_run",
            ),
        )

    if latest_apply_index < latest_run_index:
        if latest_diff_review_index < latest_run_index:
            if latest_diff_view_index < latest_run_index:
                return AgentSessionRecommendation(
                    action="Review the generated diff before applying it.",
                    reason=(
                        "The latest run is validated and gated, but no diff "
                        "review was recorded after it."
                    ),
                    commands=("/diff stat", "/diff show"),
                    evidence=(
                        f"run={_plain_text(last_run.get('run_id'))}",
                        "diff_review=missing_after_latest_run",
                    ),
                )
            return AgentSessionRecommendation(
                action="Run deterministic diff risk review before applying it.",
                reason=(
                    "The latest run has diff inspection evidence, but no risk "
                    "review is recorded after it."
                ),
                commands=("/diff review", "/diff show"),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    "diff_risk_review=missing_after_latest_diff_review",
                ),
            )
        diff_review_is_high_risk = (
            latest_diff_review is not None
            and (
                latest_diff_review.get("risk_level") == "high"
                or latest_diff_review.get("confirmation_required") is True
            )
        )
        if (
            diff_review_is_high_risk
            and latest_apply_check_index < latest_diff_review_index
        ):
            return AgentSessionRecommendation(
                action="Resolve or explicitly review the high-risk diff before applying.",
                reason="The latest deterministic diff review marked the patch high risk.",
                commands=("/diff show", "/feedback add <risk review>", "/run <task>"),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    "diff_risk=high",
                ),
            )
        if latest_apply_check_index < latest_diff_review_index:
            return AgentSessionRecommendation(
                action="Dry-run check the generated diff before applying it.",
                reason=(
                    "The latest run has diff risk review evidence, but no "
                    "apply check is recorded after it."
                ),
                commands=("/apply check", "/diff show"),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    "apply_check=missing_after_latest_diff_risk_review",
                ),
            )
        if latest_apply_check is not None and latest_apply_check.get("status") != "ready":
            return AgentSessionRecommendation(
                action="Resolve the apply-check failure before applying.",
                reason=(
                    "The latest apply check did not prove that the diff can be "
                    "applied cleanly."
                ),
                commands=("/timeline 20", "/diff show", "/run <task>"),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    f"apply_check={_plain_text(latest_apply_check.get('status'))}",
                ),
            )
        if (
            latest_apply_rejection_index >= latest_apply_check_index
            and latest_apply_rejection_index > latest_apply_approval_index
        ):
            rejection_reason = ""
            if latest_apply_rejection is not None:
                rejection_reason = _compact_text(
                    latest_apply_rejection.get("reason"),
                    limit=80,
                )
            return AgentSessionRecommendation(
                action="Turn the rejected diff into feedback before retrying.",
                reason=(
                    "The latest apply decision rejects the current diff, so "
                    "applying it would contradict the transcript."
                ),
                commands=(
                    "/feedback add <rejection reason>",
                    "/run <task>",
                    "/diff show",
                ),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    f"apply_rejection={rejection_reason or 'recorded'}",
                ),
            )
        if (
            diff_review_is_high_risk
            and latest_apply_approval_index < latest_apply_check_index
        ):
            return AgentSessionRecommendation(
                action="Approve or reject the high-risk reviewed diff.",
                reason=(
                    "The latest diff is apply-check ready but still needs an "
                    "explicit human decision before mutation."
                ),
                commands=(
                    "/approve apply <reason>",
                    "/reject apply <reason>",
                    "/diff show",
                ),
                evidence=(
                    f"run={_plain_text(last_run.get('run_id'))}",
                    "diff_risk=high",
                ),
            )
        return AgentSessionRecommendation(
            action="Decide whether to apply or checkpoint the validated diff.",
            reason="The latest run is validated, gated, reviewed, and apply-check ready.",
            commands=("/apply", "/checkpoint validated"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                "apply_check=ready",
            ),
        )

    if latest_verify_index < latest_apply_index:
        return AgentSessionRecommendation(
            action="Verify the applied working tree.",
            reason=(
                "The latest run has an apply decision but no independent "
                "verify command after it."
            ),
            commands=("/verify", "/checkpoint verified"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                "verify=missing_after_latest_apply",
            ),
        )

    if latest_checkpoint_index < latest_run_index:
        return AgentSessionRecommendation(
            action="Checkpoint the post-verify session state.",
            reason=(
                "The latest validated run has apply/verify evidence but no "
                "checkpoint after it."
            ),
            commands=("/checkpoint applied", "/export"),
            evidence=(
                f"run={_plain_text(last_run.get('run_id'))}",
                "checkpoint=missing_after_latest_run",
            ),
        )

    return AgentSessionRecommendation(
        action="Export or continue with the next scoped task.",
        reason=(
            "The latest run has validation, trace review, gate, apply decision, "
            "and checkpoint evidence."
        ),
        commands=("/export", "/run <next task>"),
        evidence=(
            f"run={_plain_text(last_run.get('run_id'))}",
            f"validation_rate={_format_rate(metrics.validation_rate)}",
        ),
    )


def format_session_recommendation(
    recommendation: AgentSessionRecommendation,
) -> str:
    lines = [
        "Next recommendation:",
        f"- Action: {recommendation.action}",
        f"- Reason: {recommendation.reason}",
        f"- Commands: {', '.join(recommendation.commands)}",
    ]
    if recommendation.evidence:
        lines.append(f"- Evidence: {', '.join(recommendation.evidence)}")
    return "\n".join(lines)


def _latest_config(rows: list[TranscriptEvent]) -> dict[str, object] | None:
    config: dict[str, object] | None = None
    for row in rows:
        event = row.event
        payload = row.payload
        if event == "session_start":
            value = payload.get("config")
            if isinstance(value, dict):
                config = dict(value)
        elif event == "config_update" and config is not None:
            _apply_config_update(config, payload)
        elif event == "context_update" and config is not None:
            paths = payload.get("context_paths")
            if isinstance(paths, list):
                config["context_paths"] = [path for path in paths if isinstance(path, str)]
    return config


def _apply_config_update(
    config: dict[str, object],
    payload: dict[str, object],
) -> None:
    field = payload.get("field")
    if field == "deepagents_model":
        config["deepagents_model"] = payload.get("value")
    elif field == "resource_budget":
        config["max_model_responses"] = payload.get("max_model_responses")
        config["max_model_tokens"] = payload.get("max_model_tokens")
    elif field == "permissions":
        config["apply"] = payload.get("apply")
        config["allow_dirty_apply"] = payload.get("allow_dirty_apply")
    elif field == "agent_profile":
        for key in (
            "agent_profile",
            "agent_profile_path",
            "agent_profile_description",
            "agent_profile_instructions",
            "agent_profile_instruction_chars",
            "deepagents_model",
            "deepagents_subagents",
            "deepagents_max_context_files",
            "max_model_responses",
            "max_model_tokens",
            "top_k",
            "test_command",
            "context_paths",
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)
    elif field == "project_instructions":
        for key in (
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)


def _payloads(
    rows: list[TranscriptEvent],
    event: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for row in rows:
        if row.event != event:
            continue
        payloads.append(row.payload)
    return payloads


def _latest_payload(
    rows: list[TranscriptEvent],
    event: str,
) -> dict[str, object] | None:
    payloads = _payloads(rows, event)
    return payloads[-1] if payloads else None


def _latest_event_index(rows: list[TranscriptEvent], event: str) -> int:
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].event == event:
            return index
    return -1


def _latest_event_is(rows: list[TranscriptEvent], event: str) -> bool:
    for row in reversed(rows):
        if row.event == "user_command":
            continue
        return row.event == event
    return False


def _latest_repeated_failure(
    rows: list[TranscriptEvent],
    *,
    threshold: int = 2,
) -> AgentRepeatedFailure | None:
    latest_run_index = _latest_event_index(rows, "run_result")
    if latest_run_index < 0:
        return None
    if any(_strategy_update_event(row) for row in rows[latest_run_index + 1 :]):
        return None

    latest_payload = _payload_at(rows[latest_run_index])
    if not _run_is_unresolved(latest_payload):
        return None
    signature = _failure_signature(latest_payload)
    count = 0
    latest_run_id = _plain_text(latest_payload.get("run_id"))
    patch_generated = latest_payload.get("repair_patch_generated")
    retrieved_files = _string_tuple(latest_payload.get("retrieved_files"))

    for row in reversed(rows[: latest_run_index + 1]):
        event = row.event
        if event == "run_result":
            payload = _payload_at(row)
            if (
                not _run_is_unresolved(payload)
                or _failure_signature(payload) != signature
            ):
                break
            count += 1
            continue
        if count > 0 and _strategy_update_event(row):
            break

    if count < threshold:
        return None
    return AgentRepeatedFailure(
        count=count,
        signature=signature,
        latest_run_id=latest_run_id,
        patch_generated=patch_generated,
        retrieved_files=retrieved_files,
    )


def _payload_at(row: TranscriptEvent) -> dict[str, object]:
    return row.payload


def _run_is_unresolved(payload: dict[str, object]) -> bool:
    tests_passed = payload.get("repair_tests_passed")
    if tests_passed is True:
        return False
    verdict = _optional_str(payload.get("repair_verdict"))
    if verdict in {
        "patch_validated",
        "patch_validated_quality_warning",
        "tests_passed_without_patch",
    }:
        return False
    test_exit_code = payload.get("test_exit_code")
    return test_exit_code != 0 or bool(verdict)


def _latest_budget_pressure(
    run_payload: dict[str, object],
    config: dict[str, object],
) -> tuple[str, ...] | None:
    if run_payload.get("repair_patch_generated") is True:
        return None
    failure = _optional_str(run_payload.get("repair_failure_category"))
    if failure != "no_patch_generated":
        return None
    evidence: list[str] = []
    response_count = _optional_int(run_payload.get("model_response_count"))
    response_cap = _positive_int(config.get("max_model_responses"))
    if (
        response_count is not None
        and response_cap is not None
        and response_count >= response_cap
    ):
        evidence.append(f"response_budget={response_count}/{response_cap}")
    token_count = _optional_int(run_payload.get("model_total_tokens"))
    token_cap = _positive_int(config.get("max_model_tokens"))
    if token_count is not None and token_cap is not None and token_count >= token_cap:
        evidence.append(f"token_budget={token_count}/{token_cap}")
    return tuple(evidence) if evidence else None


def _failure_signature(payload: dict[str, object]) -> str:
    failure = (
        _optional_str(payload.get("repair_failure_category"))
        or _optional_str(payload.get("repair_verdict"))
        or f"test_exit_code={_plain_text(payload.get('test_exit_code'))}"
    )
    return "|".join(
        [
            failure,
            f"patch_generated={_plain_text(payload.get('repair_patch_generated'))}",
            f"files={','.join(_string_tuple(payload.get('retrieved_files')))}",
        ]
    )


def _strategy_update_event(row: TranscriptEvent) -> bool:
    event = row.event
    if event in {
        "agent_profile_update",
        "context_update",
        "feedback_update",
        "instruction_view",
        "memory_view",
        "plan_update",
    }:
        return True
    if event == "config_update":
        payload = row.payload
        return _optional_str(payload.get("field")) in {
            "agent_profile",
            "deepagents_model",
            "permissions",
            "project_instructions",
            "resource_budget",
        }
    return False


def _pending_planned_task(
    rows: list[TranscriptEvent],
) -> tuple[str, int] | None:
    pending: tuple[str, int] | None = None
    for index, row in enumerate(rows):
        event = row.event
        payload = row.payload
        if event == "plan_mode_task":
            task = payload.get("task")
            if isinstance(task, str) and task.strip():
                pending = (task.strip(), index)
        elif event in {
            "plan_mode_approval",
            "plan_mode_cancel",
            "session_clear",
            "user_task",
        }:
            pending = None
        elif event == "session_restore":
            state = payload.get("state")
            if isinstance(state, dict):
                task = state.get("pending_planned_task")
                pending = (
                    (task.strip(), index)
                    if isinstance(task, str) and task.strip()
                    else None
                )
    return pending


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _positive_int(value: object) -> int | None:
    if not isinstance(value, int) or value < 0:
        return None
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _format_rate(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.2%}"


def _compact_text(value: object, *, limit: int = 120) -> str:
    text = _inline_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _inline_text(value: object) -> str:
    return _plain_text(value).replace("\n", " ")


def _plain_text(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return str(value)
