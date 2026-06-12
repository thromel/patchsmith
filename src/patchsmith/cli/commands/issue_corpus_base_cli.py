"""Base issue corpus CLI parser registration."""

from __future__ import annotations

import argparse


def register_base_issue_corpus_commands(subparsers: argparse._SubParsersAction) -> None:
    validate_issue_corpus_parser = subparsers.add_parser(
        "validate-issue-corpus",
        help="Validate public issue-corpus metadata for real-world eval planning.",
    )
    validate_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    validate_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus validation output directory.",
    )
    validate_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preflight_issue_corpus_parser = subparsers.add_parser(
        "preflight-issue-corpus",
        help="Check repository reachability for public issue-corpus entries.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus preflight output directory.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Per-repository git ls-remote timeout.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preview_issue_corpus_parser = subparsers.add_parser(
        "preview-issue-corpus-context",
        help="Clone/index public issue-corpus repos and write retrieval preview artifacts.",
    )
    preview_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preview_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus context preview output directory.",
    )
    preview_issue_corpus_parser.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph"],
        default="native_hybrid",
        help="Retriever to use for source-free public issue context previews.",
    )
    preview_issue_corpus_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved files to record per issue.",
    )
    preview_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to preview. Use 0 for all entries.",
    )
    preview_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialize_issue_corpus_parser = subparsers.add_parser(
        "materialize-issue-corpus-tasks",
        help="Write source-free task manifests from public issue context-preview results.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus materialization output directory.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--context-preview",
        default=None,
        help="Context preview results JSON. Defaults to <output>/context_preview_results.json.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to materialize. Use 0 for all entries.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    validate_materialized_issue_tasks_parser = subparsers.add_parser(
        "validate-materialized-issue-tasks",
        help="Validate source-free public issue task manifests and runbooks.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized task validation output directory.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialized_run_readiness_parser = subparsers.add_parser(
        "check-materialized-run-readiness",
        help="Check policy and risk readiness before running materialized public issue tasks.",
    )
    materialized_run_readiness_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    materialized_run_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized run readiness output directory.",
    )
    materialized_run_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )


__all__ = ["register_base_issue_corpus_commands"]
