"""Shared CLI argument helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever


def _add_repo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True, help="Local path or public Git repository URL.")
    parser.add_argument("--commit", help="Optional commit hash to check out.")
    parser.add_argument("--branch", help="Optional branch to check out.")


def _add_issue_args(parser: argparse.ArgumentParser) -> None:
    issue_group = parser.add_mutually_exclusive_group(required=True)
    issue_group.add_argument("--issue", help="Raw issue text.")
    issue_group.add_argument("--issue-file", help="Path to a file containing issue text.")
    parser.add_argument("--issue-url", help="Optional source issue URL for the run report.")


def _add_sandbox_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="local",
        help="Sandbox runner for executing task test commands.",
    )
    parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode=docker.",
    )


def _load_issue_text(args: argparse.Namespace) -> str:
    if args.issue_file:
        return Path(args.issue_file).read_text(encoding="utf-8")
    return args.issue


def _retriever_for(name: str) -> object:
    if name == "native_hybrid":
        return HybridRetriever()
    if name == "native_graph":
        return GraphRetriever()
    return KeywordRetriever()
