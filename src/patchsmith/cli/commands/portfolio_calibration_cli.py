"""Portfolio calibration and smoke CLI parser registration."""

from __future__ import annotations

import argparse


def register_portfolio_calibration_commands(subparsers: argparse._SubParsersAction) -> None:
    live_calibration = subparsers.add_parser(
        "live-calibration",
        help="Generate a live-provider calibration readiness report.",
    )
    live_calibration.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan for saved provider evidence.",
    )
    live_calibration.add_argument(
        "--output",
        default="artifacts/experiments/calibration_readiness.md",
        help="Markdown live calibration readiness report output path.",
    )
    live_calibration.add_argument(
        "--json-output",
        help="Optional JSON live calibration readiness report output path.",
    )
    live_calibration.add_argument("--json", action="store_true", help="Print JSON summary.")

    live_calibration_plan = subparsers.add_parser(
        "live-calibration-plan",
        help="Generate an executable live-provider calibration plan.",
    )
    live_calibration_plan.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan for saved provider evidence.",
    )
    live_calibration_plan.add_argument(
        "--output",
        default="artifacts/experiments/live_calibration_plan.md",
        help="Markdown live calibration plan output path.",
    )
    live_calibration_plan.add_argument(
        "--json-output",
        default="artifacts/experiments/live_calibration_plan.json",
        help="Optional JSON live calibration plan output path.",
    )
    live_calibration_plan.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    docker_smoke = subparsers.add_parser(
        "docker-smoke",
        help="Generate Docker sandbox preflight and seeded-smoke evidence.",
    )
    docker_smoke.add_argument(
        "--project-root",
        default=".",
        help="Project root containing the seeded task and Dockerfile.",
    )
    docker_smoke.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write smoke evidence.",
    )
    docker_smoke.add_argument(
        "--output",
        default="artifacts/experiments/docker_smoke.md",
        help="Markdown Docker smoke report output path.",
    )
    docker_smoke.add_argument(
        "--json-output",
        default="artifacts/experiments/docker_smoke.json",
        help="Optional JSON Docker smoke report output path.",
    )
    docker_smoke.add_argument(
        "--image",
        default="patchsmith-seeded-smoke:py312",
        help="Local Docker image containing Python and seeded-suite test dependencies.",
    )
    docker_smoke.add_argument(
        "--task-dir",
        default="evals/tasks/seeded_bugs_v1/task_001_logic_bug",
        help="Seeded task directory to run inside Docker.",
    )
    docker_smoke.add_argument(
        "--test-command",
        default="python3 -m pytest",
        help="Policy-allowed test command to run inside Docker.",
    )
    docker_smoke.add_argument(
        "--runtime",
        choices=["heuristic", "langgraph", "deepagents", "openai_agents"],
        default="heuristic",
        help="Runtime to use for the smoke repair.",
    )
    docker_smoke.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context provider to use for the smoke repair.",
    )
    docker_smoke.add_argument(
        "--docker-binary",
        default="docker",
        help="Docker CLI binary to use for preflight checks.",
    )
    docker_smoke.add_argument(
        "--skip-run",
        action="store_true",
        help="Only run Docker daemon and image preflight checks.",
    )
    docker_smoke.add_argument("--json", action="store_true", help="Print JSON summary.")


__all__ = ["register_portfolio_calibration_commands"]
