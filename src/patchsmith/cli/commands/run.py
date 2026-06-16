"""CLI run commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.agent_cli import (
    run_result_payload,
)
from patchsmith.cli._args import (
    _add_issue_args,
    _add_repo_args,
    _add_sandbox_args,
    _load_issue_text,
)
from patchsmith.cli._types import CommandHandler
from patchsmith.cli.result_output import print_run_result
from patchsmith.models import RunRequest
from patchsmith.workflow import RepairRunner


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    run = subparsers.add_parser("run", help="Run the MVP issue-to-report lifecycle.")
    _add_repo_args(run)
    _add_issue_args(run)
    run.add_argument("--test-command", help="Allowed test command to run in the sandbox.")
    run.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "deepagents"],
        default="agentless",
        help="Runtime label for the run report.",
    )
    run.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai", "deepagents"],
        default="heuristic",
        help="Repair planner used by model-capable runtimes.",
    )
    run.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra DeepAgents feedback retries after the first attempt.",
    )
    run.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native",
        help="Context broker to use before agent execution.",
    )
    run.add_argument(
        "--context-path",
        action="append",
        default=[],
        help=(
            "Repo-relative file to force into the repair context. Repeat for multiple files; "
            "an optional #symbol suffix is accepted for traceability."
        ),
    )
    run.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")
    run.add_argument("--artifacts-dir", default="artifacts", help="Artifact output directory.")
    _add_sandbox_args(run)
    run.add_argument("--json", action="store_true", help="Print machine-readable run summary.")

    return {"run": _run_command}


def _run_command(args: argparse.Namespace) -> int:
    issue_text = _load_issue_text(args)
    request = RunRequest(
        repo=args.repo,
        issue_text=issue_text,
        issue_url=args.issue_url,
        commit=args.commit,
        branch=args.branch,
        test_command=args.test_command,
        runtime=args.runtime,
        planner=args.planner,
        max_retries=args.max_retries,
        retrieval_strategy=args.context_provider,
        context_provider=args.context_provider,
        top_k=args.top_k,
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        context_paths=tuple(args.context_path or ()),
    )
    result = RepairRunner(artifacts_dir=Path(args.artifacts_dir)).run(request)
    if args.json:
        print(
            json.dumps(
                run_result_payload(result, runtime=args.runtime, planner=args.planner),
                indent=2,
            )
        )
    else:
        print_run_result(result)
    return 0
