"""Artifact writers for focused-test setup validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestSetupValidationResult,
    IssueCorpusFocusedTestSetupValidationSummary,
)
from patchsmith.evaluation_reports import render_focused_test_setup_validation_report


def write_focused_test_setup_validation_outputs(
    *,
    output_dir: Path,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    summary: IssueCorpusFocusedTestSetupValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_setup_validation_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_setup_validation_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "focused_test_setup_validation_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "setup_execution_status",
                "setup_profile",
                "repo_path",
                "validation_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "failure_category",
                "failure_summary",
                "failure_evidence",
                "command_result",
                "errors",
                "warnings",
                "next_actions",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "setup_execution_status": result.setup_execution_status,
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "validation_command": result.validation_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "failure_category": result.failure_category,
                    "failure_summary": result.failure_summary,
                    "failure_evidence": ";".join(result.failure_evidence),
                    "command_result": (
                        json.dumps(result.command_result.to_dict(), sort_keys=True)
                        if result.command_result is not None
                        else None
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_validation_report.md").write_text(
        render_focused_test_setup_validation_report(
            setup_execution_path=setup_execution_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


__all__ = ["write_focused_test_setup_validation_outputs"]
