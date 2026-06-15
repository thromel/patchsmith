from __future__ import annotations

from typing import TextIO

from patchsmith.agent_plan import plan_items_payload
from patchsmith.agent_session import session_usage_payload
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.handlers.model_budget import budget_label, model_label
from patchsmith.chat.state import AgentChatRuntime


def session_state_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(name="status", handler=handle_status_command, usage="/status"),
        ChatCommand(name="history", handler=handle_history_command, usage="/history"),
        ChatCommand(
            name="mode",
            handler=handle_mode_command,
            usage="/mode [act|plan]",
        ),
        ChatCommand(
            name="cancel",
            handler=handle_cancel_command,
            usage="/cancel [plan]",
        ),
        ChatCommand(name="clear", handler=handle_clear_command, usage="/clear"),
        ChatCommand(
            name="compact",
            handler=handle_compact_command,
            usage="/compact [note]",
        ),
    )


def handle_status_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    config = runtime.state.config
    _write_line(output_stream, f"Session: {runtime.state.session_id}")
    _write_line(output_stream, f"Chat mode: {runtime.chat_mode}")
    if runtime.pending_planned_task:
        _write_line(output_stream, f"Pending planned task: {runtime.pending_planned_task}")
    else:
        _write_line(output_stream, "Pending planned task: none")
    _write_line(output_stream, f"Repo: {config.repo}")
    _write_line(output_stream, f"Context provider: {config.context_provider}")
    _write_line(output_stream, f"Model override: {model_label(config)}")
    _write_line(output_stream, f"Agent profile: {config.agent_profile or 'none'}")
    _write_line(
        output_stream,
        f"Project instructions: {len(config.agent_instruction_files)} file(s)",
    )
    _write_line(output_stream, f"Session plan items: {len(runtime.plan_items or [])}")
    _write_line(output_stream, f"Session feedback items: {len(runtime.feedback_items or [])}")
    _write_line(output_stream, f"Budget: {budget_label(config)}")
    if config.context_paths:
        _write_line(output_stream, f"Context hints: {', '.join(config.context_paths)}")
    else:
        _write_line(output_stream, "Context hints: none")
    _write_line(output_stream, f"Top K: {config.top_k}")
    _write_line(output_stream, f"Apply by default: {str(config.apply).lower()}")
    _write_line(
        output_stream,
        f"Dirty apply allowed: {str(config.allow_dirty_apply).lower()}",
    )
    _write_line(output_stream, f"Transcript: {runtime.state.transcript_path}")
    if runtime.compaction_summary is not None:
        compacted = runtime.compaction_summary.get("compacted_task_count")
        _write_line(output_stream, f"Last compaction: {compacted} task(s)")
    last_run_id = _last_run_value(runtime, "run_id")
    if last_run_id is None:
        _write_line(output_stream, "Last run: none")
        return
    _write_line(output_stream, f"Last run: {last_run_id}")
    _write_line(output_stream, f"Last status: {_last_run_value(runtime, 'status')}")
    _write_line(output_stream, f"Last report: {_last_run_value(runtime, 'report_path')}")
    _write_line(output_stream, f"Last diff: {_last_run_value(runtime, 'final_diff_path')}")
    if runtime.last_apply is not None:
        _write_line(output_stream, f"Last apply: {runtime.last_apply.status}")
    if runtime.last_rewind is not None:
        _write_line(output_stream, f"Last rewind: {runtime.last_rewind.status}")


def handle_history_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if not runtime.history:
        if runtime.compaction_summary is not None:
            compacted = runtime.compaction_summary.get("compacted_task_count")
            _write_line(output_stream, "No tasks since last compaction.")
            _write_line(output_stream, f"Last compaction summarized {compacted} task(s).")
            return
        _write_line(output_stream, "No tasks in this session yet.")
        return
    for index, task in enumerate(runtime.history, start=1):
        _write_line(output_stream, f"{index}. {task}")


