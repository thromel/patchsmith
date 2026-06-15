from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import TextIO

from patchsmith.agent_cli import AgentCliConfig, config_with_loaded_agent_instructions
from patchsmith.agent_instructions import (
    append_agent_memory_note,
    format_agent_instructions,
    format_agent_memory,
    load_agent_instruction_bundle,
)
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def memory_instruction_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="instructions",
            handler=handle_instructions_command,
            usage="/instructions [show|reload|clear]",
        ),
        ChatCommand(
            name="memory",
            handler=handle_memory_command,
            usage="/memory [show|reload|clear|add <note>]",
        ),
    )


def handle_instructions_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    _handle_instruction_surface(
        runtime=runtime,
        argument=argument,
        output_stream=output_stream,
        context=context,
        surface="instructions",
    )


def handle_memory_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    _handle_instruction_surface(
        runtime=runtime,
        argument=argument,
        output_stream=output_stream,
        context=context,
        surface="memory",
    )


def instruction_update_payload(config: AgentCliConfig) -> dict[str, object]:
    return {
        "field": "project_instructions",
        "load_agent_instructions": config.load_agent_instructions,
        "instruction_paths": list(config.instruction_paths),
        "agent_instruction_files": list(config.agent_instruction_files),
        "agent_instruction_chars": len(config.agent_instructions or ""),
        "agent_instructions": config.agent_instructions,
    }


def _handle_instruction_surface(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
    surface: str,
) -> None:
    action = argument.strip().lower()
    command = "/memory" if surface == "memory" else "/instructions"
    label = "memory" if surface == "memory" else "instructions"
    if action in {"", "show"}:
        bundle = load_agent_instruction_bundle(
            runtime.state.config.repo,
            explicit_paths=runtime.state.config.instruction_paths,
            include_defaults=runtime.state.config.load_agent_instructions,
        )
        event = "memory_view" if surface == "memory" else "instruction_view"
        context.record(
            runtime,
            event,
            {
                "count": len(bundle.files),
                "instruction_chars": bundle.total_chars,
                "files": [file.repo_relative_path for file in bundle.files],
            },
        )
        formatter = format_agent_memory if surface == "memory" else format_agent_instructions
        write_line(output_stream, formatter(bundle))
        return
    if surface == "memory" and action.startswith("add "):
        _handle_memory_add(
            runtime=runtime,
            note=argument.strip()[len("add ") :].strip(),
            output_stream=output_stream,
            context=context,
        )
        return
    if action == "reload":
        updated_config = config_with_loaded_agent_instructions(
            dataclass_replace(
                runtime.state.config,
                load_agent_instructions=True,
                agent_instruction_files=(),
                agent_instructions=None,
            )
        )
        runtime.state = dataclass_replace(runtime.state, config=updated_config)
        context.record(runtime, "config_update", instruction_update_payload(updated_config))
        write_line(output_stream, f"Project {label} reloaded.")
        write_line(
            output_stream,
            f"Loaded instruction files: {len(updated_config.agent_instruction_files)}",
        )
        return
    if action == "clear":
        updated_config = dataclass_replace(
            runtime.state.config,
            load_agent_instructions=False,
            agent_instruction_files=(),
            agent_instructions=None,
        )
        runtime.state = dataclass_replace(runtime.state, config=updated_config)
        context.record(runtime, "config_update", instruction_update_payload(updated_config))
        write_line(output_stream, f"Project {label} disabled for later runs.")
        return
    usage = f"Usage: {command} [show|reload|clear]"
    if surface == "memory":
        usage = f"Usage: {command} [show|reload|clear|add <note>]"
    write_line(output_stream, usage)


def _handle_memory_add(
    *,
    runtime: AgentChatRuntime,
    note: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if not note:
        write_line(output_stream, "Usage: /memory add <note>")
        return
    try:
        update = append_agent_memory_note(runtime.state.config.repo, note)
    except ValueError as exc:
        write_line(output_stream, f"Project memory update failed: {exc}")
        context.record(
            runtime,
            "memory_update",
            {"status": "failed", "message": str(exc), "note": note},
        )
        return
    updated_config = config_with_loaded_agent_instructions(
        dataclass_replace(
            runtime.state.config,
            load_agent_instructions=True,
            agent_instruction_files=(),
            agent_instructions=None,
        )
    )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    payload = {
        "status": "already_present" if update.already_present else "added",
        **update.to_dict(),
    }
    context.record(runtime, "memory_update", payload)
    context.record(runtime, "config_update", instruction_update_payload(updated_config))
    if update.already_present:
        write_line(output_stream, f"Project memory already had note: {update.note}")
    else:
        write_line(output_stream, f"Project memory added: {update.note}")
    write_line(output_stream, f"Memory file: {update.repo_relative_path}")
