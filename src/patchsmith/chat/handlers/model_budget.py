from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import TextIO

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.state import AgentChatRuntime


def model_budget_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="model",
            handler=handle_model_command,
            usage="/model [model-name|clear]",
        ),
        ChatCommand(
            name="budget",
            handler=handle_budget_command,
            usage="/budget [responses <n>|tokens <n>|set <responses> <tokens>|clear]",
        ),
    )


def handle_model_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    value = argument.strip()
    if not value:
        _write_line(output_stream, f"Model override: {model_label(runtime.state.config)}")
        return
    if value.lower() == "clear":
        _set_model_override(runtime=runtime, model=None, context=context)
        _write_line(output_stream, "Model override cleared.")
        return
    _set_model_override(runtime=runtime, model=value, context=context)
    _write_line(output_stream, f"Model override: {value}")


def handle_budget_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    parts = argument.split()
    if not parts:
        _write_line(output_stream, f"Budget: {budget_label(runtime.state.config)}")
        return
    action = parts[0].lower()
    config = runtime.state.config
    if action == "clear" and len(parts) == 1:
        _set_budget(
            runtime=runtime,
            max_model_responses=-1,
            max_model_tokens=-1,
            context=context,
        )
        _write_line(output_stream, f"Budget: {budget_label(runtime.state.config)}")
        return
    if action == "responses" and len(parts) == 2:
        responses = _parse_budget_value(parts[1], "responses", output_stream)
        if responses is None:
            return
        _set_budget(
            runtime=runtime,
            max_model_responses=responses,
            max_model_tokens=config.max_model_tokens,
            context=context,
        )
        _write_line(output_stream, f"Budget: {budget_label(runtime.state.config)}")
        return
    if action == "tokens" and len(parts) == 2:
        tokens = _parse_budget_value(parts[1], "tokens", output_stream)
        if tokens is None:
            return
        _set_budget(
            runtime=runtime,
            max_model_responses=config.max_model_responses,
            max_model_tokens=tokens,
            context=context,
        )
        _write_line(output_stream, f"Budget: {budget_label(runtime.state.config)}")
        return
    if action == "set" and len(parts) == 3:
        responses = _parse_budget_value(parts[1], "responses", output_stream)
        tokens = _parse_budget_value(parts[2], "tokens", output_stream)
        if responses is None or tokens is None:
            return
        _set_budget(
            runtime=runtime,
            max_model_responses=responses,
            max_model_tokens=tokens,
            context=context,
        )
        _write_line(output_stream, f"Budget: {budget_label(runtime.state.config)}")
        return
    _write_line(
        output_stream,
        "Usage: /budget [responses <n>|tokens <n>|set <responses> <tokens>|clear]",
    )


def model_label(config: AgentCliConfig) -> str:
    return config.deepagents_model or "env/default"


def budget_label(config: AgentCliConfig) -> str:
    return (
        f"responses={_budget_value_label(config.max_model_responses)}, "
        f"tokens={_budget_value_label(config.max_model_tokens)}"
    )


def _set_model_override(
    *,
    runtime: AgentChatRuntime,
    model: str | None,
    context: ChatCommandContext,
) -> None:
    updated_config = dataclass_replace(runtime.state.config, deepagents_model=model)
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    context.record(runtime, "config_update", {"field": "deepagents_model", "value": model})


def _parse_budget_value(
    raw: str,
    label: str,
    output_stream: TextIO,
) -> int | None:
    try:
        value = int(raw)
    except ValueError:
        _write_line(output_stream, f"{label} must be an integer.")
        return None
    if value < -1:
        _write_line(output_stream, f"{label} must be -1 or non-negative.")
        return None
    return value


def _set_budget(
    *,
    runtime: AgentChatRuntime,
    max_model_responses: int,
    max_model_tokens: int,
    context: ChatCommandContext,
) -> None:
    updated_config = dataclass_replace(
        runtime.state.config,
        max_model_responses=max_model_responses,
        max_model_tokens=max_model_tokens,
    )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    context.record(
        runtime,
        "config_update",
        {
            "field": "resource_budget",
            "max_model_responses": max_model_responses,
            "max_model_tokens": max_model_tokens,
        },
    )


def _budget_value_label(value: int) -> str:
    return "unlimited" if value < 0 else str(value)


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
