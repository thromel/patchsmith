from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.chat.task_runner import run_chat_task
from patchsmith.model_preflight import ModelPreflightResult

pytestmark = pytest.mark.unit


def test_run_chat_task_records_run_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    runtime = _runtime(tmp_path)
    runtime.plan_items = [AgentPlanItem(text="inspect parser", status="completed")]
    runtime.feedback_items = ["prefer narrow patches"]
    events: list[tuple[str, dict[str, object]]] = []
    hooks: list[tuple[str, bool, dict[str, object]]] = []
    requests: list[object] = []

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == tmp_path / "artifacts"

        def run(self, request):
            requests.append(request)
            run_dir = tmp_path / "artifacts" / "runs" / "run-task"
            run_dir.mkdir(parents=True)
            final_diff_path = run_dir / "final.diff"
            final_diff_path.write_text("diff --git a/src/a.py b/src/a.py\n", encoding="utf-8")
            trace_path = run_dir / "trace.jsonl"
            trace_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-task",
                status="completed",
                report_path=run_dir / "report.md",
                trace_path=trace_path,
                final_diff_path=final_diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 123,
                    "estimated_cost_usd": 0.01,
                },
            )

    output = io.StringIO()
    run_chat_task(
        runtime=runtime,
        task="fix parser",
        output_stream=output,
        runner_cls=FakeRepairRunner,
        model_preflight_checker=None,
        record=_record_to(events),
        run_hooks=_hook_to(hooks),
    )

    assert runtime.history == ["fix parser"]
    assert runtime.last_run_payload is not None
    assert runtime.last_run_payload["run_id"] == "run-task"
    assert runtime.last_run_payload["model_response_count"] == 2
    assert [event for event, _payload in events] == [
        "user_task",
        "run_preflight",
        "run_result",
    ]
    assert [event for event, _blocking, _payload in hooks] == [
        "UserPromptSubmit",
        "PreRun",
        "PostRun",
    ]
    request = requests[0]
    assert "PatchSmith session plan" in request.issue_text
    assert "1. [completed] inspect parser" in request.issue_text
    assert "PatchSmith session feedback" in request.issue_text
    assert "1. prefer narrow patches" in request.issue_text
    assert "Task:\nfix parser" in request.issue_text
    assert output.getvalue() == (
        "Run preflight: passed\n"
        "Running PatchSmith agent...\n"
        "Run ID: run-task\n"
        "Status: completed\n"
        f"Report: {tmp_path / 'artifacts' / 'runs' / 'run-task' / 'report.md'}\n"
        f"Trace: {tmp_path / 'artifacts' / 'runs' / 'run-task' / 'trace.jsonl'}\n"
        f"Diff: {tmp_path / 'artifacts' / 'runs' / 'run-task' / 'final.diff'}\n"
        "Test exit code: 0\n"
    )


def test_run_chat_task_stops_when_model_preflight_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    hooks: list[tuple[str, bool, dict[str, object]]] = []

    class FailingRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("model preflight should block before runner")

    def unavailable_model(config: AgentCliConfig) -> ModelPreflightResult:
        return ModelPreflightResult(
            provider="openai_models",
            model=config.deepagents_model or "gpt-test",
            endpoint="https://api.openai.com/v1/models",
            status="missing",
            available=False,
            suggestions=["gpt-a"],
            error="model missing",
        )

    output = io.StringIO()
    run_chat_task(
        runtime=runtime,
        task="fix parser",
        output_stream=output,
        runner_cls=FailingRepairRunner,
        model_preflight_checker=unavailable_model,
        record=_record_to(events),
        run_hooks=_hook_to(hooks),
    )

    assert runtime.last_run_payload is None
    assert [event for event, _payload in events] == [
        "user_task",
        "run_preflight",
        "model_preflight",
    ]
    assert output.getvalue().endswith(
        "Model preflight: missing (gpt-test)\n"
        "Model suggestions: gpt-a\n"
        "Model preflight blocked: model missing\n"
    )


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
):
    def record(
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
    ) -> None:
        events.append((event, payload))

    return record


def _hook_to(
    hooks: list[tuple[str, bool, dict[str, object]]],
):
    def run_hooks(
        *,
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
        output_stream: TextIO,
        blocking: bool,
    ) -> bool:
        hooks.append((event, blocking, payload))
        return True

    return run_hooks