def handle_mode_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    value = argument.strip().lower()
    if not value:
        _write_line(output_stream, f"Chat mode: {runtime.chat_mode}")
        return
    aliases = {
        "act": "act",
        "run": "act",
        "edit": "act",
        "plan": "plan",
        "planning": "plan",
    }
    mode = aliases.get(value)
    if mode is None:
        _write_line(output_stream, "Usage: /mode [act|plan]")
        return
    runtime.chat_mode = mode
    context.record(runtime, "chat_mode_update", {"mode": mode})
    if mode == "plan":
        _write_line(
            output_stream,
            "Chat mode: plan. Plain text runs /preflight; use /run <task> to execute.",
        )
        return
    _write_line(output_stream, "Chat mode: act. Plain text runs the repair loop.")


def handle_cancel_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    value = argument.strip().lower()
    if value not in {"", "plan", "planned", "planned task", "task"}:
        _write_line(output_stream, "Usage: /cancel [plan]")
        return
    task = runtime.pending_planned_task
    if task is None:
        _write_line(output_stream, "No pending planned task.")
        return
    runtime.pending_planned_task = None
    context.record(runtime, "plan_mode_cancel", {"task": task})
    _write_line(output_stream, f"Cancelled planned task: {task}")


def handle_clear_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    payload = {
        "cleared_history_count": len(runtime.history or []),
        "cleared_plan_count": len(runtime.plan_items or []),
        "cleared_feedback_count": len(runtime.feedback_items or []),
        "cleared_last_run_id": _last_run_value(runtime, "run_id"),
        "cleared_last_apply": runtime.last_apply.status if runtime.last_apply else None,
        "cleared_last_rewind": runtime.last_rewind.status if runtime.last_rewind else None,
    }
    _clear_runtime_state(runtime)
    context.record(runtime, "session_clear", payload)
    _write_line(output_stream, "Session state cleared. Transcript retained.")


def handle_compact_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    payload = _compaction_payload(runtime=runtime, note=argument)
    runtime.compaction_summary = payload
    runtime.last_task = None
    runtime.history = []
    context.record(runtime, "session_compact", payload)
    _write_line(
        output_stream,
        f"Session compacted. Summarized {payload['compacted_task_count']} task(s).",
    )
    _write_line(output_stream, "Last run artifact pointers were preserved.")


def _clear_runtime_state(runtime: AgentChatRuntime) -> None:
    runtime.last_task = None
    runtime.last_run = None
    runtime.last_run_payload = None
    runtime.last_apply = None
    runtime.last_rewind = None
    runtime.compaction_summary = None
    runtime.pending_planned_task = None
    runtime.history = []
    runtime.plan_items = []
    runtime.feedback_items = []


def _compaction_payload(
    *,
    runtime: AgentChatRuntime,
    note: str,
) -> dict[str, object]:
    usage = session_usage_payload(runtime.state.transcript_path)
    history = list(runtime.history or [])
    return {
        "note": note.strip() or None,
        "compacted_task_count": len(history),
        "recent_tasks": history[-5:],
        "plan_items": plan_items_payload(runtime.plan_items or []),
        "feedback_items": list(runtime.feedback_items or []),
        "pending_planned_task": runtime.pending_planned_task,
        "usage": usage,
        "context_paths": list(runtime.state.config.context_paths),
        "model": runtime.state.config.deepagents_model,
        "budget": {
            "max_model_responses": runtime.state.config.max_model_responses,
            "max_model_tokens": runtime.state.config.max_model_tokens,
        },
        "last_run_id": _last_run_value(runtime, "run_id"),
        "last_status": _last_run_value(runtime, "status"),
        "last_report_path": _optional_text(_last_run_value(runtime, "report_path")),
        "last_diff_path": _optional_text(_last_run_value(runtime, "final_diff_path")),
    }


def _last_run_value(runtime: AgentChatRuntime, key: str) -> object | None:
    if runtime.last_run is not None:
        value = getattr(runtime.last_run, _result_attribute_for_payload_key(key), None)
        if value is not None:
            return value
    if runtime.last_run_payload is None:
        return None
    return runtime.last_run_payload.get(key)


def _result_attribute_for_payload_key(key: str) -> str:
    if key == "final_diff_path":
        return "final_diff_path"
    if key == "report_path":
        return "report_path"
    if key == "trace_path":
        return "trace_path"
    return key


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
