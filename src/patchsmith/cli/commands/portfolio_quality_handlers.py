"""Portfolio quality and status CLI command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from patchsmith.cli.commands.portfolio_handler_payloads import (
    evidence_refresh_payload,
    print_json_payload,
    project_status_payload,
    quality_gate_payload,
)
from patchsmith.portfolio import (
    write_evidence_refresh_report,
    write_project_status_report,
    write_quality_gate_report,
)


def _quality_gate_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    report = write_quality_gate_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        logs_dir=logs_dir,
        timeout_seconds=args.timeout_seconds,
        include_tests=not args.skip_tests,
        include_build=not args.skip_build,
    )
    if args.json:
        print_json_payload(
            quality_gate_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Quality gate report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.quality_status} "
            f"Passed: {report.passed_count} "
            f"Failed: {report.failed_count} "
            f"Skipped: {report.skipped_count}"
        )
    return 0


def _project_status_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_project_status_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print_json_payload(
            project_status_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Project status report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.overall_status} "
            f"MVP: {report.mvp_completion_percent:.1f}% "
            f"Delivery: {report.delivery_completion_percent:.1f}% "
            f"Launch: {report.launch_status} "
            f"Quality: {report.quality_status} "
            f"Environment: {report.environment_readiness_status} "
            f"Freshness: {report.evidence_freshness_status}"
        )
    return 0


def _refresh_evidence_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_evidence_refresh_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
        include_quality_gate=args.include_quality_gate,
        quality_timeout_seconds=args.quality_timeout_seconds,
        include_docker_smoke=args.include_docker_smoke,
        docker_smoke_skip_run=args.docker_smoke_skip_run,
        docker_smoke_image=args.docker_smoke_image,
        docker_binary=args.docker_binary,
    )
    if args.json:
        print_json_payload(
            evidence_refresh_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Evidence refresh report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.refresh_status} "
            f"Steps: {report.step_count} "
            f"Passed: {report.passed_count} "
            f"Failed: {report.failed_count} "
            f"Skipped: {report.skipped_count} "
            f"Docker: {str(report.docker_smoke_refreshed).lower()}"
        )
    return 0


__all__ = [
    "_project_status_command",
    "_quality_gate_command",
    "_refresh_evidence_command",
]
