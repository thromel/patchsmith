"""Focused issue corpus CLI parser registration."""

from __future__ import annotations

import argparse


def register_focused_issue_corpus_commands(subparsers: argparse._SubParsersAction) -> None:
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


__all__ = ["register_focused_issue_corpus_commands"]
