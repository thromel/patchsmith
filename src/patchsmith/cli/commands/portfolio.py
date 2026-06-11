"""CLI portfolio commands."""

from __future__ import annotations

import argparse

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands.portfolio_demo_cli import register_demo_commands
from patchsmith.cli.commands.portfolio_handlers import (
    _delivery_audit_command,
    _docker_smoke_command,
    _environment_readiness_command,
    _launch_blockers_command,
    _live_calibration_command,
    _live_calibration_plan_command,
    _mvp_progress_command,
    _project_status_command,
    _quality_gate_command,
    _refresh_evidence_command,
    _release_hygiene_command,
)
from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
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

    handlers: dict[str, CommandHandler] = {
        "live-calibration": _live_calibration_command,
        "live-calibration-plan": _live_calibration_plan_command,
        "docker-smoke": _docker_smoke_command,
        "environment-readiness": _environment_readiness_command,
        "release-hygiene": _release_hygiene_command,
        "launch-blockers": _launch_blockers_command,
        "mvp-progress": _mvp_progress_command,
        "delivery-audit": _delivery_audit_command,
        "quality-gate": _quality_gate_command,
        "project-status": _project_status_command,
        "refresh-evidence": _refresh_evidence_command,
    }
    handlers.update(register_demo_commands(subparsers))
    return handlers
