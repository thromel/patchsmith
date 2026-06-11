"""Focused-test setup planning for public issue corpus workflows."""

from __future__ import annotations

import csv
import json
import tomllib
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _fixture_listing_command,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation_models import (
    IssueCorpusFocusedTestSetupPlanResult,
    IssueCorpusFocusedTestSetupPlanSummary,
)
from patchsmith.evaluation_reports import render_focused_test_setup_plan_report


def plan_focused_test_setups(
    *,
    diagnosis_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestSetupPlanResult],
    IssueCorpusFocusedTestSetupPlanSummary,
]:
    if not diagnosis_path.exists():
        raise FileNotFoundError(f"focused test diagnosis does not exist: {diagnosis_path}")
    if not diagnosis_path.is_file():
        raise ValueError(f"focused test diagnosis path is not a file: {diagnosis_path}")
    parsed = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test diagnosis must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test diagnosis records must be JSON objects")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_plan_focused_test_setup(record=record) for record in records]
    summary = summarize_focused_test_setup_plan(
        diagnosis_path=diagnosis_path,
        results=results,
    )
    write_focused_test_setup_plan_outputs(
        output_dir=output_dir,
        diagnosis_path=diagnosis_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_plan(
    *,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
) -> IssueCorpusFocusedTestSetupPlanSummary:
    category_counts: dict[str, int] = {}
    for result in results:
        category_counts[result.category] = category_counts.get(result.category, 0) + 1
    return IssueCorpusFocusedTestSetupPlanSummary(
        diagnosis_path=str(diagnosis_path),
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        manual_review_tasks=sum(1 for result in results if result.status == "manual_review"),
        dependency_setup_tasks=sum(1 for result in results if result.severity == "dependency"),
        environment_setup_tasks=sum(1 for result in results if result.severity == "environment"),
        network_required_tasks=sum(1 for result in results if result.requires_network),
        sandbox_required_tasks=sum(1 for result in results if result.sandbox_required),
        category_counts=dict(sorted(category_counts.items())),
    )


def write_focused_test_setup_plan_outputs(
    *,
    output_dir: Path,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
    summary: IssueCorpusFocusedTestSetupPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "focused_test_setup_plan_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "focused_test_setup_plan_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "focused_test_setup_plan_results.csv").open(
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
                "category",
                "severity",
                "repo_path",
                "setup_profile",
                "setup_commands",
                "validation_command",
                "focused_files",
                "requires_network",
                "sandbox_required",
                "evidence",
                "risk_notes",
                "suggested_next_actions",
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
                    "category": result.category,
                    "severity": result.severity,
                    "repo_path": result.repo_path,
                    "setup_profile": result.setup_profile,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "focused_files": ";".join(result.focused_files),
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "evidence": ";".join(result.evidence),
                    "risk_notes": ";".join(result.risk_notes),
                    "suggested_next_actions": ";".join(result.suggested_next_actions),
                }
            )
    (output_dir / "focused_test_setup_plan_report.md").write_text(
        render_focused_test_setup_plan_report(
            diagnosis_path=diagnosis_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _plan_focused_test_setup(
    *,
    record: dict[str, Any],
) -> IssueCorpusFocusedTestSetupPlanResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    category = _optional_string(record.get("category")) or "unknown"
    severity = _optional_string(record.get("severity")) or "unknown"
    command = _optional_string(record.get("command"))
    repo_path = _optional_string(record.get("repo_path"))
    focused_files = _string_list(record.get("focused_files"))
    evidence = _string_list(record.get("evidence"))
    diagnosis_next_actions = _string_list(record.get("suggested_next_actions"))
    validation_command = command

    setup_profile = "manual_review"
    setup_commands: list[str] = []
    status = "manual_review"
    requires_network = False
    sandbox_required = True
    risk_notes = [
        "setup planning only; commands are not executed by this report",
        "run setup only in a disposable sandbox with no host secrets",
    ]
    suggested_next_actions = [
        "review the focused diagnosis and repository setup docs before executing setup",
    ]

    if category == "focused_test_passed":
        setup_profile = "no_setup_required"
        status = "ready"
        sandbox_required = False
        risk_notes = ["focused command already passed in the saved run"]
        suggested_next_actions = [
            "use the focused command as targeted validation for a later repair attempt",
        ]
    elif category == "missing_generated_version_metadata":
        setup_profile = "python_editable_install_build_metadata"
        status = "planned"
        requires_network = True
        setup_commands = [
            "python3 -m pip install -e .",
            "python3 -m pytest --version",
        ]
        suggested_next_actions = [
            "prepare generated package metadata in an isolated Python environment",
            "rerun the focused validation command after setup succeeds",
        ]
    elif category == "pytest_fixture_dependency_error":
        setup_profile = "pytest_fixture_environment"
        status = "planned"
        requires_network = True
        setup_commands = [
            _focused_test_dependency_install_command(repo_path),
            _fixture_listing_command(focused_files),
        ]
        risk_notes.append("fixture setup may require optional test dependencies or local services")
        suggested_next_actions = [
            "install upstream test extras in an isolated Python environment",
            "prefer narrower issue-specific tests that avoid service fixtures when possible",
        ]
    elif category == "missing_python_module":
        setup_profile = "python_dependency_install"
        status = "planned"
        requires_network = True
        setup_commands = ["python3 -m pip install -e ."]
        suggested_next_actions = [
            "install repository dependencies in an isolated Python environment",
            "rerun focused validation before repair attempts",
        ]
    elif category == "pytest_setup_error":
        setup_profile = "pytest_setup_environment"
        status = "planned"
        requires_network = True
        setup_commands = [_focused_test_dependency_install_command(repo_path)]
        suggested_next_actions = [
            "inspect fixture and service requirements before automated repair",
            "rerun focused validation after setup changes",
        ]
    elif category == "timeout":
        setup_profile = "scope_timeout_review"
        suggested_next_actions = [
            "reduce the focused command scope or raise timeout only after cost review",
        ]
    elif category == "execution_blocked":
        setup_profile = "policy_or_sandbox_review"
        suggested_next_actions = [
            "fix command policy, repo snapshot, or sandbox availability before running setup",
        ]
    elif category == "missing_logs":
        setup_profile = "rerun_with_log_capture"
        suggested_next_actions = [
            "rerun the focused command with stdout and stderr capture before setup planning",
        ]
    elif diagnosis_next_actions:
        suggested_next_actions = diagnosis_next_actions

    return IssueCorpusFocusedTestSetupPlanResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        category=category,
        severity=severity,
        repo_path=repo_path,
        setup_profile=setup_profile,
        setup_commands=setup_commands,
        validation_command=validation_command,
        focused_files=focused_files,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        evidence=evidence,
        risk_notes=risk_notes,
        suggested_next_actions=suggested_next_actions,
    )


def _focused_test_dependency_install_command(repo_path: str | None) -> str:
    pyproject_path = Path(repo_path) / "pyproject.toml" if repo_path else None
    if pyproject_path is not None and pyproject_path.exists():
        try:
            parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            parsed = {}
        dependency_groups = parsed.get("dependency-groups")
        if isinstance(dependency_groups, dict) and "test" in dependency_groups:
            return "python3 -m pip install -e . --group test"
    return 'python3 -m pip install -e ".[test]"'
