"""CLI commands for portfolio demo and final-evaluation reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchsmith.cli._types import CommandHandler
from patchsmith.portfolio import (
    write_demo_media_assets,
    write_demo_readiness_report,
    write_demo_script_report,
    write_final_evaluation_report,
)


def register_demo_commands(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    demo_readiness = subparsers.add_parser(
        "demo-readiness",
        help="Generate a portfolio demo readiness report from saved artifacts.",
    )
    demo_readiness.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_readiness.add_argument(
        "--output",
        default="artifacts/experiments/demo_readiness.md",
        help="Markdown demo readiness report output path.",
    )
    demo_readiness.add_argument(
        "--json-output",
        help="Optional JSON demo readiness report output path.",
    )
    demo_readiness.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_readiness.add_argument("--json", action="store_true", help="Print JSON summary.")

    demo_script = subparsers.add_parser(
        "demo-script",
        help="Generate a timed portfolio demo script from saved artifacts.",
    )
    demo_script.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_script.add_argument(
        "--output",
        default="artifacts/experiments/demo_script.md",
        help="Markdown demo script output path.",
    )
    demo_script.add_argument(
        "--json-output",
        help="Optional JSON demo script output path.",
    )
    demo_script.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_script.add_argument("--json", action="store_true", help="Print JSON summary.")

    demo_media = subparsers.add_parser(
        "demo-media",
        help="Generate demo media assets from saved artifact evidence.",
    )
    demo_media.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    demo_media.add_argument(
        "--output",
        default="artifacts/experiments/demo_media.md",
        help="Markdown demo media report output path.",
    )
    demo_media.add_argument(
        "--svg-output",
        default="artifacts/experiments/demo_media.svg",
        help="SVG demo media asset output path.",
    )
    demo_media.add_argument(
        "--png-output",
        default="artifacts/experiments/demo_media.png",
        help="PNG demo media asset output path.",
    )
    demo_media.add_argument(
        "--json-output",
        help="Optional JSON demo media report output path.",
    )
    demo_media.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    demo_media.add_argument("--json", action="store_true", help="Print JSON summary.")

    final_evaluation = subparsers.add_parser(
        "final-evaluation",
        help="Generate a final evaluation narrative from saved artifacts.",
    )
    final_evaluation.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Root artifact directory to scan.",
    )
    final_evaluation.add_argument(
        "--output",
        default="artifacts/experiments/final_evaluation.md",
        help="Markdown final evaluation report output path.",
    )
    final_evaluation.add_argument(
        "--json-output",
        help="Optional JSON final evaluation report output path.",
    )
    final_evaluation.add_argument(
        "--max-failure-runs",
        type=int,
        default=0,
        help="Maximum recent runs to scan for failure visibility. Use 0 to scan all runs.",
    )
    final_evaluation.add_argument("--json", action="store_true", help="Print JSON summary.")

    return {
        "demo-readiness": _demo_readiness_command,
        "demo-script": _demo_script_command,
        "demo-media": _demo_media_command,
        "final-evaluation": _final_evaluation_command,
    }


def _demo_readiness_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_demo_readiness_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "readiness_status": report.readiness_status,
                    "experiment_count": report.experiment_count,
                    "run_count": report.run_count,
                    "metric_count": report.metric_count,
                    "runs_requiring_attention": report.runs_requiring_attention,
                    "failure_categories": report.failure_categories,
                    "model_providers": report.model_providers,
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
            )
        )
    else:
        print(f"Demo readiness report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.readiness_status} "
            f"Experiments: {report.experiment_count} "
            f"Runs: {report.run_count} "
            f"Metrics: {report.metric_count}"
        )
    return 0


def _demo_script_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_demo_script_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "target_duration_seconds": report.target_duration_seconds,
                    "readiness_status": report.readiness_status,
                    "section_count": len(report.sections),
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
            )
        )
    else:
        print(f"Demo script: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.readiness_status} "
            f"Sections: {len(report.sections)} "
            f"Target: {report.target_duration_seconds}s"
        )
    return 0


def _demo_media_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_demo_media_assets(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        svg_output_path=Path(args.svg_output),
        png_output_path=Path(args.png_output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "readiness_status": report.readiness_status,
                    "markdown_path": report.markdown_path,
                    "svg_path": report.svg_path,
                    "png_path": report.png_path,
                    "width": report.width,
                    "height": report.height,
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
            )
        )
    else:
        print(f"Demo media report: {Path(args.output)}")
        print(f"SVG: {Path(args.svg_output)}")
        print(f"PNG: {Path(args.png_output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
    return 0


def _final_evaluation_command(args: argparse.Namespace) -> int:
    json_output_path = Path(args.json_output) if args.json_output else None
    max_failure_runs = None if args.max_failure_runs == 0 else args.max_failure_runs
    report = write_final_evaluation_report(
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        json_output_path=json_output_path,
        max_failure_runs=max_failure_runs,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "artifacts_dir": report.artifacts_dir,
                    "generated_at": report.generated_at,
                    "readiness_status": report.readiness_status,
                    "experiment_count": report.experiment_count,
                    "run_count": report.run_count,
                    "metric_count": report.metric_count,
                    "runs_requiring_attention": report.runs_requiring_attention,
                    "deepagents_package_run_count": report.deepagents_package_run_count,
                    "deepagents_compatibility_run_count": (
                        report.deepagents_compatibility_run_count
                    ),
                    "decision_count": len(report.decisions),
                    "limitation_count": len(report.limitations),
                    "report_path": str(Path(args.output)),
                    "json_path": str(json_output_path) if json_output_path else None,
                },
                indent=2,
            )
        )
    else:
        print(f"Final evaluation report: {Path(args.output)}")
        if json_output_path:
            print(f"JSON: {json_output_path}")
        print(
            f"Status: {report.readiness_status} "
            f"Experiments: {report.experiment_count} "
            f"Metrics: {report.metric_count}"
        )
    return 0
