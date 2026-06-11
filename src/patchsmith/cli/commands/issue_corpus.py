"""CLI issue corpus commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands.public_issue_cli import register_public_issue_commands
from patchsmith.evaluation import (
    check_focused_test_setup_readiness,
    check_materialized_issue_run_readiness,
    diagnose_focused_test_runs,
    execute_focused_test_setups,
    materialize_issue_corpus_tasks,
    plan_focused_test_setups,
    plan_materialized_issue_focused_tests,
    preflight_issue_corpus_repositories,
    preview_issue_corpus_context,
    run_materialized_issue_focused_tests,
    validate_focused_test_setups,
    validate_issue_corpus,
    validate_materialized_issue_tasks,
)


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    validate_issue_corpus_parser = subparsers.add_parser(
        "validate-issue-corpus",
        help="Validate public issue-corpus metadata for real-world eval planning.",
    )
    validate_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    validate_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus validation output directory.",
    )
    validate_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preflight_issue_corpus_parser = subparsers.add_parser(
        "preflight-issue-corpus",
        help="Check repository reachability for public issue-corpus entries.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus preflight output directory.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Per-repository git ls-remote timeout.",
    )
    preflight_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    preview_issue_corpus_parser = subparsers.add_parser(
        "preview-issue-corpus-context",
        help="Clone/index public issue-corpus repos and write retrieval preview artifacts.",
    )
    preview_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    preview_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus context preview output directory.",
    )
    preview_issue_corpus_parser.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph"],
        default="native_hybrid",
        help="Retriever to use for source-free public issue context previews.",
    )
    preview_issue_corpus_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved files to record per issue.",
    )
    preview_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to preview. Use 0 for all entries.",
    )
    preview_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialize_issue_corpus_parser = subparsers.add_parser(
        "materialize-issue-corpus-tasks",
        help="Write source-free task manifests from public issue context-preview results.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--corpus",
        default="evals/issue_corpora/public_issue_smoke_v1/issues.json",
        help="Issue corpus JSON manifest.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Issue corpus materialization output directory.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--context-preview",
        default=None,
        help="Context preview results JSON. Defaults to <output>/context_preview_results.json.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--max-issues",
        type=int,
        default=0,
        help="Maximum issue entries to materialize. Use 0 for all entries.",
    )
    materialize_issue_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    validate_materialized_issue_tasks_parser = subparsers.add_parser(
        "validate-materialized-issue-tasks",
        help="Validate source-free public issue task manifests and runbooks.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized task validation output directory.",
    )
    validate_materialized_issue_tasks_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    materialized_run_readiness_parser = subparsers.add_parser(
        "check-materialized-run-readiness",
        help="Check policy and risk readiness before running materialized public issue tasks.",
    )
    materialized_run_readiness_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    materialized_run_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Materialized run readiness output directory.",
    )
    materialized_run_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_plan_parser = subparsers.add_parser(
        "plan-materialized-focused-tests",
        help="Plan focused pytest commands from materialized public issue retrieval hints.",
    )
    focused_test_plan_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized task subdirectories.",
    )
    focused_test_plan_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test plan output directory.",
    )
    focused_test_plan_parser.add_argument(
        "--max-paths",
        type=int,
        default=2,
        help="Maximum retrieved test-like paths to include in each focused command.",
    )
    focused_test_plan_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_run_parser = subparsers.add_parser(
        "run-materialized-focused-tests",
        help="Execute focused pytest commands planned for materialized public issue tasks.",
    )
    focused_test_run_parser.add_argument(
        "--plan",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json",
        help="Focused test plan results JSON.",
    )
    focused_test_run_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test run output directory.",
    )
    focused_test_run_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="local",
        help="Sandbox runner to use for focused test commands.",
    )
    focused_test_run_parser.add_argument(
        "--sandbox-image",
        default="python:3.12-slim",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_run_parser.add_argument(
        "--sandbox-network",
        default="none",
        help="Docker network mode for focused test commands when --sandbox-mode docker is selected.",
    )
    focused_test_run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Per-task focused test timeout.",
    )
    focused_test_run_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum planned tasks to execute. Use 0 for all planned tasks.",
    )
    focused_test_run_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_diagnosis_parser = subparsers.add_parser(
        "diagnose-focused-test-runs",
        help="Classify focused public issue test failures from saved stdout/stderr logs.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--results",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json",
        help="Focused test run results JSON.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test diagnosis output directory.",
    )
    focused_test_diagnosis_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_parser = subparsers.add_parser(
        "plan-focused-test-setups",
        help="Plan sandbox setup steps from focused public issue test diagnoses.",
    )
    focused_test_setup_parser.add_argument(
        "--diagnosis",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json",
        help="Focused test diagnosis results JSON.",
    )
    focused_test_setup_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-plan output directory.",
    )
    focused_test_setup_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_readiness_parser = subparsers.add_parser(
        "check-focused-test-setup-readiness",
        help="Check sandbox and repository readiness before executing focused test setup plans.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--setup-plan",
        default="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_results.json",
        help="Focused test setup-plan results JSON.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--docker-smoke",
        default="artifacts/experiments/docker_smoke.json",
        help="Docker smoke JSON report to use as sandbox readiness evidence.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-readiness output directory.",
    )
    focused_test_setup_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_execution_parser = subparsers.add_parser(
        "execute-focused-test-setups",
        help="Dry-run or execute focused public issue setup commands after readiness checks.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--readiness",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_results.json"
        ),
        help="Focused test setup-readiness results JSON.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-execution output directory.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-image",
        default="patchsmith-seeded-smoke:py312",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-setup-command timeout when --execute is set.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum readiness records to process. Use 0 for all records.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute commands instead of writing dry-run evidence.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Permit readiness-warning tasks to proceed after review.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--allow-dependency-installs",
        action="store_true",
        help="Permit the narrow editable-install setup policy; requires --sandbox-mode docker.",
    )
    focused_test_setup_execution_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    focused_test_setup_validation_parser = subparsers.add_parser(
        "validate-focused-test-setups",
        help="Dry-run or run validation commands after focused public issue setup execution.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--setup-execution",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_results.json"
        ),
        help="Focused test setup-execution results JSON.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Focused test setup-validation output directory.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-image",
        default="patchsmith-seeded-smoke:py312",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-validation-command timeout when --execute is set.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum setup-execution records to process. Use 0 for all records.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute validation commands instead of writing dry-run evidence.",
    )
    focused_test_setup_validation_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    handlers: dict[str, CommandHandler] = {
        "validate-issue-corpus": _validate_issue_corpus_command,
        "preflight-issue-corpus": _preflight_issue_corpus_command,
        "preview-issue-corpus-context": _preview_issue_corpus_context_command,
        "materialize-issue-corpus-tasks": _materialize_issue_corpus_tasks_command,
        "validate-materialized-issue-tasks": _validate_materialized_issue_tasks_command,
        "check-materialized-run-readiness": _check_materialized_run_readiness_command,
        "plan-materialized-focused-tests": _plan_materialized_focused_tests_command,
        "run-materialized-focused-tests": _run_materialized_focused_tests_command,
        "diagnose-focused-test-runs": _diagnose_focused_test_runs_command,
        "plan-focused-test-setups": _plan_focused_test_setups_command,
        "check-focused-test-setup-readiness": _check_focused_test_setup_readiness_command,
        "execute-focused-test-setups": _execute_focused_test_setups_command,
        "validate-focused-test-setups": _validate_focused_test_setups_command,
    }
    handlers.update(register_public_issue_commands(subparsers))
    return handlers


def _validate_issue_corpus_command(args: argparse.Namespace) -> int:
    results, summary = validate_issue_corpus(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "corpus_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'corpus_report.md'}")
        print(
            f"valid={summary.valid_entries}/{summary.entry_count} "
            f"errors={summary.error_count} warnings={summary.warning_count}"
        )
    return 0


def _preflight_issue_corpus_command(args: argparse.Namespace) -> int:
    results, summary = preflight_issue_corpus_repositories(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "repo_preflight_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'repo_preflight_report.md'}")
        print(
            f"reachable={summary.reachable_repositories}/{summary.repository_count} "
            f"issues={summary.issue_count}"
        )
    return 0


def _preview_issue_corpus_context_command(args: argparse.Namespace) -> int:
    max_issues = None if args.max_issues == 0 else args.max_issues
    results, summary = preview_issue_corpus_context(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
        context_provider=args.context_provider,
        top_k=args.top_k,
        max_issues=max_issues,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "context_preview_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'context_preview_report.md'}")
        print(
            f"completed={summary.completed_issues}/{summary.attempted_issues} "
            f"context_provider={summary.context_provider}"
        )
    return 0


def _materialize_issue_corpus_tasks_command(args: argparse.Namespace) -> int:
    max_issues = None if args.max_issues == 0 else args.max_issues
    context_preview = (
        Path(args.context_preview)
        if args.context_preview
        else Path(args.output) / "context_preview_results.json"
    )
    results, summary = materialize_issue_corpus_tasks(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
        context_preview_path=context_preview,
        max_issues=max_issues,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "materialized_task_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'materialized_task_report.md'}")
        print(
            f"materialized={summary.materialized_tasks}/{summary.attempted_issues} "
            f"source_free={str(summary.source_free).lower()}"
        )
    return 0


def _validate_materialized_issue_tasks_command(args: argparse.Namespace) -> int:
    results, summary = validate_materialized_issue_tasks(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "materialized_task_validation_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'materialized_task_validation_report.md'}")
        print(
            f"valid={summary.valid_tasks}/{summary.task_count} "
            f"errors={summary.error_count} warnings={summary.warning_count}"
        )
    return 0


def _check_materialized_run_readiness_command(args: argparse.Namespace) -> int:
    results, summary = check_materialized_issue_run_readiness(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "materialized_run_readiness_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'materialized_run_readiness_report.md'}")
        print(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        )
    return 0


def _plan_materialized_focused_tests_command(args: argparse.Namespace) -> int:
    results, summary = plan_materialized_issue_focused_tests(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
        max_paths=args.max_paths,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "focused_test_plan_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_plan_report.md'}")
        print(
            f"planned={summary.planned_tasks} fallback={summary.fallback_tasks} "
            f"blocked={summary.blocked_tasks}"
        )
    return 0


def _run_materialized_focused_tests_command(args: argparse.Namespace) -> int:
    results, summary = run_materialized_issue_focused_tests(
        plan_path=Path(args.plan),
        output_dir=Path(args.output),
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        sandbox_network=args.sandbox_network,
        timeout_seconds=args.timeout_seconds,
        max_tasks=args.max_tasks,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "focused_test_run_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_run_report.md'}")
        print(
            f"passed={summary.passed_tasks} failed={summary.failed_tasks} "
            f"timed_out={summary.timed_out_tasks} blocked={summary.blocked_tasks}"
        )
    return 0


def _diagnose_focused_test_runs_command(args: argparse.Namespace) -> int:
    results, summary = diagnose_focused_test_runs(
        results_path=Path(args.results),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "focused_test_diagnosis_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_diagnosis_report.md'}")
        print(
            f"environment={summary.environment_issue_tasks} "
            f"dependency={summary.dependency_issue_tasks} "
            f"unknown={summary.unknown_failure_tasks}"
        )
    return 0


def _plan_focused_test_setups_command(args: argparse.Namespace) -> int:
    results, summary = plan_focused_test_setups(
        diagnosis_path=Path(args.diagnosis),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "focused_test_setup_plan_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_setup_plan_report.md'}")
        print(
            f"planned={summary.planned_tasks} ready={summary.ready_tasks} "
            f"manual_review={summary.manual_review_tasks}"
        )
    return 0


def _check_focused_test_setup_readiness_command(args: argparse.Namespace) -> int:
    results, summary = check_focused_test_setup_readiness(
        setup_plan_path=Path(args.setup_plan),
        docker_smoke_path=Path(args.docker_smoke),
        output_dir=Path(args.output),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "focused_test_setup_readiness_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_setup_readiness_report.md'}")
        print(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        )
    return 0


def _execute_focused_test_setups_command(args: argparse.Namespace) -> int:
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
    results, summary = execute_focused_test_setups(
        readiness_path=Path(args.readiness),
        output_dir=Path(args.output),
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        sandbox_network=args.sandbox_network,
        timeout_seconds=args.timeout_seconds,
        max_tasks=max_tasks,
        dry_run=not args.execute,
        allow_warnings=args.allow_warnings,
        allow_dependency_installs=args.allow_dependency_installs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "focused_test_setup_execution_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_setup_execution_report.md'}")
        print(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"passed={summary.completed_tasks} blocked={summary.blocked_tasks}"
        )
    return 0


def _validate_focused_test_setups_command(args: argparse.Namespace) -> int:
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
    results, summary = validate_focused_test_setups(
        setup_execution_path=Path(args.setup_execution),
        output_dir=Path(args.output),
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        sandbox_network=args.sandbox_network,
        timeout_seconds=args.timeout_seconds,
        max_tasks=max_tasks,
        dry_run=not args.execute,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "focused_test_setup_validation_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'focused_test_setup_validation_report.md'}")
        print(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"passed={summary.passed_tasks} blocked={summary.blocked_tasks}"
        )
    return 0
