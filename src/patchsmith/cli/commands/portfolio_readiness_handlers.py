"""Portfolio readiness CLI command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from patchsmith.cli.commands.portfolio_handler_payloads import (
    delivery_audit_payload,
    docker_smoke_payload,
    environment_readiness_payload,
    launch_blockers_payload,
    mvp_progress_payload,
    print_json_payload,
    release_hygiene_payload,
)
from patchsmith.portfolio import (
    write_delivery_audit_report,
    write_docker_smoke_report,
    write_environment_readiness_report,
    write_launch_blocker_report,
    write_mvp_progress_report,
    write_release_hygiene_report,
)


def _docker_smoke_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_docker_smoke_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        image=args.image,
        task_dir=Path(args.task_dir),
        test_command=args.test_command,
        runtime=args.runtime,
        context_provider=args.context_provider,
        docker_binary=args.docker_binary,
        run_seeded=not args.skip_run,
    )
    if args.json:
        print_json_payload(
            docker_smoke_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Docker smoke report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.smoke_status} "
            f"Image: {report.image} "
            f"Run: {report.run_id or 'n/a'} "
            f"Test exit: {report.test_exit_code if report.test_exit_code is not None else 'n/a'}"
        )
    return 0


def _environment_readiness_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_environment_readiness_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print_json_payload(
            environment_readiness_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Environment readiness report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.readiness_status} "
            f"Passed: {report.passed_count} "
            f"Warnings: {report.warning_count} "
            f"Blocked: {report.blocked_count}"
        )
    return 0


def _release_hygiene_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_release_hygiene_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print_json_payload(
            release_hygiene_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Release hygiene report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.release_status} "
            f"Passed: {report.passed_count} "
            f"Warnings: {report.warning_count} "
            f"Blocked: {report.blocked_count}"
        )
    return 0


def _launch_blockers_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_launch_blocker_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print_json_payload(
            launch_blockers_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Launch blocker report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.launch_status} "
            f"Items: {report.item_count} "
            f"Blocked: {report.blocked_count} "
            f"Warnings: {report.warning_count}"
        )
    return 0


def _mvp_progress_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_mvp_progress_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print_json_payload(
            mvp_progress_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"MVP progress report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.status} "
            f"Completion: {report.completion_percent:.1f}% "
            f"Passed: {report.passed_count} "
            f"Warnings: {report.warning_count} "
            f"Missing: {report.missing_count} "
            f"Blocked: {report.blocked_count}"
        )
    return 0


def _delivery_audit_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_delivery_audit_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print_json_payload(
            delivery_audit_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Delivery audit report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.delivery_status} "
            f"Completion: {report.completion_percent:.1f}% "
            f"Passed: {report.passed_count} "
            f"Warnings: {report.warning_count} "
            f"Missing: {report.missing_count} "
            f"Blocked: {report.blocked_count}"
        )
    return 0


__all__ = [
    "_delivery_audit_command",
    "_docker_smoke_command",
    "_environment_readiness_command",
    "_launch_blockers_command",
    "_mvp_progress_command",
    "_release_hygiene_command",
]
