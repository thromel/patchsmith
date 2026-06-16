from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import TextIO

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_permissions import format_permissions, permission_state
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def permission_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="permissions",
            handler=handle_permissions_command,
            usage="/permissions [show|apply auto|apply manual|dirty allow|dirty deny]",
        ),
    )


def handle_permissions_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, raw_value = argument.partition(" ")
    action = action.strip().lower()
    value = raw_value.strip().lower()
    if action in {"", "show"}:
        context.record(
            runtime,
            "permission_view",
            permission_state(runtime.state.config).to_dict(),
        )
        write_line(output_stream, format_permissions(runtime.state.config))
        return
    if action == "apply":
        next_value = _parse_apply_permission(value, output_stream)
        if next_value is None:
            return
        _set_apply_permission(
            runtime=runtime,
            apply_after_run=next_value,
            context=context,
        )
        write_line(output_stream, format_permissions(runtime.state.config))
        return
    if action == "dirty":
        next_value = _parse_dirty_permission(
            value,
            config=runtime.state.config,
            output_stream=output_stream,
        )
        if next_value is None:
            return
        _set_dirty_apply_permission(
            runtime=runtime,
            allow_dirty_apply=next_value,
            context=context,
        )
        write_line(output_stream, format_permissions(runtime.state.config))
        return
    write_line(
        output_stream,
        "Usage: /permissions [show|apply auto|apply manual|dirty allow|dirty deny]",
    )


def _parse_apply_permission(raw: str, output_stream: TextIO) -> bool | None:
    if raw in {"auto", "on", "true"}:
        return True
    if raw in {"manual", "off", "false"}:
        return False
    write_line(output_stream, "Usage: /permissions apply [auto|manual]")
    return None


def _parse_dirty_permission(
    raw: str,
    *,
    config: AgentCliConfig,
    output_stream: TextIO,
) -> bool | None:
    if raw in {"deny", "denied", "off", "false"}:
        return False
    if raw in {"allow", "allowed", "on", "true"}:
        if not config.apply:
            write_line(
                output_stream,
                "Enable auto apply before allowing dirty apply: /permissions apply auto",
            )
            return None
        return True
    write_line(output_stream, "Usage: /permissions dirty [allow|deny]")
    return None


def _set_apply_permission(
    *,
    runtime: AgentChatRuntime,
    apply_after_run: bool,
    context: ChatCommandContext,
) -> None:
    updated_config = dataclass_replace(
        runtime.state.config,
        apply=apply_after_run,
        allow_dirty_apply=(runtime.state.config.allow_dirty_apply if apply_after_run else False),
    )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    context.record(runtime, "config_update", _permission_update_payload(updated_config))


def _set_dirty_apply_permission(
    *,
    runtime: AgentChatRuntime,
    allow_dirty_apply: bool,
    context: ChatCommandContext,
) -> None:
    updated_config = dataclass_replace(
        runtime.state.config,
        allow_dirty_apply=allow_dirty_apply,
    )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    context.record(runtime, "config_update", _permission_update_payload(updated_config))


def _permission_update_payload(config: AgentCliConfig) -> dict[str, object]:
    return {
        "field": "permissions",
        "apply": config.apply,
        "allow_dirty_apply": config.allow_dirty_apply,
    }
