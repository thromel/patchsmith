"""Shared CLI run-result output helpers."""

from __future__ import annotations

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.models import RepairRunResult


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
