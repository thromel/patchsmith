"""Core public issue corpus evaluation dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IssueCorpusEntryValidationResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    errors: list[str]
    warnings: list[str]
    language: str | None
    task_type: str | None
    state_at_capture: str | None
    expected_workflow: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusValidationSummary:
    corpus_path: str
    corpus_id: str | None
    entry_count: int
    valid_entries: int
    invalid_entries: int
    warning_count: int
    error_count: int
    repositories: list[str]
    languages: list[str]
    task_types: list[str]
    open_issue_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusRepoPreflightResult:
    repository: str
    repo_url: str
    status: str
    default_branch: str | None
    head_sha: str | None
    latency_ms: int
    error: str | None
    issue_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusRepoPreflightSummary:
    corpus_path: str
    repository_count: int
    reachable_repositories: int
    unreachable_repositories: int
    issue_count: int
    avg_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusContextPreviewResult:
    task_id: str
    repository: str
    issue_url: str
    status: str
    error: str | None
    repo_path: str | None
    commit_hash: str | None
    branch: str | None
    file_count: int
    language_summary: dict[str, int]
    package_manager: str | None
    test_commands: list[str]
    context_provider: str
    context_count: int
    retrieved_files: list[str]
    top_contexts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusContextPreviewSummary:
    corpus_path: str
    attempted_issues: int
    completed_issues: int
    failed_issues: int
    repository_count: int
    context_provider: str
    avg_context_count: float
    source_free: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
