from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.session_state import session_state_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_session_state_commands_are_registered() -> None:
    registry = build_command_registry(session_state_commands())

    assert sorted(registry) == [
        "cancel",
        "clear",
        "compact",
        "history",
        "mode",
        "status",
    ]
    assert registry["status"].usage == "/status"
    assert registry["mode"].usage == "/mode [act|plan]"
    assert registry["compact"].usage == "/compact [note]"


def test_mode_and_cancel_commands_update_runtime_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(session_state_commands())

    mode_output = io.StringIO()
    registry["mode"].handler(
        runtime=runtime,
        argument="plan",
        output_stream=mode_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.chat_mode == "plan"
    assert "Chat mode: plan. Plain text runs /preflight" in mode_output.getvalue()
    assert events[-1] == ("chat_mode_update", {"mode": "plan"})

    runtime.pending_planned_task = "fix parser"
    cancel_output = io.StringIO()
    registry["cancel"].handler(
        runtime=runtime,
        argument="plan",
        output_stream=cancel_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert runtime.pending_planned_task is None
    assert cancel_output.getvalue() == "Cancelled planned task: fix parser\n"
    assert events[-1] == ("plan_mode_cancel", {"task": "fix parser"})


def test_status_and_history_commands_render_session_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.chat_mode = "plan"
    runtime.pending_planned_task = "fix parser"
    runtime.history = ["fix one", "fix two"]
    runtime.feedback_items = ["prefer tests first"]
    runtime.plan_items = [AgentPlanItem(text="inspect parser", status="in_progress")]
    runtime.last_run_payload = {
        "run_id": "run-1",
        "status": "completed",
        "report_path": "artifacts/runs/run-1/report.md",
        "final_diff_path": "artifacts/runs/run-1/final.diff",
    }
    registry = build_command_registry(session_state_commands())

    status_output = io.StringIO()
    registry["status"].handler(
        runtime=runtime,
        argument="",
        output_stream=status_output,
        context=ChatCommandContext(record=_noop_record),
    )
    status_text = status_output.getvalue()
    assert "Session: test-session\n" in status_text
    assert "Chat mode: plan\n" in status_text
    assert "Pending planned task: fix parser\n" in status_text
    assert "Session plan items: 1\n" in status_text
    assert "Session feedback items: 1\n" in status_text
    assert "Last run: run-1\n" in status_text
    assert "Last diff: artifacts/runs/run-1/final.diff\n" in status_text

    history_output = io.StringIO()
    registry["history"].handler(
        runtime=runtime,
        argument="",
        output_stream=history_output,
        context=ChatCommandContext(record=_noop_record),
    )
    assert history_output.getvalue() == "1. fix one\n2. fix two\n"


def test_clear_and_compact_commands_record_replayable_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.history = ["fix one"]
    runtime.plan_items = [AgentPlanItem(text="inspect parser")]
    runtime.feedback_items = ["prefer tests first"]
    runtime.pending_planned_task = "fix parser"
    runtime.last_run_payload = {"run_id": "run-1", "status": "completed"}
    runtime.last_apply = AgentApplyResult(
        status="applied",
        repo_path=str(tmp_path),
        diff_path="final.diff",
        message="applied",
        applied=True,
    )
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(session_state_commands())

    compact_output = io.StringIO()
    registry["compact"].handler(
        runtime=runtime,
        argument="keep parser target",
        output_stream=compact_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert compact_output.getvalue() == (
        "Session compacted. Summarized 1 task(s).\n"
        "Last run artifact pointers were preserved.\n"
    )
    assert runtime.history == []
    assert runtime.compaction_summary is not None
    assert events[-1][0] == "session_compact"
    assert events[-1][1]["note"] == "keep parser target"
    assert events[-1][1]["recent_tasks"] == ["fix one"]
    assert events[-1][1]["last_run_id"] == "run-1"

    clear_output = io.StringIO()
    registry["clear"].handler(
        runtime=runtime,
        argument="",
        output_stream=clear_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert clear_output.getvalue() == "Session state cleared. Transcript retained.\n"
    assert runtime.plan_items == []
    assert runtime.feedback_items == []
    assert runtime.compaction_summary is None
    assert events[-1][0] == "session_clear"
    assert events[-1][1]["cleared_last_run_id"] == "run-1"
    assert events[-1][1]["cleared_last_apply"] == "applied"


def test_session_state_commands_report_invalid_inputs(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(session_state_commands())

    bad_mode_output = io.StringIO()
    registry["mode"].handler(
        runtime=runtime,
        argument="unknown",
        output_stream=bad_mode_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_mode_output.getvalue() == "Usage: /mode [act|plan]\n"

    bad_cancel_output = io.StringIO()
    registry["cancel"].handler(
        runtime=runtime,
        argument="everything",
        output_stream=bad_cancel_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert bad_cancel_output.getvalue() == "Usage: /cancel [plan]\n"
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


def _noop_record(
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
) -> None:
    return None


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
