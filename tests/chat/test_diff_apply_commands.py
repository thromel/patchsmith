from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.diff_apply import diff_apply_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_diff_apply_commands_are_registered() -> None:
    registry = build_command_registry(diff_apply_commands())

    assert sorted(registry) == ["apply", "approve", "diff", "reject", "rewind", "undo"]
    assert registry["diff"].usage == "/diff [path|stat|show [1-300]|review]"
    assert registry["apply"].usage == "/apply [check]"
    assert registry["approve"].usage == "/approve apply <reason>"
    assert registry["reject"].usage == "/reject apply <reason>"
    assert registry["rewind"].usage == "/rewind"
    assert registry["undo"] is registry["rewind"]


def test_diff_command_records_path_stat_and_preview(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    runtime = _runtime(tmp_path, diff_path=diff_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(diff_apply_commands())["diff"]

    path_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=path_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert path_output.getvalue() == f"Diff: {diff_path}\n"
    assert events[-1] == ("diff_view", {"mode": "path", "diff_path": str(diff_path)})

    stat_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="stat",
        output_stream=stat_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "Diff summary:" in stat_output.getvalue()
    assert events[-1][0] == "diff_view"
    assert events[-1][1]["mode"] == "stat"

    preview_output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="show 3",
        output_stream=preview_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert "```diff" in preview_output.getvalue()
    assert events[-1][1]["mode"] == "show"
    assert events[-1][1]["max_lines"] == 3


def test_apply_check_uses_injected_checker_and_records_result(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    runtime = _runtime(tmp_path, diff_path=diff_path)
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(diff_apply_commands())["apply"]

    def check_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        assert repo == str(tmp_path)
        assert diff_path.name == "final.diff"
        assert allow_dirty is False
        return AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff can be applied to working tree",
        )

    output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="check",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            check_agent_run_diff=check_diff,
        ),
    )

    assert output.getvalue() == ("Apply check: ready - diff can be applied to working tree\n")
    assert events[-1][0] == "apply_check_result"
    assert events[-1][1]["status"] == "ready"


def test_apply_without_review_is_blocked_before_apply_function(
    tmp_path: Path,
) -> None:
    diff_path = _write_diff(tmp_path)
    runtime = _runtime(tmp_path, diff_path=diff_path)
    _append_transcript(runtime, "run_result", {"final_diff_path": str(diff_path)})
    events: list[tuple[str, dict[str, object]]] = []
    command = build_command_registry(diff_apply_commands())["apply"]

    def fail_apply(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        raise AssertionError("guarded apply should not call apply")

    output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            apply_agent_run_diff=fail_apply,
        ),
    )

    assert output.getvalue() == "Apply blocked: run /diff review before /apply.\n"
    assert events[-1][0] == "apply_blocked"
    assert events[-1][1]["reason_code"] == "missing_diff_review"


def test_approve_and_reject_record_decisions_after_review_and_check(
    tmp_path: Path,
) -> None:
    diff_path = _write_diff(tmp_path)
    runtime = _runtime(tmp_path, diff_path=diff_path)
    _append_transcript(runtime, "run_result", {"final_diff_path": str(diff_path)})
    _append_transcript(
        runtime,
        "diff_review",
        {
            "diff_path": str(diff_path),
            "risk_level": "high",
            "confirmation_required": True,
        },
    )
    _append_transcript(
        runtime,
        "apply_check_result",
        {"diff_path": str(diff_path), "status": "ready"},
    )
    events: list[tuple[str, dict[str, object]]] = []
    registry = build_command_registry(diff_apply_commands())

    approve_output = io.StringIO()
    registry["approve"].handler(
        runtime=runtime,
        argument="apply reviewed risky import move",
        output_stream=approve_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert approve_output.getvalue() == ("Apply approved: high - reviewed risky import move\n")
    assert events[-1][0] == "apply_approval"
    assert events[-1][1]["risk_level"] == "high"

    reject_output = io.StringIO()
    registry["reject"].handler(
        runtime=runtime,
        argument="apply too broad",
        output_stream=reject_output,
        context=ChatCommandContext(record=_record_to(events)),
    )
    assert reject_output.getvalue() == "Apply rejected: high - too broad\n"
    assert events[-1][0] == "apply_rejection"
    assert events[-1][1]["status"] == "rejected"


def test_rewind_uses_injected_reverse_and_hooks(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    runtime = _runtime(tmp_path, diff_path=diff_path)
    events: list[tuple[str, dict[str, object]]] = []
    hook_events: list[str] = []
    command = build_command_registry(diff_apply_commands())["rewind"]

    def run_hooks(
        *,
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
        output_stream: io.StringIO,
        blocking: bool,
    ) -> bool:
        hook_events.append(event)
        return True

    def reverse_diff(
        *,
        repo: str,
        diff_path: Path,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="reverted",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff reversed from working tree",
            applied=True,
        )

    output = io.StringIO()
    command.handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(
            record=_record_to(events),
            run_hooks=run_hooks,
            reverse_agent_run_diff=reverse_diff,
        ),
    )

    assert output.getvalue() == "Rewind: reverted - diff reversed from working tree\n"
    assert runtime.last_rewind is not None
    assert runtime.last_rewind.status == "reverted"
    assert events[-1][0] == "rewind_result"
    assert hook_events == ["PreRewind", "PostRewind"]


def _runtime(tmp_path: Path, *, diff_path: Path | None = None) -> AgentChatRuntime:
    artifacts = tmp_path / "artifacts"
    transcript_path = artifacts / "chat_sessions" / "test.jsonl"
    transcript_path.parent.mkdir(parents=True)
    last_run_payload = None
    if diff_path is not None:
        last_run_payload = {
            "run_id": "run-test",
            "status": "completed",
            "final_diff_path": str(diff_path),
        }
    return AgentChatRuntime(
        state=AgentChatState(
            session_id="test-session",
            transcript_path=transcript_path,
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        ),
        last_run_payload=last_run_payload,
    )


def _write_diff(tmp_path: Path) -> Path:
    diff_path = tmp_path / "artifacts" / "runs" / "run-test" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n",
        encoding="utf-8",
    )
    return diff_path


def _append_transcript(
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
) -> None:
    row = {
        "timestamp": "2026-06-15T00:00:00+00:00",
        "session_id": runtime.state.session_id,
        "event": event,
        "payload": payload,
    }
    with runtime.state.transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


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
