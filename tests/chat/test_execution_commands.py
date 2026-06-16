from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

import patchsmith.chat.handlers.execution as execution_handler
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.execution import execution_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.models import CommandPolicyDecision, CommandResult

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


def test_preflight_command_records_config_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(execution_commands())
    output = io.StringIO()

    registry["preflight"].handler(
        runtime=runtime,
        argument="fix parser",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue().startswith("Preflight: passed\n")
    assert events[-1][0] == "preflight"
    assert events[-1][1]["status"] == "passed"
    assert events[-1][1]["runtime_config"] == {
        "subagent_mode": "auto",
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
        },
    }


def test_preflight_command_reports_config_errors(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.state = runtime.state.__class__(
        session_id=runtime.state.session_id,
        transcript_path=runtime.state.transcript_path,
        config=AgentCliConfig(
            repo=str(tmp_path),
            artifacts_dir=str(tmp_path / "artifacts"),
            allow_dirty_apply=True,
        ),
    )
    events: list[tuple[str, dict[str, object]]] = []
    output = io.StringIO()

    build_command_registry(execution_commands())["preflight"].handler(
        runtime=runtime,
        argument="fix parser",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == "--allow-dirty-apply requires --apply.\n"
    assert events == [("preflight_error", {"message": "--allow-dirty-apply requires --apply."})]


def test_preflight_command_without_task_prints_usage(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    output = io.StringIO()

    build_command_registry(execution_commands())["preflight"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == "Usage: /preflight <task>\n"
    assert events == []


def test_verify_command_records_sandbox_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    calls: list[tuple[str, Path, int]] = []

    class FakeSandbox:
        def run(
            self,
            *,
            command: str,
            workspace: Path,
            timeout_seconds: int,
        ) -> CommandResult:
            calls.append((command, workspace, timeout_seconds))
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="ok\n",
                stderr="",
                duration_ms=12,
                timed_out=False,
                policy_decision=CommandPolicyDecision(
                    allowed=True,
                    reason="allowed",
                    tokens=("pytest",),
                ),
            )

    monkeypatch.setattr(
        execution_handler,
        "create_sandbox_runner",
        lambda *, mode, image: FakeSandbox(),
    )

    output = io.StringIO()
    build_command_registry(execution_commands())["verify"].handler(
        runtime=runtime,
        argument="pytest -q",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert calls == [("pytest -q", tmp_path, 60)]
    assert output.getvalue() == (
        "Verify: passed\nCommand: pytest -q\nExit code: 0\nDuration: 12 ms\nstdout: ok\n"
    )
    assert events[-1][0] == "verify_result"
    assert events[-1][1]["status"] == "passed"
    assert events[-1][1]["result"] == {
        "command": "pytest -q",
        "exit_code": 0,
        "stdout": "ok\n",
        "stderr": "",
        "duration_ms": 12,
        "timed_out": False,
        "policy_decision": {
            "allowed": True,
            "reason": "allowed",
            "tokens": ("pytest",),
        },
    }


def test_verify_command_without_command_prints_usage(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    output = io.StringIO()

    build_command_registry(execution_commands())["verify"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == (
        "Usage: /verify <allowed-test-command>\nNo test command is configured for this session.\n"
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
