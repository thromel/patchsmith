"""Focused public issue test execution."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _optional_string,
    _string_list,
)
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestRunResult,
    IssueCorpusFocusedTestRunSummary,
)
from patchsmith.evaluation_reports import render_materialized_issue_focused_test_run_report
from patchsmith.sandbox import create_sandbox_runner


def run_materialized_issue_focused_tests(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
    sandbox_network: str = "none",
    timeout_seconds: int = 60,
    max_tasks: int | None = None,
) -> tuple[list[IssueCorpusFocusedTestRunResult], IssueCorpusFocusedTestRunSummary]:
    if not plan_path.exists():
        raise FileNotFoundError(f"focused test plan does not exist: {plan_path}")
    if not plan_path.is_file():
        raise ValueError(f"focused test plan path is not a file: {plan_path}")
    parsed = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test plan must contain a JSON list")
    plan_records = [record for record in parsed if isinstance(record, dict)]
    if len(plan_records) != len(parsed):
        raise ValueError("focused test plan records must be JSON objects")
    selected_records = plan_records
    if max_tasks is not None and max_tasks > 0:
        selected_records = plan_records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_runs"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    runner = create_sandbox_runner(
        mode=sandbox_mode,
        image=sandbox_image,
        network=sandbox_network,
    )
    results = [
        _run_materialized_issue_focused_test_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            timeout_seconds=timeout_seconds,
        )
        for record in selected_records
    ]
    summary = summarize_materialized_issue_focused_test_runs(
        plan_path=plan_path,
        results=results,
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_materialized_issue_focused_test_run_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_focused_test_runs(
    *,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    sandbox_mode: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestRunSummary:
    return IssueCorpusFocusedTestRunSummary(
        plan_path=str(plan_path),
        task_count=len(results),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )


def write_materialized_issue_focused_test_run_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    summary: IssueCorpusFocusedTestRunSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_run_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_run_summary.json", summary.to_dict(), trailing_newline=True
    )
    with (output_dir / "focused_test_run_results.csv").open(
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
                "command",
                "repo_path",
                "focused_files",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "errors",
                "warnings",
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
                    "command": result.command,
                    "repo_path": result.repo_path,
                    "focused_files": ";".join(result.focused_files),
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "focused_test_run_report.md").write_text(
        render_materialized_issue_focused_test_run_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _run_materialized_issue_focused_test_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestRunResult:
    errors: list[str] = []
    warnings: list[str] = []
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    command = _optional_string(record.get("command"))
    repo_path_value = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    plan_policy_allowed = bool(record.get("policy_allowed"))
    plan_policy_reason = _optional_string(record.get("policy_reason"))

    workspace: Path | None = None
    if not command:
        errors.append("focused test plan has no command")
    if not plan_policy_allowed:
        errors.append(
            "focused test plan command was not policy-allowed"
            + (f": {plan_policy_reason}" if plan_policy_reason else "")
        )
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("focused test plan has no repo_path")

    if errors:
        return IssueCorpusFocusedTestRunResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            command=command,
            repo_path=repo_path_value,
            focused_files=focused_files,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=False,
            policy_reason=plan_policy_reason,
            stdout_path=None,
            stderr_path=None,
            errors=errors,
            warnings=warnings,
        )

    assert command is not None
    assert workspace is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    command_result = runner.run(
        command=command,
        workspace=workspace,
        timeout_seconds=timeout_seconds,
    )
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(command_result.stdout, encoding="utf-8")
    stderr_path.write_text(command_result.stderr, encoding="utf-8")
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason
    if not policy_allowed:
        status = "blocked"
        errors.append(f"focused test command rejected by policy: {policy_reason}")
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"focused test command timed out after {timeout_seconds}s")
    elif command_result.exit_code is None:
        status = "blocked"
        errors.append("focused test command did not return an exit code")
    elif command_result.exit_code == 0:
        status = "passed"
    else:
        status = "failed"
        warnings.append(f"focused test command exited {command_result.exit_code}")

    return IssueCorpusFocusedTestRunResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        command=command,
        repo_path=repo_path_value,
        focused_files=focused_files,
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        errors=errors,
        warnings=warnings,
    )
