"""Focused-test setup validation workflow for public issue corpus tasks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestSetupCommandResult,
    IssueCorpusFocusedTestSetupValidationResult,
    IssueCorpusFocusedTestSetupValidationSummary,
)
from patchsmith.evaluation_reports import render_focused_test_setup_validation_report
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy


def validate_focused_test_setups(
    *,
    setup_execution_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusFocusedTestSetupValidationResult],
    IssueCorpusFocusedTestSetupValidationSummary,
]:
    if not setup_execution_path.exists():
        raise FileNotFoundError(
            f"focused test setup execution does not exist: {setup_execution_path}"
        )
    if not setup_execution_path.is_file():
        raise ValueError(f"focused test setup execution path is not a file: {setup_execution_path}")
    parsed = json.loads(setup_execution_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup execution must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup execution records must be JSON objects")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_setup_validation"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            policy=policy,
            network=sandbox_network,
        )
    )
    results = [
        _validate_focused_test_setup_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )
        for record in selected_records
    ]
    summary = summarize_focused_test_setup_validation(
        setup_execution_path=setup_execution_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_focused_test_setup_validation_outputs(
        output_dir=output_dir,
        setup_execution_path=setup_execution_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_validation(
    *,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestSetupValidationSummary:
    failure_category_counts: dict[str, int] = {}
    for result in results:
        if result.failure_category:
            failure_category_counts[result.failure_category] = (
                failure_category_counts.get(result.failure_category, 0) + 1
            )
    return IssueCorpusFocusedTestSetupValidationSummary(
        setup_execution_path=str(setup_execution_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        skipped_tasks=sum(1 for result in results if result.status == "skipped"),
        failure_category_counts=failure_category_counts,
    )


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


def _classify_focused_test_setup_validation_failure(
    *,
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
) -> tuple[str | None, str | None, list[str], list[str]]:
    if status in {"passed", "dry_run", "skipped"}:
        return None, None, [], []
    if status == "timed_out":
        return (
            "validation_timeout",
            "validation command timed out before producing a stable setup signal",
            [],
            ["raise or split the timeout only after confirming the command scope is focused"],
        )
    if status == "blocked":
        return (
            "validation_policy_or_setup_blocker",
            "validation command could not run because setup or command policy blocked it",
            [],
            ["resolve setup and command-policy blockers before interpreting validation output"],
        )

    combined = "\n".join(part for part in [stderr, stdout] if part)
    combined_lower = combined.lower()
    if "minversion" in combined_lower and "actual pytest-" in combined_lower:
        return (
            "pytest_in_tree_version_metadata",
            "pytest validation imported the repository development version below pyproject minversion",
            _diagnostic_lines(
                combined,
                ["minversion", "actual pytest-"],
            ),
            [
                "refresh the pytest setup recipe to run through the repository's supported tox/nox workflow or generated version metadata",
            ],
        )
    if "recursive dependency involving fixture 'httpbin'" in combined_lower:
        return (
            "missing_httpbin_fixture_provider",
            "requests validation requires an external httpbin fixture provider instead of the recursive local fixture alias",
            _diagnostic_lines(
                combined,
                ["recursive dependency involving fixture 'httpbin'", "tests/conftest.py"],
            ),
            [
                "narrow requests validation to issue-specific tests that do not require httpbin or add a controlled httpbin fixture provider",
            ],
        )
    if "no module named" in combined_lower:
        return (
            "missing_python_dependency",
            "validation failed because a required Python dependency was not importable",
            _diagnostic_lines(combined, ["no module named"]),
            ["extend the disposable setup recipe with the missing dependency only after review"],
        )
    if "file or directory not found" in combined_lower or "not found:" in combined_lower:
        return (
            "invalid_validation_target",
            "validation command references a test path or selector that pytest cannot find",
            _diagnostic_lines(combined, ["file or directory not found", "not found:"]),
            ["regenerate the focused validation command from current repository paths"],
        )
    if exit_code is not None:
        return (
            "unknown_validation_failure",
            f"validation command exited {exit_code} without a recognized setup diagnostic",
            _diagnostic_lines(combined, ["error", "failed", "traceback"]),
            ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
        )
    return (
        "unknown_validation_failure",
        "validation command failed without an exit code or recognized setup diagnostic",
        _diagnostic_lines(combined, ["error", "failed", "traceback"]),
        ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
    )


def _diagnostic_lines(text: str, patterns: list[str], *, limit: int = 3) -> list[str]:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    evidence: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            evidence.append(stripped[:240])
        if len(evidence) >= limit:
            break
    return evidence


def _validate_focused_test_setup_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any | None,
    policy: CommandPolicy,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
    dry_run: bool,
) -> IssueCorpusFocusedTestSetupValidationResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    setup_status = _optional_string(record.get("status")) or "unknown"
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    validation_command = _optional_string(record.get("validation_command"))
    errors: list[str] = []
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    command_result_payload: IssueCorpusFocusedTestSetupCommandResult | None = None

    workspace: Path | None = None
    if setup_status not in {"passed", "skipped"}:
        errors.append(f"setup execution status is {setup_status}")
        next_actions.append("complete setup execution before running validation")
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("setup execution record has no repo_path")
    if not validation_command:
        errors.append("setup execution record has no validation command")

    if workspace is not None and validation_command:
        decision = policy.evaluate(validation_command, workspace=workspace)
        command_result_payload = IssueCorpusFocusedTestSetupCommandResult(
            command=validation_command,
            status="dry_run" if decision.allowed else "policy_blocked",
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=decision.allowed,
            policy_reason=decision.reason,
            stdout_path=None,
            stderr_path=None,
        )
        if not decision.allowed:
            errors.append(f"validation command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusFocusedTestSetupValidationResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            setup_execution_status=setup_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            validation_command=validation_command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            failure_category="validation_policy_or_setup_blocker",
            failure_summary=(
                "validation command could not run because setup or command policy blocked it"
            ),
            failure_evidence=_dedupe_preserve_order(errors),
            command_result=command_result_payload,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "resolve setup and command-policy blockers before interpreting validation output",
                ]
            ),
        )

    if dry_run:
        return IssueCorpusFocusedTestSetupValidationResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            setup_execution_status=setup_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            validation_command=validation_command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            failure_category=None,
            failure_summary=None,
            failure_evidence=[],
            command_result=command_result_payload,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute after reviewing validation dry-run evidence"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert validation_command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    command_result = runner.run(
        command=validation_command,
        workspace=workspace,
        timeout_seconds=timeout_seconds,
    )
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(command_result.stdout, encoding="utf-8")
    stderr_path.write_text(command_result.stderr, encoding="utf-8")

    if not command_result.policy_decision.allowed:
        status = "blocked"
        errors.append(
            f"validation command rejected by policy: {command_result.policy_decision.reason}"
        )
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"validation command timed out after {timeout_seconds}s")
    elif command_result.exit_code == 0:
        status = "passed"
    else:
        status = "failed"
        warnings.append(f"validation command exited {command_result.exit_code}")
    failure_category, failure_summary, failure_evidence, failure_next_actions = (
        _classify_focused_test_setup_validation_failure(
            status=status,
            stdout=command_result.stdout,
            stderr=command_result.stderr,
            exit_code=command_result.exit_code,
        )
    )
    if failure_summary:
        warnings.append(failure_summary)

    command_result_payload = IssueCorpusFocusedTestSetupCommandResult(
        command=validation_command,
        status=status if status in {"passed", "failed", "timed_out"} else "policy_blocked",
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=command_result.policy_decision.allowed,
        policy_reason=command_result.policy_decision.reason,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
    return IssueCorpusFocusedTestSetupValidationResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        setup_execution_status=setup_status,
        setup_profile=setup_profile,
        repo_path=repo_path_value,
        validation_command=validation_command,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        failure_category=failure_category,
        failure_summary=failure_summary,
        failure_evidence=failure_evidence,
        command_result=command_result_payload,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(
            [
                *next_actions,
                *failure_next_actions,
                "use validation result as setup-readiness evidence only",
            ]
        ),
    )
