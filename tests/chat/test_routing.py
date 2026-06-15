from __future__ import annotations

import pytest

from patchsmith.chat.routing import (
    memory_note_from_natural_command,
    normalized_natural_command,
    parse_slash_command,
    route_natural_command,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/help", ("help", "")),
        ("/diff review", ("diff", "review")),
        ("/memory add keep parser fixes focused", ("memory", "add keep parser fixes focused")),
        ("/", ("help", "")),
    ],
)
def test_parse_slash_command(raw: str, expected: tuple[str, str]) -> None:
    assert parse_slash_command(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("what next?", "/next"),
        ("show status", "/status"),
        ("review diff", "/diff review"),
        ("apply check", "/apply check"),
        ("cancel plan", "/cancel plan"),
        ("show memory", "/memory show"),
        ("reload memory", "/memory reload"),
        ("clear memory", "/memory clear"),
        ("preflight fix parser", "/preflight fix parser"),
        ("remember that parser fixes stay minimal", "/memory add parser fixes stay minimal"),
        ("add project memory prefer focused tests", "/memory add prefer focused tests"),
    ],
)
def test_route_natural_command(raw: str, expected: str) -> None:
    assert route_natural_command(raw) == expected


def test_route_natural_command_leaves_tasks_unrouted() -> None:
    assert route_natural_command("fix the parser bug") is None


def test_memory_note_from_natural_command() -> None:
    assert memory_note_from_natural_command("remember to run focused tests") == (
        "run focused tests"
    )
    assert memory_note_from_natural_command("remember") is None


def test_normalized_natural_command() -> None:
    assert normalized_natural_command("  What   NEXT?! ") == "what next"
