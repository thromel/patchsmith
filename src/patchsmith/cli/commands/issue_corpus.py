"""CLI issue corpus commands."""

from __future__ import annotations

import argparse

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands.issue_corpus_base_cli import (
    register_base_issue_corpus_commands,
)
from patchsmith.cli.commands.issue_corpus_focused_cli import (
    register_focused_issue_corpus_commands,
)
from patchsmith.cli.commands.issue_corpus_handlers import issue_corpus_command_handlers
from patchsmith.cli.commands.public_issue_cli import register_public_issue_commands


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    register_base_issue_corpus_commands(subparsers)
    register_focused_issue_corpus_commands(subparsers)
    handlers = issue_corpus_command_handlers()
    handlers.update(register_public_issue_commands(subparsers))
    return handlers
