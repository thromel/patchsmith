from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
    rehydrate_config_instructions,
    string_list_from_payload,
)
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.session.store import read_known_transcript_events


@dataclass
class _ResumeAccumulator:
    config: AgentCliConfig
    history: list[str] = field(default_factory=list)
    last_run_payload: dict[str, object] | None = None
    last_apply: AgentApplyResult | None = None
    last_rewind: AgentApplyResult | None = None
    compaction_summary: dict[str, object] | None = None
    plan_items: list[AgentPlanItem] = field(default_factory=list)
    feedback_items: list[str] = field(default_factory=list)
    chat_mode: str = "act"
    pending_planned_task: str | None = None


def _on_session_start(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    config_payload = payload.get("config")
    if isinstance(config_payload, dict):
        acc.config = config_from_payload(config_payload, acc.config)


def _on_context_update(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    context_paths = context_paths_from_payload(payload)
    if context_paths is not None:
        acc.config = dataclass_replace(acc.config, context_paths=context_paths)


def _on_config_update(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.config = apply_config_update(acc.config, payload)


def _on_chat_mode_update(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.chat_mode = chat_mode_from_payload(payload.get("mode"))


def _on_plan_mode_task(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.pending_planned_task = optional_text(payload.get("task"))


def _on_plan_mode_resolved(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.pending_planned_task = None


def _on_plan_update(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.plan_items = plan_items_from_payload(payload.get("items"))


def _on_feedback_update(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.feedback_items = feedback_items_from_update(current=acc.feedback_items, payload=payload)


def _on_user_task(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    task = payload.get("task")
    if isinstance(task, str):
        acc.history.append(task)
        acc.pending_planned_task = None


def _on_run_result(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.last_run_payload = dict(payload)


def _on_apply_result(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.last_apply = apply_result_from_payload(payload)


def _on_rewind_result(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.last_rewind = apply_result_from_payload(payload)


def _on_session_compact(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.history = []
    acc.compaction_summary = dict(payload)


def _on_session_clear(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    acc.history = []
    acc.plan_items = []
    acc.feedback_items = []
    acc.last_run_payload = None
    acc.last_apply = None
    acc.last_rewind = None
    acc.compaction_summary = None
    acc.pending_planned_task = None


def _on_session_restore(acc: _ResumeAccumulator, payload: dict[str, object]) -> None:
    state_payload = payload.get("state")
    if not isinstance(state_payload, dict):
        return
    config_payload = state_payload.get("config")
    if isinstance(config_payload, dict):
        acc.config = config_from_payload(config_payload, acc.config)
    acc.history = string_list_from_payload(state_payload.get("history"))
    acc.plan_items = plan_items_from_payload(state_payload.get("plan_items"))
    acc.feedback_items = string_list_from_payload(state_payload.get("feedback_items"))
    acc.last_run_payload = dict_or_none(state_payload.get("last_run_payload"))
    acc.last_apply = apply_result_from_state(state_payload.get("last_apply"))
    acc.last_rewind = apply_result_from_state(state_payload.get("last_rewind"))
    acc.chat_mode = chat_mode_from_payload(state_payload.get("chat_mode"))
    acc.pending_planned_task = optional_text(state_payload.get("pending_planned_task"))
    acc.compaction_summary = dict_or_none(state_payload.get("compaction_summary"))


_ResumeEventHandler = Callable[["_ResumeAccumulator", dict[str, object]], None]
_RESUME_EVENT_HANDLERS: dict[str, _ResumeEventHandler] = {
    "session_start": _on_session_start,
    "context_update": _on_context_update,
    "config_update": _on_config_update,
    "chat_mode_update": _on_chat_mode_update,
    "plan_mode_task": _on_plan_mode_task,
    "plan_mode_approval": _on_plan_mode_resolved,
    "plan_mode_cancel": _on_plan_mode_resolved,
    "plan_update": _on_plan_update,
    "feedback_update": _on_feedback_update,
    "user_task": _on_user_task,
    "run_result": _on_run_result,
    "apply_result": _on_apply_result,
    "rewind_result": _on_rewind_result,
    "session_compact": _on_session_compact,
    "session_clear": _on_session_clear,
    "session_restore": _on_session_restore,
}


def runtime_from_transcript(
    *,
    state: AgentChatState,
    fallback_config: AgentCliConfig,
) -> AgentChatRuntime | None:
    if not state.transcript_path.is_file():
        return None
    acc = _ResumeAccumulator(config=fallback_config)
    for row in read_known_transcript_events(state.transcript_path):
        handler = _RESUME_EVENT_HANDLERS.get(row.event)
        if handler is not None:
            handler(acc, row.payload)
    config = rehydrate_config_instructions(acc.config)
    return AgentChatRuntime(
        state=dataclass_replace(state, config=config),
        chat_mode=acc.chat_mode,
        pending_planned_task=acc.pending_planned_task,
        history=acc.history,
        last_run_payload=acc.last_run_payload,
        last_apply=acc.last_apply,
        last_rewind=acc.last_rewind,
        compaction_summary=acc.compaction_summary,
        plan_items=acc.plan_items,
        feedback_items=acc.feedback_items,
    )
