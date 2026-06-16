"""Portfolio quality and status CLI command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from patchsmith.cli.commands.portfolio_handler_payloads import (
    evidence_refresh_payload,
    print_json_payload,
    project_status_payload,
    quality_gate_payload,
    release_gate_payload,
)
from patchsmith.portfolio import (
    write_evidence_refresh_report,
    write_project_status_report,
    write_quality_gate_report,
    write_release_gate_report,
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


def _release_gate_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    benchmark_results_path = Path(args.benchmark_results) if args.benchmark_results else None
    report = write_release_gate_report(
        project_root=Path(args.project_root),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        logs_dir=logs_dir,
        timeout_seconds=args.timeout_seconds,
        include_unit_tests=not args.skip_unit_tests,
        include_smoke=not args.skip_smoke,
        include_build=not args.skip_build,
        include_cli_help=not args.skip_cli_help,
        include_sample_transcript_export=not args.skip_sample_transcript_export,
        include_benchmark_validation=not args.skip_benchmark_validation,
        benchmark_results_path=benchmark_results_path,
    )
    if args.json:
        print_json_payload(
            release_gate_payload(
                report,
                output=args.output,
                json_output_path=json_output_path,
            )
        )
    else:
        print(f"Release gate report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.release_status} "
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
        include_complex_suite=args.include_complex_suite,
        complex_suite_spec_path=(
            Path(args.complex_suite_spec) if args.complex_suite_spec else None
        ),
        complex_suite_attempt_dirs=tuple(Path(path) for path in args.complex_suite_attempt_dir),
        complex_suite_output_dir=(
            Path(args.complex_suite_output_dir) if args.complex_suite_output_dir else None
        ),
        complex_suite_benchmark=args.complex_suite_benchmark,
        complex_suite_min_validation_rate=args.complex_suite_min_validation_rate,
        complex_suite_min_live_provider_tasks=(args.complex_suite_min_live_provider_tasks),
        complex_suite_min_unique_tasks=args.complex_suite_min_unique_tasks,
        complex_suite_max_selected_cost_per_validated_task_usd=(
            args.complex_suite_max_selected_cost_per_validated_task_usd
        ),
        complex_suite_max_selected_tokens_per_validated_task=(
            args.complex_suite_max_selected_tokens_per_validated_task
        ),
        complex_suite_max_selected_virtual_files_per_validated_task=(
            args.complex_suite_max_selected_virtual_files_per_validated_task
        ),
        complex_suite_max_selected_tokens_per_virtual_file=(
            args.complex_suite_max_selected_tokens_per_virtual_file
        ),
        complex_suite_max_selected_responses_per_virtual_file=(
            args.complex_suite_max_selected_responses_per_virtual_file
        ),
        complex_suite_min_selected_progress_score=(args.complex_suite_min_selected_progress_score),
        complex_suite_min_selected_context_target_recall=(
            args.complex_suite_min_selected_context_target_recall
        ),
        complex_suite_min_selected_context_target_precision=(
            args.complex_suite_min_selected_context_target_precision
        ),
        complex_suite_min_repo_instructions_manifest_rate=(
            args.complex_suite_min_repo_instructions_manifest_rate
        ),
        complex_suite_min_repo_instructions_read_first_rate=(
            args.complex_suite_min_repo_instructions_read_first_rate
        ),
        complex_suite_min_acceptance_rubric_manifest_rate=(
            args.complex_suite_min_acceptance_rubric_manifest_rate
        ),
        complex_suite_min_acceptance_rubric_read_first_rate=(
            args.complex_suite_min_acceptance_rubric_read_first_rate
        ),
        complex_suite_min_acceptance_rubric_alignment_rate=(
            args.complex_suite_min_acceptance_rubric_alignment_rate
        ),
        complex_suite_min_agent_trajectory_score=(args.complex_suite_min_agent_trajectory_score),
        complex_suite_min_contextual_verifier_rate=(
            args.complex_suite_min_contextual_verifier_rate
        ),
        complex_suite_min_process_quality_score=(args.complex_suite_min_process_quality_score),
        complex_suite_max_process_risky_validated_tasks=(
            args.complex_suite_max_process_risky_validated_tasks
        ),
        complex_suite_min_target_alignment_rate=(args.complex_suite_min_target_alignment_rate),
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
            f"Docker: {str(report.docker_smoke_refreshed).lower()} "
            f"Complex suite: {str(report.complex_suite_refreshed).lower()}"
        )
    return 0


__all__ = [
    "_project_status_command",
    "_quality_gate_command",
    "_refresh_evidence_command",
    "_release_gate_command",
]
