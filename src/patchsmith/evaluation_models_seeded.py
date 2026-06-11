"""Seeded dataset evaluation dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SeededTask:
    task_id: str
    task_dir: Path
    repo: Path
    issue_text: str
    test_command: str
    expected_touched_files: list[str]
    expected_related_tests: list[str]
    language: str
    failure_type: str


@dataclass(frozen=True)
class SeededTaskValidationResult:
    task_dir: str
    task_id: str | None
    status: str
    errors: list[str]
    warnings: list[str]
    issue_path: str | None
    repo_path: str | None
    expected_path: str | None
    expected_touched_files: list[str]
    expected_related_tests: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeededDatasetValidationSummary:
    dataset_dir: str
    task_count: int
    valid_tasks: int
    invalid_tasks: int
    warning_count: int
    error_count: int
    duplicate_task_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
