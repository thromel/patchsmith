"""Shared CLI run-result output helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.models import RepairRunResult


class SummaryProtocol(Protocol):
    """Any evaluation summary that can be serialized for CLI JSON output."""

    def to_dict(self) -> dict[str, Any]: ...


def emit_summary(
    *,
    args: argparse.Namespace,
    result_count: int,
    report_filename: str,
    summary: SummaryProtocol,
    text: str,
) -> None:
    """Print either a JSON envelope or a human-readable report for a summary."""
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


def print_run_result(
    result: RepairRunResult,
    *,
    apply_result: AgentApplyResult | None = None,
) -> None:
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Report: {result.report_path}")
    print(f"Trace: {result.trace_path}")
    print(f"Diff: {result.final_diff_path}")
    if apply_result is not None:
        print(f"Apply status: {apply_result.status}")
        print(f"Apply message: {apply_result.message}")
    if result.test_result:
        print(f"Test exit code: {result.test_result.exit_code}")
    if result.retrieved_context:
        print("Top retrieved files:")
        for context in result.retrieved_context[:5]:
            print(f"  {context.rank}. {context.path} ({context.score:.2f})")
