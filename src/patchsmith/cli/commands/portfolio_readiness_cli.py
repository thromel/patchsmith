"""Portfolio readiness and release review CLI parser registration."""

from __future__ import annotations

import argparse


def register_portfolio_readiness_commands(subparsers: argparse._SubParsersAction) -> None:
    environment_readiness = subparsers.add_parser(
        "environment-readiness",
        help="Summarize current launch environment prerequisites from saved evidence.",
    )
    environment_readiness.add_argument(
        "--project-root",
        default=".",
        help="Project root to include in the environment readiness report.",
    )
    environment_readiness.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to inspect.",
    )
    environment_readiness.add_argument(
        "--output",
        default="artifacts/experiments/environment_readiness.md",
        help="Markdown environment readiness report output path.",
    )
    environment_readiness.add_argument(
        "--json-output",
        default="artifacts/experiments/environment_readiness.json",
        help="Optional JSON environment readiness output path.",
    )
    environment_readiness.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    release_hygiene = subparsers.add_parser(
        "release-hygiene",
        help="Generate a release hygiene checklist from saved artifacts and project files.",
    )
    release_hygiene.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, Git metadata, CI, and public assets.",
    )
    release_hygiene.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    release_hygiene.add_argument(
        "--output",
        default="artifacts/experiments/release_hygiene.md",
        help="Markdown release hygiene report output path.",
    )
    release_hygiene.add_argument(
        "--json-output",
        help="Optional JSON release hygiene report output path.",
    )
    release_hygiene.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    release_hygiene.add_argument("--json", action="store_true", help="Print JSON summary.")

    launch_blockers = subparsers.add_parser(
        "launch-blockers",
        help="Generate a prioritized launch-blocker backlog from readiness artifacts.",
    )
    launch_blockers.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    launch_blockers.add_argument(
        "--output",
        default="artifacts/experiments/launch_blockers.md",
        help="Markdown launch-blocker backlog output path.",
    )
    launch_blockers.add_argument(
        "--json-output",
        default="artifacts/experiments/launch_blockers.json",
        help="Optional JSON launch-blocker backlog output path.",
    )
    launch_blockers.add_argument("--json", action="store_true", help="Print JSON summary.")

    mvp_progress = subparsers.add_parser(
        "mvp-progress",
        help="Generate an evidence-weighted MVP checklist progress report.",
    )
    mvp_progress.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for source, docs, tests, and checklist evidence.",
    )
    mvp_progress.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    mvp_progress.add_argument(
        "--output",
        default="artifacts/experiments/mvp_progress.md",
        help="Markdown MVP progress report output path.",
    )
    mvp_progress.add_argument(
        "--json-output",
        help="Optional JSON MVP progress report output path.",
    )
    mvp_progress.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    mvp_progress.add_argument("--json", action="store_true", help="Print JSON summary.")

    delivery_audit = subparsers.add_parser(
        "delivery-audit",
        help="Generate an objective-to-evidence delivery audit report.",
    )
    delivery_audit.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, tests, and Git metadata.",
    )
    delivery_audit.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    delivery_audit.add_argument(
        "--output",
        default="artifacts/experiments/delivery_audit.md",
        help="Markdown delivery audit output path.",
    )
    delivery_audit.add_argument(
        "--json-output",
        default="artifacts/experiments/delivery_audit.json",
        help="Optional JSON delivery audit output path.",
    )
    delivery_audit.add_argument("--json", action="store_true", help="Print JSON summary.")


__all__ = ["register_portfolio_readiness_commands"]
