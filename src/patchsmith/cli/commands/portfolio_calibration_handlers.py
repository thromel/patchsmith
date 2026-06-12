"""Portfolio calibration CLI command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from patchsmith.cli.commands.portfolio_handler_payloads import (
    live_calibration_payload,
    live_calibration_plan_payload,
    print_json_payload,
)
from patchsmith.portfolio import (
    write_live_calibration_plan_report,
    write_live_calibration_report,
)


def _live_calibration_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_live_calibration_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print_json_payload(
            live_calibration_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Live calibration report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.calibration_status} "
            f"Saved live-provider runs: {report.saved_live_provider_count} "
            f"DeepAgents package runs: {report.deepagents_package_run_count} "
            f"OpenAI Agents package runs: {report.openai_agents_package_run_count}"
        )
    return 0


def _live_calibration_plan_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_live_calibration_plan_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    ready_runs = sum(1 for run in report.runs if run.status == "ready")
    blocked_runs = sum(1 for run in report.runs if run.status == "blocked")
    if args.json:
        print_json_payload(
            live_calibration_plan_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
                ready_runs=ready_runs,
                blocked_runs=blocked_runs,
            )
        )
    else:
        print(f"Live calibration plan: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.plan_status} "
            f"Runs: {len(report.runs)} "
            f"Ready: {ready_runs} "
            f"Blocked: {blocked_runs}"
        )
    return 0


__all__ = [
    "_live_calibration_command",
    "_live_calibration_plan_command",
]
