from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext
from patchsmith.chat.custom_commands import handle_custom_command
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_handle_custom_command_returns_false_for_missing_command(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    output = io.StringIO()

    handled = handle_custom_command(
        runtime=runtime,
        command="missing",
        argument="parser",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_task=_run_task_to(tasks),
        ),
    )

    assert handled is False
    assert output.getvalue() == ""
    assert events == []
    assert tasks == []


def test_handle_custom_command_records_and_runs_rendered_prompt(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    command_path = _write_custom_command(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    hook_payloads: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    output = io.StringIO()

    handled = handle_custom_command(
        runtime=runtime,
        command="review",
        argument="parser edge cases",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_hooks=_run_hooks_to(hook_payloads, allowed=True),
            run_task=_run_task_to(tasks),
        ),
    )

    assert handled is True
    assert output.getvalue() == "Running custom command: /review\n"
    assert hook_payloads == [
        (
            "UserPromptExpansion",
            {
                "command": "review",
                "argument": "parser edge cases",
                "command_path": str(command_path),
                "prompt_chars": len(tasks[0]),
                "matcher_target": "review",
            },
        )
    ]
    assert events == [
        (
            "custom_command",
            {
                "command": "review",
                "argument": "parser edge cases",
                "command_path": str(command_path),
                "prompt_chars": len(tasks[0]),
            },
        )
    ]
    assert len(tasks) == 1
    assert "PatchSmith custom command /review" in tasks[0]
    assert "Focus: parser edge cases" in tasks[0]
    assert "description:" not in tasks[0]


def test_handle_custom_command_stops_when_prompt_expansion_hook_blocks(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _write_custom_command(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    hook_payloads: list[tuple[str, dict[str, object]]] = []
    tasks: list[str] = []
    output = io.StringIO()

    handled = handle_custom_command(
        runtime=runtime,
        command="review",
        argument="parser edge cases",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_hooks=_run_hooks_to(hook_payloads, allowed=False),
            run_task=_run_task_to(tasks),
        ),
    )

    assert handled is True
    assert hook_payloads[0][0] == "UserPromptExpansion"
    assert events == []
    assert tasks == []


def _write_custom_command(tmp_path: Path) -> Path:
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    command_path = command_dir / "review.md"
    command_path.write_text(
        "---\n"
        "description: Review selected code\n"
        "---\n"
        "Review the selected code path.\n\n"
        "Focus: $ARGUMENTS\n",
        encoding="utf-8",
    )
    return command_path


def _runtime(tmp_path: Path) -> AgentChatRuntime:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "test.jsonl"
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


def _run_task_to(tasks: list[str]):
    def run_task(
        *,
        runtime: AgentChatRuntime,
        task: str,
        output_stream: io.StringIO,
    ) -> None:
        tasks.append(task)

    return run_task


def _run_hooks_to(
    hook_payloads: list[tuple[str, dict[str, object]]],
    *,
    allowed: bool,
):
    def run_hooks(
        *,
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
        output_stream: io.StringIO,
        blocking: bool,
    ) -> bool:
        hook_payloads.append((event, payload))
        return allowed

    return run_hooks
