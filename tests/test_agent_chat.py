from __future__ import annotations

import io
import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_chat import run_chat_session
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_session import (
    AgentSessionGateConfig,
    evaluate_session_gate,
    session_metrics,
)
from patchsmith.model_preflight import ModelPreflightResult

pytestmark = pytest.mark.unit


def test_chat_session_runs_preflight_task_apply_and_writes_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-chat" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text(_low_risk_diff_text(), encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            captured["artifacts_dir"] = artifacts_dir

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id="run-chat",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 300,
                    "estimated_cost_usd": 0.001,
                },
                retrieved_context=[],
            )

    def fake_apply_agent_run_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="applied",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff applied to working tree",
            applied=True,
        )

    def fake_check_agent_run_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff can be applied to working tree",
            applied=False,
        )

    import patchsmith.agent_cli as agent_cli
    import patchsmith.chat.controller as chat_controller

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        chat_controller,
        "apply_agent_run_diff",
        fake_apply_agent_run_diff,
    )
    monkeypatch.setattr(
        chat_controller,
        "check_agent_run_diff",
        fake_check_agent_run_diff,
    )
    monkeypatch.setattr(agent_cli, "apply_agent_run_diff", fake_apply_agent_run_diff)
    monkeypatch.setattr(
        agent_cli,
        "preflight_agent_apply_target",
        lambda *, repo, allow_dirty=False: AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path="<pending>",
            message="ready",
            applied=False,
        ),
    )

    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            test_command="pytest -q",
            artifacts_dir=str(artifacts),
            deepagents_max_context_files=2,
        ),
        input_stream=io.StringIO(
            "/preflight fix parser\n"
            "/context add src/simple_calc.py#add\n"
            "/context show\n"
            "/run fix parser\n"
            "/context remove src/simple_calc.py#add\n"
            "/context clear\n"
            "/status\n"
            "/diff review\n"
            "/apply check\n"
            "/apply\n"
            "/history\n"
            "/exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="test-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "PatchSmith Chat" in text
    assert "Preflight: passed" in text
    assert "Added context: src/simple_calc.py#add" in text
    assert "Forced context hints:" in text
    assert "Removed context: src/simple_calc.py#add" in text
    assert "Context hints cleared." in text
    assert "Run preflight: passed" in text
    assert "Run ID: run-chat" in text
    assert "Apply check: ready - diff can be applied to working tree" in text
    assert "Apply: applied" in text
    assert "1. fix parser" in text
    assert captured["artifacts_dir"] == artifacts
    request = captured["request"]
    assert request.issue_text == "fix parser"
    assert request.context_paths == ("src/simple_calc.py#add",)
    assert request.runtime == "deepagents"
    assert request.planner == "deepagents"
    assert request.runtime_config == {
        "subagent_mode": "auto",
        "max_context_files": 2,
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
        },
    }

    transcript_path = artifacts / "chat_sessions" / "test-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == [
        "session_start",
        "user_command",
        "preflight",
        "user_command",
        "context_update",
        "user_command",
        "user_command",
        "user_task",
        "run_preflight",
        "run_result",
        "user_command",
        "context_update",
        "user_command",
        "context_update",
        "user_command",
        "user_command",
        "diff_review",
        "user_command",
        "apply_check_result",
        "user_command",
        "apply_result",
        "user_command",
        "user_command",
        "session_end",
    ]
    run_result = next(row for row in rows if row["event"] == "run_result")
    assert run_result["payload"]["model_response_count"] == 2
    assert run_result["payload"]["model_total_tokens"] == 300
    assert run_result["payload"]["estimated_cost_usd"] == 0.001


def test_chat_session_treats_plain_text_as_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-plain" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            return SimpleNamespace(
                run_id="run-plain",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=None,
                retrieved_context=[],
            )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()

    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO("fix parser\n/exit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="plain-session",
    )

    assert exit_code == 0
    assert "Run ID: run-plain" in output.getvalue()


def test_chat_session_model_preflight_blocks_before_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("runner must not start after failed model preflight")

    def failed_model_preflight(config: AgentCliConfig) -> ModelPreflightResult:
        assert config.deepagents_model == "gpt-5.4-mini"
        return ModelPreflightResult(
            provider="openai_models",
            model="gpt-5.4-mini",
            endpoint="https://api.openai.com/v1/models",
            status="http_error",
            available=False,
            error="OpenAI Models API error 401: invalid or unauthorized API key.",
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()

    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            artifacts_dir=str(artifacts),
            deepagents_model="gpt-5.4-mini",
        ),
        input_stream=io.StringIO("fix parser\n/exit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        model_preflight_checker=failed_model_preflight,
        session_id="model-preflight-blocked-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Run preflight: passed" in text
    assert "Model preflight: http_error (gpt-5.4-mini)" in text
    assert "Model preflight blocked: OpenAI Models API error 401" in text
    assert "Running PatchSmith agent..." not in text
    transcript_path = artifacts / "chat_sessions" / "model-preflight-blocked-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    model_preflight = next(row for row in rows if row["event"] == "model_preflight")
    assert model_preflight["payload"]["status"] == "http_error"
    assert model_preflight["payload"]["available"] is False
    assert [row["event"] for row in rows].count("run_result") == 0


def test_chat_session_routes_obvious_natural_commands_without_running_agent(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("natural control phrases must not start a run")

    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO(
            "what next?\n"
            "show status\n"
            "show metrics\n"
            "show cost\n"
            "show evidence\n"
            "review diff\n"
            "apply check\n"
            "exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="natural-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Run a bounded preflight, then start the first repair run." in text
    assert "Session: natural-session" in text
    assert "Session metrics:" in text
    assert "Session usage:" in text
    assert "No run evidence is available." in text
    assert "No run is available." in text
    assert "No run is available to apply." in text
    transcript_path = artifacts / "chat_sessions" / "natural-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    routed = [row["payload"]["routed_command"] for row in rows if row["event"] == "natural_command"]
    assert routed == [
        "/next",
        "/status",
        "/metrics",
        "/cost",
        "/evidence",
        "/diff review",
        "/apply check",
        "/exit",
    ]


def test_chat_session_plan_mode_preflights_plain_text_until_approved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-after-plan" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")
    requests = []

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            requests.append(request)
            return SimpleNamespace(
                run_id="run-after-plan",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            test_command="pytest -q",
            artifacts_dir=str(artifacts),
        ),
        input_stream=io.StringIO("plan mode\nfix parser\nshow status\ngo ahead\nexit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="plan-mode-session",
    )

    assert exit_code == 0
    assert len(requests) == 1
    assert requests[0].issue_text == "fix parser"
    text = output.getvalue()
    assert "Chat mode: plan. Plain text runs /preflight" in text
    assert "Plan mode: running preflight only. Say 'go ahead' or use /run to execute." in text
    assert "Preflight: passed" in text
    assert "Chat mode: plan" in text
    assert "Pending planned task: fix parser" in text
    assert "Approved planned task: fix parser" in text
    assert "Run ID: run-after-plan" in text
    transcript_path = artifacts / "chat_sessions" / "plan-mode-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    mode_updates = [row["payload"]["mode"] for row in rows if row["event"] == "chat_mode_update"]
    assert mode_updates == ["plan"]
    assert [row["event"] for row in rows].count("plan_mode_task") == 1
    assert [row["event"] for row in rows].count("plan_mode_approval") == 1
    assert [row["event"] for row in rows].count("preflight") == 1
    assert [row["event"] for row in rows].count("run_result") == 1


def test_chat_session_cancel_plan_mode_task_prevents_later_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("cancelled plan-mode task must not run")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            test_command="pytest -q",
            artifacts_dir=str(artifacts),
        ),
        input_stream=io.StringIO("plan mode\nfix parser\ncancel plan\ngo ahead\nexit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="plan-cancel-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Pending planned task: fix parser" in text
    assert "Cancelled planned task: fix parser" in text
    assert "No pending planned task. Usage: /run <task>" in text
    transcript_path = artifacts / "chat_sessions" / "plan-cancel-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows].count("plan_mode_task") == 1
    assert [row["event"] for row in rows].count("plan_mode_cancel") == 1
    assert [row["event"] for row in rows].count("plan_mode_approval") == 0
    assert [row["event"] for row in rows].count("run_result") == 0


def test_chat_session_next_recommends_pending_plan_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("pending plan-mode task must not run")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            test_command="pytest -q",
            artifacts_dir=str(artifacts),
        ),
        input_stream=io.StringIO("plan mode\nfix parser\nwhat next\nexit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="plan-next-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Approve or cancel the pending planned task." in text
    assert "- Commands: /run, /cancel plan, /mode act" in text
    assert "- Evidence: pending_task=fix parser, plan_mode=pending" in text
    transcript_path = artifacts / "chat_sessions" / "plan-next-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert next_event["payload"]["action"] == ("Approve or cancel the pending planned task.")
    assert next_event["payload"]["commands"] == [
        "/run",
        "/cancel plan",
        "/mode act",
    ]
    assert [row["event"] for row in rows].count("plan_mode_approval") == 0
    assert [row["event"] for row in rows].count("run_result") == 0


def test_chat_session_next_blocks_pending_plan_when_preflight_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("blocked plan-mode task must not run")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(
            repo=str(tmp_path),
            test_command="pytest -q",
            artifacts_dir=str(artifacts),
        ),
        input_stream=io.StringIO("plan mode\nfix parser\n/next\nexit\n"),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="plan-next-blocked-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Fix readiness or cancel the pending planned task." in text
    assert "- Commands: /doctor, /preflight fix parser, /cancel plan" in text
    assert "- Evidence: pending_task=fix parser, latest_preflight=blocked" in text
    transcript_path = artifacts / "chat_sessions" / "plan-next-blocked-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert next_event["payload"]["action"] == ("Fix readiness or cancel the pending planned task.")
    assert next_event["payload"]["commands"] == [
        "/doctor",
        "/preflight fix parser",
        "/cancel plan",
    ]
    assert [row["event"] for row in rows].count("run_result") == 0


def test_chat_session_updates_model_and_budget_before_run(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-budget" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            captured["artifacts_dir"] = artifacts_dir

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id="run-budget",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=None,
                retrieved_context=[],
            )

    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO(
            "/model gpt-5-mini\n/budget set 6 90000\n/status\n/run fix parser\n/exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="config-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Model override: gpt-5-mini" in text
    assert "Budget: responses=6, tokens=90000" in text
    request = captured["request"]
    assert request.runtime_config == {
        "subagent_mode": "auto",
        "model": "gpt-5-mini",
        "resource_budget": {
            "max_model_responses": 6,
            "max_model_tokens": 90000,
        },
    }
    transcript_path = artifacts / "chat_sessions" / "config-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    config_updates = [row for row in rows if row["event"] == "config_update"]
    assert config_updates == [
        {
            "event": "config_update",
            "payload": {"field": "deepagents_model", "value": "gpt-5-mini"},
            "session_id": "config-session",
            "timestamp": config_updates[0]["timestamp"],
        },
        {
            "event": "config_update",
            "payload": {
                "field": "resource_budget",
                "max_model_responses": 6,
                "max_model_tokens": 90000,
            },
            "session_id": "config-session",
            "timestamp": config_updates[1]["timestamp"],
        },
    ]


def test_chat_session_updates_permissions_and_resumes_them(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    first_output = io.StringIO()

    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/permissions\n"
                "/permissions dirty allow\n"
                "/permissions apply auto\n"
                "/permissions dirty allow\n"
                "/exit\n"
            ),
            output_stream=first_output,
            session_id="permission-session",
        )
        == 0
    )

    first_text = first_output.getvalue()
    assert "Apply after run: manual" in first_text
    assert "Dirty apply: denied" in first_text
    assert "Enable auto apply before allowing dirty apply" in first_text
    assert "Apply after run: auto" in first_text
    assert "Dirty apply: allowed" in first_text

    resumed_output = io.StringIO()
    report_path = artifacts / "exports" / "permission-session.md"
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(f"/status\n/permissions\n/export {report_path}\n/exit\n"),
            output_stream=resumed_output,
            session_id="permission-session",
            resume=True,
        )
        == 0
    )

    resumed_text = resumed_output.getvalue()
    assert "PatchSmith Chat (resumed)" in resumed_text
    assert "Apply by default: true" in resumed_text
    assert "Dirty apply allowed: true" in resumed_text
    assert "Apply after run: auto" in resumed_text
    assert "Dirty apply: allowed" in resumed_text

    transcript_path = artifacts / "chat_sessions" / "permission-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    permission_view = next(row for row in rows if row["event"] == "permission_view")
    assert permission_view["payload"]["apply_after_run"] is False
    permission_updates = [
        row["payload"]
        for row in rows
        if row["event"] == "config_update" and row["payload"].get("field") == "permissions"
    ]
    assert permission_updates == [
        {"field": "permissions", "apply": True, "allow_dirty_apply": False},
        {"field": "permissions", "apply": True, "allow_dirty_apply": True},
    ]
    report = report_path.read_text(encoding="utf-8")
    assert "- Apply after run: `True`" in report
    assert "- Dirty apply allowed: `True`" in report


