"""Materialized public issue task dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskResult:
    task_id: str
    repository: str
    issue_url: str
    status: str
    error: str | None
    task_dir: str | None
    manifest_path: str | None
    issue_path: str | None
    runbook_path: str | None
    repo_url: str
    commit_hash: str | None
    context_provider: str | None
    context_count: int
    retrieved_files: list[str]
    suggested_test_commands: list[str]
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskSummary:
    corpus_path: str
    context_preview_path: str
    output_dir: str
    attempted_issues: int
    materialized_tasks: int
    failed_tasks: int
    repository_count: int
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskValidationResult:
    task_id: str | None
    task_dir: str
    status: str
    errors: list[str]
    warnings: list[str]
    manifest_path: str | None
    issue_path: str | None
    runbook_path: str | None
    repository: str | None
    issue_url: str | None
    repo_path: str | None
    retrieved_files: list[str]
    suggested_commands: list[str]
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedTaskValidationSummary:
    tasks_dir: str
    task_count: int
    valid_tasks: int
    invalid_tasks: int
    warning_count: int
    error_count: int
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedRunReadinessResult:
    task_id: str | None
    task_dir: str
    status: str
    repository: str | None
    issue_url: str | None
    repo_path: str | None
    repo_exists: bool
    file_count: int | None
    package_manager: str | None
    test_commands: list[str]
    allowed_test_commands: int
    blocked_test_commands: int
    command_checks: list[dict[str, Any]]
    suggested_commands: list[str]
    risk_level: str
    risk_notes: list[str]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusMaterializedRunReadinessSummary:
    tasks_dir: str
    task_count: int
    ready_tasks: int
    warning_tasks: int
    blocked_tasks: int
    allowed_test_commands: int
    blocked_test_commands: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
