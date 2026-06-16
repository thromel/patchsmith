from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import patchsmith.cli.commands.agent as agent_commands

pytestmark = pytest.mark.unit


def test_agent_command_module_registers_and_runs_one_shot(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_agent_once(*, config, issue_text: str, runner_cls) -> SimpleNamespace:
        captured["config"] = config
        captured["issue_text"] = issue_text
        captured["runner_cls"] = runner_cls
        return SimpleNamespace(
            exit_code=0,
            apply_result=None,
            result=SimpleNamespace(
                run_id="run-agent-module",
                status="completed",
                report_path=Path("artifacts/runs/run-agent-module/report.md"),
                trace_path=Path("artifacts/runs/run-agent-module/traces.jsonl"),
                final_diff_path=Path("artifacts/runs/run-agent-module/final.diff"),
                test_result=SimpleNamespace(exit_code=0),
                retrieved_context=[],
                model_usage={"response_count": 2, "total_tokens": 123},
            ),
        )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    handlers = agent_commands.register(subparsers)
    monkeypatch.setattr(agent_commands, "run_agent_once", fake_run_agent_once)

    args = parser.parse_args(["agent", "Fix parser", "--skip-model-preflight", "--json"])

    assert handlers["agent"](args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "run-agent-module"
    assert payload["model_response_count"] == 2
    assert captured["issue_text"] == "Fix parser"
    assert captured["runner_cls"] is agent_commands.RepairRunner
    assert captured["config"].repo == "."


def test_agent_command_module_rejects_interactive_preflight(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    handlers = agent_commands.register(subparsers)
    args = parser.parse_args(["agent", "--interactive", "--preflight"])

    assert handlers["agent"](args) == 2
    assert "pass either --interactive or --preflight" in capsys.readouterr().err