def test_chat_session_doctor_and_cost_report_transcript_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-usage" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            return SimpleNamespace(
                run_id="run-usage",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 2,
                    "response_count": 4,
                    "total_tokens": 500,
                    "estimated_cost_usd": 0.012345,
                },
                retrieved_context=[],
            )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    report_path = artifacts / "exports" / "usage-session.md"
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO(
            f"/doctor\n/run fix parser\n/cost\n/export {report_path}\n/exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="usage-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Doctor: passed" in text
    assert "- deepagents_dependency: passed" in text
    assert "- openai_api_key: passed" in text
    assert "Session usage:" in text
    assert "Tasks: 1" in text
    assert "Runs: 1" in text
    assert "Validated runs: 1" in text
    assert "Model calls: 2" in text
    assert "Model responses: 4" in text
    assert "Model tokens: 500" in text
    assert "Estimated cost: $0.012345" in text
    assert f"Exported session report: {report_path}" in text
    report = report_path.read_text(encoding="utf-8")
    assert "# PatchSmith Chat Session" in report
    assert "- Session: `usage-session`" in report
    assert "- Tasks: `1`" in report
    assert "- Runs: `1`" in report
    assert "- Validated runs: `1`" in report
    assert "- Model responses: `4`" in report
    assert "- Estimated cost: `$0.012345`" in report
    assert "1. fix parser" in report
    assert "`run-usage`" in report
    transcript_path = artifacts / "chat_sessions" / "usage-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["event"] == "doctor" for row in rows)
    assert any(row["event"] == "session_export" for row in rows)
    usage = next(row for row in rows if row["event"] == "session_usage")
    assert usage["payload"] == {
        "estimated_cost_usd": 0.012345,
        "model_call_count": 2,
        "model_response_count": 4,
        "model_total_tokens": 500,
        "run_count": 1,
        "run_error_count": 0,
        "task_count": 1,
        "validated_run_count": 1,
    }


def test_chat_session_verify_runs_policy_checked_test_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text(
        "def test_smoke():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent))

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(
                repo=str(tmp_path),
                artifacts_dir=str(artifacts),
                test_command="python -m pytest tests/test_smoke.py -q",
            ),
            input_stream=io.StringIO("/verify\n/metrics\n/timeline 8\n/exit\n"),
            output_stream=output,
            session_id="verify-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Verify: passed" in text
    assert "Command: python -m pytest tests/test_smoke.py -q" in text
    assert "Exit code: 0" in text
    assert "- Verify runs: 1" in text
    assert "- Passed verify runs: 1" in text
    assert (
        "verify_result | status=passed exit=0 command=python -m pytest tests/test_smoke.py -q"
        in text
    )

    transcript_path = artifacts / "chat_sessions" / "verify-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    verify = next(row for row in rows if row["event"] == "verify_result")
    assert verify["payload"]["status"] == "passed"
    assert verify["payload"]["result"]["exit_code"] == 0
    assert verify["payload"]["result"]["policy_decision"]["allowed"] is True
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["verify_count"] == 1
    assert metrics["payload"]["verify_passed_count"] == 1


def test_chat_session_verify_blocks_unallowlisted_command(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/verify python -c 'print(1)'\n/metrics\n/exit\n"),
            output_stream=output,
            session_id="verify-block-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Verify: blocked" in text
    assert "Policy: blocked - command is not allowlisted: python" in text
    assert "- Verify runs: 1" in text
    assert "- Passed verify runs: 0" in text

    transcript_path = artifacts / "chat_sessions" / "verify-block-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    verify = next(row for row in rows if row["event"] == "verify_result")
    assert verify["payload"]["status"] == "blocked"
    assert verify["payload"]["result"]["policy_decision"]["allowed"] is False


def test_chat_session_metrics_report_process_rates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deepagents_dependency_available: None,
) -> None:
    artifacts = tmp_path / "artifacts"
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "review.md").write_text(
        "Review this target: $ARGUMENTS\n",
        encoding="utf-8",
    )
    diff_path = artifacts / "runs" / "run-metrics" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text(_low_risk_diff_text(), encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-metrics",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 400,
                    "estimated_cost_usd": 0.004,
                },
                retrieved_context=[],
            )

    def fake_apply_agent_run_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="applied",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff applied",
            applied=True,
        )

    def fake_check_agent_run_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff can be applied to working tree",
            applied=False,
        )

    import patchsmith.agent_cli as agent_cli
    import patchsmith.chat.controller as chat_controller

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        chat_controller,
        "apply_agent_run_diff",
        fake_apply_agent_run_diff,
    )
    monkeypatch.setattr(
        chat_controller,
        "check_agent_run_diff",
        fake_check_agent_run_diff,
    )
    monkeypatch.setattr(agent_cli, "apply_agent_run_diff", fake_apply_agent_run_diff)
    monkeypatch.setattr(
        agent_cli,
        "preflight_agent_apply_target",
        lambda *, repo, allow_dirty=False: AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path="<pending>",
            message="ready",
            applied=False,
        ),
    )

    output = io.StringIO()
    report_path = artifacts / "exports" / "metrics-session.md"
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO(
            "/preflight fix metrics\n"
            "/context add src/a.py#target\n"
            "/permissions apply auto\n"
            "/model gpt-test\n"
            "/budget set 3 50000\n"
            "/review parser behavior\n"
            "/diff review\n"
            "/apply check\n"
            "/apply\n"
            f"/metrics\n/export {report_path}\n"
            "/exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="metrics-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Session metrics:" in text
    assert "- Preflights: 1" in text
    assert "- Passed preflights: 1" in text
    assert "- Run preflights: 1" in text
    assert "- Passed run preflights: 1" in text
    assert "- Runs: 1" in text
    assert "- Validated runs: 1" in text
    assert "- Validation rate: 100.00%" in text
    assert "- Preflight-to-run rate: 100.00%" in text
    assert "Auto apply deferred: run /diff review, /apply check, then /apply." in text
    assert "- Apply attempts: 1" in text
    assert "- Applied diffs: 1" in text
    assert "- Apply success rate: 100.00%" in text
    assert "- Deferred auto applies: 1" in text
    assert "- Custom commands: 1" in text
    assert "- Context updates: 1" in text
    assert "- Permission updates: 1" in text
    assert "- Model updates: 1" in text
    assert "- Budget updates: 1" in text
    assert "- Cost per validated run: $0.004000" in text

    transcript_path = artifacts / "chat_sessions" / "metrics-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    deferred = next(row for row in rows if row["event"] == "apply_auto_deferred")
    assert deferred["payload"]["reason_code"] == "interactive_apply_requires_review"
    assert deferred["payload"]["run_id"] == "run-metrics"
    assert metrics_event["payload"]["run_preflight_count"] == 1
    assert metrics_event["payload"]["run_preflight_passed_count"] == 1
    assert metrics_event["payload"]["apply_auto_deferred_count"] == 1
    assert metrics_event["payload"]["validation_rate"] == 1.0
    assert metrics_event["payload"]["preflight_to_run_rate"] == 1.0
    assert metrics_event["payload"]["apply_success_rate"] == 1.0
    assert metrics_event["payload"]["cost_per_validated_run_usd"] == 0.004

    report = report_path.read_text(encoding="utf-8")
    assert "## Process Metrics" in report
    assert "- Run preflights: `1`" in report
    assert "- Deferred auto applies: `1`" in report
    assert "- Validation rate: `100.00%`" in report
    assert "- Cost per validated run: `$0.004000`" in report


def test_chat_session_trace_summarizes_last_run_artifacts(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-trace"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1 +1 @@\n"
        "-old_value = 1\n"
        "+new_value = 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node": "retrieve", "status": "completed"})
        + "\n"
        + json.dumps({"node_name": "plan", "status": "completed"})
        + "\n"
        + json.dumps({"event_type": "sandbox", "status": "failed"})
        + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n\nvalidated\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-trace",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 123,
                    "estimated_cost_usd": 0.001,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/run fix trace\n/trace\n/metrics\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="trace-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Run evidence: run-trace" in text
    assert "- Trace events: 3" in text
    assert "- Trace statuses: completed=2, failed=1" in text
    assert "- Trace nodes: plan=1, retrieve=1, sandbox=1" in text
    assert "- Failed trace events: 1" in text
    assert "- Diff files: 1" in text
    assert "- Diff lines: +1 / -1" in text
    assert "- Changed files: src/app.py" in text
    assert "- Model responses: 2" in text
    assert "- Model tokens: 123" in text
    assert "- Estimated cost: $0.001000" in text
    assert "- Run evidence views: 1" in text

    resumed_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/evidence\n/exit\n"),
            output_stream=resumed_output,
            runner_cls=FakeRepairRunner,
            session_id="trace-session",
            resume=True,
        )
        == 0
    )
    assert "PatchSmith Chat (resumed)" in resumed_output.getvalue()
    assert "Run evidence: run-trace" in resumed_output.getvalue()

    transcript_path = artifacts / "chat_sessions" / "trace-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    evidence_events = [row for row in rows if row["event"] == "run_evidence"]
    assert len(evidence_events) == 2
    assert evidence_events[0]["payload"]["trace_event_count"] == 3
    assert evidence_events[0]["payload"]["trace_status_counts"] == {
        "completed": 2,
        "failed": 1,
    }
    assert evidence_events[0]["payload"]["diff_changed_files"] == ["src/app.py"]


