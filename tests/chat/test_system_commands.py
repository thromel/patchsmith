from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest

import patchsmith.chat.handlers.system as system_handler
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.system import system_commands
from patchsmith.chat.state import AgentChatRuntime, AgentChatState

pytestmark = pytest.mark.unit


def test_system_commands_are_registered() -> None:
    registry = build_command_registry(system_commands())

    assert sorted(registry) == ["doctor", "help"]
    assert registry["help"].usage == "/help"
    assert registry["doctor"].usage == "/doctor"


def test_help_command_renders_chat_help(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    output = io.StringIO()

    build_command_registry(system_commands())["help"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_noop_record),
    )

    text = output.getvalue()
    assert text.startswith("Commands:\n")
    assert "  /help                 Show this help.\n" in text
    assert "  /doctor               Check local agent readiness.\n" in text
    assert "  /exit, /quit          End the session.\n" in text
    assert "Project commands are loaded from .patchsmith/commands/*.md.\n" in text
    assert "Project hooks are loaded from .patchsmith/hooks.json.\n" in text
    assert "Project agent profiles are loaded from .patchsmith/agents/*.md.\n" in text
    assert "Project instructions are loaded from AGENTS.md/CLAUDE.md-style files.\n" in text


def test_help_documents_every_registered_command(tmp_path: Path) -> None:
    from patchsmith.chat.registry import chat_commands

    runtime = _runtime(tmp_path)
    output = io.StringIO()
    build_command_registry(system_commands())["help"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_noop_record),
    )
    help_text = output.getvalue()

    # The command registry is the source of truth for which slash commands
    # exist; every primary command must be documented in /help so the two
    # cannot drift (aliases may be omitted).
    missing = sorted(
        command.name for command in chat_commands() if f"/{command.name}" not in help_text
    )
    assert missing == []


def test_doctor_command_records_diagnostic_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []

    def fake_validate_agent_cli_config(
        config: AgentCliConfig,
        *,
        require_apply_ready: bool,
    ) -> tuple[dict[str, object], dict[str, object], None]:
        assert config is runtime.state.config
        assert require_apply_ready is False
        return {"runtime": "deepagents"}, {"apply": "ready"}, None

    def fake_agent_diagnostic_payload(
        *,
        config: AgentCliConfig,
        runtime_config: dict[str, object],
        apply_preflight: dict[str, object],
    ) -> dict[str, object]:
        assert config is runtime.state.config
        assert runtime_config == {"runtime": "deepagents"}
        assert apply_preflight == {"apply": "ready"}
        return {
            "status": "passed",
            "checks": [
                {
                    "name": "repo",
                    "status": "passed",
                    "message": "ready",
                }
            ],
        }

    monkeypatch.setattr(
        system_handler,
        "validate_agent_cli_config",
        fake_validate_agent_cli_config,
    )
    monkeypatch.setattr(
        system_handler,
        "agent_diagnostic_payload",
        fake_agent_diagnostic_payload,
    )

    output = io.StringIO()
    build_command_registry(system_commands())["doctor"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == "Doctor: passed\n- repo: passed - ready\n"
    assert events == [
        (
            "doctor",
            {
                "status": "passed",
                "checks": [
                    {
                        "name": "repo",
                        "status": "passed",
                        "message": "ready",
                    }
                ],
            },
        )
    ]


def test_doctor_command_records_validation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []

    def fake_validate_agent_cli_config(
        config: AgentCliConfig,
        *,
        require_apply_ready: bool,
    ) -> tuple[dict[str, object], dict[str, object], str]:
        return {}, {}, "repo path is invalid"

    monkeypatch.setattr(
        system_handler,
        "validate_agent_cli_config",
        fake_validate_agent_cli_config,
    )

    output = io.StringIO()
    build_command_registry(system_commands())["doctor"].handler(
        runtime=runtime,
        argument="",
        output_stream=output,
        context=ChatCommandContext(record=_record_to(events)),
    )

    assert output.getvalue() == "repo path is invalid\n"
    assert events == [("doctor_error", {"message": "repo path is invalid"})]


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
