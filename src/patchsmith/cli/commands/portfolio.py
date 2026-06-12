"""CLI portfolio commands."""

from __future__ import annotations

import argparse

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands.portfolio_calibration_cli import (
    register_portfolio_calibration_commands,
)
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
from patchsmith.cli.commands.portfolio_quality_cli import register_portfolio_quality_commands
from patchsmith.cli.commands.portfolio_readiness_cli import (
    register_portfolio_readiness_commands,
)


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    register_portfolio_calibration_commands(subparsers)
    register_portfolio_readiness_commands(subparsers)
    register_portfolio_quality_commands(subparsers)
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
