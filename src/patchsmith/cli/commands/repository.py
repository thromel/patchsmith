"""Direct repository indexing and retrieval CLI commands."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from patchsmith.cli._args import (
    _add_issue_args,
    _add_repo_args,
    _load_issue_text,
    _retriever_for,
)
from patchsmith.cli._types import CommandHandler
from patchsmith.ingest import clone_or_copy_repository, index_repository


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
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
        "index": _index_command,
        "retrieve": _retrieve_command,
    }


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