def test_chat_session_diff_stat_and_preview_are_transcripted(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-diff" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-old = 1\n"
        "+new = 2\n"
        " keep = True\n"
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n"
        "+++ b/tests/test_app.py\n"
        "@@ -1 +1 @@\n"
        "-assert old\n"
        "+assert new\n",
        encoding="utf-8",
    )

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-diff",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 80,
                    "estimated_cost_usd": 0.004,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run fix diff\n/diff\n/diff stat\n/diff show 6\n/timeline 12\n/metrics\n/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="diff-session",
        )
        == 0
    )

    text = output.getvalue()
    assert f"Diff: {diff_path}" in text
    assert "Diff summary:" in text
    assert "- Files: 2" in text
    assert "- Lines: +2 / -2" in text
    assert "- Changed files: src/app.py, tests/test_app.py" in text
    assert "```diff" in text
    assert "+new = 2" in text
    assert "... truncated 7 line(s)" in text
    assert "diff_view | mode=show files=2 lines=+2/-2 shown=6/13" in text
    assert "- Diff views: 3" in text

    transcript_path = artifacts / "chat_sessions" / "diff-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    diff_events = [row for row in rows if row["event"] == "diff_view"]
    assert [row["payload"]["mode"] for row in diff_events] == ["path", "stat", "show"]
    assert diff_events[-1]["payload"]["changed_files"] == [
        "src/app.py",
        "tests/test_app.py",
    ]
    assert diff_events[-1]["payload"]["truncated"] is True
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["diff_view_count"] == 3


