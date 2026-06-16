from __future__ import annotations

import argparse

import pytest

import patchsmith.cli.commands.chat as chat_commands

pytestmark = pytest.mark.unit


def test_chat_command_module_registers_and_runs_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chat_session(
        *,
        config,
        initial_prompt: str,
        input_stream,
        output_stream,
        runner_cls,
        model_preflight_checker=None,
        session_id=None,
        resume: bool = False,
    ) -> int:
        captured["config"] = config
        captured["initial_prompt"] = initial_prompt
        captured["runner_cls"] = runner_cls
        captured["model_preflight_checker"] = model_preflight_checker
        captured["session_id"] = session_id
        captured["resume"] = resume
        return 0

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    handlers = chat_commands.register(subparsers)
    monkeypatch.setattr(chat_commands, "run_chat_session", fake_run_chat_session)

    args = parser.parse_args(["chat", "Fix parser", "--skip-model-preflight"])

    assert handlers["chat"](args) == 0
    assert captured["initial_prompt"] == "Fix parser"
    assert captured["runner_cls"] is chat_commands.RepairRunner
    assert captured["model_preflight_checker"] is None
    assert captured["session_id"] is None
    assert captured["resume"] is False
    assert captured["config"].repo == "."


def test_chat_session_action_validation_rejects_conflicts() -> None:
    args = argparse.Namespace(
        list_sessions=True,
        list_commands=False,
        list_hooks=False,
        list_agents=False,
        list_instructions=False,
        session_metrics="session-a",
        session_gate=None,
        session_next=None,
        export_session=None,
        export_path=None,
        require_validated_run=False,
        require_diff_review=False,
        require_ready_apply_check=False,
        min_validation_rate=None,
        min_preflight_to_run_rate=None,
        min_apply_success_rate=None,
        max_high_risk_diff_reviews=None,
        max_cost_per_validated_run_usd=None,
        max_run_errors=None,
    )

    assert chat_commands.validate_offline_session_actions(args) == (
        "pass only one of --list-sessions, --list-commands, --list-hooks, "
        "--list-agents, --list-instructions, --session-metrics, --session-gate, "
        "--session-next, or --export-session."
    )
