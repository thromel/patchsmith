from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.model_budget import model_budget_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_model_budget_commands_are_registered() -> None:
    registry = build_command_registry(model_budget_commands())

    assert sorted(registry) == ["budget", "model"]
    assert registry["model"].usage == "/model [model-name|clear]"
    assert (
        registry["budget"].usage
        == "/budget [responses <n>|tokens <n>|set <responses> <tokens>|clear]"
    )


def test_model_command_updates_runtime_config(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(model_budget_commands())["model"]

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert show_output.getvalue() == "Model override: env/default\n"
    assert events == []

    set_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="gpt-5-mini",
        output_stream=set_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.deepagents_model == "gpt-5-mini"
    assert set_output.getvalue() == "Model override: gpt-5-mini\n"
    assert events[-1] == (
        "config_update",
        {"field": "deepagents_model", "value": "gpt-5-mini"},
    )

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.deepagents_model is None
    assert clear_output.getvalue() == "Model override cleared.\n"
    assert events[-1] == (
        "config_update",
        {"field": "deepagents_model", "value": None},
    )


def test_budget_command_updates_runtime_config(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(model_budget_commands())["budget"]

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert show_output.getvalue() == "Budget: responses=12, tokens=200000\n"

    set_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="set 6 90000",
        output_stream=set_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.max_model_responses == 6
    assert runtime.state.config.max_model_tokens == 90000
    assert set_output.getvalue() == "Budget: responses=6, tokens=90000\n"
    assert events[-1] == (
        "config_update",
        {
            "field": "resource_budget",
            "max_model_responses": 6,
            "max_model_tokens": 90000,
        },
    )

    responses_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="responses -1",
        output_stream=responses_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.max_model_responses == -1
    assert runtime.state.config.max_model_tokens == 90000
    assert responses_output.getvalue() == "Budget: responses=unlimited, tokens=90000\n"

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.max_model_responses == -1
    assert runtime.state.config.max_model_tokens == -1
    assert clear_output.getvalue() == "Budget: responses=unlimited, tokens=unlimited\n"


def test_budget_command_rejects_invalid_values_without_recording(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(model_budget_commands())["budget"]

    bad_integer_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="tokens many",
        output_stream=bad_integer_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_integer_output.getvalue() == "tokens must be an integer.\n"

    negative_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="responses -2",
        output_stream=negative_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert negative_output.getvalue() == "responses must be -1 or non-negative.\n"

    usage_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="set 6",
        output_stream=usage_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert usage_output.getvalue() == (
        "Usage: /budget [responses <n>|tokens <n>|set <responses> <tokens>|clear]\n"
    )
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
