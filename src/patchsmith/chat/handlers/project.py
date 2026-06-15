from __future__ import annotations

from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import TextIO

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_commands import format_custom_commands, list_custom_commands
from patchsmith.agent_hooks import format_agent_hooks, list_agent_hooks
from patchsmith.agent_profiles import (
    AgentProfile,
    format_agent_profiles,
    list_agent_profiles,
    load_agent_profile,
)
from patchsmith.agent_session import format_session_summaries, list_session_summaries
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def project_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="sessions",
            handler=handle_sessions_command,
            usage="/sessions",
        ),
        ChatCommand(
            name="commands",
            handler=handle_commands_command,
            usage="/commands",
        ),
        ChatCommand(
            name="hooks",
            handler=handle_hooks_command,
            usage="/hooks",
        ),
        ChatCommand(
            name="agents",
            aliases=("profiles",),
            handler=handle_agent_profiles_command,
            usage="/agents",
        ),
        ChatCommand(
            name="agent",
            aliases=("profile",),
            handler=handle_agent_profile_command,
            usage="/agent [name|clear]",
        ),
    )


def handle_sessions_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    summaries = list_session_summaries(Path(runtime.state.config.artifacts_dir))
    context.record(
        runtime,
        "session_list",
        {
            "count": len(summaries),
            "artifacts_dir": runtime.state.config.artifacts_dir,
        },
    )
    write_line(output_stream, format_session_summaries(summaries))


def handle_commands_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    commands = list_custom_commands(runtime.state.config.repo)
    context.record(
        runtime,
        "custom_command_list",
        {
            "count": len(commands),
            "repo": runtime.state.config.repo,
            "command_root": ".patchsmith/commands",
        },
    )
    write_line(output_stream, format_custom_commands(commands))


def handle_hooks_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    hooks = list_agent_hooks(runtime.state.config.repo)
    context.record(
        runtime,
        "hook_list",
        {
            "count": len(hooks),
            "repo": runtime.state.config.repo,
            "hook_config": ".patchsmith/hooks.json",
        },
    )
    write_line(output_stream, format_agent_hooks(hooks))


def handle_agent_profiles_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    profiles = list_agent_profiles(runtime.state.config.repo)
    context.record(
        runtime,
        "agent_profile_list",
        {
            "count": len(profiles),
            "repo": runtime.state.config.repo,
            "profile_root": ".patchsmith/agents",
        },
    )
    write_line(output_stream, format_agent_profiles(profiles))


def handle_agent_profile_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action = argument.strip().lower()
    if action in {"", "show"}:
        _print_agent_profile(runtime=runtime, output_stream=output_stream)
        return
    if action == "clear":
        _set_agent_profile(runtime=runtime, profile=None, context=context)
        write_line(output_stream, "Agent profile cleared.")
        return
    profile = load_agent_profile(runtime.state.config.repo, action)
    if profile is None:
        write_line(output_stream, f"Agent profile not found: {action}")
        write_line(output_stream, "Use /agents to list project profiles.")
        return
    _set_agent_profile(runtime=runtime, profile=profile, context=context)
    write_line(output_stream, f"Agent profile: /{profile.name}")
    if profile.description:
        write_line(output_stream, f"Description: {profile.description}")


def _print_agent_profile(
    *,
    runtime: AgentChatRuntime,
    output_stream: TextIO,
) -> None:
    config = runtime.state.config
    if not config.agent_profile:
        write_line(output_stream, "Agent profile: none")
        return
    write_line(output_stream, f"Agent profile: /{config.agent_profile}")
    if config.agent_profile_description:
        write_line(output_stream, f"Description: {config.agent_profile_description}")
    if config.agent_profile_path:
        write_line(output_stream, f"Source: {config.agent_profile_path}")


def _set_agent_profile(
    *,
    runtime: AgentChatRuntime,
    profile: AgentProfile | None,
    context: ChatCommandContext,
) -> None:
    config = runtime.state.config
    if profile is None:
        updated_config = dataclass_replace(
            config,
            agent_profile=None,
            agent_profile_path=None,
            agent_profile_description=None,
            agent_profile_instructions=None,
        )
    else:
        updated_config = dataclass_replace(
            config,
            agent_profile=profile.name,
            agent_profile_path=str(profile.path),
            agent_profile_description=profile.description,
            agent_profile_instructions=profile.instructions,
            deepagents_model=profile.model or config.deepagents_model,
            deepagents_subagents=profile.subagents or config.deepagents_subagents,
            deepagents_max_context_files=(
                profile.max_context_files
                if profile.max_context_files is not None
                else config.deepagents_max_context_files
            ),
            max_model_responses=(
                profile.max_model_responses
                if profile.max_model_responses is not None
                else config.max_model_responses
            ),
            max_model_tokens=(
                profile.max_model_tokens
                if profile.max_model_tokens is not None
                else config.max_model_tokens
            ),
            top_k=profile.top_k if profile.top_k is not None else config.top_k,
            test_command=profile.test_command or config.test_command,
            context_paths=_merged_context_paths(
                config.context_paths,
                profile.context_paths,
            ),
        )
    runtime.state = dataclass_replace(runtime.state, config=updated_config)
    context.record(runtime, "config_update", _agent_profile_update_payload(updated_config))


def _agent_profile_update_payload(config: AgentCliConfig) -> dict[str, object]:
    return {
        "field": "agent_profile",
        "agent_profile": config.agent_profile,
        "agent_profile_path": config.agent_profile_path,
        "agent_profile_description": config.agent_profile_description,
        "agent_profile_instructions": config.agent_profile_instructions,
        "agent_profile_instruction_chars": len(config.agent_profile_instructions or ""),
        "deepagents_model": config.deepagents_model,
        "deepagents_subagents": config.deepagents_subagents,
        "deepagents_max_context_files": config.deepagents_max_context_files,
        "max_model_responses": config.max_model_responses,
        "max_model_tokens": config.max_model_tokens,
        "top_k": config.top_k,
        "test_command": config.test_command,
        "context_paths": list(config.context_paths),
    }


def _merged_context_paths(
    existing: tuple[str, ...],
    added: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *added)))
