"""CLI commands for public issue reproduction and repair gates."""

from __future__ import annotations

import argparse

from patchsmith.cli._types import CommandHandler
from patchsmith.cli.commands.public_issue_handlers import public_issue_command_handlers


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

    return public_issue_command_handlers()
