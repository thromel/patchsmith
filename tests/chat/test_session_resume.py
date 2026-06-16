from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem
from patchsmith.chat.session_payloads import config_payload
from patchsmith.chat.session_resume import runtime_from_transcript
from patchsmith.chat.state import AgentChatState
from patchsmith.session.store import append_transcript_event

pytestmark = pytest.mark.unit


def test_runtime_from_transcript_returns_none_for_missing_transcript(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    config = AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts))
    state = AgentChatState(
        session_id="missing-session",
        transcript_path=artifacts / "chat_sessions" / "missing-session.jsonl",
        config=config,
    )

    assert runtime_from_transcript(state=state, fallback_config=config) is None


def test_runtime_from_transcript_replays_session_state(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "resume-session.jsonl"
    config = AgentCliConfig(
        repo=str(tmp_path),
        artifacts_dir=str(artifacts),
        test_command="pytest -q",
        deepagents_model="gpt-start",
    )
    run_payload = {
        "run_id": "run-resume",
        "status": "completed",
        "final_diff_path": str(artifacts / "runs" / "run-resume" / "final.diff"),
        "model_total_tokens": 1200,
    }
    apply_result = AgentApplyResult(
        status="applied",
        repo_path=str(tmp_path),
        diff_path=run_payload["final_diff_path"],
        message="diff applied",
        applied=True,
    )
    rewind_result = AgentApplyResult(
        status="reverted",
        repo_path=str(tmp_path),
        diff_path=run_payload["final_diff_path"],
        message="diff reverted",
        applied=True,
    )

    _append(transcript_path, "session_start", {"config": config_payload(config)})
    _append(transcript_path, "context_update", {"context_paths": ["src/a.py#fix"]})
    _append(
        transcript_path,
        "config_update",
        {
            "field": "resource_budget",
            "max_model_responses": 6,
            "max_model_tokens": 90_000,
        },
    )
    _append(
        transcript_path,
        "config_update",
        {"field": "permissions", "apply": True, "allow_dirty_apply": True},
    )
    _append(transcript_path, "chat_mode_update", {"mode": "plan"})
    _append(transcript_path, "plan_mode_task", {"task": "draft patch"})
    _append(
        transcript_path,
        "plan_update",
        {
            "items": [
                {"text": "inspect parser", "status": "completed"},
                {"text": "write focused test", "status": "pending"},
            ]
        },
    )
    _append(
        transcript_path,
        "feedback_update",
        {"items": ["prefer tests first", "keep public API stable"]},
    )
    _append(transcript_path, "user_task", {"task": "fix parser"})
    _append(transcript_path, "run_result", run_payload)
    _append(transcript_path, "apply_result", apply_result.to_dict())
    _append(transcript_path, "rewind_result", rewind_result.to_dict())

    runtime = runtime_from_transcript(
        state=AgentChatState(
            session_id="resume-session",
            transcript_path=transcript_path,
            config=config,
        ),
        fallback_config=config,
    )

    assert runtime is not None
    assert runtime.state.config.context_paths == ("src/a.py#fix",)
    assert runtime.state.config.max_model_responses == 6
    assert runtime.state.config.max_model_tokens == 90_000
    assert runtime.state.config.apply is True
    assert runtime.state.config.allow_dirty_apply is True
    assert runtime.state.config.deepagents_model == "gpt-start"
    assert runtime.chat_mode == "plan"
    assert runtime.pending_planned_task is None
    assert runtime.history == ["fix parser"]
    assert runtime.plan_items == [
        AgentPlanItem(text="inspect parser", status="completed"),
        AgentPlanItem(text="write focused test"),
    ]
    assert runtime.feedback_items == ["prefer tests first", "keep public API stable"]
    assert runtime.last_run_payload == run_payload
    assert runtime.last_apply == apply_result
    assert runtime.last_rewind == rewind_result


def test_runtime_from_transcript_replays_clear_compact_and_restore(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "restore-session.jsonl"
    config = AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts))
    state = AgentChatState(
        session_id="restore-session",
        transcript_path=transcript_path,
        config=config,
    )
    pre_clear_apply = AgentApplyResult(
        status="applied",
        repo_path=str(tmp_path),
        diff_path=str(artifacts / "runs" / "run-1" / "final.diff"),
        message="diff applied",
        applied=True,
    )
    restored_config = AgentCliConfig(
        repo=str(tmp_path),
        artifacts_dir=str(artifacts),
        context_paths=("src/restored.py#bug",),
        deepagents_model="gpt-restored",
        max_model_responses=3,
        max_model_tokens=50_000,
    )
    restored_apply = AgentApplyResult(
        status="ready",
        repo_path=str(tmp_path),
        diff_path=str(artifacts / "runs" / "run-restored" / "final.diff"),
        message="diff can be applied",
    )
    restored_rewind = AgentApplyResult(
        status="reverted",
        repo_path=str(tmp_path),
        diff_path=str(artifacts / "runs" / "run-restored" / "final.diff"),
        message="diff reverted",
        applied=True,
    )

    _append(transcript_path, "session_start", {"config": config_payload(config)})
    _append(transcript_path, "user_task", {"task": "first task"})
    _append(transcript_path, "run_result", {"run_id": "run-1", "status": "completed"})
    _append(
        transcript_path,
        "plan_update",
        {"items": [{"text": "old plan", "status": "in_progress"}]},
    )
    _append(transcript_path, "feedback_update", {"item": "old feedback", "action": "add"})
    _append(transcript_path, "apply_result", pre_clear_apply.to_dict())
    _append(transcript_path, "session_compact", {"task_count": 1, "notes": "kept"})
    _append(transcript_path, "user_task", {"task": "second task"})
    _append(transcript_path, "run_result", {"run_id": "run-2", "status": "completed"})
    _append(transcript_path, "session_clear", {})

    cleared_runtime = runtime_from_transcript(state=state, fallback_config=config)

    assert cleared_runtime is not None
    assert cleared_runtime.history == []
    assert cleared_runtime.plan_items == []
    assert cleared_runtime.feedback_items == []
    assert cleared_runtime.last_run_payload is None
    assert cleared_runtime.last_apply is None
    assert cleared_runtime.last_rewind is None
    assert cleared_runtime.compaction_summary is None
    assert cleared_runtime.pending_planned_task is None

    restored_state = {
        "config": config_payload(restored_config),
        "chat_mode": "plan",
        "pending_planned_task": "restore pending task",
        "history": ["restored task"],
        "plan_items": [{"text": "restore plan", "status": "in_progress"}],
        "feedback_items": ["restore feedback"],
        "last_run_payload": {
            "run_id": "run-restored",
            "status": "completed",
            "final_diff_path": restored_apply.diff_path,
        },
        "last_apply": restored_apply.to_dict(),
        "last_rewind": restored_rewind.to_dict(),
        "compaction_summary": {"task_count": 2, "notes": "restored"},
    }
    _append(transcript_path, "session_restore", {"state": restored_state})

    restored_runtime = runtime_from_transcript(state=state, fallback_config=config)

    assert restored_runtime is not None
    assert restored_runtime.state.config.context_paths == ("src/restored.py#bug",)
    assert restored_runtime.state.config.deepagents_model == "gpt-restored"
    assert restored_runtime.state.config.max_model_responses == 3
    assert restored_runtime.state.config.max_model_tokens == 50_000
    assert restored_runtime.chat_mode == "plan"
    assert restored_runtime.pending_planned_task == "restore pending task"
    assert restored_runtime.history == ["restored task"]
    assert restored_runtime.plan_items == [AgentPlanItem(text="restore plan", status="in_progress")]
    assert restored_runtime.feedback_items == ["restore feedback"]
    assert restored_runtime.last_run_payload == restored_state["last_run_payload"]
    assert restored_runtime.last_apply == restored_apply
    assert restored_runtime.last_rewind == restored_rewind
    assert restored_runtime.compaction_summary == {"task_count": 2, "notes": "restored"}


def _append(
    transcript_path: Path,
    event: str,
    payload: dict[str, object],
) -> None:
    append_transcript_event(
        transcript_path,
        session_id=transcript_path.stem,
        event=event,
        payload=payload,
    )
