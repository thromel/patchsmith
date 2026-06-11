"""CLI commands for public issue reproduction and repair gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.cli._types import CommandHandler
from patchsmith.evaluation import (
    check_public_issue_repair_readiness,
    discover_public_issue_failure_signals,
    execute_public_issue_repairs,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
    validate_public_issue_reproduction_specs,
)


def register_public_issue_commands(
    subparsers: argparse._SubParsersAction,
) -> dict[str, CommandHandler]:
    public_reproduction_plan_parser = subparsers.add_parser(
        "plan-public-issue-reproductions",
        help="Plan issue-specific failing reproduction checks before public issue repairs.",
    )
    public_reproduction_plan_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized public issue task manifests.",
    )
    public_reproduction_plan_parser.add_argument(
        "--focused-plan",
        default=("artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json"),
        help="Focused public issue test-plan results JSON.",
    )
    public_reproduction_plan_parser.add_argument(
        "--reproduction-specs",
        default=None,
        help=(
            "Optional reviewed JSON file containing task_id, command, and "
            "expected_failure_signals overrides for public issue reproduction."
        ),
    )
    public_reproduction_plan_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue reproduction-plan output directory.",
    )
    public_reproduction_plan_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    public_reproduction_spec_validation_parser = subparsers.add_parser(
        "validate-public-issue-reproduction-specs",
        help="Validate reviewed public issue reproduction specs before execution.",
    )
    public_reproduction_spec_validation_parser.add_argument(
        "--specs",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_specs_template.json"
        ),
        help="Reviewed public issue reproduction specs JSON.",
    )
    public_reproduction_spec_validation_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Directory containing materialized public issue task manifests.",
    )
    public_reproduction_spec_validation_parser.add_argument(
        "--focused-plan",
        default=("artifacts/experiments/public_issue_corpus_v1/focused_test_plan_results.json"),
        help="Focused public issue test-plan results JSON.",
    )
    public_reproduction_spec_validation_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue reproduction-spec validation output directory.",
    )
    public_reproduction_spec_validation_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    public_failure_signal_discovery_parser = subparsers.add_parser(
        "discover-public-issue-failure-signals",
        help="Dry-run or execute candidate public issue commands to collect failure-signal hints.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--plan",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_plan_results.json"
        ),
        help="Public issue reproduction-plan results JSON.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue failure-signal discovery output directory.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--sandbox-image",
        default="patchsmith-seeded-smoke:py312",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-discovery-command timeout when --execute is set.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum reproduction-plan records to process. Use 0 for all records.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute candidate commands instead of writing dry-run evidence.",
    )
    public_failure_signal_discovery_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    public_reproduction_execution_parser = subparsers.add_parser(
        "execute-public-issue-reproductions",
        help="Dry-run or execute planned public issue failing reproduction checks.",
    )
    public_reproduction_execution_parser.add_argument(
        "--plan",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_plan_results.json"
        ),
        help="Public issue reproduction-plan results JSON.",
    )
    public_reproduction_execution_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue reproduction-execution output directory.",
    )
    public_reproduction_execution_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner to use when --execute is set.",
    )
    public_reproduction_execution_parser.add_argument(
        "--sandbox-image",
        default="patchsmith-seeded-smoke:py312",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    public_reproduction_execution_parser.add_argument(
        "--sandbox-network",
        choices=["none", "bridge"],
        default="none",
        help="Docker network mode used when --execute and --sandbox-mode docker are selected.",
    )
    public_reproduction_execution_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-reproduction-command timeout when --execute is set.",
    )
    public_reproduction_execution_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum reproduction-plan records to process. Use 0 for all records.",
    )
    public_reproduction_execution_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute reproduction commands instead of writing dry-run evidence.",
    )
    public_reproduction_execution_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    public_repair_readiness_parser = subparsers.add_parser(
        "check-public-issue-repair-readiness",
        help="Gate readiness before attempting PatchSmith repairs on public issue tasks.",
    )
    public_repair_readiness_parser.add_argument(
        "--focused-run",
        default=("artifacts/experiments/public_issue_corpus_v1/focused_test_run_results.json"),
        help="Focused public issue test-run results JSON.",
    )
    public_repair_readiness_parser.add_argument(
        "--diagnosis",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_results.json"
        ),
        help="Focused public issue test-diagnosis results JSON.",
    )
    public_repair_readiness_parser.add_argument(
        "--setup-validation",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "focused_test_setup_validation_results.json"
        ),
        help="Focused public issue setup-validation results JSON.",
    )
    public_repair_readiness_parser.add_argument(
        "--reproduction-execution",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_execution_results.json"
        ),
        help="Optional public issue reproduction-execution results JSON.",
    )
    public_repair_readiness_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Optional directory containing materialized task manifests.",
    )
    public_repair_readiness_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue repair-readiness output directory.",
    )
    public_repair_readiness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

    public_repair_attempt_parser = subparsers.add_parser(
        "execute-public-issue-repairs",
        help="Dry-run or execute readiness-gated PatchSmith repairs on public issue tasks.",
    )
    public_repair_attempt_parser.add_argument(
        "--readiness",
        default=(
            "artifacts/experiments/public_issue_corpus_v1/"
            "public_issue_repair_readiness_results.json"
        ),
        help="Public issue repair-readiness results JSON.",
    )
    public_repair_attempt_parser.add_argument(
        "--tasks-dir",
        default="artifacts/experiments/public_issue_corpus_v1/materialized_tasks",
        help="Optional directory containing materialized task manifests.",
    )
    public_repair_attempt_parser.add_argument(
        "--output",
        default="artifacts/experiments/public_issue_corpus_v1",
        help="Public issue repair-attempt output directory.",
    )
    public_repair_attempt_parser.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "langgraph", "deepagents", "openai_agents"],
        default="langgraph",
        help="Runtime used for executed repair attempts.",
    )
    public_repair_attempt_parser.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai", "deepagents"],
        default="fake_model",
        help="Planner used for executed repair attempts.",
    )
    public_repair_attempt_parser.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context provider used for executed repair attempts.",
    )
    public_repair_attempt_parser.add_argument(
        "--sandbox-mode",
        choices=["local", "docker"],
        default="docker",
        help="Sandbox runner used by PatchSmith validation when --execute is set.",
    )
    public_repair_attempt_parser.add_argument(
        "--sandbox-image",
        default="patchsmith-seeded-smoke:py312",
        help="Docker image used when --sandbox-mode docker is selected.",
    )
    public_repair_attempt_parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Maximum repair-readiness records to process. Use 0 for all records.",
    )
    public_repair_attempt_parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra DeepAgents feedback retries after the first public repair attempt.",
    )
    public_repair_attempt_parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow warning-class readiness only when reproduction evidence is already proven.",
    )
    public_repair_attempt_parser.add_argument(
        "--execute",
        action="store_true",
        help="Launch PatchSmith repairs instead of writing dry-run evidence.",
    )
    public_repair_attempt_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary.",
    )

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
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "public_issue_reproduction_plan_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'public_issue_reproduction_plan_report.md'}")
        print(
            f"planned={summary.planned_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
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
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "public_issue_reproduction_spec_validation_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(
            f"Report: {Path(args.output) / 'public_issue_reproduction_spec_validation_report.md'}"
        )
        print(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
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
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "public_issue_failure_signal_discovery_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'public_issue_failure_signal_discovery_report.md'}")
        print(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"observed_failure={summary.observed_failure_tasks} "
            f"candidate_signal={summary.candidate_signal_tasks}"
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
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "public_issue_reproduction_execution_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'public_issue_reproduction_execution_report.md'}")
        print(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"reproduced={summary.reproduced_tasks} blocked={summary.blocked_tasks}"
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
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(
                        Path(args.output) / "public_issue_repair_readiness_report.md"
                    ),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'public_issue_repair_readiness_report.md'}")
        print(
            f"ready={summary.ready_tasks} warning={summary.warning_tasks} "
            f"blocked={summary.blocked_tasks}"
        )
    return 0


def _execute_public_issue_repairs_command(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else None
    max_tasks = None if args.max_tasks == 0 else args.max_tasks
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
        dry_run=not args.execute,
        allow_warnings=args.allow_warnings,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "result_count": len(results),
                    "report_path": str(Path(args.output) / "public_issue_repair_attempt_report.md"),
                    "summary": summary.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {Path(args.output) / 'public_issue_repair_attempt_report.md'}")
        print(
            f"dry_run={summary.dry_run_tasks} attempted={summary.attempted_tasks} "
            f"validated={summary.validated_tasks} blocked={summary.blocked_tasks}"
        )
    return 0
