from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.session_plan import plan_feedback_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_plan_feedback_commands_are_registered() -> None:
    registry = build_command_registry(plan_feedback_commands())

    assert sorted(registry) == ["feedback", "note", "notes", "plan"]
    assert registry["plan"].usage == "/plan [show|set|add|start|done|block|skip|pending|clear] ..."
    assert registry["feedback"].usage == "/feedback [show|add|clear] [guidance]"
    assert registry["note"] is registry["feedback"]
    assert registry["notes"] is registry["feedback"]


def test_plan_command_updates_session_plan(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(plan_feedback_commands())["plan"]

    set_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="set inspect parser; write focused test",
        output_stream=set_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert [item.text for item in runtime.plan_items or []] == [
        "inspect parser",
        "write focused test",
    ]
    assert "1 | pending | inspect parser" in set_output.getvalue()
    assert events[-1][0] == "plan_update"
    assert events[-1][1]["action"] == "set"

    start_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="start 1",
        output_stream=start_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert (runtime.plan_items or [])[0].status == "in_progress"
    assert "1 | in_progress | inspect parser" in start_output.getvalue()
    assert events[-1][1]["action"] == "start"
    assert events[-1][1]["index"] == 1

    show_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="show",
        output_stream=show_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Session plan:" in show_output.getvalue()
    assert events[-1][0] == "plan_view"

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.plan_items == []
    assert clear_output.getvalue() == "Session plan cleared.\n"
    assert events[-1][1]["action"] == "clear"


def test_plan_command_reports_invalid_updates_without_recording(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(plan_feedback_commands())["plan"]

    bad_index_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="start nope",
        output_stream=bad_index_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_index_output.getvalue() == "Usage: /plan start <index>\n"

    missing_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="done 99",
        output_stream=missing_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert missing_output.getvalue() == "Plan item not found: 99\n"

    empty_set_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="set",
        output_stream=empty_set_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert empty_set_output.getvalue() == "Usage: /plan set <task>; <task>; ...\n"
    assert events == []


def test_feedback_command_updates_session_feedback(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(plan_feedback_commands())["feedback"]

    show_empty_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=show_empty_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert show_empty_output.getvalue() == "No session feedback.\n"
    assert events[-1] == ("feedback_view", {"items": []})

    shorthand_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="keep the public API stable",
        output_stream=shorthand_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.feedback_items == ["keep the public API stable"]
    assert shorthand_output.getvalue() == "Added feedback: keep the public API stable\n"
    assert events[-1] == (
        "feedback_update",
        {
            "action": "add",
            "item": "keep the public API stable",
            "items": ["keep the public API stable"],
        },
    )

    add_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="add avoid broad rewrites",
        output_stream=add_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.feedback_items == [
        "keep the public API stable",
        "avoid broad rewrites",
    ]
    assert add_output.getvalue() == "Added feedback: avoid broad rewrites\n"

    clear_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="clear",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.feedback_items == []
    assert clear_output.getvalue() == "Session feedback cleared.\n"
    assert events[-1] == ("feedback_update", {"action": "clear", "items": []})


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
