"""Focused public issue test dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IssueCorpusFocusedTestPlanResult:
    task_id: str | None
    task_dir: str
    status: str
    repository: str | None
    issue_url: str | None
    repo_path: str | None
    focused_files: list[str]
    command: str | None
    policy_allowed: bool
    policy_reason: str | None
    fallback_command: str | None
    risk_notes: list[str]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestPlanSummary:
    tasks_dir: str
    task_count: int
    planned_tasks: int
    fallback_tasks: int
    blocked_tasks: int
    policy_allowed_commands: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestRunResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    command: str | None
    repo_path: str | None
    focused_files: list[str]
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    policy_allowed: bool
    policy_reason: str | None
    stdout_path: str | None
    stderr_path: str | None
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestRunSummary:
    plan_path: str
    task_count: int
    attempted_tasks: int
    passed_tasks: int
    failed_tasks: int
    timed_out_tasks: int
    blocked_tasks: int
    sandbox_mode: str
    sandbox_network: str
    timeout_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestDiagnosisResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    run_status: str | None
    command: str | None
    repo_path: str | None
    focused_files: list[str]
    category: str
    severity: str
    summary: str
    evidence: list[str]
    suggested_next_actions: list[str]
    stdout_path: str | None
    stderr_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestDiagnosisSummary:
    run_results_path: str
    task_count: int
    passed_tasks: int
    environment_issue_tasks: int
    dependency_issue_tasks: int
    timeout_tasks: int
    blocked_tasks: int
    unknown_failure_tasks: int
    category_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupPlanResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    category: str
    severity: str
    repo_path: str | None
    setup_profile: str
    setup_commands: list[str]
    validation_command: str | None
    focused_files: list[str]
    requires_network: bool
    sandbox_required: bool
    evidence: list[str]
    risk_notes: list[str]
    suggested_next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupPlanSummary:
    diagnosis_path: str
    task_count: int
    planned_tasks: int
    ready_tasks: int
    manual_review_tasks: int
    dependency_setup_tasks: int
    environment_setup_tasks: int
    network_required_tasks: int
    sandbox_required_tasks: int
    category_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupReadinessResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    setup_profile: str
    repo_path: str | None
    repo_exists: bool
    setup_commands: list[str]
    validation_command: str | None
    requires_network: bool
    sandbox_required: bool
    docker_smoke_status: str
    errors: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupReadinessSummary:
    setup_plan_path: str
    docker_smoke_path: str
    docker_smoke_status: str
    task_count: int
    ready_tasks: int
    warning_tasks: int
    blocked_tasks: int
    network_required_tasks: int
    sandbox_required_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupCommandResult:
    command: str
    status: str
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    policy_allowed: bool
    policy_reason: str | None
    stdout_path: str | None
    stderr_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupExecutionResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    readiness_status: str
    setup_profile: str
    repo_path: str | None
    setup_commands: list[str]
    validation_command: str | None
    requires_network: bool
    sandbox_required: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    dry_run: bool
    allow_dependency_installs: bool
    command_results: list[IssueCorpusFocusedTestSetupCommandResult]
    errors: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command_results"] = [
            command_result.to_dict() for command_result in self.command_results
        ]
        return payload


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupExecutionSummary:
    readiness_path: str
    task_count: int
    dry_run: bool
    allow_warnings: bool
    allow_dependency_installs: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    timeout_seconds: int
    dry_run_tasks: int
    attempted_tasks: int
    completed_tasks: int
    failed_tasks: int
    timed_out_tasks: int
    blocked_tasks: int
    skipped_tasks: int
    command_count: int
    attempted_commands: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupValidationResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    setup_execution_status: str
    setup_profile: str
    repo_path: str | None
    validation_command: str | None
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    dry_run: bool
    failure_category: str | None
    failure_summary: str | None
    failure_evidence: list[str]
    command_result: IssueCorpusFocusedTestSetupCommandResult | None
    errors: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command_result"] = (
            self.command_result.to_dict() if self.command_result is not None else None
        )
        return payload


@dataclass(frozen=True)
class IssueCorpusFocusedTestSetupValidationSummary:
    setup_execution_path: str
    task_count: int
    dry_run: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    timeout_seconds: int
    dry_run_tasks: int
    attempted_tasks: int
    passed_tasks: int
    failed_tasks: int
    timed_out_tasks: int
    blocked_tasks: int
    skipped_tasks: int
    failure_category_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
