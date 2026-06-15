from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_chat import run_chat_session
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.memory import memory_instruction_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_memory_instruction_commands_are_registered() -> None:
    registry = build_command_registry(memory_instruction_commands())

    assert sorted(registry) == ["instructions", "memory"]
    assert registry["instructions"].usage == "/instructions [show|reload|clear]"
    assert registry["memory"].usage == "/memory [show|reload|clear|add <note>]"


def test_memory_add_persists_note_and_reloads_instruction_config(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    output = io.StringIO()
    command = build_command_registry(memory_instruction_commands())["memory"]

    command.handler(
        runtime=runtime,
        argument="add  keep parser fixes focused  ",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    memory_path = tmp_path / ".patchsmith" / "instructions.md"
    memory_text = memory_path.read_text(encoding="utf-8")
    assert "## PatchSmith Memory" in memory_text
    assert "- keep parser fixes focused" in memory_text
    assert "Project memory added: keep parser fixes focused" in output.getvalue()
    assert "Memory file: .patchsmith/instructions.md" in output.getvalue()
    assert runtime.state.config.load_agent_instructions is True
    assert runtime.state.config.agent_instruction_files == (".patchsmith/instructions.md",)
    assert "keep parser fixes focused" in (runtime.state.config.agent_instructions or "")
    assert [event for event, _payload in events] == ["memory_update", "config_update"]
    assert events[0][1]["status"] == "added"
    assert events[1][1]["field"] == "project_instructions"

    duplicate_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="add keep parser fixes focused",
        output_stream=duplicate_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert memory_path.read_text(encoding="utf-8").count("- keep parser fixes focused") == 1
    assert "Project memory already had note: keep parser fixes focused" in (
        duplicate_output.getvalue()
    )
    assert events[-2][0] == "memory_update"
    assert events[-2][1]["status"] == "already_present"


def test_memory_add_empty_note_prints_usage(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    output = io.StringIO()
    command = build_command_registry(memory_instruction_commands())["memory"]

    command.handler(
        runtime=runtime,
        argument="add   ",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == "Usage: /memory [show|reload|clear|add <note>]\n"
    assert events == []
    assert not (tmp_path / ".patchsmith" / "instructions.md").exists()


def test_chat_session_memory_add_uses_registered_command_handler(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            raise AssertionError("memory commands must not run the repair loop")

    output = io.StringIO()

    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/memory add keep parser fixes focused\n"
                "/memory\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=NoRunRepairRunner,
            session_id="memory-add-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Project memory added: keep parser fixes focused" in text
    assert "Project memory files:" in text
    assert ".patchsmith/instructions.md | patchsmith" in text
    memory_text = (tmp_path / ".patchsmith" / "instructions.md").read_text(
        encoding="utf-8"
    )
    assert "- keep parser fixes focused" in memory_text

    transcript_path = artifacts / "chat_sessions" / "memory-add-session.jsonl"
    rows = [
        json.loads(line)
        for line in transcript_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(
        row["event"] == "memory_update" and row["payload"]["status"] == "added"
        for row in rows
    )
    assert any(
        row["event"] == "config_update"
        and row["payload"]["field"] == "project_instructions"
        for row in rows
    )
    assert any(row["event"] == "memory_view" for row in rows)


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
