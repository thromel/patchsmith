"""Portfolio CLI command handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.portfolio import (
    write_delivery_audit_report,
    write_docker_smoke_report,
    write_environment_readiness_report,
    write_evidence_refresh_report,
    write_launch_blocker_report,
    write_live_calibration_plan_report,
    write_live_calibration_report,
    write_mvp_progress_report,
    write_project_status_report,
    write_quality_gate_report,
    write_release_hygiene_report,
)


def _live_calibration_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    report = write_live_calibration_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "calibration_status": report.calibration_status,
                    "saved_live_provider_count": report.saved_live_provider_count,
                    "deepagents_package_run_count": report.deepagents_package_run_count,
                    "deepagents_compatibility_run_count": (
                        report.deepagents_compatibility_run_count
                    ),
                    "openai_agents_package_run_count": (report.openai_agents_package_run_count),
                    "openai_agents_compatibility_run_count": (
                        report.openai_agents_compatibility_run_count
                    ),
                    "model_providers": report.model_providers,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "plan_status": report.plan_status,
                    "calibration_status": report.calibration_status,
                    "saved_live_provider_count": report.saved_live_provider_count,
                    "run_count": len(report.runs),
                    "ready_runs": ready_runs,
                    "blocked_runs": blocked_runs,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "smoke_status": report.smoke_status,
                    "image": report.image,
                    "task_dir": report.task_dir,
                    "run_id": report.run_id,
                    "test_exit_code": report.test_exit_code,
                    "environment": report.environment,
                    "remediation_commands": report.remediation_commands,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "readiness_status": report.readiness_status,
                    "passed_count": report.passed_count,
                    "warning_count": report.warning_count,
                    "blocked_count": report.blocked_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "release_status": report.release_status,
                    "passed_count": report.passed_count,
                    "warning_count": report.warning_count,
                    "blocked_count": report.blocked_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "launch_status": report.launch_status,
                    "item_count": report.item_count,
                    "blocked_count": report.blocked_count,
                    "warning_count": report.warning_count,
                    "ready_count": report.ready_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "status": report.status,
                    "completion_percent": report.completion_percent,
                    "item_count": report.item_count,
                    "passed_count": report.passed_count,
                    "warning_count": report.warning_count,
                    "blocked_count": report.blocked_count,
                    "missing_count": report.missing_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "delivery_status": report.delivery_status,
                    "completion_percent": report.completion_percent,
                    "item_count": report.item_count,
                    "passed_count": report.passed_count,
                    "warning_count": report.warning_count,
                    "blocked_count": report.blocked_count,
                    "missing_count": report.missing_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "quality_status": report.quality_status,
                    "passed_count": report.passed_count,
                    "failed_count": report.failed_count,
                    "skipped_count": report.skipped_count,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "overall_status": report.overall_status,
                    "mvp_status": report.mvp_status,
                    "mvp_completion_percent": report.mvp_completion_percent,
                    "delivery_status": report.delivery_status,
                    "delivery_completion_percent": report.delivery_completion_percent,
                    "quality_status": report.quality_status,
                    "launch_status": report.launch_status,
                    "release_status": report.release_status,
                    "docker_smoke_status": report.docker_smoke_status,
                    "environment_readiness_status": (report.environment_readiness_status),
                    "live_calibration_status": report.live_calibration_status,
                    "saved_live_provider_count": report.saved_live_provider_count,
                    "blocker_count": report.blocker_count,
                    "warning_count": report.warning_count,
                    "evidence_freshness_status": report.evidence_freshness_status,
                    "stale_source_count": report.stale_source_count,
                    "undated_source_count": report.undated_source_count,
                    "missing_source_count": len(report.missing_sources),
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
        print(
            json.dumps(
                {
                    "project_root": report.project_root,
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "refresh_status": report.refresh_status,
                    "step_count": report.step_count,
                    "passed_count": report.passed_count,
                    "failed_count": report.failed_count,
                    "skipped_count": report.skipped_count,
                    "quality_gate_refreshed": report.quality_gate_refreshed,
                    "docker_smoke_refreshed": report.docker_smoke_refreshed,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
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
