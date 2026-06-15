from __future__ import annotations

from typing import TextIO

from patchsmith.agent_plan import (
    AgentPlanItem,
    format_agent_plan,
    parse_plan_items,
    plan_items_payload,
    update_plan_item_status,
)
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.state import AgentChatRuntime


def plan_feedback_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="plan",
            handler=handle_plan_command,
            usage="/plan [show|set|add|start|done|block|skip|pending|clear] ...",
        ),
        ChatCommand(
            name="feedback",
            aliases=("note", "notes"),
            handler=handle_feedback_command,
            usage="/feedback [show|add|clear] [guidance]",
        ),
    )


def handle_plan_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, rest = argument.partition(" ")
    action = action.strip().lower()
    value = rest.strip()
    if action in {"", "show"}:
        _write_line(output_stream, format_agent_plan(runtime.plan_items or []))
        context.record(
            runtime,
            "plan_view",
            {"items": plan_items_payload(runtime.plan_items or [])},
        )
        return
    if action in {"set", "reset"}:
        items = parse_plan_items(value)
        if not items:
            _write_line(output_stream, "Usage: /plan set <task>; <task>; ...")
            return
        _set_plan_items(runtime=runtime, items=items, action=action, context=context)
        _write_line(output_stream, format_agent_plan(items))
        return
    if action == "add":
        if not value:
            _write_line(output_stream, "Usage: /plan add <task>")
            return
        items = [*(runtime.plan_items or []), AgentPlanItem(text=value)]
        _set_plan_items(runtime=runtime, items=items, action="add", context=context)
        _write_line(output_stream, format_agent_plan(items))
        return
    if action in {"start", "done", "block", "skip", "pending"}:
        status = _plan_status_for_action(action)
        _update_plan_status(
            runtime=runtime,
            raw_index=value,
            status=status,
            action=action,
            output_stream=output_stream,
            context=context,
        )
        return
    if action == "clear":
        _set_plan_items(runtime=runtime, items=[], action="clear", context=context)
        _write_line(output_stream, "Session plan cleared.")
        return
    _write_line(
        output_stream,
        "Usage: /plan [show|set|add|start|done|block|skip|pending|clear] ...",
    )


def handle_feedback_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, rest = argument.partition(" ")
    action = action.strip().lower()
    value = rest.strip()
    if action in {"", "show", "list"}:
        _write_line(output_stream, format_feedback(runtime.feedback_items or []))
        context.record(
            runtime,
            "feedback_view",
            {"items": list(runtime.feedback_items or [])},
        )
        return
    if action == "add":
        if not value:
            _write_line(output_stream, "Usage: /feedback add <guidance for next run>")
            return
        _add_feedback_item(runtime=runtime, item=value, context=context)
        _write_line(output_stream, f"Added feedback: {value}")
        return
    if action == "clear":
        runtime.feedback_items = []
        context.record(runtime, "feedback_update", {"action": "clear", "items": []})
        _write_line(output_stream, "Session feedback cleared.")
        return
    _add_feedback_item(runtime=runtime, item=argument.strip(), context=context)
    _write_line(output_stream, f"Added feedback: {argument.strip()}")


def format_feedback(items: list[str]) -> str:
    if not items:
        return "No session feedback."
    lines = ["Session feedback:"]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def agent_feedback_context(items: list[str]) -> str:
    if not items:
        return ""
    lines = ["PatchSmith session feedback"]
    lines.extend(f"{index}. {item}" for index, item in enumerate(items, start=1))
    return "\n".join(lines)


def _plan_status_for_action(action: str) -> str:
    return {
        "start": "in_progress",
        "done": "completed",
        "block": "blocked",
        "skip": "skipped",
        "pending": "pending",
    }[action]


def _update_plan_status(
    *,
    runtime: AgentChatRuntime,
    raw_index: str,
    status: str,
    action: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    try:
        index = int(raw_index)
    except ValueError:
        _write_line(output_stream, f"Usage: /plan {action} <index>")
        return
    try:
        items = update_plan_item_status(
            runtime.plan_items or [],
            index=index,
            status=status,
        )
    except IndexError:
        _write_line(output_stream, f"Plan item not found: {index}")
        return
    _set_plan_items(
        runtime=runtime,
        items=items,
        action=action,
        index=index,
        context=context,
    )
    _write_line(output_stream, format_agent_plan(items))


def _set_plan_items(
    *,
    runtime: AgentChatRuntime,
    items: list[AgentPlanItem],
    action: str,
    context: ChatCommandContext,
    index: int | None = None,
) -> None:
    runtime.plan_items = list(items)
    context.record(
        runtime,
        "plan_update",
        {
            "action": action,
            "index": index,
            "items": plan_items_payload(runtime.plan_items or []),
        },
    )


def _add_feedback_item(
    *,
    runtime: AgentChatRuntime,
    item: str,
    context: ChatCommandContext,
) -> None:
    feedback_items = [*(runtime.feedback_items or []), item]
    runtime.feedback_items = feedback_items
    context.record(
        runtime,
        "feedback_update",
        {"action": "add", "item": item, "items": feedback_items},
    )


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
