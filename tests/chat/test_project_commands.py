from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.project import project_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_project_commands_are_registered() -> None:
    registry = build_command_registry(project_commands())

    assert sorted(registry) == [
        "agent",
        "agents",
        "commands",
        "hooks",
        "profile",
        "profiles",
        "sessions",
    ]
    assert registry["agent"].usage == "/agent [name|clear]"
    assert registry["profile"] is registry["agent"]


def test_project_listing_commands_record_counts(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(project_commands())
    _write_custom_command(tmp_path)
    _write_hook_config(tmp_path)
    _write_agent_profile(tmp_path)

    commands_output = io.StringIO()
    registry["commands"].handler(
        runtime=runtime,
        argument="",
        output_stream=commands_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Project custom commands:" in commands_output.getvalue()
    assert events[-1] == (
        "custom_command_list",
        {
            "count": 1,
            "repo": str(tmp_path),
            "command_root": ".patchsmith/commands",
        },
    )

    hooks_output = io.StringIO()
    registry["hooks"].handler(
        runtime=runtime,
        argument="",
        output_stream=hooks_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Project hooks:" in hooks_output.getvalue()
    assert events[-1] == (
        "hook_list",
        {
            "count": 1,
            "repo": str(tmp_path),
            "hook_config": ".patchsmith/hooks.json",
        },
    )

    agents_output = io.StringIO()
    registry["agents"].handler(
        runtime=runtime,
        argument="",
        output_stream=agents_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Project agent profiles:" in agents_output.getvalue()
    assert events[-1] == (
        "agent_profile_list",
        {
            "count": 1,
            "repo": str(tmp_path),
            "profile_root": ".patchsmith/agents",
        },
    )


def test_agent_profile_command_updates_runtime_config(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(project_commands())["agent"]
    profile_path = _write_agent_profile(tmp_path)

    set_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="verifier",
        output_stream=set_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert set_output.getvalue() == (
        "Agent profile: /verifier\nDescription: Verify patches\n"
    )
    assert runtime.state.config.agent_profile == "verifier"
    assert runtime.state.config.agent_profile_path == str(profile_path)
    assert runtime.state.config.deepagents_model == "gpt-test"
    assert runtime.state.config.max_model_responses == 3
    assert runtime.state.config.max_model_tokens == 50000
    assert runtime.state.config.top_k == 7
    assert runtime.state.config.context_paths == ("src/a.py",)
    assert events[-1][0] == "config_update"
    assert events[-1][1]["field"] == "agent_profile"
    assert events[-1][1]["agent_profile"] == "verifier"

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="show",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Agent profile: /verifier\n" in show_output.getvalue()
    assert f"Source: {profile_path}\n" in show_output.getvalue()

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.agent_profile is None
    assert clear_output.getvalue() == "Agent profile cleared.\n"
    assert events[-1][1]["agent_profile"] is None


def test_agent_profile_command_reports_missing_profile(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(project_commands())["agent"]

    output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="missing",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == (
        "Agent profile not found: missing\nUse /agents to list project profiles.\n"
    )
    assert events == []


def _write_custom_command(tmp_path: Path) -> Path:
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    command_path = command_dir / "review.md"
    command_path.write_text("Review $ARGUMENTS\n", encoding="utf-8")
    return command_path


def _write_hook_config(tmp_path: Path) -> Path:
    hook_path = tmp_path / ".patchsmith" / "hooks.json"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        '{"hooks":{"PreRun":{"command":"python -m pytest","name":"unit"}}}\n',
        encoding="utf-8",
    )
    return hook_path


def _write_agent_profile(tmp_path: Path) -> Path:
    profile_dir = tmp_path / ".patchsmith" / "agents"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "verifier.md"
    profile_path.write_text(
        "---\n"
        "description: Verify patches\n"
        "model: gpt-test\n"
        "max_model_responses: 3\n"
        "max_model_tokens: 50000\n"
        "top_k: 7\n"
        "context_paths: src/a.py\n"
        "---\n"
        "Check patch behavior before editing.\n",
        encoding="utf-8",
    )
    return profile_path


def _runtime(tmp_path: Path) -> AgentChatRuntime:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "test.jsonl"
    transcript_path.parent.mkdir(parents=True)
    return AgentChatRuntime(
        state=AgentChatState(
            session_id="test-session",
            transcript_path=transcript_path,
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        )
    )


def _record_to(
    events: list[tuple[str, dict[str, object]]],
) -> Callable[[AgentChatRuntime, str, dict[str, object]], None]:
    def record(
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
    ) -> None:
        events.append((event, payload))

    return record
