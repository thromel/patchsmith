from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.execution import execution_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_execution_commands_are_registered() -> None:
    registry = build_command_registry(execution_commands())

    assert sorted(registry) == ["preflight", "run", "verify"]
    assert registry["preflight"].usage == "/preflight <task>"
    assert registry["verify"].usage == "/verify [command]"
    assert registry["run"].usage == "/run <task>"


def test_run_command_delegates_explicit_task(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    command = build_command_registry(execution_commands())["run"]
    output = io.StringIO()

    command.handler(
        runtime=runtime,
        argument="fix parser",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_task=_capture_task(tasks),
        ),
    )

    assert output.getvalue() == ""
    assert tasks == ["fix parser"]
    assert events == []


def test_run_command_approves_pending_planned_task(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.pending_planned_task = "fix parser"
    events: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    command = build_command_registry(execution_commands())["run"]
    output = io.StringIO()

    command.handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_task=_capture_task(tasks),
        ),
    )

    assert output.getvalue() == "Approved planned task: fix parser\n"
    assert runtime.pending_planned_task is None
    assert tasks == ["fix parser"]
    assert events == [("plan_mode_approval", {"task": "fix parser"})]


def test_run_command_without_task_prints_usage(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    command = build_command_registry(execution_commands())["run"]
    output = io.StringIO()

    command.handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_task=_capture_task(tasks),
        ),
    )

    assert output.getvalue() == "No pending planned task. Usage: /run <task>\n"
    assert tasks == []
    assert events == []


def test_preflight_and_verify_commands_delegate_arguments(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    delegated: list[tuple[str, str]] = []
    registry = build_command_registry(execution_commands())

    registry["preflight"].handler(
        runtime=runtime,
        argument="fix parser",
        output_stream=io.StringIO(),
        context=ChatCommandContext(
            record=_record_to(events),
            preflight_task=_capture_preflight(delegated),
        ),
    )
    registry["verify"].handler(
        runtime=runtime,
        argument="pytest -q",
        output_stream=io.StringIO(),
        context=ChatCommandContext(
            record=_record_to(events),
            verify_command=_capture_verify(delegated),
        ),
    )

    assert delegated == [("preflight", "fix parser"), ("verify", "pytest -q")]
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


def _capture_task(
    tasks: list[str],
) -> Callable[[AgentChatRuntime, str, io.StringIO], None]:
    def run_task(
        *,
        runtime: AgentChatRuntime,
        task: str,
        output_stream: io.StringIO,
    ) -> None:
        tasks.append(task)

    return run_task


def _capture_preflight(
    delegated: list[tuple[str, str]],
) -> Callable[[AgentChatRuntime, str, io.StringIO], None]:
    def preflight(
        *,
        runtime: AgentChatRuntime,
        task: str,
        output_stream: io.StringIO,
    ) -> None:
        delegated.append(("preflight", task))

    return preflight


def _capture_verify(
    delegated: list[tuple[str, str]],
) -> Callable[[AgentChatRuntime, str, io.StringIO], None]:
    def verify(
        *,
        runtime: AgentChatRuntime,
        argument: str,
        output_stream: io.StringIO,
    ) -> None:
        delegated.append(("verify", argument))

    return verify


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
