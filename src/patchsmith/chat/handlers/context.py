from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import TextIO

from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def context_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="context",
            handler=handle_context_command,
            usage="/context [show|add|remove|clear] [path]",
        ),
    )


def handle_context_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, rest = argument.partition(" ")
    action = action.strip().lower()
    context_path = rest.strip()
    if action in {"", "show"}:
        _print_context(runtime=runtime, output_stream=output_stream)
        return
    if action == "add":
        if not context_path:
            write_line(output_stream, "Usage: /context add <repo-relative-path[#symbol]>")
            return
        _add_context_path(
            runtime=runtime,
            context_path=context_path,
            output_stream=output_stream,
            context=context,
        )
        return
    if action in {"remove", "rm"}:
        if not context_path:
            write_line(output_stream, "Usage: /context remove <repo-relative-path[#symbol]>")
            return
        _remove_context_path(
            runtime=runtime,
            context_path=context_path,
            output_stream=output_stream,
            context=context,
        )
        return
    if action == "clear":
        _set_context_paths(runtime=runtime, context_paths=())
        write_line(output_stream, "Context hints cleared.")
        context.record(runtime, "context_update", {"action": "clear", "context_paths": []})
        return
    write_line(output_stream, "Usage: /context [show|add|remove|clear] [path]")


def _add_context_path(
    *,
    runtime: AgentChatRuntime,
    context_path: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    context_paths = runtime.state.config.context_paths
    if context_path in context_paths:
        write_line(output_stream, f"Context already includes: {context_path}")
        return
    updated = (*context_paths, context_path)
    _set_context_paths(runtime=runtime, context_paths=updated)
    write_line(output_stream, f"Added context: {context_path}")
    context.record(
        runtime,
        "context_update",
        {"action": "add", "context_path": context_path, "context_paths": list(updated)},
    )


def _remove_context_path(
    *,
    runtime: AgentChatRuntime,
    context_path: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    context_paths = runtime.state.config.context_paths
    if context_path not in context_paths:
        write_line(output_stream, f"Context hint not found: {context_path}")
        return
    updated = tuple(path for path in context_paths if path != context_path)
    _set_context_paths(runtime=runtime, context_paths=updated)
    write_line(output_stream, f"Removed context: {context_path}")
    context.record(
        runtime,
        "context_update",
        {
            "action": "remove",
            "context_path": context_path,
            "context_paths": list(updated),
        },
    )


def _set_context_paths(
    *,
    runtime: AgentChatRuntime,
    context_paths: tuple[str, ...],
) -> None:
    updated_config = dataclass_replace(
        runtime.state.config,
        context_paths=context_paths,
    )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)


def _print_context(*, runtime: AgentChatRuntime, output_stream: TextIO) -> None:
    context_paths = runtime.state.config.context_paths
    if not context_paths:
        write_line(output_stream, "No forced context hints.")
        return
    write_line(output_stream, "Forced context hints:")
    for index, context_path in enumerate(context_paths, start=1):
        write_line(output_stream, f"{index}. {context_path}")
