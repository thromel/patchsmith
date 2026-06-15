from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.context import context_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_context_command_is_registered() -> None:
    registry = build_command_registry(context_commands())

    assert sorted(registry) == ["context"]
    assert registry["context"].usage == "/context [show|add|remove|clear] [path]"


def test_context_command_updates_runtime_context_paths(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(context_commands())["context"]

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="show",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert show_output.getvalue() == "No forced context hints.\n"
    assert events == []

    add_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="add src/simple_calc.py#add",
        output_stream=add_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.context_paths == ("src/simple_calc.py#add",)
    assert add_output.getvalue() == "Added context: src/simple_calc.py#add\n"
    assert events[-1] == (
        "context_update",
        {
            "action": "add",
            "context_path": "src/simple_calc.py#add",
            "context_paths": ["src/simple_calc.py#add"],
        },
    )

    duplicate_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="add src/simple_calc.py#add",
        output_stream=duplicate_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert duplicate_output.getvalue() == (
        "Context already includes: src/simple_calc.py#add\n"
    )
    assert len(events) == 1

    remove_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="rm src/simple_calc.py#add",
        output_stream=remove_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.context_paths == ()
    assert remove_output.getvalue() == "Removed context: src/simple_calc.py#add\n"
    assert events[-1] == (
        "context_update",
        {
            "action": "remove",
            "context_path": "src/simple_calc.py#add",
            "context_paths": [],
        },
    )

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.context_paths == ()
    assert clear_output.getvalue() == "Context hints cleared.\n"
    assert events[-1] == (
        "context_update",
        {"action": "clear", "context_paths": []},
    )


def test_context_command_prints_usage_for_missing_or_unknown_actions(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(context_commands())["context"]

    add_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="add",
        output_stream=add_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert add_output.getvalue() == "Usage: /context add <repo-relative-path[#symbol]>\n"

    remove_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="remove",
        output_stream=remove_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert remove_output.getvalue() == (
        "Usage: /context remove <repo-relative-path[#symbol]>\n"
    )

    unknown_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="unknown",
        output_stream=unknown_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert unknown_output.getvalue() == "Usage: /context [show|add|remove|clear] [path]\n"
    assert events == []


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
