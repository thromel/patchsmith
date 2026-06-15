"""CLI command for OpenAI model availability preflight."""

from __future__ import annotations

import argparse
import json

from patchsmith.cli._types import CommandHandler
from patchsmith.model_config import DEFAULT_OPENAI_MODEL
from patchsmith.model_preflight import openai_model_preflight_from_env


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    model_preflight = subparsers.add_parser(
        "openai-model-preflight",
        help="Check whether the configured OpenAI account exposes a model id.",
    )
    model_preflight.add_argument(
        "--model",
        default=DEFAULT_OPENAI_MODEL,
        help="Model id to check before running live repair evaluation.",
    )
    model_preflight.add_argument(
        "--endpoint",
        default="https://api.openai.com/v1/models",
        help="OpenAI Models API endpoint.",
    )
    model_preflight.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout for the model availability request.",
    )
    model_preflight.add_argument("--json", action="store_true", help="Print JSON result.")
    return {"openai-model-preflight": _openai_model_preflight_command}


def _openai_model_preflight_command(args: argparse.Namespace) -> int:
    result = openai_model_preflight_from_env(
        model=args.model,
        endpoint=args.endpoint,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Model: {result.model}")
        print(f"Status: {result.status}")
        print(f"Available: {result.available}")
        if result.suggestions:
            print("Suggestions:")
            for suggestion in result.suggestions:
                print(f"  - {suggestion}")
        if result.error:
            print(f"Error: {result.error}")
    return 0 if result.available else 2
