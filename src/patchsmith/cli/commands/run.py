"""CLI run commands."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from patchsmith.cli._args import (
    _add_issue_args,
    _add_repo_args,
    _add_sandbox_args,
    _load_issue_text,
    _retriever_for,
)
from patchsmith.cli._types import CommandHandler
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.model_config import DEFAULT_OPENAI_MODEL
from patchsmith.model_preflight import openai_model_preflight_from_env
from patchsmith.models import RunRequest
from patchsmith.workflow import RepairRunner


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    run = subparsers.add_parser("run", help="Run the MVP issue-to-report lifecycle.")
    _add_repo_args(run)
    _add_issue_args(run)
    run.add_argument("--test-command", help="Allowed test command to run in the sandbox.")
    run.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "langgraph", "deepagents", "openai_agents"],
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
        help="Maximum extra LangGraph planning/edit retries after the first attempt.",
    )
    run.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native",
        help="Context broker to use before agent execution.",
    )
    run.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")
    run.add_argument("--artifacts-dir", default="artifacts", help="Artifact output directory.")
    _add_sandbox_args(run)
    run.add_argument("--json", action="store_true", help="Print machine-readable run summary.")

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

    index = subparsers.add_parser(
        "index", help="Clone/copy a repository and print file index JSON."
    )
    _add_repo_args(index)

    retrieve = subparsers.add_parser("retrieve", help="Run keyword retrieval and print JSON.")
    _add_repo_args(retrieve)
    _add_issue_args(retrieve)
    retrieve.add_argument(
        "--retrieval",
        choices=["keyword", "native_hybrid", "native_graph"],
        default="keyword",
        help="Retrieval strategy for this direct retrieval command.",
    )
    retrieve.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")

    return {
        "run": _run_command,
        "openai-model-preflight": _openai_model_preflight_command,
        "index": _index_command,
        "retrieve": _retrieve_command,
    }


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
    )
    result = RepairRunner(artifacts_dir=Path(args.artifacts_dir)).run(request)
    if args.json:
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "status": result.status,
                    "runtime": args.runtime,
                    "planner": args.planner,
                    "report_path": str(result.report_path),
                    "trace_path": str(result.trace_path),
                    "final_diff_path": str(result.final_diff_path),
                    "test_exit_code": (
                        result.test_result.exit_code if result.test_result else None
                    ),
                    "retrieved_files": [context.path for context in result.retrieved_context],
                },
                indent=2,
            )
        )
    else:
        print(f"Run ID: {result.run_id}")
        print(f"Status: {result.status}")
        print(f"Report: {result.report_path}")
        if result.test_result:
            print(f"Test exit code: {result.test_result.exit_code}")
        if result.retrieved_context:
            print("Top retrieved files:")
            for context in result.retrieved_context[:5]:
                print(f"  {context.rank}. {context.path} ({context.score:.2f})")
    return 0


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


def _index_command(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="patchsmith-index-") as tmp_dir:
        repo_path = clone_or_copy_repository(
            args.repo,
            Path(tmp_dir) / "repo",
            commit=args.commit,
            branch=args.branch,
        ).repo_path
        repo_index = index_repository(repo_path)
        print(json.dumps(repo_index.to_dict(), indent=2))
    return 0


def _retrieve_command(args: argparse.Namespace) -> int:
    issue_text = _load_issue_text(args)
    with tempfile.TemporaryDirectory(prefix="patchsmith-retrieve-") as tmp_dir:
        snapshot = clone_or_copy_repository(
            args.repo,
            Path(tmp_dir) / "repo",
            commit=args.commit,
            branch=args.branch,
        )
        repo_index = index_repository(snapshot.repo_path)
        retriever = _retriever_for(args.retrieval)
        contexts = retriever.retrieve(
            repo_path=snapshot.repo_path,
            repo_index=repo_index,
            issue_text=issue_text,
            top_k=args.top_k,
        )
        print(json.dumps([context.to_dict() for context in contexts], indent=2))
    return 0
