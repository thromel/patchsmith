from __future__ import annotations

import inspect

import pytest

import patchsmith.chat.controller as chat_controller
from patchsmith.chat.registry import chat_command_registry, chat_commands

pytestmark = pytest.mark.unit


def test_chat_command_registry_collects_all_command_families() -> None:
    registry = chat_command_registry()

    expected_commands = {
        "agent",
        "agents",
        "apply",
        "approve",
        "budget",
        "cancel",
        "checkpoint",
        "checkpoints",
        "clear",
        "commands",
        "compact",
        "context",
        "cost",
        "diff",
        "doctor",
        "evidence",
        "export",
        "feedback",
        "gate",
        "help",
        "history",
        "hooks",
        "instructions",
        "memory",
        "metrics",
        "mode",
        "model",
        "next",
        "note",
        "notes",
        "permissions",
        "preflight",
        "profile",
        "profiles",
        "recommend",
        "reject",
        "restore",
        "rewind",
        "run",
        "sessions",
        "status",
        "timeline",
        "trace",
        "undo",
        "verify",
    }

    assert expected_commands <= registry.keys()
    assert registry["undo"] is registry["rewind"]
    assert registry["note"] is registry["feedback"]
    assert registry["profile"] is registry["agent"]
    assert registry["evidence"] is registry["trace"]
    assert registry["recommend"] is registry["next"]


def test_chat_commands_have_unique_registered_names() -> None:
    names = [name for command in chat_commands() for name in command.names]

    assert len(names) == len(set(names))


def test_controller_uses_central_chat_command_registry() -> None:
    source = inspect.getsource(chat_controller)

    assert "_REGISTERED_CHAT_COMMANDS = chat_command_registry()" in source
    assert "from patchsmith.chat.registry import chat_command_registry" in source
    assert "system_commands" not in source
    assert "memory_instruction_commands" not in source
    assert "diff_apply_commands" not in source
    assert "checkpoint_commands" not in source
