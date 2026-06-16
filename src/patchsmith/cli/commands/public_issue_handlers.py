"""Execution handlers for public issue reproduction and repair CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from patchsmith.cli._types import CommandHandler
from patchsmith.evaluation import (
    check_public_issue_repair_readiness,
    discover_public_issue_failure_signals,
    execute_public_issue_repairs,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
    validate_public_issue_reproduction_specs,
)


class _Summary(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def public_issue_command_handlers() -> dict[str, CommandHandler]:
    return {
        "plan-public-issue-reproductions": _plan_public_issue_reproductions_command,
        "validate-public-issue-reproduction-specs": _validate_public_issue_reproduction_specs_command,
        "discover-public-issue-failure-signals": _discover_public_issue_failure_signals_command,
        "execute-public-issue-reproductions": _execute_public_issue_reproductions_command,
        "check-public-issue-repair-readiness": _check_public_issue_repair_readiness_command,
        "execute-public-issue-repairs": _execute_public_issue_repairs_command,
    }


def _plan_public_issue_reproductions_command(args: argparse.Namespace) -> int:
    focused_plan = Path(args.focused_plan) if args.focused_plan else None
    reproduction_specs = Path(args.reproduction_specs) if args.reproduction_specs else None
    results, summary = plan_public_issue_reproductions(
        tasks_dir=Path(args.tasks_dir),
        focused_plan_path=focused_plan,
        reproduction_specs_path=reproduction_specs,
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="public_issue_reproduction_plan_report.md",
        summary=summary,
        text=(
            f"planned={summary.planned_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _validate_public_issue_reproduction_specs_command(args: argparse.Namespace) -> int:
    focused_plan = Path(args.focused_plan) if args.focused_plan else None
    results, summary = validate_public_issue_reproduction_specs(
        specs_path=Path(args.specs),
        tasks_dir=Path(args.tasks_dir),
        focused_plan_path=focused_plan,
        output_dir=Path(args.output),
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="public_issue_reproduction_spec_validation_report.md",
        summary=summary,
        text=(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _discover_public_issue_failure_signals_command(args: argparse.Namespace) -> int:
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
    results, summary = discover_public_issue_failure_signals(
        plan_path=Path(args.plan),
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
        report_filename="public_issue_failure_signal_discovery_report.md",
        summary=summary,
        text=(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"observed_failure={summary.observed_failure_tasks} "
            f"candidate_signal={summary.candidate_signal_tasks}"
        ),
    )
    return 0


def _execute_public_issue_reproductions_command(args: argparse.Namespace) -> int:
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
    results, summary = execute_public_issue_reproductions(
        plan_path=Path(args.plan),
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
        report_filename="public_issue_reproduction_execution_report.md",
        summary=summary,
        text=(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"reproduced={summary.reproduced_tasks} blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _check_public_issue_repair_readiness_command(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else None
    results, summary = check_public_issue_repair_readiness(
        focused_run_path=Path(args.focused_run),
        diagnosis_path=Path(args.diagnosis),
        setup_validation_path=Path(args.setup_validation),
        reproduction_execution_path=Path(args.reproduction_execution),
        output_dir=Path(args.output),
        tasks_dir=tasks_dir,
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="public_issue_repair_readiness_report.md",
        summary=summary,
        text=(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        ),
    )
    return 0


def _execute_public_issue_repairs_command(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else None
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
    if args.deepagents_max_context_files < 0:
        raise ValueError("--deepagents-max-context-files must be non-negative")
    if args.max_actual_model_responses is not None and args.max_actual_model_responses < 0:
        raise ValueError("--max-actual-model-responses must be non-negative")
    if args.max_actual_model_tokens is not None and args.max_actual_model_tokens < 0:
        raise ValueError("--max-actual-model-tokens must be non-negative")
    deepagents_max_context_files = (
        args.deepagents_max_context_files if args.deepagents_max_context_files > 0 else None
    )
    results, summary = execute_public_issue_repairs(
        readiness_path=Path(args.readiness),
        output_dir=Path(args.output),
        tasks_dir=tasks_dir,
        runtime=args.runtime,
        planner=args.planner,
        context_provider=args.context_provider,
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        max_retries=args.max_retries,
        max_tasks=max_tasks,
        task_ids=args.task_ids,
        repeats=max(1, args.repeats),
        stop_on_validated=args.stop_on_validated,
        dry_run=not args.execute,
        allow_warnings=args.allow_warnings,
        max_live_cost_usd=args.max_live_cost_usd,
        estimated_cost_per_attempt_usd=args.estimated_cost_per_attempt_usd,
        deepagents_max_context_files=deepagents_max_context_files,
        max_actual_model_responses=args.max_actual_model_responses,
        max_actual_model_tokens=args.max_actual_model_tokens,
        deepagents_subagent_mode=args.deepagents_subagents,
    )
    _emit_summary(
        args=args,
        result_count=len(results),
        report_filename="public_issue_repair_attempt_report.md",
        summary=summary,
        text=(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"validated={summary.validated_tasks} blocked={summary.blocked_tasks} "
            f"pass_at_n={summary.validated_task_pass_at_n_rate:.3f}"
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


__all__ = ["public_issue_command_handlers"]
