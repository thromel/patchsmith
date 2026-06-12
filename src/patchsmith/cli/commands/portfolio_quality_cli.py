"""Portfolio quality and status CLI parser registration."""

from __future__ import annotations

import argparse

from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS


def register_portfolio_quality_commands(subparsers: argparse._SubParsersAction) -> None:
    quality_gate = subparsers.add_parser(
        "quality-gate",
        help="Run local verification commands and save a quality-gate report.",
    )
    quality_gate.add_argument(
        "--project-root",
        default=".",
        help="Project root where verification commands run.",
    )
    quality_gate.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write logs under.",
    )
    quality_gate.add_argument(
        "--output",
        default="artifacts/experiments/quality_gate.md",
        help="Markdown quality-gate report output path.",
    )
    quality_gate.add_argument(
        "--json-output",
        default="artifacts/experiments/quality_gate.json",
        help="Optional JSON quality-gate output path.",
    )
    quality_gate.add_argument(
        "--logs-dir",
        help="Directory for per-command stdout/stderr logs.",
    )
    quality_gate.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
        help="Per-command timeout in seconds.",
    )
    quality_gate.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the full pytest gate.",
    )
    quality_gate.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the package build gate.",
    )
    quality_gate.add_argument("--json", action="store_true", help="Print JSON summary.")

    project_status = subparsers.add_parser(
        "project-status",
        help="Generate a consolidated status report from saved evidence artifacts.",
    )
    project_status.add_argument(
        "--project-root",
        default=".",
        help="Project root to include in the status report.",
    )
    project_status.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    project_status.add_argument(
        "--output",
        default="artifacts/experiments/project_status.md",
        help="Markdown project status report output path.",
    )
    project_status.add_argument(
        "--json-output",
        default="artifacts/experiments/project_status.json",
        help="Optional JSON project status output path.",
    )
    project_status.add_argument("--json", action="store_true", help="Print JSON summary.")

    refresh_evidence = subparsers.add_parser(
        "refresh-evidence",
        help="Regenerate saved review/status evidence artifacts in dependency order.",
    )
    refresh_evidence.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, Git metadata, and quality-gate context.",
    )
    refresh_evidence.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to refresh.",
    )
    refresh_evidence.add_argument(
        "--output",
        default="artifacts/experiments/evidence_refresh.md",
        help="Markdown evidence-refresh report output path.",
    )
    refresh_evidence.add_argument(
        "--json-output",
        default="artifacts/experiments/evidence_refresh.json",
        help="Optional JSON evidence-refresh output path.",
    )
    refresh_evidence.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    refresh_evidence.add_argument(
        "--include-quality-gate",
        action="store_true",
        help="Also run the full quality gate during refresh.",
    )
    refresh_evidence.add_argument(
        "--quality-timeout-seconds",
        type=int,
        default=DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
        help="Per-command timeout for quality-gate steps when included.",
    )
    refresh_evidence.add_argument(
        "--include-docker-smoke",
        action="store_true",
        help="Also refresh Docker sandbox smoke evidence before launch/status reports.",
    )
    refresh_evidence.add_argument(
        "--docker-smoke-skip-run",
        action="store_true",
        help="When Docker smoke is included, stop after daemon/image preflight.",
    )
    refresh_evidence.add_argument(
        "--docker-smoke-image",
        default="patchsmith-seeded-smoke:py312",
        help="Local Docker image to inspect and optionally run for Docker smoke.",
    )
    refresh_evidence.add_argument(
        "--docker-binary",
        default="docker",
        help="Docker CLI binary used when Docker smoke is included.",
    )
    refresh_evidence.add_argument("--json", action="store_true", help="Print JSON summary.")


__all__ = ["register_portfolio_quality_commands"]
