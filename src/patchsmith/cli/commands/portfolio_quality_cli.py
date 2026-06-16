"""Portfolio quality and status CLI parser registration."""

from __future__ import annotations

import argparse

from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS
from patchsmith.portfolio.release_gate import DEFAULT_RELEASE_GATE_TIMEOUT_SECONDS


def register_portfolio_quality_commands(subparsers: argparse._SubParsersAction) -> None:
    quality_gate = subparsers.add_parser(
        "quality-gate",
        help="Run local verification commands and save a quality-gate report.",
    )
    quality_gate.add_argument(
        "--project-root",
        default=".",
        help="Project root where verification commands run.",
    )
    quality_gate.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write logs under.",
    )
    quality_gate.add_argument(
        "--output",
        default="artifacts/experiments/quality_gate.md",
        help="Markdown quality-gate report output path.",
    )
    quality_gate.add_argument(
        "--json-output",
        default="artifacts/experiments/quality_gate.json",
        help="Optional JSON quality-gate output path.",
    )
    quality_gate.add_argument(
        "--logs-dir",
        help="Directory for per-command stdout/stderr logs.",
    )
    quality_gate.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
        help="Per-command timeout in seconds.",
    )
    quality_gate.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the full pytest gate.",
    )
    quality_gate.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the package build gate.",
    )
    quality_gate.add_argument("--json", action="store_true", help="Print JSON summary.")

    release_gate = subparsers.add_parser(
        "release-gate",
        help="Run the product release gate and save a release-gate report.",
    )
    release_gate.add_argument(
        "--project-root",
        default=".",
        help="Project root where verification commands run.",
    )
    release_gate.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to write logs and sample artifacts under.",
    )
    release_gate.add_argument(
        "--output",
        default="artifacts/experiments/release_gate.md",
        help="Markdown release-gate report output path.",
    )
    release_gate.add_argument(
        "--json-output",
        default="artifacts/experiments/release_gate.json",
        help="Optional JSON release-gate output path.",
    )
    release_gate.add_argument(
        "--logs-dir",
        help="Directory for per-command stdout/stderr logs.",
    )
    release_gate.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_RELEASE_GATE_TIMEOUT_SECONDS,
        help="Per-command timeout in seconds.",
    )
    release_gate.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="Skip the full pytest release-gate step.",
    )
    release_gate.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip the focused smoke lane.",
    )
    release_gate.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the package build step.",
    )
    release_gate.add_argument(
        "--skip-cli-help",
        action="store_true",
        help="Skip CLI help snapshot checks.",
    )
    release_gate.add_argument(
        "--skip-sample-transcript-export",
        action="store_true",
        help="Skip the sample transcript export check.",
    )
    release_gate.add_argument(
        "--skip-benchmark-validation",
        action="store_true",
        help="Skip saved complex benchmark result validation.",
    )
    release_gate.add_argument(
        "--benchmark-results",
        help=(
            "Saved complex_benchmark_results.json to validate. Defaults to "
            "artifacts/experiments/complex_benchmark_suite/complex_benchmark_results.json."
        ),
    )
    release_gate.add_argument("--json", action="store_true", help="Print JSON summary.")

    project_status = subparsers.add_parser(
        "project-status",
        help="Generate a consolidated status report from saved evidence artifacts.",
    )
    project_status.add_argument(
        "--project-root",
        default=".",
        help="Project root to include in the status report.",
    )
    project_status.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    project_status.add_argument(
        "--output",
        default="artifacts/experiments/project_status.md",
        help="Markdown project status report output path.",
    )
    project_status.add_argument(
        "--json-output",
        default="artifacts/experiments/project_status.json",
        help="Optional JSON project status output path.",
    )
    project_status.add_argument("--json", action="store_true", help="Print JSON summary.")

    refresh_evidence = subparsers.add_parser(
        "refresh-evidence",
        help="Regenerate saved review/status evidence artifacts in dependency order.",
    )
    refresh_evidence.add_argument(
        "--project-root",
        default=".",
        help="Project root to inspect for docs, Git metadata, and quality-gate context.",
    )
    refresh_evidence.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to refresh.",
    )
    refresh_evidence.add_argument(
        "--output",
        default="artifacts/experiments/evidence_refresh.md",
        help="Markdown evidence-refresh report output path.",
    )
    refresh_evidence.add_argument(
        "--json-output",
        default="artifacts/experiments/evidence_refresh.json",
        help="Optional JSON evidence-refresh output path.",
    )
    refresh_evidence.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    refresh_evidence.add_argument(
        "--include-quality-gate",
        action="store_true",
        help="Also run the full quality gate during refresh.",
    )
    refresh_evidence.add_argument(
        "--quality-timeout-seconds",
        type=int,
        default=DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
        help="Per-command timeout for quality-gate steps when included.",
    )
    refresh_evidence.add_argument(
        "--include-docker-smoke",
        action="store_true",
        help="Also refresh Docker sandbox smoke evidence before launch/status reports.",
    )
    refresh_evidence.add_argument(
        "--docker-smoke-skip-run",
        action="store_true",
        help="When Docker smoke is included, stop after daemon/image preflight.",
    )
    refresh_evidence.add_argument(
        "--docker-smoke-image",
        default="patchsmith-seeded-smoke:py312",
        help="Local Docker image to inspect and optionally run for Docker smoke.",
    )
    refresh_evidence.add_argument(
        "--docker-binary",
        default="docker",
        help="Docker CLI binary used when Docker smoke is included.",
    )
    refresh_evidence.add_argument(
        "--include-complex-suite",
        action="store_true",
        help="Aggregate saved complex benchmark attempt directories during refresh.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-spec",
        help=(
            "JSON suite spec containing benchmark, attempt_dirs, optional output_dir, "
            "and gate thresholds. Supplying this enables complex-suite refresh."
        ),
    )
    refresh_evidence.add_argument(
        "--complex-suite-attempt-dir",
        action="append",
        default=[],
        help=(
            "Saved public-issue repair attempt directory to aggregate. "
            "Repeat for each task/attempt directory."
        ),
    )
    refresh_evidence.add_argument(
        "--complex-suite-output-dir",
        help=(
            "Output directory for complex suite artifacts. Defaults to "
            "artifacts/experiments/complex_benchmark_suite."
        ),
    )
    refresh_evidence.add_argument(
        "--complex-suite-benchmark",
        default="public_issue_repair_attempts",
        help="Benchmark label to write into the complex suite report.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-validation-rate",
        type=float,
        help="Fail the complex suite gate when validation rate is below this value.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-live-provider-tasks",
        type=int,
        help="Fail the complex suite gate when live-provider task count is below this value.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-unique-tasks",
        type=int,
        help="Fail the complex suite gate when unique task count is below this value.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-selected-cost-per-validated-task-usd",
        type=float,
        help="Fail the complex suite gate above this selected cost per validated task.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-selected-tokens-per-validated-task",
        type=float,
        help="Fail the complex suite gate above this selected token count per validated task.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-selected-virtual-files-per-validated-task",
        type=float,
        help=(
            "Fail the complex suite gate above this selected DeepAgents virtual "
            "file count per validated task."
        ),
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-selected-tokens-per-virtual-file",
        type=float,
        help="Fail the complex suite gate above this selected token count per virtual file.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-selected-responses-per-virtual-file",
        type=float,
        help=("Fail the complex suite gate above this selected response count per virtual file."),
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-selected-progress-score",
        type=float,
        help="Fail the complex suite gate below this selected-attempt progress score.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-selected-context-target-recall",
        type=float,
        help="Fail the complex suite gate below this selected context-target recall.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-selected-context-target-precision",
        type=float,
        help="Fail the complex suite gate below this selected context-target precision.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-repo-instructions-manifest-rate",
        type=float,
        help="Fail the complex suite gate below this repo-instructions manifest rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-repo-instructions-read-first-rate",
        type=float,
        help="Fail the complex suite gate below this repo-instructions read-first rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-acceptance-rubric-manifest-rate",
        type=float,
        help="Fail the complex suite gate below this acceptance-rubric manifest rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-acceptance-rubric-read-first-rate",
        type=float,
        help="Fail the complex suite gate below this acceptance-rubric read-first rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-acceptance-rubric-alignment-rate",
        type=float,
        help="Fail the complex suite gate below this acceptance-rubric alignment rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-agent-trajectory-score",
        type=float,
        help="Fail the complex suite gate when average agent trajectory is below this value.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-contextual-verifier-rate",
        type=float,
        help="Fail the complex suite gate below this contextual-verifier rate.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-process-quality-score",
        type=float,
        help="Fail the complex suite gate below this average process-quality score.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-max-process-risky-validated-tasks",
        type=int,
        help="Fail when more than this many validated tasks are process-risky.",
    )
    refresh_evidence.add_argument(
        "--complex-suite-min-target-alignment-rate",
        type=float,
        help="Fail the complex suite gate when target-aligned patch rate is below this value.",
    )
    refresh_evidence.add_argument("--json", action="store_true", help="Print JSON summary.")


__all__ = ["register_portfolio_quality_commands"]
