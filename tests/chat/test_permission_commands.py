from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.permissions import permission_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_permission_command_is_registered() -> None:
    registry = build_command_registry(permission_commands())

    assert sorted(registry) == ["permissions"]
    assert (
        registry["permissions"].usage
        == "/permissions [show|apply auto|apply manual|dirty allow|dirty deny]"
    )


def test_permission_command_updates_runtime_config(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(permission_commands())["permissions"]

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Permissions:\n" in show_output.getvalue()
    assert events[-1] == (
        "permission_view",
        {
            "repo": str(tmp_path),
            "apply_after_run": False,
            "allow_dirty_apply": False,
            "sandbox_mode": "local",
            "test_command": None,
        },
    )

    dirty_before_apply_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="dirty allow",
        output_stream=dirty_before_apply_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert dirty_before_apply_output.getvalue() == (
        "Enable auto apply before allowing dirty apply: /permissions apply auto\n"
    )
    assert len(events) == 1

    apply_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="apply auto",
        output_stream=apply_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.apply is True
    assert runtime.state.config.allow_dirty_apply is False
    assert events[-1] == (
        "config_update",
        {"field": "permissions", "apply": True, "allow_dirty_apply": False},
    )

    dirty_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="dirty allow",
        output_stream=dirty_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.allow_dirty_apply is True
    assert events[-1] == (
        "config_update",
        {"field": "permissions", "apply": True, "allow_dirty_apply": True},
    )

    manual_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="apply manual",
        output_stream=manual_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.state.config.apply is False
    assert runtime.state.config.allow_dirty_apply is False
    assert events[-1] == (
        "config_update",
        {"field": "permissions", "apply": False, "allow_dirty_apply": False},
    )


def test_permission_command_rejects_invalid_values_without_recording(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(permission_commands())["permissions"]

    bad_apply_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="apply maybe",
        output_stream=bad_apply_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_apply_output.getvalue() == "Usage: /permissions apply [auto|manual]\n"

    bad_dirty_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="dirty maybe",
        output_stream=bad_dirty_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_dirty_output.getvalue() == "Usage: /permissions dirty [allow|deny]\n"

    bad_action_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="unknown",
        output_stream=bad_action_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_action_output.getvalue() == (
        "Usage: /permissions [show|apply auto|apply manual|dirty allow|dirty deny]\n"
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
