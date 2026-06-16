from __future__ import annotations

from dataclasses import replace as dataclass_replace

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem, plan_items_from_payload
from patchsmith.chat.session_payloads import (
    apply_config_update,
    apply_result_from_payload,
    apply_result_from_state,
    chat_mode_from_payload,
    config_from_payload,
    context_paths_from_payload,
    dict_or_none,
    feedback_items_from_update,
    optional_text,
    string_list_from_payload,
)
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.session.store import read_known_transcript_events


def runtime_from_transcript(
    *,
    state: AgentChatState,
    fallback_config: AgentCliConfig,
) -> AgentChatRuntime | None:
    if not state.transcript_path.is_file():
        return None
    config = fallback_config
    history: list[str] = []
    last_run_payload: dict[str, object] | None = None
    last_apply: AgentApplyResult | None = None
    last_rewind: AgentApplyResult | None = None
    compaction_summary: dict[str, object] | None = None
    plan_items: list[AgentPlanItem] = []
    feedback_items: list[str] = []
    chat_mode = "act"
    pending_planned_task: str | None = None
    for row in read_known_transcript_events(state.transcript_path):
        event = row.event
        payload = row.payload
        if event == "session_start":
            config_payload = payload.get("config")
            if isinstance(config_payload, dict):
                config = config_from_payload(config_payload, config)
        elif event == "context_update":
            context_paths = context_paths_from_payload(payload)
            if context_paths is not None:
                config = dataclass_replace(config, context_paths=context_paths)
        elif event == "config_update":
            config = apply_config_update(config, payload)
        elif event == "chat_mode_update":
            chat_mode = chat_mode_from_payload(payload.get("mode"))
        elif event == "plan_mode_task":
            pending_planned_task = optional_text(payload.get("task"))
        elif event in {"plan_mode_approval", "plan_mode_cancel"}:
            pending_planned_task = None
        elif event == "plan_update":
            plan_items = plan_items_from_payload(payload.get("items"))
        elif event == "feedback_update":
            feedback_items = feedback_items_from_update(
                current=feedback_items,
                payload=payload,
            )
        elif event == "user_task":
            task = payload.get("task")
            if isinstance(task, str):
                history.append(task)
                pending_planned_task = None
        elif event == "run_result":
            last_run_payload = dict(payload)
        elif event == "apply_result":
            last_apply = apply_result_from_payload(payload)
        elif event == "rewind_result":
            last_rewind = apply_result_from_payload(payload)
        elif event == "session_compact":
            history = []
            compaction_summary = dict(payload)
        elif event == "session_clear":
            history = []
            plan_items = []
            feedback_items = []
            last_run_payload = None
            last_apply = None
            last_rewind = None
            compaction_summary = None
            pending_planned_task = None
        elif event == "session_restore":
            state_payload = payload.get("state")
            if isinstance(state_payload, dict):
                config_payload = state_payload.get("config")
                if isinstance(config_payload, dict):
                    config = config_from_payload(config_payload, config)
                history = string_list_from_payload(state_payload.get("history"))
                plan_items = plan_items_from_payload(state_payload.get("plan_items"))
                feedback_items = string_list_from_payload(
                    state_payload.get("feedback_items")
                )
                last_run_payload = dict_or_none(state_payload.get("last_run_payload"))
                last_apply = apply_result_from_state(state_payload.get("last_apply"))
                last_rewind = apply_result_from_state(
                    state_payload.get("last_rewind")
                )
                chat_mode = chat_mode_from_payload(state_payload.get("chat_mode"))
                pending_planned_task = optional_text(
                    state_payload.get("pending_planned_task")
                )
                compaction_summary = dict_or_none(
                    state_payload.get("compaction_summary")
                )
    return AgentChatRuntime(
        state=dataclass_replace(state, config=config),
        chat_mode=chat_mode,
        pending_planned_task=pending_planned_task,
        history=history,
        last_run_payload=last_run_payload,
        last_apply=last_apply,
        last_rewind=last_rewind,
        compaction_summary=compaction_summary,
        plan_items=plan_items,
        feedback_items=feedback_items,
    )