def test_chat_session_timeline_summarizes_recent_events(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-timeline"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1 +1 @@\n"
        "-old = 1\n"
        "+new = 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-timeline",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 60,
                    "estimated_cost_usd": 0.002,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/preflight fix parser\n"
                "/feedback stable API only\n"
                "/run fix parser\n"
                "/gate clean\n"
                "/trace\n"
                "/timeline 12\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="timeline-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Session timeline:" in text
    assert "Time | Event | Summary" in text
    assert "preflight | status=" in text
    assert "feedback_update | action=add item=stable API only count=1" in text
    assert "user_task | fix parser" in text
    assert "run_preflight | status=" in text
    assert "run_result | run=run-timeline status=completed test=0 cost=$0.002000" in text
    assert "session_gate | profile=clean status=passed" in text
    assert "run_evidence | run=run-timeline trace_events=1 diff_files=1" in text
    assert "user_command | /timeline 12" in text
    assert "- Timeline views: 1" in text

    transcript_path = artifacts / "chat_sessions" / "timeline-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    timeline = next(row for row in rows if row["event"] == "session_timeline")
    assert timeline["payload"]["limit"] == 12
    assert timeline["payload"]["entry_count"] == 12
    assert any(
        entry["event"] == "run_result" and "run=run-timeline" in entry["summary"]
        for entry in timeline["payload"]["entries"]
    )
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["timeline_view_count"] == 1


def test_chat_session_next_recommends_evidence_backed_actions(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-next"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1 +1 @@\n"
        "-old = 1\n"
        "+new = 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-next",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 70,
                    "estimated_cost_usd": 0.003,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/next\n"
                "/run fix parser\n"
                "/next\n"
                "/trace\n"
                "/next\n"
                "/gate clean\n"
                "/next\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="next-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Next recommendation:" in text
    assert "Run a bounded preflight, then start the first repair run." in text
    assert "Inspect the latest validated run artifacts." in text
    assert "Gate the latest validated run before promotion." in text
    assert "Review the generated diff before applying it." in text
    assert "- Next recommendations: 4" in text

    transcript_path = artifacts / "chat_sessions" / "next-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    next_events = [row for row in rows if row["event"] == "session_next"]
    assert [row["payload"]["action"] for row in next_events] == [
        "Run a bounded preflight, then start the first repair run.",
        "Inspect the latest validated run artifacts.",
        "Gate the latest validated run before promotion.",
        "Review the generated diff before applying it.",
    ]
    assert next_events[-1]["payload"]["commands"] == [
        "/diff stat",
        "/diff show",
    ]
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["next_view_count"] == 4


def test_chat_session_next_breaks_repeated_failure_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"
    attempts = 0

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            nonlocal attempts
            attempts += 1
            run_id = f"run-stuck-{attempts}"
            run_dir = artifacts / "runs" / run_id
            run_dir.mkdir(parents=True)
            diff_path = run_dir / "final.diff"
            trace_path = run_dir / "traces.jsonl"
            report_path = run_dir / "report.md"
            diff_path.write_text("", encoding="utf-8")
            trace_path.write_text(
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "payload": {
                            "status": "unresolved",
                            "verdict": "no_patch_tests_failed",
                            "failure_category": "no_patch_generated",
                            "patch_generated": False,
                            "tests_passed": False,
                            "next_action": "Improve planning before rerunning.",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            report_path.write_text("# Report\n", encoding="utf-8")
            return SimpleNamespace(
                run_id=run_id,
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=1),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 21056,
                    "estimated_cost_usd": 0.01,
                },
                retrieved_context=[
                    SimpleNamespace(path="calc.py"),
                    SimpleNamespace(path="test_calc.py"),
                ],
            )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/run fix parser\n/trace\n/run fix parser\n/next\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="stuck-next-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Break the repeated failure loop before another run." in text
    assert "failure=no_patch_generated" in text
    assert "repeat_count=2" in text
    transcript_path = artifacts / "chat_sessions" / "stuck-next-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    run_results = [row for row in rows if row["event"] == "run_result"]
    assert [row["payload"]["repair_failure_category"] for row in run_results] == [
        "no_patch_generated",
        "no_patch_generated",
    ]
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert next_event["payload"]["action"] == (
        "Break the repeated failure loop before another run."
    )
    assert next_event["payload"]["commands"] == [
        "/trace",
        "/feedback add <what changed after reviewing the failure>",
        "/context add <path[#symbol]>",
    ]


def test_chat_session_next_flags_budget_exhausted_no_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            run_dir = artifacts / "runs" / "run-budget-exhausted"
            run_dir.mkdir(parents=True)
            diff_path = run_dir / "final.diff"
            trace_path = run_dir / "traces.jsonl"
            report_path = run_dir / "report.md"
            diff_path.write_text("", encoding="utf-8")
            trace_path.write_text(
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "payload": {
                            "status": "unresolved",
                            "verdict": "no_patch_tests_failed",
                            "failure_category": "no_patch_generated",
                            "patch_generated": False,
                            "tests_passed": False,
                            "next_action": "Improve planning before rerunning.",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            report_path.write_text("# Report\n", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-budget-exhausted",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=1),
                model_usage={
                    "call_count": 1,
                    "response_count": 6,
                    "total_tokens": 90000,
                    "estimated_cost_usd": 0.01,
                },
                retrieved_context=[SimpleNamespace(path="pricing.py")],
            )

    def passed_model_preflight(config: AgentCliConfig) -> ModelPreflightResult:
        return ModelPreflightResult(
            provider="openai_models",
            model=config.deepagents_model or "gpt-test",
            endpoint="https://api.openai.com/v1/models",
            status="available",
            available=True,
            available_model_count=3,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(
                repo=str(tmp_path),
                artifacts_dir=str(artifacts),
                deepagents_model="gpt-test",
                max_model_responses=6,
                max_model_tokens=120000,
            ),
            input_stream=io.StringIO("/run fix checkout total\n/next\n/metrics\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            model_preflight_checker=passed_model_preflight,
            session_id="budget-exhausted-next-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Model preflight: available (gpt-test)" in text
    assert "Adjust budget, model, or context strategy before retrying." in text
    assert "response_budget=6/6" in text
    assert "- Model preflights: 1" in text
    assert "- Passed model preflights: 1" in text
    transcript_path = artifacts / "chat_sessions" / "budget-exhausted-next-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert next_event["payload"]["action"] == (
        "Adjust budget, model, or context strategy before retrying."
    )
    assert "response_budget=6/6" in next_event["payload"]["evidence"]
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["model_preflight_count"] == 1
    assert metrics["payload"]["model_preflight_passed_count"] == 1
    assert metrics["payload"]["model_preflight_blocked_count"] == 0


def test_chat_session_checks_apply_without_mutating_repo(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-apply-check"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-apply-check",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 90,
                    "estimated_cost_usd": 0.004,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(repo), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run update app value\n"
                "/trace\n"
                "/gate clean\n"
                "/diff stat\n"
                "/next\n"
                "/diff review\n"
                "/next\n"
                "/apply check\n"
                "/next\n"
                "/gate reviewed\n"
                "/metrics\n"
                "/timeline 20\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="apply-check-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Run deterministic diff risk review before applying it." in text
    assert "Diff risk review:" in text
    assert "- Risk: low" in text
    assert "Dry-run check the generated diff before applying it." in text
    assert "Apply check: ready - diff can be applied to working tree" in text
    assert "Decide whether to apply or checkpoint the validated diff." in text
    assert "Session gate: passed" in text
    assert "diff_review_count: passed" in text
    assert "ready_apply_check_count: passed" in text
    assert "high_risk_diff_review_count: passed" in text
    assert "- Diff reviews: 1" in text
    assert "- High-risk diff reviews: 0" in text
    assert "- Apply checks: 1" in text
    assert "- Ready apply checks: 1" in text
    assert "apply_check_result" in text
    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 1\n"

    transcript_path = artifacts / "chat_sessions" / "apply-check-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    diff_review = next(row for row in rows if row["event"] == "diff_review")
    assert diff_review["payload"]["risk_level"] == "low"
    assert diff_review["payload"]["decision"] == "ready_for_apply_check"
    assert diff_review["payload"]["confirmation_required"] is False
    apply_check = next(row for row in rows if row["event"] == "apply_check_result")
    assert apply_check["payload"]["status"] == "ready"
    assert apply_check["payload"]["applied"] is False
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["diff_review_count"] == 1
    assert metrics["payload"]["diff_review_high_count"] == 0
    assert metrics["payload"]["apply_check_count"] == 1
    assert metrics["payload"]["apply_check_ready_count"] == 1
    next_events = [row for row in rows if row["event"] == "session_next"]
    assert [row["payload"]["action"] for row in next_events] == [
        "Run deterministic diff risk review before applying it.",
        "Dry-run check the generated diff before applying it.",
        "Decide whether to apply or checkpoint the validated diff.",
    ]


def test_chat_session_diff_review_blocks_empty_diff(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-empty-diff-review"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-empty-diff-review",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 90,
                    "estimated_cost_usd": 0.004,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(repo), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/run update app value\n/diff review\n/apply check\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="empty-diff-review-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Diff risk review:" in text
    assert "- Risk: not_available" in text
    assert "- Decision: blocked" in text
    assert "empty_diff: generated diff is empty" in text
    assert "Apply check: empty_diff - generated diff is empty; nothing to apply" in text

    transcript_path = artifacts / "chat_sessions" / "empty-diff-review-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    diff_review = next(row for row in rows if row["event"] == "diff_review")
    assert diff_review["payload"]["risk_level"] == "not_available"
    assert diff_review["payload"]["decision"] == "blocked"
    assert diff_review["payload"]["confirmation_required"] is True
    assert diff_review["payload"]["findings"][0]["code"] == "empty_diff"
    apply_check = next(row for row in rows if row["event"] == "apply_check_result")
    assert apply_check["payload"]["status"] == "empty_diff"
    assert apply_check["payload"]["applied"] is False


def test_session_gate_uses_latest_review_and_apply_check_window(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    transcript_dir = artifacts / "chat_sessions"
    transcript_dir.mkdir(parents=True)
    transcript_path = transcript_dir / "superseded-review.jsonl"
    rows = [
        {
            "timestamp": "2026-06-14T00:00:00+00:00",
            "session_id": "superseded-review",
            "event": "run_result",
            "payload": {
                "run_id": "run-review",
                "status": "completed",
                "test_exit_code": 0,
                "model_call_count": 1,
                "model_response_count": 2,
                "model_total_tokens": 100,
                "estimated_cost_usd": 0.01,
            },
        },
        {
            "timestamp": "2026-06-14T00:00:01+00:00",
            "session_id": "superseded-review",
            "event": "diff_review",
            "payload": {
                "risk_level": "high",
                "decision": "confirm_required",
                "confirmation_required": True,
                "findings": [{"code": "old", "severity": "high"}],
            },
        },
        {
            "timestamp": "2026-06-14T00:00:02+00:00",
            "session_id": "superseded-review",
            "event": "apply_check_result",
            "payload": {"status": "ready", "applied": False},
        },
        {
            "timestamp": "2026-06-14T00:00:03+00:00",
            "session_id": "superseded-review",
            "event": "diff_review",
            "payload": {
                "risk_level": "medium",
                "decision": "review_recommended",
                "confirmation_required": False,
                "findings": [{"code": "new", "severity": "medium"}],
            },
        },
    ]
    transcript_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    config = AgentSessionGateConfig(
        require_validated_run=True,
        require_diff_review=True,
        require_ready_apply_check=True,
        min_validation_rate=1.0,
        max_high_risk_diff_reviews=0,
        max_run_errors=0,
    )
    metrics = session_metrics(transcript_path)
    gate = evaluate_session_gate(metrics, config)

    assert metrics.diff_review_high_count == 1
    assert metrics.current_diff_review_high_count == 0
    assert metrics.apply_check_ready_count == 1
    assert metrics.current_apply_check_ready_count == 0
    checks = {check.name: check for check in gate.checks}
    assert checks["high_risk_diff_review_count"].status == "passed"
    assert checks["ready_apply_check_count"].status == "failed"

    rows.append(
        {
            "timestamp": "2026-06-14T00:00:04+00:00",
            "session_id": "superseded-review",
            "event": "apply_check_result",
            "payload": {"status": "ready", "applied": False},
        }
    )
    transcript_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    metrics = session_metrics(transcript_path)
    gate = evaluate_session_gate(metrics, config)

    assert metrics.current_apply_check_ready_count == 1
    assert gate.status == "passed"


def test_chat_session_diff_review_stops_high_risk_apply_path(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-high-risk-diff"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n"
        "+++ b/tests/test_app.py\n"
        "@@ -1 +1 @@\n"
        "-assert value == 1\n"
        "+assert value == 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-high-risk-diff",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 80,
                    "estimated_cost_usd": 0.003,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run update test\n"
                "/trace\n"
                "/gate clean\n"
                "/diff stat\n"
                "/diff review\n"
                "/next\n"
                "/gate reviewed\n"
                "/apply\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="high-risk-diff-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "- Risk: high" in text
    assert "test_target_patch" in text
    assert "Resolve or explicitly review the high-risk diff before applying." in text
    assert "Session gate: failed" in text
    assert "ready_apply_check_count: failed" in text
    assert "high_risk_diff_review_count: failed" in text
    assert "Apply blocked: run /apply check after /diff review before /apply." in text
    assert "- Blocked applies: 1" in text
    assert "- High-risk diff reviews: 1" in text

    transcript_path = artifacts / "chat_sessions" / "high-risk-diff-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    diff_review = next(row for row in rows if row["event"] == "diff_review")
    assert diff_review["payload"]["risk_level"] == "high"
    assert diff_review["payload"]["confirmation_required"] is True
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["diff_review_high_count"] == 1
    assert metrics["payload"]["apply_block_count"] == 1
    apply_block = next(row for row in rows if row["event"] == "apply_blocked")
    assert apply_block["payload"]["reason_code"] == "missing_apply_check"
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert (
        next_event["payload"]["action"]
        == "Resolve or explicitly review the high-risk diff before applying."
    )


def test_chat_session_next_honors_diff_review_without_prior_diff_view(
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    test_dir = repo / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_app.py"
    test_file.write_text("assert value == 1\n", encoding="utf-8")
    _run_git(repo, "add", "tests/test_app.py")
    _run_git(repo, "commit", "-m", "add test fixture")

    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-high-risk-ready"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n"
        "+++ b/tests/test_app.py\n"
        "@@ -1 +1 @@\n"
        "-assert value == 1\n"
        "+assert value == 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-high-risk-ready",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 80,
                    "estimated_cost_usd": 0.003,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(repo), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run update app value\n"
                "/trace\n"
                "/gate clean\n"
                "/diff review\n"
                "/apply check\n"
                "/next\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="high-risk-ready-next-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Approve or reject the high-risk reviewed diff." in text
    assert "Review the generated diff before applying it." not in text
    transcript_path = artifacts / "chat_sessions" / "high-risk-ready-next-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    next_event = next(row for row in rows if row["event"] == "session_next")
    assert next_event["payload"]["action"] == ("Approve or reject the high-risk reviewed diff.")
    assert next_event["payload"]["commands"] == [
        "/approve apply <reason>",
        "/reject apply <reason>",
        "/diff show",
    ]


def test_chat_session_high_risk_apply_requires_explicit_approval(
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    test_dir = repo / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_app.py"
    test_file.write_text("assert value == 1\n", encoding="utf-8")
    _run_git(repo, "add", "tests/test_app.py")
    _run_git(repo, "commit", "-m", "add test fixture")

    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "runs" / "run-approved-risk"
    diff_path = run_dir / "final.diff"
    trace_path = run_dir / "traces.jsonl"
    report_path = run_dir / "report.md"
    run_dir.mkdir(parents=True)
    diff_path.write_text(
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n"
        "+++ b/tests/test_app.py\n"
        "@@ -1 +1 @@\n"
        "-assert value == 1\n"
        "+assert value == 2\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps({"node_name": "test", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    report_path.write_text("# Report\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-approved-risk",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 80,
                    "estimated_cost_usd": 0.003,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(repo), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run update test expectation\n"
                "/trace\n"
                "/gate clean\n"
                "/diff stat\n"
                "/diff review\n"
                "/apply check\n"
                "/next\n"
                "/apply\n"
                "/reject apply not accepted without fixture owner review\n"
                "/next\n"
                "/apply\n"
                "/approve apply accepted because this fixture is the explicit target\n"
                "/apply\n"
                "/metrics\n"
                "/timeline 20\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="approved-risk-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Apply blocked: latest /diff review is high risk; run /approve apply" in text
    assert "Approve or reject the high-risk reviewed diff." in text
    assert "Apply rejected: high - not accepted without fixture owner review" in text
    assert "Turn the rejected diff into feedback before retrying." in text
    assert "Apply blocked: latest apply decision rejected this diff: not accepted" in text
    assert "Apply approved: high - accepted because this fixture is the explicit target" in text
    assert "Apply: applied - diff applied to working tree" in text
    assert "- Apply approvals: 1" in text
    assert "- High-risk apply approvals: 1" in text
    assert "- Apply rejections: 1" in text
    assert "- High-risk apply rejections: 1" in text
    assert "- Blocked applies: 2" in text
    assert test_file.read_text(encoding="utf-8") == "assert value == 2\n"

    transcript_path = artifacts / "chat_sessions" / "approved-risk-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    approval = next(row for row in rows if row["event"] == "apply_approval")
    assert approval["payload"]["risk_level"] == "high"
    assert approval["payload"]["reason"] == ("accepted because this fixture is the explicit target")
    rejection = next(row for row in rows if row["event"] == "apply_rejection")
    assert rejection["payload"]["risk_level"] == "high"
    assert rejection["payload"]["reason"] == "not accepted without fixture owner review"
    next_events = [row for row in rows if row["event"] == "session_next"]
    assert next_events[0]["payload"]["action"] == ("Approve or reject the high-risk reviewed diff.")
    next_event = next_events[1]
    assert (
        next_event["payload"]["action"] == "Turn the rejected diff into feedback before retrying."
    )
    apply_blocks = [row for row in rows if row["event"] == "apply_blocked"]
    assert [row["payload"]["reason_code"] for row in apply_blocks] == [
        "missing_apply_approval",
        "apply_rejected",
    ]
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["apply_approval_count"] == 1
    assert metrics["payload"]["high_risk_apply_approval_count"] == 1
    assert metrics["payload"]["apply_rejection_count"] == 1
    assert metrics["payload"]["high_risk_apply_rejection_count"] == 1
    assert metrics["payload"]["apply_block_count"] == 2
    assert metrics["payload"]["apply_success_count"] == 1


def test_chat_session_apply_requires_review_and_ready_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-guarded-apply" / "final.diff"
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

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-guarded-apply",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 70,
                    "estimated_cost_usd": 0.002,
                },
                retrieved_context=[],
            )

    def fail_apply(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        raise AssertionError("guarded apply should not call git apply")

    import patchsmith.chat.controller as chat_controller

    monkeypatch.setattr(chat_controller, "apply_agent_run_diff", fail_apply)

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/run guarded apply\n/apply\n/metrics\n/timeline 10\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="guarded-apply-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Apply blocked: run /diff review before /apply." in text
    assert "- Blocked applies: 1" in text
    assert "apply_blocked | reason=missing_diff_review" in text

    transcript_path = artifacts / "chat_sessions" / "guarded-apply-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    apply_block = next(row for row in rows if row["event"] == "apply_blocked")
    assert apply_block["payload"]["reason_code"] == "missing_diff_review"
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["apply_block_count"] == 1
    assert metrics["payload"]["apply_attempt_count"] == 0


def test_chat_session_lists_saved_sessions(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"

    for session_id, task in (("older", "fix older"), ("newer", "fix newer")):
        output = io.StringIO()
        assert (
            run_chat_session(
                config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
                input_stream=io.StringIO(f"/run {task}\n/exit\n"),
                output_stream=output,
                runner_cls=_fake_runner_for_session_list(artifacts, session_id),
                session_id=session_id,
            )
            == 0
        )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/sessions\n/exit\n"),
            output_stream=output,
            session_id="listing-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Session | Updated | Tasks | Runs | Validated | Errors | Cost | Last" in text
    assert "older" in text
    assert "newer" in text
    assert "listing-session" in text
    assert "1 | 1 | 1 | 0 | $0.002000" in text
    transcript_path = artifacts / "chat_sessions" / "listing-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    session_list = next(row for row in rows if row["event"] == "session_list")
    assert session_list["payload"]["count"] == 3


def test_chat_session_runs_project_custom_slash_commands(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    command_dir = tmp_path / ".patchsmith" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "review.md").write_text(
        "---\n"
        "description: Review the selected code path\n"
        "argument_hint: target path\n"
        "---\n"
        "Review the patch target.\n\n"
        "Focus: $ARGUMENTS\n",
        encoding="utf-8",
    )
    nested_dir = command_dir / "bench"
    nested_dir.mkdir()
    (nested_dir / "live.md").write_text(
        "Plan a bounded live benchmark.\n\nConstraints: {{arguments}}\n",
        encoding="utf-8",
    )
    captured_tasks: list[str] = []

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            captured_tasks.append(request.issue_text)
            run_id = f"run-custom-{len(captured_tasks)}"
            diff_path = artifacts / "runs" / run_id / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id=run_id,
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=None,
                retrieved_context=[],
            )

    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO(
            "/commands\n/review parser edge cases\n/bench:live cost cap $0.05\n/exit\n"
        ),
        output_stream=output,
        runner_cls=FakeRepairRunner,
        session_id="custom-command-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Project custom commands:" in text
    assert "/review" in text
    assert "/bench:live" in text
    assert "Review the selected code path" in text
    assert "[target path]" in text
    assert "Running custom command: /review" in text
    assert "Running custom command: /bench:live" in text
    assert len(captured_tasks) == 2
    assert "PatchSmith custom command /review" in captured_tasks[0]
    assert "Focus: parser edge cases" in captured_tasks[0]
    assert "description:" not in captured_tasks[0]
    assert "PatchSmith custom command /bench:live" in captured_tasks[1]
    assert "Constraints: cost cap $0.05" in captured_tasks[1]

    transcript_path = artifacts / "chat_sessions" / "custom-command-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    command_list = next(row for row in rows if row["event"] == "custom_command_list")
    assert command_list["payload"]["count"] == 2
    custom_events = [row for row in rows if row["event"] == "custom_command"]
    assert [row["payload"]["command"] for row in custom_events] == [
        "review",
        "bench:live",
    ]
    assert all(row["payload"]["prompt_chars"] > 0 for row in custom_events)


def test_chat_session_lists_project_hooks(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    hook_config = tmp_path / ".patchsmith" / "hooks.json"
    hook_config.parent.mkdir(parents=True)
    hook_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreRun": [
                        {
                            "name": "guard-expensive-run",
                            "matcher": "benchmark",
                            "command": "python scripts/check_budget.py",
                            "timeout_seconds": 4,
                        }
                    ],
                    "PreApply": ["python scripts/check_diff.py"],
                }
            }
        ),
        encoding="utf-8",
    )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/hooks\n/exit\n"),
            output_stream=output,
            session_id="hook-list-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Project hooks:" in text
    assert "PreRun: guard-expensive-run [benchmark] timeout=4s" in text
    assert "PreApply: preapply-1 [*] timeout=30s" in text
    transcript_path = artifacts / "chat_sessions" / "hook-list-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    hook_list = next(row for row in rows if row["event"] == "hook_list")
    assert hook_list["payload"]["count"] == 2


def test_chat_session_prerun_hook_can_block_task(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    script = tmp_path / "block_prerun.py"
    script.write_text(
        "import json\n"
        "import sys\n"
        "payload = json.load(sys.stdin)\n"
        "assert payload['event'] == 'PreRun'\n"
        "print(json.dumps({'decision': 'block', 'reason': 'budget exhausted'}))\n",
        encoding="utf-8",
    )
    hook_config = tmp_path / ".patchsmith" / "hooks.json"
    hook_config.parent.mkdir(parents=True)
    hook_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreRun": [
                        {
                            "name": "budget-guard",
                            "matcher": "parser",
                            "command": _python_command(script),
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("blocked PreRun hook should stop the runner")

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/run fix parser\n/status\n/exit\n"),
            output_stream=output,
            runner_cls=NoRunRepairRunner,
            session_id="blocked-prerun-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Hook blocked PreRun: budget exhausted" in text
    assert "Last run: none" in text
    transcript_path = artifacts / "chat_sessions" / "blocked-prerun-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert not any(row["event"] == "user_task" for row in rows)
    hook_result = next(row for row in rows if row["event"] == "hook_result")
    assert hook_result["payload"]["event"] == "PreRun"
    assert hook_result["payload"]["status"] == "blocked"
    assert hook_result["payload"]["runs"][0]["hook"]["name"] == "budget-guard"


def test_chat_session_preapply_hook_can_block_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-hook-apply" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")
    script = tmp_path / "block_apply.py"
    script.write_text(
        "import json\n"
        "import sys\n"
        "payload = json.load(sys.stdin)\n"
        "assert payload['event'] == 'PreApply'\n"
        "print(json.dumps({'decision': 'block', 'reason': 'diff needs review'}))\n",
        encoding="utf-8",
    )
    hook_config = tmp_path / ".patchsmith" / "hooks.json"
    hook_config.parent.mkdir(parents=True)
    hook_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreApply": [
                        {
                            "name": "review-before-apply",
                            "command": _python_command(script),
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            return SimpleNamespace(
                run_id="run-hook-apply",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    def fail_apply(*, repo: str, diff_path: Path, allow_dirty: bool = False) -> AgentApplyResult:
        raise AssertionError("blocked PreApply hook should stop apply")

    def fake_check_agent_run_diff(
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult:
        return AgentApplyResult(
            status="ready",
            repo_path=repo,
            diff_path=str(diff_path),
            message="diff can be applied to working tree",
            applied=False,
        )

    import patchsmith.chat.controller as chat_controller

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(chat_controller, "apply_agent_run_diff", fail_apply)
    monkeypatch.setattr(
        chat_controller,
        "check_agent_run_diff",
        fake_check_agent_run_diff,
    )
    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run fix parser\n/diff review\n/apply check\n/apply\n/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="blocked-apply-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Run ID: run-hook-apply" in text
    assert "Hook blocked PreApply: diff needs review" in text
    transcript_path = artifacts / "chat_sessions" / "blocked-apply-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["event"] == "run_result" for row in rows)
    assert not any(row["event"] == "apply_result" for row in rows)
    hook_result = [row for row in rows if row["event"] == "hook_result"][-1]
    assert hook_result["payload"]["event"] == "PreApply"
    assert hook_result["payload"]["status"] == "blocked"


def test_chat_session_lists_and_applies_project_agent_profile(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    profile_dir = tmp_path / ".patchsmith" / "agents"
    profile_dir.mkdir(parents=True)
    profile_instructions = "Localize the failure before editing.\nReject broad rewrites."
    (profile_dir / "verifier.md").write_text(
        "---\n"
        "description: Verify fixes before broader exploration\n"
        "model: gpt-5-mini\n"
        "subagents: inline\n"
        "max_context_files: 3\n"
        "max_model_responses: 4\n"
        "max_model_tokens: 90000\n"
        "top_k: 7\n"
        "test_command: pytest tests/test_parser.py -q\n"
        "context_paths: |\n"
        "  - src/parser.py#parse\n"
        "  - tests/test_parser.py\n"
        "---\n"
        f"{profile_instructions}\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            captured["request"] = request
            diff_path = artifacts / "runs" / "run-profile" / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-profile",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/agents\n/agent verifier\n/status\n/run fix parser\n/metrics\n/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="profile-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Project agent profiles:" in text
    assert "/agent verifier" in text
    assert "Verify fixes before broader exploration" in text
    assert "Agent profile: /verifier" in text
    assert "Agent profile: verifier" in text
    assert "- Agent profile updates: 1" in text
    request = captured["request"]
    assert "PatchSmith agent profile /verifier" in request.issue_text
    assert "Localize the failure before editing." in request.issue_text
    assert "Task:\nfix parser" in request.issue_text
    assert request.test_command == "pytest tests/test_parser.py -q"
    assert request.top_k == 7
    assert request.context_paths == ("src/parser.py#parse", "tests/test_parser.py")
    assert request.runtime_config == {
        "subagent_mode": "inline",
        "model": "gpt-5-mini",
        "max_context_files": 3,
        "resource_budget": {
            "max_model_responses": 4,
            "max_model_tokens": 90000,
        },
        "agent_profile": {
            "name": "verifier",
            "path": str(profile_dir / "verifier.md"),
            "description": "Verify fixes before broader exploration",
            "instruction_chars": len(profile_instructions),
        },
    }

    transcript_path = artifacts / "chat_sessions" / "profile-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["event"] == "agent_profile_list" for row in rows)
    profile_update = next(
        row
        for row in rows
        if row["event"] == "config_update" and row["payload"].get("field") == "agent_profile"
    )
    assert profile_update["payload"]["agent_profile"] == "verifier"
    # Profile text is not persisted to transcripts; only metadata is recorded.
    assert "agent_profile_instructions" not in profile_update["payload"]
    assert profile_update["payload"]["agent_profile_instruction_chars"] == len(profile_instructions)


def test_chat_session_loads_project_instructions_into_runs(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    (tmp_path / "AGENTS.md").write_text(
        "## Repository expectations\n- Keep parser fixes minimal.\n- Run focused parser tests.\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            captured["request"] = request
            diff_path = artifacts / "runs" / "run-instructions" / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-instructions",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/instructions\n/status\n/run fix parser\n/metrics\n/exit\n"),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="instruction-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Project instruction files:" in text
    assert "AGENTS.md | root" in text
    assert "Project instructions: 1 file(s)" in text
    assert "- Instruction views: 1" in text
    request = captured["request"]
    assert "PatchSmith project instructions" in request.issue_text
    assert "Keep parser fixes minimal." in request.issue_text
    assert "Task:\nfix parser" in request.issue_text
    project_instructions = request.runtime_config["project_instructions"]
    assert project_instructions["files"] == ["AGENTS.md"]
    assert project_instructions["instruction_chars"] > 0

    transcript_path = artifacts / "chat_sessions" / "instruction-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    session_start = rows[0]["payload"]["config"]
    assert session_start["agent_instruction_files"] == ["AGENTS.md"]
    # Full instruction text must never be persisted to transcripts; only metadata.
    assert "agent_instructions" not in session_start
    assert session_start["agent_instruction_chars"] > 0
    assert any(row["event"] == "instruction_view" for row in rows)


def test_chat_session_exposes_project_memory_as_first_class_command(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    (tmp_path / "AGENTS.md").write_text(
        "## Repository memory\n- Prefer minimal parser patches.\n",
        encoding="utf-8",
    )

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
                "show memory\n/memory reload\n/memory clear\n/memory\n/metrics\n/exit\n"
            ),
            output_stream=output,
            runner_cls=NoRunRepairRunner,
            session_id="memory-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Project memory files:" in text
    assert "AGENTS.md | root" in text
    assert "Project memory reloaded." in text
    assert "Project memory disabled for later runs." in text
    assert "No project memory files loaded." in text
    assert "- Memory views: 2" in text
    assert "- Instruction views: 0" in text

    transcript_path = artifacts / "chat_sessions" / "memory-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    memory_views = [row for row in rows if row["event"] == "memory_view"]
    assert [row["payload"]["count"] for row in memory_views] == [1, 0]
    metrics = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics["payload"]["memory_view_count"] == 2
    assert metrics["payload"]["instruction_view_count"] == 0


def test_chat_session_plan_guides_runs_and_resumes(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            captured["request"] = request
            diff_path = artifacts / "runs" / "run-plan" / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-plan",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 100,
                    "estimated_cost_usd": 0.001,
                },
                retrieved_context=[],
            )

    first_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/plan set inspect parser; write focused test\n"
                "/plan start 1\n"
                "/run fix parser\n"
                "/plan done 1\n"
                "/plan show\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=first_output,
            runner_cls=FakeRepairRunner,
            session_id="plan-session",
        )
        == 0
    )

    text = first_output.getvalue()
    assert "Session plan:" in text
    assert "1 | in_progress | inspect parser" in text
    assert "1 | completed | inspect parser" in text
    assert "- Plan updates: 3" in text
    assert "- Plan views: 1" in text
    request = captured["request"]
    assert "PatchSmith session plan" in request.issue_text
    assert "1. [in_progress] inspect parser" in request.issue_text
    assert "2. [pending] write focused test" in request.issue_text
    assert "Task:\nfix parser" in request.issue_text

    transcript_path = artifacts / "chat_sessions" / "plan-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    plan_updates = [row for row in rows if row["event"] == "plan_update"]
    assert [row["payload"]["action"] for row in plan_updates] == [
        "set",
        "start",
        "done",
    ]
    user_task = next(row for row in rows if row["event"] == "user_task")
    assert user_task["payload"]["plan_items"][0]["status"] == "in_progress"
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics_event["payload"]["plan_update_count"] == 3
    assert metrics_event["payload"]["plan_view_count"] == 1

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("resume plan inspection should not run")

    resumed_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/plan show\n/status\n/exit\n"),
            output_stream=resumed_output,
            runner_cls=NoRunRepairRunner,
            session_id="plan-session",
            resume=True,
        )
        == 0
    )
    resumed_text = resumed_output.getvalue()
    assert "1 | completed | inspect parser" in resumed_text
    assert "2 | pending | write focused test" in resumed_text
    assert "Session plan items: 2" in resumed_text


def test_chat_session_feedback_guides_runs_and_resumes(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    captured: dict[str, object] = {}

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            captured["request"] = request
            diff_path = artifacts / "runs" / "run-feedback" / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="run-feedback",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 50,
                    "estimated_cost_usd": 0.0005,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/feedback keep the public API stable\n"
                "/feedback add avoid broad rewrites\n"
                "/feedback show\n"
                "/run fix parser\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="feedback-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Added feedback: keep the public API stable" in text
    assert "Added feedback: avoid broad rewrites" in text
    assert "Session feedback:" in text
    assert "1. keep the public API stable" in text
    assert "- Feedback updates: 2" in text
    assert "- Feedback views: 1" in text
    request = captured["request"]
    assert "PatchSmith session feedback" in request.issue_text
    assert "1. keep the public API stable" in request.issue_text
    assert "2. avoid broad rewrites" in request.issue_text
    assert "Task:\nfix parser" in request.issue_text

    transcript_path = artifacts / "chat_sessions" / "feedback-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    feedback_updates = [row for row in rows if row["event"] == "feedback_update"]
    assert [row["payload"]["item"] for row in feedback_updates] == [
        "keep the public API stable",
        "avoid broad rewrites",
    ]
    user_task = next(row for row in rows if row["event"] == "user_task")
    assert user_task["payload"]["feedback_items"] == [
        "keep the public API stable",
        "avoid broad rewrites",
    ]
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics_event["payload"]["feedback_update_count"] == 2
    assert metrics_event["payload"]["feedback_view_count"] == 1

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("resume feedback inspection should not run")

    resumed_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/feedback show\n/status\n/feedback clear\n/feedback\n/exit\n"
            ),
            output_stream=resumed_output,
            runner_cls=NoRunRepairRunner,
            session_id="feedback-session",
            resume=True,
        )
        == 0
    )
    resumed_text = resumed_output.getvalue()
    assert "PatchSmith Chat (resumed)" in resumed_text
    assert "1. keep the public API stable" in resumed_text
    assert "Session feedback items: 2" in resumed_text
    assert "Session feedback cleared." in resumed_text
    assert "No session feedback." in resumed_text


def test_chat_session_can_rewind_last_applied_diff(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-rewind" / "final.diff"
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

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-rewind",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(repo), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run fix app\n"
                "/diff review\n"
                "/apply check\n"
                "/apply\n"
                "/rewind\n"
                "/metrics\n"
                "/status\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="rewind-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Apply: applied - diff applied to working tree" in text
    assert "Rewind: reverted - diff reversed from working tree" in text
    assert "- Rewind attempts: 1" in text
    assert "- Reverted diffs: 1" in text
    assert "- Rewind success rate: 100.00%" in text
    assert "Last rewind: reverted" in text
    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 1\n"

    transcript_path = artifacts / "chat_sessions" / "rewind-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    rewind = next(row for row in rows if row["event"] == "rewind_result")
    assert rewind["payload"]["status"] == "reverted"
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics_event["payload"]["rewind_attempt_count"] == 1
    assert metrics_event["payload"]["rewind_success_count"] == 1
    assert metrics_event["payload"]["rewind_success_rate"] == 1.0


def test_chat_session_gate_profiles_report_pass_and_failure(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-gate" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            return SimpleNamespace(
                run_id="run-gate",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 100,
                    "estimated_cost_usd": 0.01,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/gate\n/run fix parser\n/gate clean\n/gate cost 0.001\n/metrics\n/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="gate-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Session gate: failed" in text
    assert "no validated runs recorded" in text
    assert "Session gate: passed" in text
    assert "$0.010000 > $0.001000" in text
    assert "- Session gates: 3" in text
    assert "- Failed session gates: 2" in text

    transcript_path = artifacts / "chat_sessions" / "gate-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    gates = [row for row in rows if row["event"] == "session_gate"]
    assert [row["payload"]["gate"]["status"] for row in gates] == [
        "failed",
        "passed",
        "failed",
    ]
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics_event["payload"]["session_gate_count"] == 3
    assert metrics_event["payload"]["session_gate_failure_count"] == 2


def _fake_runner_for_session_list(artifacts: Path, session_id: str):
    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            diff_path = artifacts / "runs" / session_id / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id=f"run-{session_id}",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 200,
                    "estimated_cost_usd": 0.002,
                },
                retrieved_context=[],
            )

    return FakeRepairRunner


def _python_command(script: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _run_git(path, "init")
    _run_git(path, "config", "user.email", "patchsmith@example.invalid")
    _run_git(path, "config", "user.name", "PatchSmith Test")
    (path / "app.py").write_text("value = 1\n", encoding="utf-8")
    _run_git(path, "add", "app.py")
    _run_git(path, "commit", "-m", "init")
    return path


def _low_risk_diff_text() -> str:
    return (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n"
    )


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_chat_session_resumes_config_history_and_last_run(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    diff_path = artifacts / "runs" / "run-resume" / "final.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("diff --git a/a b/a\n", encoding="utf-8")

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            return SimpleNamespace(
                run_id="run-resume",
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=None,
                retrieved_context=[],
            )

    first_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/context add src/a.py#fix\n"
                "/model gpt-5-mini\n"
                "/budget set 6 90000\n"
                "/run fix one\n"
                "/exit\n"
            ),
            output_stream=first_output,
            runner_cls=FakeRepairRunner,
            session_id="resume-session",
        )
        == 0
    )

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("resume status should not run the agent")

    second_output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO("/status\n/diff\n/history\n/exit\n"),
        output_stream=second_output,
        runner_cls=NoRunRepairRunner,
        session_id="resume-session",
        resume=True,
    )

    assert exit_code == 0
    text = second_output.getvalue()
    assert "PatchSmith Chat (resumed)" in text
    assert "Context hints: src/a.py#fix" in text
    assert "Model override: gpt-5-mini" in text
    assert "Budget: responses=6, tokens=90000" in text
    assert "Last run: run-resume" in text
    assert f"Diff: {diff_path}" in text
    assert "1. fix one" in text
    transcript_path = artifacts / "chat_sessions" / "resume-session.jsonl"
    events = [
        json.loads(line)["event"]
        for line in transcript_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "session_resume" in events


def test_chat_session_compacts_and_clears_replayable_state(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_index = 0

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            nonlocal run_index
            run_index += 1
            run_id = f"run-{run_index}"
            diff_path = artifacts / "runs" / run_id / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id=run_id,
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 2,
                    "total_tokens": 100,
                    "estimated_cost_usd": 0.001,
                },
                retrieved_context=[],
            )

    first_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/run first task\n/compact keep target notes\n/history\n/run second task\n/exit\n"
            ),
            output_stream=first_output,
            runner_cls=FakeRepairRunner,
            session_id="compact-session",
        )
        == 0
    )
    first_text = first_output.getvalue()
    assert "Session compacted. Summarized 1 task(s)." in first_text
    assert "No tasks since last compaction." in first_text

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("resume inspection should not run the agent")

    resumed_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/history\n/status\n/clear\n/history\n/status\n/exit\n"),
            output_stream=resumed_output,
            runner_cls=NoRunRepairRunner,
            session_id="compact-session",
            resume=True,
        )
        == 0
    )
    resumed_text = resumed_output.getvalue()
    assert "PatchSmith Chat (resumed)" in resumed_text
    assert "1. second task" in resumed_text
    assert "Last compaction: 1 task(s)" in resumed_text
    assert "Last run: run-2" in resumed_text
    assert "Session state cleared. Transcript retained." in resumed_text
    assert "No tasks in this session yet." in resumed_text
    assert "Last run: none" in resumed_text
    transcript_path = artifacts / "chat_sessions" / "compact-session.jsonl"
    events = [
        json.loads(line)["event"]
        for line in transcript_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "session_compact" in events
    assert "session_clear" in events


def test_chat_session_checkpoints_restore_state_and_resume(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    run_index = 0

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def run(self, request):
            nonlocal run_index
            run_index += 1
            run_id = f"run-{run_index}"
            diff_path = artifacts / "runs" / run_id / "final.diff"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_text(f"diff --git a/{run_id}.py b/{run_id}.py\n", encoding="utf-8")
            return SimpleNamespace(
                run_id=run_id,
                status="completed",
                report_path=diff_path.parent / "report.md",
                trace_path=diff_path.parent / "traces.jsonl",
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=0),
                model_usage={
                    "call_count": 1,
                    "response_count": 1,
                    "total_tokens": 100,
                    "estimated_cost_usd": 0.001,
                },
                retrieved_context=[],
            )

    output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO(
                "/context add src/a.py#fix\n"
                "/model gpt-a\n"
                "/budget set 2 100\n"
                "/plan set inspect; test\n"
                "/run fix one\n"
                "/checkpoint stable\n"
                "/checkpoints\n"
                "/context add src/b.py#extra\n"
                "/model gpt-b\n"
                "/plan done 1\n"
                "/run fix two\n"
                "/restore stable\n"
                "/status\n"
                "/history\n"
                "/diff\n"
                "/metrics\n"
                "/exit\n"
            ),
            output_stream=output,
            runner_cls=FakeRepairRunner,
            session_id="checkpoint-session",
        )
        == 0
    )

    text = output.getvalue()
    assert "Checkpoint saved: ckpt-" in text
    assert "(stable)" in text
    assert "Checkpoints:" in text
    assert "Restored checkpoint: ckpt-" in text
    assert "Context hints: src/a.py#fix" in text
    assert "src/b.py#extra" not in text[text.rfind("Restored checkpoint:") :]
    assert "Model override: gpt-a" in text
    assert "Budget: responses=2, tokens=100" in text
    assert "Last run: run-1" in text
    assert "1. fix one" in text
    assert "2. fix two" not in text[text.rfind("Restored checkpoint:") :]
    assert f"Diff: {artifacts / 'runs' / 'run-1' / 'final.diff'}" in text
    assert "- Runs: 2" in text
    assert "- Checkpoints: 1" in text
    assert "- Restores: 1" in text

    transcript_path = artifacts / "chat_sessions" / "checkpoint-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    checkpoint = next(row for row in rows if row["event"] == "session_checkpoint")
    assert checkpoint["payload"]["label"] == "stable"
    assert checkpoint["payload"]["state"]["history"] == ["fix one"]
    assert checkpoint["payload"]["state"]["last_run_payload"]["run_id"] == "run-1"
    restore = next(row for row in rows if row["event"] == "session_restore")
    assert restore["payload"]["state"]["history"] == ["fix one"]
    metrics_event = next(row for row in rows if row["event"] == "session_metrics")
    assert metrics_event["payload"]["checkpoint_count"] == 1
    assert metrics_event["payload"]["restore_count"] == 1

    class NoRunRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise AssertionError("resume inspection should not run the agent")

    resumed_output = io.StringIO()
    assert (
        run_chat_session(
            config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
            input_stream=io.StringIO("/status\n/history\n/diff\n/exit\n"),
            output_stream=resumed_output,
            runner_cls=NoRunRepairRunner,
            session_id="checkpoint-session",
            resume=True,
        )
        == 0
    )
    resumed_text = resumed_output.getvalue()
    assert "PatchSmith Chat (resumed)" in resumed_text
    assert "Context hints: src/a.py#fix" in resumed_text
    assert "Model override: gpt-a" in resumed_text
    assert "Last run: run-1" in resumed_text
    assert "1. fix one" in resumed_text
    assert f"Diff: {artifacts / 'runs' / 'run-1' / 'final.diff'}" in resumed_text


def test_chat_session_resume_missing_transcript_returns_error(tmp_path: Path) -> None:
    output = io.StringIO()

    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(tmp_path / "artifacts")),
        input_stream=io.StringIO("/exit\n"),
        output_stream=output,
        session_id="missing-session",
        resume=True,
    )

    assert exit_code == 2
    assert "Cannot resume missing session: missing-session" in output.getvalue()


def test_chat_session_records_run_error_without_crashing(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"

    class FailingRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            pass

        def run(self, request):
            raise RuntimeError("DeepAgents extra is missing")

    output = io.StringIO()
    exit_code = run_chat_session(
        config=AgentCliConfig(repo=str(tmp_path), artifacts_dir=str(artifacts)),
        input_stream=io.StringIO("/run fix parser\n/status\n/exit\n"),
        output_stream=output,
        runner_cls=FailingRepairRunner,
        session_id="error-session",
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "DeepAgents extra is missing" in text
    assert "Last run: none" in text
    transcript_path = artifacts / "chat_sessions" / "error-session.jsonl"
    rows = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
    run_error = next(row for row in rows if row["event"] == "run_error")
    assert run_error["payload"] == {
        "error_type": "RuntimeError",
        "message": "DeepAgents extra is missing",
    }
