"""Execution handlers for issue-corpus CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from patchsmith.cli._types import CommandHandler
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


class _Summary(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def issue_corpus_command_handlers() -> dict[str, CommandHandler]:
    return {
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


def _validate_issue_corpus_command(args: argparse.Namespace) -> int:
    results, summary = validate_issue_corpus(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="corpus_report.md",
        summary=summary,
        text=(
            f"valid={summary.valid_entries}/{summary.entry_count} "
            f"errors={summary.error_count} warnings={summary.warning_count}"
        ),
    )
    return 0


def _preflight_issue_corpus_command(args: argparse.Namespace) -> int:
    results, summary = preflight_issue_corpus_repositories(
        corpus_path=Path(args.corpus),
        output_dir=Path(args.output),
        timeout_seconds=args.timeout_seconds,
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="repo_preflight_report.md",
        summary=summary,
        text=(
            f"reachable={summary.reachable_repositories}/{summary.repository_count} "
            f"issues={summary.issue_count}"
        ),
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
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="context_preview_report.md",
        summary=summary,
        text=(
            f"completed={summary.completed_issues}/{summary.attempted_issues} "
            f"context_provider={summary.context_provider}"
        ),
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
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="materialized_task_report.md",
        summary=summary,
        text=(
            f"materialized={summary.materialized_tasks}/{summary.attempted_issues} "
            f"source_free={str(summary.source_free).lower()}"
        ),
    )
    return 0


def _validate_materialized_issue_tasks_command(args: argparse.Namespace) -> int:
    results, summary = validate_materialized_issue_tasks(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="materialized_task_validation_report.md",
        summary=summary,
        text=(
            f"valid={summary.valid_tasks}/{summary.task_count} "
            f"errors={summary.error_count} warnings={summary.warning_count}"
        ),
    )
    return 0


def _check_materialized_run_readiness_command(args: argparse.Namespace) -> int:
    results, summary = check_materialized_issue_run_readiness(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="materialized_run_readiness_report.md",
        summary=summary,
        text=(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _plan_materialized_focused_tests_command(args: argparse.Namespace) -> int:
    results, summary = plan_materialized_issue_focused_tests(
        tasks_dir=Path(args.tasks_dir),
        output_dir=Path(args.output),
        max_paths=args.max_paths,
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_plan_report.md",
        summary=summary,
        text=(
            f"planned={summary.planned_tasks} fallback={summary.fallback_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
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
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_run_report.md",
        summary=summary,
        text=(
            f"passed={summary.passed_tasks} failed={summary.failed_tasks} "
            f"timed_out={summary.timed_out_tasks} blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _diagnose_focused_test_runs_command(args: argparse.Namespace) -> int:
    results, summary = diagnose_focused_test_runs(
        results_path=Path(args.results),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_diagnosis_report.md",
        summary=summary,
        text=(
            f"environment={summary.environment_issue_tasks} "
            f"dependency={summary.dependency_issue_tasks} "
            f"unknown={summary.unknown_failure_tasks}"
        ),
    )
    return 0


def _plan_focused_test_setups_command(args: argparse.Namespace) -> int:
    results, summary = plan_focused_test_setups(
        diagnosis_path=Path(args.diagnosis),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_setup_plan_report.md",
        summary=summary,
        text=(
            f"planned={summary.planned_tasks} ready={summary.ready_tasks} "
            f"manual_review={summary.manual_review_tasks}"
        ),
    )
    return 0


def _check_focused_test_setup_readiness_command(args: argparse.Namespace) -> int:
    results, summary = check_focused_test_setup_readiness(
        setup_plan_path=Path(args.setup_plan),
        docker_smoke_path=Path(args.docker_smoke),
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_setup_readiness_report.md",
        summary=summary,
        text=(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
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
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_setup_execution_report.md",
        summary=summary,
        text=(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"passed={summary.completed_tasks} blocked={summary.blocked_tasks}"
        ),
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
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="focused_test_setup_validation_report.md",
        summary=summary,
        text=(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"passed={summary.passed_tasks} blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _emit_summary(
    *,
    args: argparse.Namespace,
    result_count: int,
    report_filename: str,
    summary: _Summary,
    text: str,
) -> None:
    report_path = Path(args.output) / report_filename
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": result_count,
                    "report_path": str(report_path),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
        return
    print(f"Report: {report_path}")
    print(text)
