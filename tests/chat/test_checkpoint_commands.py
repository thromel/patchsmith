from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import replace as dataclass_replace
from pathlib import Path

import pytest

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.checkpoints import checkpoint_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.session.store import append_transcript_event

pytestmark = pytest.mark.unit


def test_checkpoint_commands_are_registered() -> None:
    registry = build_command_registry(checkpoint_commands())

    assert sorted(registry) == ["checkpoint", "checkpoints", "restore"]
    assert registry["checkpoint"].usage == "/checkpoint [label]"
    assert registry["checkpoints"].usage == "/checkpoints"
    assert registry["restore"].usage == "/restore <checkpoint-id-or-label>"


def test_checkpoint_and_list_commands_record_replayable_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.chat_mode = "plan"
    runtime.pending_planned_task = "fix parser"
    runtime.history = ["fix one"]
    runtime.plan_items = [AgentPlanItem(text="inspect parser", status="completed")]
    runtime.feedback_items = ["prefer tests first"]
    runtime.last_run_payload = {
        "run_id": "run-1",
        "status": "completed",
        "final_diff_path": "artifacts/runs/run-1/final.diff",
    }
    runtime.last_apply = AgentApplyResult(
        status="checked",
        repo_path=str(tmp_path),
        diff_path="final.diff",
        message="clean",
        applied=False,
    )
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(checkpoint_commands())

    checkpoint_output = io.StringIO()
    registry["checkpoint"].handler(
        runtime=runtime,
        argument="stable",
        output_stream=checkpoint_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert checkpoint_output.getvalue().startswith("Checkpoint saved: ckpt-")
    assert checkpoint_output.getvalue().endswith("(stable)\n")
    assert events[-1][0] == "session_checkpoint"
    checkpoint = events[-1][1]
    assert checkpoint["label"] == "stable"
    assert checkpoint["history_count"] == 1
    assert checkpoint["last_run_id"] == "run-1"
    assert checkpoint["state"] == {
        "config": {
            "repo": str(tmp_path),
            "commit": None,
            "branch": None,
            "issue_url": None,
            "test_command": None,
            "context_provider": "native_hybrid",
            "context_paths": ["src/a.py#fix"],
            "top_k": 5,
            "artifacts_dir": str(tmp_path / "artifacts"),
            "sandbox_mode": "local",
            "sandbox_image": "python:3.12-slim",
            "apply": False,
            "allow_dirty_apply": False,
            "max_retries": 1,
            "deepagents_max_context_files": 0,
            "deepagents_subagents": "auto",
            "deepagents_model": "gpt-a",
            "max_model_responses": 2,
            "max_model_tokens": 100,
            "agent_profile": None,
            "agent_profile_path": None,
            "agent_profile_description": None,
            "agent_profile_instructions": None,
            "agent_profile_instruction_chars": 0,
            "load_agent_instructions": True,
            "instruction_paths": [],
            "agent_instruction_files": [],
            "agent_instructions": None,
            "agent_instruction_chars": 0,
        },
        "chat_mode": "plan",
        "pending_planned_task": "fix parser",
        "history": ["fix one"],
        "plan_items": [{"status": "completed", "text": "inspect parser"}],
        "feedback_items": ["prefer tests first"],
        "last_run_payload": {
            "run_id": "run-1",
            "status": "completed",
            "final_diff_path": "artifacts/runs/run-1/final.diff",
        },
        "last_apply": {
            "applied": False,
            "diff_path": "final.diff",
            "message": "clean",
            "repo_path": str(tmp_path),
            "status": "checked",
        },
        "last_rewind": None,
        "compaction_summary": None,
    }

    list_output = io.StringIO()
    registry["checkpoints"].handler(
        runtime=runtime,
        argument="",
        output_stream=list_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert "Checkpoints:\n" in list_output.getvalue()
    assert "stable" in list_output.getvalue()
    assert "run-1" in list_output.getvalue()
    assert events[-1] == ("session_checkpoint_list", {"count": 1})


def test_restore_command_restores_checkpoint_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.history = ["fix one"]
    runtime.plan_items = [AgentPlanItem(text="inspect parser")]
    runtime.feedback_items = ["prefer tests first"]
    runtime.last_run_payload = {"run_id": "run-1", "status": "completed"}
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(checkpoint_commands())

    registry["checkpoint"].handler(
        runtime=runtime,
        argument="stable",
        output_stream=io.StringIO(),
        context=ChatCommandContext(record=_record_to(events)),
    )

    runtime.state = dataclass_replace(
        runtime.state,
        config=dataclass_replace(
            runtime.state.config,
            context_paths=("src/b.py#extra",),
            deepagents_model="gpt-b",
        ),
    )
    runtime.history.append("fix two")
    runtime.plan_items = []
    runtime.feedback_items = []
    runtime.last_run_payload = {"run_id": "run-2", "status": "completed"}

    restore_output = io.StringIO()
    registry["restore"].handler(
        runtime=runtime,
        argument="stable",
        output_stream=restore_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert restore_output.getvalue().startswith("Restored checkpoint: ckpt-")
    assert restore_output.getvalue().endswith("(stable)\n")
    assert runtime.state.config.context_paths == ("src/a.py#fix",)
    assert runtime.state.config.deepagents_model == "gpt-a"
    assert runtime.history == ["fix one"]
    assert runtime.plan_items == [AgentPlanItem(text="inspect parser")]
    assert runtime.feedback_items == ["prefer tests first"]
    assert runtime.last_run_payload == {"run_id": "run-1", "status": "completed"}
    assert runtime.last_run is None
    assert events[-1][0] == "session_restore"
    assert events[-1][1]["label"] == "stable"
    assert events[-1][1]["state"] == events[0][1]["state"]


def test_restore_command_reports_invalid_inputs(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(checkpoint_commands())

    missing_selector_output = io.StringIO()
    registry["restore"].handler(
        runtime=runtime,
        argument="",
        output_stream=missing_selector_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert missing_selector_output.getvalue() == "Usage: /restore <checkpoint-id-or-label>\n"

    unknown_output = io.StringIO()
    registry["restore"].handler(
        runtime=runtime,
        argument="unknown",
        output_stream=unknown_output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert unknown_output.getvalue() == "Checkpoint not found: unknown\n"
    assert events == []


def _runtime(tmp_path: Path) -> AgentChatRuntime:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "test.jsonl"
    transcript_path.parent.mkdir(parents=True)
    return AgentChatRuntime(
        state=AgentChatState(
            session_id="test-session",
            transcript_path=transcript_path,
            config=AgentCliConfig(
                repo=str(tmp_path),
                artifacts_dir=str(artifacts),
                context_paths=("src/a.py#fix",),
                deepagents_model="gpt-a",
                max_model_responses=2,
                max_model_tokens=100,
            ),
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
        append_transcript_event(
            runtime.state.transcript_path,
            session_id=runtime.state.session_id,
            event=event,
            payload=payload,
        )

    return record
