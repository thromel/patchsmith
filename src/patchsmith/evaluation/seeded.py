"""Evaluation seeded (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _duplicate_task_ids,
    _expected_string,
    _expected_string_list,
    _validate_expected_repo_file,
    _with_validation_error,
)
from patchsmith.evaluation_models import (
    SeededDatasetValidationSummary,
    SeededTask,
    SeededTaskValidationResult,
)
from patchsmith.evaluation_reports import (
    render_seeded_dataset_validation_report,
)


def load_seeded_tasks(dataset_dir: Path) -> list[SeededTask]:
    tasks: list[SeededTask] = []
    for task_dir in sorted(path for path in dataset_dir.iterdir() if path.is_dir()):
        expected_path = task_dir / "expected.json"
        issue_path = task_dir / "issue.md"
        repo_path = task_dir / "repo"
        if not expected_path.exists() or not issue_path.exists() or not repo_path.exists():
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        tasks.append(
            SeededTask(
                task_id=str(expected["task_id"]),
                task_dir=task_dir,
                repo=repo_path,
                issue_text=issue_path.read_text(encoding="utf-8"),
                test_command=str(expected["test_command"]),
                expected_touched_files=list(expected.get("expected_touched_files", [])),
                expected_related_tests=list(expected.get("expected_related_tests", [])),
                language=str(expected.get("language", "unknown")),
                failure_type=str(expected.get("failure_type", "unknown")),
            )
        )
    return tasks


def validate_seeded_dataset(
    *,
    dataset_dir: Path,
    output_dir: Path,
) -> tuple[list[SeededTaskValidationResult], SeededDatasetValidationSummary]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset directory does not exist: {dataset_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    task_dirs = sorted(path for path in dataset_dir.iterdir() if path.is_dir())
    results = [_validate_seeded_task_dir(task_dir) for task_dir in task_dirs]
    duplicate_task_ids = _duplicate_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_validation_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]

    summary = summarize_seeded_dataset_validation(
        dataset_dir=dataset_dir,
        results=results,
        duplicate_task_ids=duplicate_task_ids,
    )
    write_seeded_dataset_validation_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_seeded_dataset_validation(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    duplicate_task_ids: list[str] | None = None,
) -> SeededDatasetValidationSummary:
    return SeededDatasetValidationSummary(
        dataset_dir=str(dataset_dir),
        task_count=len(results),
        valid_tasks=sum(1 for result in results if result.status == "valid"),
        invalid_tasks=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        duplicate_task_ids=duplicate_task_ids or _duplicate_task_ids(results),
    )


def write_seeded_dataset_validation_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> None:
    results_json = output_dir / "validation_results.json"
    results_csv = output_dir / "validation_results.csv"
    summary_json = output_dir / "validation_summary.json"
    report_path = output_dir / "validation_report.md"

    write_json(results_json, [result.to_dict() for result in results])
    write_json(summary_json, summary.to_dict())

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["errors"] = ";".join(result.errors)
                row["warnings"] = ";".join(result.warnings)
                row["expected_touched_files"] = ";".join(result.expected_touched_files)
                row["expected_related_tests"] = ";".join(result.expected_related_tests)
                writer.writerow(row)

    report_path.write_text(
        render_seeded_dataset_validation_report(
            dataset_dir=dataset_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _validate_seeded_task_dir(task_dir: Path) -> SeededTaskValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    expected_path = task_dir / "expected.json"
    issue_path = task_dir / "issue.md"
    repo_path = task_dir / "repo"
    expected: dict[str, Any] = {}

    if not expected_path.exists():
        errors.append("missing expected.json")
    else:
        try:
            parsed = json.loads(expected_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                errors.append("expected.json must contain a JSON object")
            else:
                expected = parsed
        except json.JSONDecodeError as error:
            errors.append(f"expected.json is invalid JSON: {error.msg}")

    if not issue_path.exists():
        errors.append("missing issue.md")
    elif not issue_path.read_text(encoding="utf-8").strip():
        errors.append("issue.md is empty")

    if not repo_path.exists():
        errors.append("missing repo directory")
    elif not repo_path.is_dir():
        errors.append("repo path is not a directory")

    task_id = _expected_string(expected, "task_id", errors)
    test_command = _expected_string(expected, "test_command", errors)
    language = _expected_string(expected, "language", errors)
    _expected_string(expected, "failure_type", errors)
    expected_touched_files = _expected_string_list(expected, "expected_touched_files", errors)
    expected_related_tests = _expected_string_list(expected, "expected_related_tests", errors)

    if task_id and task_id != task_dir.name:
        warnings.append(f"task_id does not match directory name: {task_id} != {task_dir.name}")
    if test_command and "pytest" not in test_command:
        warnings.append(f"test command is not the current seeded-suite default: {test_command}")
    if language and language.lower() != "python":
        warnings.append(f"non-python seeded task language: {language}")
    if repo_path.exists() and repo_path.is_dir():
        for relative_path in expected_touched_files:
            _validate_expected_repo_file(repo_path, relative_path, "expected_touched_files", errors)
        for relative_path in expected_related_tests:
            _validate_expected_repo_file(repo_path, relative_path, "expected_related_tests", errors)
        if not any(repo_path.rglob("test_*.py")):
            warnings.append("repo has no Python test files matching test_*.py")

    return SeededTaskValidationResult(
        task_dir=str(task_dir),
        task_id=task_id,
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        issue_path=str(issue_path) if issue_path.exists() else None,
        repo_path=str(repo_path) if repo_path.exists() else None,
        expected_path=str(expected_path) if expected_path.exists() else None,
        expected_touched_files=expected_touched_files,
        expected_related_tests=expected_related_tests,
    )
