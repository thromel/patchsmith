from __future__ import annotations

import io
from pathlib import Path

import pytest

import patchsmith.chat.hooks as chat_hooks
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


class FakeHookResult:
    def __init__(
        self,
        *,
        status: str,
        runs: list[dict[str, object]],
        block_reason: str | None = None,
    ) -> None:
        self.event = "PreRun"
        self.status = status
        self.runs = runs
        self.block_reason = block_reason

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    def to_dict(self) -> dict[str, object]:
        return {"event": self.event, "status": self.status, "runs": self.runs}


def test_run_chat_hooks_records_enriched_hook_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    output = io.StringIO()
    events: list[tuple[str, dict[str, object]]] = []
    captured: dict[str, object] = {}

    def fake_run_agent_hooks(
        *,
        repo: str,
        event: str,
        payload: dict[str, object],
    ) -> FakeHookResult:
        captured["repo"] = repo
        captured["event"] = event
        captured["payload"] = payload
        return FakeHookResult(
            status="passed",
            runs=[{"hook": {"name": "budget-guard"}, "status": "passed"}],
        )

    monkeypatch.setattr(chat_hooks, "run_agent_hooks", fake_run_agent_hooks)

    allowed = chat_hooks.run_chat_hooks(
        runtime=runtime,
        event="PreRun",
        payload={"task": "fix parser"},
        output_stream=output,
        blocking=True,
        record=lambda runtime, event, payload: events.append((event, payload)),
    )

    assert allowed is True
    assert output.getvalue() == ""
    assert captured["repo"] == str(tmp_path)
    assert captured["event"] == "PreRun"
    assert captured["payload"] == {
        "session_id": "session-1",
        "transcript_path": str(runtime.state.transcript_path),
        "task": "fix parser",
    }
    assert events == [
        (
            "hook_result",
            {
                "event": "PreRun",
                "status": "passed",
                "runs": [{"hook": {"name": "budget-guard"}, "status": "passed"}],
            },
        )
    ]


def test_run_chat_hooks_blocks_when_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    output = io.StringIO()
    events: list[tuple[str, dict[str, object]]] = []

    def fake_run_agent_hooks(
        *,
        repo: str,
        event: str,
        payload: dict[str, object],
    ) -> FakeHookResult:
        return FakeHookResult(
            status="blocked",
            runs=[{"hook": {"name": "budget-guard"}, "status": "blocked"}],
            block_reason="budget exhausted",
        )

    monkeypatch.setattr(chat_hooks, "run_agent_hooks", fake_run_agent_hooks)

    allowed = chat_hooks.run_chat_hooks(
        runtime=runtime,
        event="PreRun",
        payload={"task": "fix parser"},
        output_stream=output,
        blocking=True,
        record=lambda runtime, event, payload: events.append((event, payload)),
    )

    assert allowed is False
    assert output.getvalue() == "Hook blocked PreRun: budget exhausted\n"
    assert events == [
        (
            "hook_result",
            {
                "event": "PreRun",
                "status": "blocked",
                "runs": [{"hook": {"name": "budget-guard"}, "status": "blocked"}],
            },
        )
    ]


def _runtime(tmp_path: Path) -> AgentChatRuntime:
    return AgentChatRuntime(
        state=AgentChatState(
            session_id="session-1",
            transcript_path=tmp_path / "artifacts" / "chat_sessions" / "session.jsonl",
            config=AgentCliConfig(repo=str(tmp_path)),
        )
    )
