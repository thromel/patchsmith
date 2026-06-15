"""PatchSmith command-line interface."""

from __future__ import annotations

import argparse

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands import (
    demo,
    evals,
    issue_corpus,
    model_preflight,
    observability,
    portfolio,
    run,
)

_COMMAND_MODULES = (
    run,
    model_preflight,
    demo,
    evals,
    issue_corpus,
    observability,
    portfolio,
)


def _build_parser_and_handlers() -> tuple[argparse.ArgumentParser, dict[str, CommandHandler]]:
    parser = argparse.ArgumentParser(prog="patchsmith")
    subparsers = parser.add_subparsers(dest="command")
    handlers: dict[str, CommandHandler] = {}
    for module in _COMMAND_MODULES:
        handlers.update(module.register(subparsers))
    return parser, handlers


def build_parser() -> argparse.ArgumentParser:
    parser, _handlers = _build_parser_and_handlers()
    return parser


def main(argv: list[str] | None = None) -> int:
    parser, handlers = _build_parser_and_handlers()
    args = parser.parse_args(argv)
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)
