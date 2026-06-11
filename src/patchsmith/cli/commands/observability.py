"""CLI observability commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.cli._types import CommandHandler
from patchsmith.observability import write_artifact_index, write_failure_report


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    index_artifacts = subparsers.add_parser(
        "index-artifacts", help="Generate a static index of saved run and experiment artifacts."
    )
    index_artifacts.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    index_artifacts.add_argument(
        "--output",
        default="artifacts/experiments/index.md",
        help="Markdown artifact-index output path.",
    )
    index_artifacts.add_argument(
        "--json-output",
        help="Optional JSON artifact-index output path.",
    )
    index_artifacts.add_argument(
        "--html-output",
        help="Optional static HTML artifact-dashboard output path.",
    )
    index_artifacts.add_argument(
        "--run-detail-output-dir",
        help="Optional directory for static run-detail HTML pages.",
    )
    index_artifacts.add_argument("--json", action="store_true", help="Print JSON summary.")

    inspect_failures = subparsers.add_parser(
        "inspect-failures",
        help="Summarize failure signals from saved run trace artifacts.",
    )
    inspect_failures.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    inspect_failures.add_argument(
        "--output",
        default="artifacts/experiments/failure_report.md",
        help="Markdown failure report output path.",
    )
    inspect_failures.add_argument(
        "--json-output",
        help="Optional JSON failure report output path.",
    )
    inspect_failures.add_argument(
        "--max-runs",
        type=int,
        default=100,
        help="Maximum recent runs to scan. Use 0 to scan all runs.",
    )
    inspect_failures.add_argument("--json", action="store_true", help="Print JSON summary.")

    return {
        "index-artifacts": _index_artifacts_command,
        "inspect-failures": _inspect_failures_command,
    }


def _index_artifacts_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    html_output_path = Path(args.html_output) if args.html_output else None
    run_detail_output_dir = Path(args.run_detail_output_dir) if args.run_detail_output_dir else None
    index = write_artifact_index(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        html_output_path=html_output_path,
        run_detail_output_dir=run_detail_output_dir,
    )
    if args.json:
        payload = {
            "artifacts_dir": index.artifacts_dir,
            "generated_at": index.generated_at,
            "experiment_count": index.experiment_count,
            "run_count": index.run_count,
            "metric_count": len(index.metrics),
            "index_path": str(Path(args.output)),
            "json_path": str(json_output_path) if json_output_path else None,
            "html_path": str(html_output_path) if html_output_path else None,
            "run_detail_dir": (str(run_detail_output_dir) if run_detail_output_dir else None),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Index: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        if html_output_path:
            print(f"HTML: {html_output_path}")
        if run_detail_output_dir:
            print(f"Run details: {run_detail_output_dir}")
        print(
            f"Experiments: {index.experiment_count} "
            f"Runs: {index.run_count} "
            f"Metrics: {len(index.metrics)}"
        )
    return 0


def _inspect_failures_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_runs = None if args.max_runs == 0 else args.max_runs
    report = write_failure_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_runs=max_runs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "runs_scanned": report.runs_scanned,
                    "runs_requiring_attention": report.runs_requiring_attention,
                    "failed_event_count": report.failed_event_count,
                    "category_counts": report.category_counts,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
            )
        )
    else:
        print(f"Failure report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Runs scanned: {report.runs_scanned} "
            f"Runs requiring attention: {report.runs_requiring_attention} "
            f"Failed events: {report.failed_event_count}"
        )
    return 0
