"""Focused-test run diagnosis for public issue corpus workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import _optional_string, _string_list
from patchsmith.evaluation.issue_corpus.log_signals import last_nonempty_lines, matching_lines
from patchsmith.evaluation_models import IssueCorpusFocusedTestDiagnosisResult


def diagnose_focused_test_run_record(
    *,
    record: dict[str, Any],
) -> IssueCorpusFocusedTestDiagnosisResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    run_status = _optional_string(record.get("status"))
    command = _optional_string(record.get("command"))
    repo_path = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    stdout_path = _optional_string(record.get("stdout_path"))
    stderr_path = _optional_string(record.get("stderr_path"))
    logs = focused_test_log_text(stdout_path=stdout_path, stderr_path=stderr_path)

    if run_status == "passed":
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="focused_test_passed",
            severity="info",
            summary="Focused test command passed in the saved run.",
            evidence=[],
            suggested_next_actions=[
                "Use the focused command as targeted validation input for a later repair attempt.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if run_status == "timed_out":
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="timeout",
            severity="environment",
            summary="Focused test command timed out in the saved run.",
            evidence=matching_lines(logs, ["timed out", "timeout"], limit=2),
            suggested_next_actions=[
                "Run the focused command in a stricter isolated environment with an explicit timeout budget.",
                "Reduce the command to issue-specific tests before using it as repair validation.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if run_status == "blocked":
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="execution_blocked",
            severity="blocked",
            summary="Focused test command was blocked before meaningful test execution.",
            evidence=_string_list(record.get("errors"))
            or matching_lines(logs, ["blocked", "policy", "exit code"], limit=3),
            suggested_next_actions=[
                "Fix the focused test plan or sandbox availability before running public issue repairs.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "_pytest._version" in logs:
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="missing_generated_version_metadata",
            severity="dependency",
            summary="Pytest snapshot failed before collection because generated version metadata is missing.",
            evidence=matching_lines(logs, ["_pytest._version", "ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Prepare the repository in an isolated environment using its documented build step before running tests.",
                "Record the setup command separately from repair validation; do not treat this as a patch failure.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "recursive dependency involving fixture" in logs:
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="pytest_fixture_dependency_error",
            severity="environment",
            summary="Pytest fixture setup failed before issue-specific assertions could run.",
            evidence=matching_lines(
                logs,
                ["recursive dependency involving fixture", "ERROR at setup"],
                limit=4,
            ),
            suggested_next_actions=[
                "Install or configure upstream test fixtures in an isolated environment.",
                "Prefer narrower issue-specific tests that avoid service fixtures when possible.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "ModuleNotFoundError" in logs:
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="missing_python_module",
            severity="dependency",
            summary="Focused test command failed because Python import dependencies are missing.",
            evidence=matching_lines(logs, ["ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Resolve repository test dependencies in a sandbox before interpreting repair quality.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "ERROR at setup" in logs:
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category="pytest_setup_error",
            severity="environment",
            summary="Focused test command reached pytest but failed during setup.",
            evidence=matching_lines(logs, ["ERROR at setup"], limit=4),
            suggested_next_actions=[
                "Inspect fixture and service requirements before attempting automated repair.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if not logs.strip():
        evidence = _string_list(record.get("errors")) or _string_list(record.get("warnings"))
        category = "missing_logs" if not evidence else "nonzero_exit"
        summary = (
            "Focused test command did not produce saved logs."
            if category == "missing_logs"
            else "Focused test command failed without a classified log signature."
        )
        return _diagnosis_result(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            run_status=run_status,
            command=command,
            repo_path=repo_path,
            focused_files=focused_files,
            category=category,
            severity="environment" if category == "missing_logs" else "unknown",
            summary=summary,
            evidence=evidence,
            suggested_next_actions=[
                "Rerun the focused command and capture stdout/stderr before interpreting failure quality.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    return _diagnosis_result(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        run_status=run_status,
        command=command,
        repo_path=repo_path,
        focused_files=focused_files,
        category="nonzero_exit",
        severity="unknown",
        summary="Focused test command failed without a known readiness signature.",
        evidence=last_nonempty_lines(logs, limit=4),
        suggested_next_actions=[
            "Inspect the saved stdout/stderr and add a narrower diagnosis before repair-quality claims.",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def focused_test_log_text(*, stdout_path: str | None, stderr_path: str | None) -> str:
    parts: list[str] = []
    for path_value in [stdout_path, stderr_path]:
        if not path_value:
            continue
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _diagnosis_result(
    *,
    task_id: str | None,
    repository: str | None,
    issue_url: str | None,
    run_status: str | None,
    command: str | None,
    repo_path: str | None,
    focused_files: list[str],
    category: str,
    severity: str,
    summary: str,
    evidence: list[str],
    suggested_next_actions: list[str],
    stdout_path: str | None,
    stderr_path: str | None,
) -> IssueCorpusFocusedTestDiagnosisResult:
    return IssueCorpusFocusedTestDiagnosisResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        run_status=run_status,
        command=command,
        repo_path=repo_path,
        focused_files=focused_files,
        category=category,
        severity=severity,
        summary=summary,
        evidence=evidence,
        suggested_next_actions=suggested_next_actions,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
