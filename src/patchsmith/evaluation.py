from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
import time
import tomllib
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from patchsmith.context import (
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBundle,
    CtxhelmCliBroker,
    PatchSmithNativeBroker,
    retrieved_context_from_bundle,
)
from patchsmith.context_packing import summarize_context_pack
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext, RunRequest
from patchsmith.patching import PatchSafetyError, apply_text_replacement
from patchsmith.planning import HeuristicRepairPlanner, RepairPlan
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy, FocusedSetupCommandPolicy
from patchsmith.workflow import RepairRunner

PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES = 64_000


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


@dataclass(frozen=True)
class IssueCorpusPublicReproductionPlanResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    repo_path: str | None
    repo_exists: bool
    reproduction_command: str | None
    command_source: str
    policy_allowed: bool
    policy_reason: str | None
    focused_files: list[str]
    fixture_files: list[dict[str, str]]
    expected_failure_signals: list[str]
    manual_spec_required: bool
    evidence: list[str]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicReproductionPlanSummary:
    generated_at: str
    tasks_dir: str
    focused_plan_path: str | None
    task_count: int
    planned_tasks: int
    warning_tasks: int
    blocked_tasks: int
    manual_spec_required_tasks: int
    command_count: int
    policy_allowed_commands: int
    fixture_file_tasks: int
    fixture_file_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicReproductionSpecValidationResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    spec_present: bool
    repo_path: str | None
    repo_exists: bool
    reproduction_command: str | None
    command_source: str
    policy_allowed: bool
    policy_reason: str | None
    fixture_files: list[dict[str, str]]
    expected_failure_signals: list[str]
    errors: list[str]
    warnings: list[str]
    evidence: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicReproductionSpecValidationSummary:
    generated_at: str
    specs_path: str
    tasks_dir: str
    focused_plan_path: str | None
    task_count: int
    spec_count: int
    ready_tasks: int
    warning_tasks: int
    blocked_tasks: int
    missing_spec_tasks: int
    empty_signal_tasks: int
    policy_blocked_tasks: int
    extra_spec_tasks: int
    fixture_file_tasks: int
    fixture_file_count: int
    unsafe_fixture_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicFailureSignalDiscoveryResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    reproduction_plan_status: str
    repo_path: str | None
    reproduction_command: str | None
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    dry_run: bool
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    policy_allowed: bool
    policy_reason: str | None
    stdout_path: str | None
    stderr_path: str | None
    fixture_paths: list[str]
    candidate_failure_signals: list[str]
    errors: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicFailureSignalDiscoverySummary:
    generated_at: str
    reproduction_plan_path: str
    task_count: int
    dry_run: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    timeout_seconds: int
    dry_run_tasks: int
    attempted_tasks: int
    observed_failure_tasks: int
    passed_tasks: int
    timed_out_tasks: int
    blocked_tasks: int
    policy_allowed_commands: int
    candidate_signal_tasks: int
    fixture_file_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicReproductionExecutionResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    reproduction_plan_status: str
    repo_path: str | None
    reproduction_command: str | None
    expected_failure_signals: list[str]
    manual_spec_required: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    dry_run: bool
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    policy_allowed: bool
    policy_reason: str | None
    stdout_path: str | None
    stderr_path: str | None
    fixture_paths: list[str]
    matched_failure_signals: list[str]
    missing_failure_signals: list[str]
    errors: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicReproductionExecutionSummary:
    generated_at: str
    reproduction_plan_path: str
    task_count: int
    dry_run: bool
    sandbox_mode: str
    sandbox_image: str
    sandbox_network: str
    timeout_seconds: int
    dry_run_tasks: int
    attempted_tasks: int
    reproduced_tasks: int
    not_reproduced_tasks: int
    failed_tasks: int
    timed_out_tasks: int
    blocked_tasks: int
    manual_spec_required_tasks: int
    policy_allowed_commands: int
    fixture_file_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicRepairReadinessResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    repo_path: str | None
    repo_exists: bool
    repair_command: str | None
    validation_command: str | None
    focused_run_status: str | None
    diagnosis_category: str | None
    setup_validation_status: str | None
    setup_failure_category: str | None
    reproduction_execution_status: str | None
    reproduction_stdout_path: str | None
    reproduction_stderr_path: str | None
    matched_failure_signals: list[str]
    sandbox_mode: str | None
    sandbox_network: str | None
    evidence: list[str]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicRepairReadinessSummary:
    generated_at: str
    tasks_dir: str | None
    focused_run_path: str
    diagnosis_path: str
    setup_validation_path: str
    reproduction_execution_path: str | None
    task_count: int
    ready_tasks: int
    warning_tasks: int
    blocked_tasks: int
    repair_command_tasks: int
    passed_focused_tasks: int
    passed_setup_validation_tasks: int
    reproduced_tasks: int
    missing_reproduction_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicRepairAttemptResult:
    task_id: str | None
    repository: str | None
    issue_url: str | None
    status: str
    readiness_status: str
    repo_path: str | None
    repo_exists: bool
    repair_command: str | None
    validation_command: str | None
    reproduction_execution_status: str | None
    runtime: str
    planner: str
    context_provider: str
    sandbox_mode: str
    sandbox_image: str
    dry_run: bool
    run_id: str | None
    run_status: str | None
    report_path: str | None
    trace_path: str | None
    final_diff_path: str | None
    test_exit_code: int | None
    patch_generated: bool
    errors: list[str]
    warnings: list[str]
    evidence: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueCorpusPublicRepairAttemptSummary:
    generated_at: str
    readiness_path: str
    tasks_dir: str | None
    task_count: int
    dry_run: bool
    allow_warnings: bool
    runtime: str
    planner: str
    context_provider: str
    sandbox_mode: str
    sandbox_image: str
    dry_run_tasks: int
    attempted_tasks: int
    validated_tasks: int
    failed_tasks: int
    blocked_tasks: int
    warning_tasks: int
    reproduced_input_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvalResult:
    task_id: str
    context_provider: str
    status: str
    error: str | None
    retrieved_files: list[str]
    related_test_files: list[str]
    expected_touched_files: list[str]
    expected_related_tests: list[str]
    top1_touched_recall: float
    top3_touched_recall: float
    top5_touched_recall: float
    related_test_recall: float
    latency_ms: int
    context_count: int
    source_context_count: int
    test_context_count: int
    context_excerpt_chars: int
    context_approx_tokens: int
    fallback_used: bool
    source_text_logged: bool
    source_free_violation: bool
    raw_artifact_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvalSummary:
    provider: str
    attempted_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_top1_touched_recall: float
    avg_top3_touched_recall: float
    avg_top5_touched_recall: float
    avg_related_test_recall: float
    avg_latency_ms: float
    avg_context_count: float
    avg_source_context_count: float
    avg_test_context_count: float
    avg_context_excerpt_chars: float
    avg_context_approx_tokens: float
    fallback_count: int
    source_free_violation_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairEvalResult:
    task_id: str
    runtime: str
    planner: str
    context_provider: str
    status: str
    error: str | None
    patch_generated: bool
    targeted_tests_passed: bool
    test_exit_code: int | None
    report_path: str | None
    trace_path: str | None
    final_diff_path: str | None
    retrieved_files: list[str]
    latency_ms: int
    trace_event_count: int = 0
    runtime_node_count: int = 0
    failed_trace_event_count: int = 0
    retry_event_count: int = 0
    debuggability_score: float = 0.0
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairEvalSummary:
    runtime: str
    planner: str
    context_provider: str
    attempted_tasks: int
    completed_tasks: int
    patch_generated_rate: float
    targeted_test_pass_rate: float
    avg_latency_ms: float
    avg_trace_events: float = 0.0
    avg_runtime_nodes: float = 0.0
    failed_trace_event_count: int = 0
    avg_retry_events: float = 0.0
    avg_debuggability_score: float = 0.0
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScaffoldComparisonResult:
    scaffold: str
    runtime: str
    planner: str
    context_provider: str
    attempted_tasks: int
    completed_tasks: int
    patch_generated_rate: float
    targeted_test_pass_rate: float
    avg_latency_ms: float
    avg_trace_events: float
    avg_runtime_nodes: float
    failed_trace_event_count: int
    avg_retry_events: float
    avg_debuggability_score: float
    model_provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    repair_report_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScaffoldVariant:
    name: str
    runtime: str
    planner: str


SCAFFOLD_VARIANTS: dict[str, ScaffoldVariant] = {
    "agentless": ScaffoldVariant("agentless", "agentless", "heuristic"),
    "heuristic": ScaffoldVariant("heuristic", "heuristic", "heuristic"),
    "langgraph": ScaffoldVariant("langgraph", "langgraph", "heuristic"),
    "langgraph_fake_model": ScaffoldVariant("langgraph_fake_model", "langgraph", "fake_model"),
    "deepagents": ScaffoldVariant("deepagents", "deepagents", "heuristic"),
    "openai_agents": ScaffoldVariant("openai_agents", "openai_agents", "heuristic"),
}


@dataclass(frozen=True)
class PatchSearchCandidateResult:
    candidate_index: int
    name: str
    path: str | None
    status: str
    test_exit_code: int | None
    tests_passed: bool
    diff: str
    duration_ms: int
    risk_score: float
    reason: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchSearchEvalResult:
    task_id: str
    variant: str
    candidate_count: int
    status: str
    success_at_1: bool
    success_at_k: bool
    selected_candidate_index: int | None
    selected_candidate_name: str | None
    selected_candidate_passed: bool
    test_runs: int
    latency_ms: int
    candidate_results: list[PatchSearchCandidateResult]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchSearchEvalSummary:
    variant: str
    candidate_count: int
    attempted_tasks: int
    completed_tasks: int
    success_at_1_rate: float
    success_at_k_rate: float
    selected_success_rate: float
    avg_latency_ms: float
    avg_test_runs: float
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def validate_issue_corpus(
    *,
    corpus_path: Path,
    output_dir: Path,
) -> tuple[list[IssueCorpusEntryValidationResult], IssueCorpusValidationSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"issue corpus is invalid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ValueError("issue corpus must contain a JSON object")
    entries_payload = payload.get("issues")
    if not isinstance(entries_payload, list):
        raise ValueError("issue corpus missing list field: issues")
    results = [
        _validate_issue_corpus_entry(entry, index)
        for index, entry in enumerate(entries_payload)
    ]
    duplicate_task_ids = _duplicate_issue_corpus_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_issue_corpus_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]
    summary = summarize_issue_corpus_validation(
        corpus_path=corpus_path,
        corpus_id=payload.get("corpus_id") if isinstance(payload.get("corpus_id"), str) else None,
        results=results,
    )
    write_issue_corpus_validation_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_validation(
    *,
    corpus_path: Path,
    corpus_id: str | None,
    results: list[IssueCorpusEntryValidationResult],
) -> IssueCorpusValidationSummary:
    repositories = sorted(
        {
            result.repository
            for result in results
            if result.repository
        }
    )
    languages = sorted({result.language for result in results if result.language})
    task_types = sorted({result.task_type for result in results if result.task_type})
    return IssueCorpusValidationSummary(
        corpus_path=str(corpus_path),
        corpus_id=corpus_id,
        entry_count=len(results),
        valid_entries=sum(1 for result in results if result.status == "valid"),
        invalid_entries=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        repositories=repositories,
        languages=languages,
        task_types=task_types,
        open_issue_count=sum(1 for result in results if result.state_at_capture == "open"),
    )


def write_issue_corpus_validation_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusEntryValidationResult],
    summary: IssueCorpusValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corpus_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "corpus_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "corpus_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "errors",
                "warnings",
                "language",
                "task_type",
                "state_at_capture",
                "expected_workflow",
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
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "language": result.language,
                    "task_type": result.task_type,
                    "state_at_capture": result.state_at_capture,
                    "expected_workflow": ";".join(result.expected_workflow),
                }
            )
    (output_dir / "corpus_report.md").write_text(
        render_issue_corpus_validation_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def preflight_issue_corpus_repositories(
    *,
    corpus_path: Path,
    output_dir: Path,
    timeout_seconds: int = 20,
) -> tuple[list[IssueCorpusRepoPreflightResult], IssueCorpusRepoPreflightSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    repositories = _issue_corpus_repositories(payload["issues"])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _preflight_issue_corpus_repository(
            repository=repository,
            repo_url=repo_url,
            issue_count=issue_count,
            timeout_seconds=timeout_seconds,
        )
        for repository, repo_url, issue_count in repositories
    ]
    summary = summarize_issue_corpus_repo_preflight(
        corpus_path=corpus_path,
        results=results,
    )
    write_issue_corpus_repo_preflight_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_repo_preflight(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
) -> IssueCorpusRepoPreflightSummary:
    latencies = [result.latency_ms for result in results if result.status == "reachable"]
    return IssueCorpusRepoPreflightSummary(
        corpus_path=str(corpus_path),
        repository_count=len(results),
        reachable_repositories=sum(1 for result in results if result.status == "reachable"),
        unreachable_repositories=sum(1 for result in results if result.status != "reachable"),
        issue_count=sum(result.issue_count for result in results),
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    )


def write_issue_corpus_repo_preflight_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repo_preflight_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "repo_preflight_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "repo_preflight_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())
    (output_dir / "repo_preflight_report.md").write_text(
        render_issue_corpus_repo_preflight_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def preview_issue_corpus_context(
    *,
    corpus_path: Path,
    output_dir: Path,
    context_provider: str = "native_hybrid",
    top_k: int = 5,
    max_issues: int | None = None,
) -> tuple[list[IssueCorpusContextPreviewResult], IssueCorpusContextPreviewSummary]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    issues = [issue for issue in payload["issues"] if isinstance(issue, dict)]
    if max_issues is not None:
        issues = issues[:max_issues]
    output_dir.mkdir(parents=True, exist_ok=True)
    repositories_dir = output_dir / "repositories"
    repositories_dir.mkdir(parents=True, exist_ok=True)
    snapshots: dict[str, Any] = {}
    indexes: dict[str, Any] = {}
    results: list[IssueCorpusContextPreviewResult] = []

    for issue in issues:
        task_id = str(issue.get("task_id", "unknown"))
        repository = str(issue.get("repository", "unknown"))
        issue_url = str(issue.get("issue_url", ""))
        repo_url = str(issue.get("repo_url", ""))
        try:
            if repository not in snapshots:
                repo_dir = repositories_dir / _safe_artifact_name(repository)
                if repo_dir.exists():
                    _remove_artifact_dir(root=output_dir, target=repo_dir)
                snapshot = clone_or_copy_repository(repo_url, repo_dir)
                snapshots[repository] = snapshot
                indexes[repository] = index_repository(snapshot.repo_path)
            snapshot = snapshots[repository]
            repo_index = indexes[repository]
            retriever = _issue_corpus_retriever(context_provider)
            contexts = retriever.retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=_issue_corpus_issue_text(issue),
                top_k=top_k,
            )
            contexts = _supplement_context_preview_source_neighbors(
                contexts=contexts,
                repo_index=repo_index,
                top_k=top_k,
                context_provider=context_provider,
            )
            results.append(
                IssueCorpusContextPreviewResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="completed",
                    error=None,
                    repo_path=str(snapshot.repo_path),
                    commit_hash=snapshot.commit_hash,
                    branch=snapshot.branch,
                    file_count=snapshot.file_count,
                    language_summary=snapshot.language_summary,
                    package_manager=snapshot.package_manager,
                    test_commands=snapshot.test_commands,
                    context_provider=context_provider,
                    context_count=len(contexts),
                    retrieved_files=[context.path for context in contexts],
                    top_contexts=[_source_free_context(context) for context in contexts],
                )
            )
        except Exception as error:  # noqa: BLE001 - report all corpus materialization failures.
            results.append(
                IssueCorpusContextPreviewResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="failed",
                    error=str(error),
                    repo_path=None,
                    commit_hash=None,
                    branch=None,
                    file_count=0,
                    language_summary={},
                    package_manager=None,
                    test_commands=[],
                    context_provider=context_provider,
                    context_count=0,
                    retrieved_files=[],
                    top_contexts=[],
                )
            )

    summary = summarize_issue_corpus_context_preview(
        corpus_path=corpus_path,
        results=results,
        context_provider=context_provider,
    )
    write_issue_corpus_context_preview_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_context_preview(
    *,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    context_provider: str,
) -> IssueCorpusContextPreviewSummary:
    completed = [result for result in results if result.status == "completed"]
    return IssueCorpusContextPreviewSummary(
        corpus_path=str(corpus_path),
        attempted_issues=len(results),
        completed_issues=len(completed),
        failed_issues=sum(1 for result in results if result.status != "completed"),
        repository_count=len({result.repository for result in results}),
        context_provider=context_provider,
        avg_context_count=(
            round(sum(result.context_count for result in completed) / len(completed), 1)
            if completed
            else 0.0
        ),
        source_free=all(
            "excerpt" not in context
            for result in results
            for context in result.top_contexts
        ),
    )


def write_issue_corpus_context_preview_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    summary: IssueCorpusContextPreviewSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "context_preview_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "context_preview_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "context_preview_results.csv").open(
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
                "error",
                "commit_hash",
                "branch",
                "file_count",
                "package_manager",
                "test_commands",
                "context_provider",
                "context_count",
                "retrieved_files",
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
                    "error": result.error,
                    "commit_hash": result.commit_hash,
                    "branch": result.branch,
                    "file_count": result.file_count,
                    "package_manager": result.package_manager,
                    "test_commands": ";".join(result.test_commands),
                    "context_provider": result.context_provider,
                    "context_count": result.context_count,
                    "retrieved_files": ";".join(result.retrieved_files),
                }
            )
    (output_dir / "context_preview_report.md").write_text(
        render_issue_corpus_context_preview_report(
            corpus_path=corpus_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def materialize_issue_corpus_tasks(
    *,
    corpus_path: Path,
    output_dir: Path,
    context_preview_path: Path | None = None,
    max_issues: int | None = None,
) -> tuple[
    list[IssueCorpusMaterializedTaskResult],
    IssueCorpusMaterializedTaskSummary,
]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"issue corpus does not exist: {corpus_path}")
    context_preview_path = context_preview_path or output_dir / "context_preview_results.json"
    if not context_preview_path.exists():
        raise FileNotFoundError(
            f"context preview results do not exist: {context_preview_path}"
        )

    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
        raise ValueError("issue corpus missing list field: issues")
    issues = [issue for issue in payload["issues"] if isinstance(issue, dict)]
    if max_issues is not None:
        issues = issues[:max_issues]

    preview_payload = json.loads(context_preview_path.read_text(encoding="utf-8"))
    if not isinstance(preview_payload, list):
        raise ValueError("context preview results must contain a JSON list")
    previews_by_task = {
        str(item.get("task_id")): item
        for item in preview_payload
        if isinstance(item, dict) and item.get("task_id")
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = output_dir / "materialized_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results: list[IssueCorpusMaterializedTaskResult] = []
    corpus_id = payload.get("corpus_id") if isinstance(payload.get("corpus_id"), str) else None

    for issue in issues:
        task_id = str(issue.get("task_id", "unknown"))
        repository = str(issue.get("repository", "unknown"))
        issue_url = str(issue.get("issue_url", ""))
        repo_url = str(issue.get("repo_url", ""))
        task_dir = tasks_dir / _safe_artifact_name(task_id)
        try:
            preview = previews_by_task.get(task_id)
            if not isinstance(preview, dict) or preview.get("status") != "completed":
                raise ValueError(f"missing completed context preview for task: {task_id}")
            if task_dir.exists():
                _remove_artifact_dir(root=output_dir, target=task_dir)
            task_dir.mkdir(parents=True)
            issue_path = task_dir / "issue.md"
            manifest_path = task_dir / "task_manifest.json"
            runbook_path = task_dir / "RUNBOOK.md"
            manifest = _issue_corpus_task_manifest(
                issue=issue,
                preview=preview,
                corpus_id=corpus_id,
                task_dir=task_dir,
                issue_path=issue_path,
            )
            issue_path.write_text(
                _render_materialized_issue(issue=issue, preview=preview),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            runbook_path.write_text(
                _render_materialized_task_runbook(manifest=manifest),
                encoding="utf-8",
            )
            test_commands = _materialized_test_commands(preview)
            source_free = _manifest_is_source_free(manifest)
            results.append(
                IssueCorpusMaterializedTaskResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="materialized",
                    error=None,
                    task_dir=str(task_dir),
                    manifest_path=str(manifest_path),
                    issue_path=str(issue_path),
                    runbook_path=str(runbook_path),
                    repo_url=repo_url,
                    commit_hash=_optional_string(preview.get("commit_hash")),
                    context_provider=_optional_string(preview.get("context_provider")),
                    context_count=int(preview.get("context_count") or 0),
                    retrieved_files=_string_list(preview.get("retrieved_files")),
                    suggested_test_commands=test_commands,
                    source_free=source_free,
                )
            )
        except Exception as error:  # noqa: BLE001 - keep materialization reports complete.
            results.append(
                IssueCorpusMaterializedTaskResult(
                    task_id=task_id,
                    repository=repository,
                    issue_url=issue_url,
                    status="failed",
                    error=str(error),
                    task_dir=str(task_dir),
                    manifest_path=None,
                    issue_path=None,
                    runbook_path=None,
                    repo_url=repo_url,
                    commit_hash=None,
                    context_provider=None,
                    context_count=0,
                    retrieved_files=[],
                    suggested_test_commands=[],
                    source_free=False,
                )
            )

    summary = summarize_issue_corpus_materialized_tasks(
        corpus_path=corpus_path,
        context_preview_path=context_preview_path,
        output_dir=output_dir,
        results=results,
    )
    write_issue_corpus_materialized_task_outputs(
        output_dir=output_dir,
        corpus_path=corpus_path,
        context_preview_path=context_preview_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_issue_corpus_materialized_tasks(
    *,
    corpus_path: Path,
    context_preview_path: Path,
    output_dir: Path,
    results: list[IssueCorpusMaterializedTaskResult],
) -> IssueCorpusMaterializedTaskSummary:
    materialized = [result for result in results if result.status == "materialized"]
    return IssueCorpusMaterializedTaskSummary(
        corpus_path=str(corpus_path),
        context_preview_path=str(context_preview_path),
        output_dir=str(output_dir),
        attempted_issues=len(results),
        materialized_tasks=len(materialized),
        failed_tasks=sum(1 for result in results if result.status != "materialized"),
        repository_count=len({result.repository for result in results}),
        source_free=all(
            result.status == "materialized" and result.source_free
            for result in results
        ),
    )


def write_issue_corpus_materialized_task_outputs(
    *,
    output_dir: Path,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "materialized_task_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "materialized_task_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "materialized_task_results.csv").open(
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
                "error",
                "task_dir",
                "commit_hash",
                "context_provider",
                "context_count",
                "retrieved_files",
                "suggested_test_commands",
                "source_free",
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
                    "error": result.error,
                    "task_dir": result.task_dir,
                    "commit_hash": result.commit_hash,
                    "context_provider": result.context_provider,
                    "context_count": result.context_count,
                    "retrieved_files": ";".join(result.retrieved_files),
                    "suggested_test_commands": ";".join(result.suggested_test_commands),
                    "source_free": result.source_free,
                }
            )
    (output_dir / "materialized_task_report.md").write_text(
        render_issue_corpus_materialized_task_report(
            corpus_path=corpus_path,
            context_preview_path=context_preview_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def validate_materialized_issue_tasks(
    *,
    tasks_dir: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusMaterializedTaskValidationResult],
    IssueCorpusMaterializedTaskValidationSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [_validate_materialized_issue_task_dir(task_dir) for task_dir in task_dirs]
    duplicate_task_ids = _duplicate_materialized_task_ids(results)
    if duplicate_task_ids:
        duplicate_set = set(duplicate_task_ids)
        results = [
            _with_materialized_validation_error(result, "duplicate task_id")
            if result.task_id in duplicate_set
            else result
            for result in results
        ]
    summary = summarize_materialized_issue_task_validation(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_task_validation_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_task_validation(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
) -> IssueCorpusMaterializedTaskValidationSummary:
    return IssueCorpusMaterializedTaskValidationSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        valid_tasks=sum(1 for result in results if result.status == "valid"),
        invalid_tasks=sum(1 for result in results if result.status == "invalid"),
        warning_count=sum(len(result.warnings) for result in results),
        error_count=sum(len(result.errors) for result in results),
        source_free=all(result.source_free for result in results),
    )


def write_materialized_issue_task_validation_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "materialized_task_validation_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "materialized_task_validation_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "materialized_task_validation_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())
    (output_dir / "materialized_task_validation_report.md").write_text(
        render_materialized_issue_task_validation_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def check_materialized_issue_run_readiness(
    *,
    tasks_dir: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusMaterializedRunReadinessResult],
    IssueCorpusMaterializedRunReadinessSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _check_materialized_issue_task_run_readiness(task_dir=task_dir, policy=policy)
        for task_dir in task_dirs
    ]
    summary = summarize_materialized_issue_run_readiness(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_run_readiness_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_run_readiness(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
) -> IssueCorpusMaterializedRunReadinessSummary:
    return IssueCorpusMaterializedRunReadinessSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        allowed_test_commands=sum(result.allowed_test_commands for result in results),
        blocked_test_commands=sum(result.blocked_test_commands for result in results),
    )


def write_materialized_issue_run_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
    summary: IssueCorpusMaterializedRunReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "materialized_run_readiness_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "materialized_run_readiness_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "materialized_run_readiness_results.csv").open(
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
                "repo_exists",
                "file_count",
                "package_manager",
                "allowed_test_commands",
                "blocked_test_commands",
                "risk_level",
                "risk_notes",
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
                    "repo_exists": result.repo_exists,
                    "file_count": result.file_count,
                    "package_manager": result.package_manager,
                    "allowed_test_commands": result.allowed_test_commands,
                    "blocked_test_commands": result.blocked_test_commands,
                    "risk_level": result.risk_level,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "materialized_run_readiness_report.md").write_text(
        render_materialized_issue_run_readiness_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def plan_materialized_issue_focused_tests(
    *,
    tasks_dir: Path,
    output_dir: Path,
    max_paths: int = 2,
) -> tuple[list[IssueCorpusFocusedTestPlanResult], IssueCorpusFocusedTestPlanSummary]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _plan_materialized_issue_focused_test(
            task_dir=task_dir,
            policy=policy,
            max_paths=max_paths,
        )
        for task_dir in task_dirs
    ]
    summary = summarize_materialized_issue_focused_test_plan(
        tasks_dir=tasks_dir,
        results=results,
    )
    write_materialized_issue_focused_test_plan_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_materialized_issue_focused_test_plan(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
) -> IssueCorpusFocusedTestPlanSummary:
    return IssueCorpusFocusedTestPlanSummary(
        tasks_dir=str(tasks_dir),
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        fallback_tasks=sum(1 for result in results if result.status == "fallback"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
    )


def write_materialized_issue_focused_test_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
    summary: IssueCorpusFocusedTestPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_plan_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_plan_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_plan_results.csv").open(
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
                "focused_files",
                "command",
                "policy_allowed",
                "policy_reason",
                "fallback_command",
                "risk_notes",
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
                    "focused_files": ";".join(result.focused_files),
                    "command": result.command,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fallback_command": result.fallback_command,
                    "risk_notes": ";".join(result.risk_notes),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                }
            )
    (output_dir / "focused_test_plan_report.md").write_text(
        render_materialized_issue_focused_test_plan_report(
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


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
    (output_dir / "focused_test_run_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_run_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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


def diagnose_focused_test_runs(
    *,
    results_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestDiagnosisResult],
    IssueCorpusFocusedTestDiagnosisSummary,
]:
    if not results_path.exists():
        raise FileNotFoundError(f"focused test run results do not exist: {results_path}")
    if not results_path.is_file():
        raise ValueError(f"focused test run results path is not a file: {results_path}")
    parsed = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test run results must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test run result records must be JSON objects")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _diagnose_focused_test_run_record(record=record)
        for record in records
    ]
    summary = summarize_focused_test_diagnosis(
        results_path=results_path,
        results=results,
    )
    write_focused_test_diagnosis_outputs(
        output_dir=output_dir,
        results_path=results_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_diagnosis(
    *,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
) -> IssueCorpusFocusedTestDiagnosisSummary:
    category_counts: dict[str, int] = {}
    for result in results:
        category_counts[result.category] = category_counts.get(result.category, 0) + 1
    return IssueCorpusFocusedTestDiagnosisSummary(
        run_results_path=str(results_path),
        task_count=len(results),
        passed_tasks=sum(1 for result in results if result.category == "focused_test_passed"),
        environment_issue_tasks=sum(1 for result in results if result.severity == "environment"),
        dependency_issue_tasks=sum(1 for result in results if result.severity == "dependency"),
        timeout_tasks=sum(1 for result in results if result.category == "timeout"),
        blocked_tasks=sum(1 for result in results if result.severity == "blocked"),
        unknown_failure_tasks=sum(1 for result in results if result.category == "nonzero_exit"),
        category_counts=dict(sorted(category_counts.items())),
    )


def write_focused_test_diagnosis_outputs(
    *,
    output_dir: Path,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
    summary: IssueCorpusFocusedTestDiagnosisSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_diagnosis_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_diagnosis_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_diagnosis_results.csv").open(
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
                "run_status",
                "command",
                "repo_path",
                "focused_files",
                "category",
                "severity",
                "summary",
                "evidence",
                "suggested_next_actions",
                "stdout_path",
                "stderr_path",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "run_status": result.run_status,
                    "command": result.command,
                    "repo_path": result.repo_path,
                    "focused_files": ";".join(result.focused_files),
                    "category": result.category,
                    "severity": result.severity,
                    "summary": result.summary,
                    "evidence": ";".join(result.evidence),
                    "suggested_next_actions": ";".join(result.suggested_next_actions),
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                }
            )
    (output_dir / "focused_test_diagnosis_report.md").write_text(
        render_focused_test_diagnosis_report(
            results_path=results_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


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
    (output_dir / "focused_test_setup_plan_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_plan_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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


def check_focused_test_setup_readiness(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    output_dir: Path,
) -> tuple[
    list[IssueCorpusFocusedTestSetupReadinessResult],
    IssueCorpusFocusedTestSetupReadinessSummary,
]:
    if not setup_plan_path.exists():
        raise FileNotFoundError(f"focused test setup plan does not exist: {setup_plan_path}")
    if not setup_plan_path.is_file():
        raise ValueError(f"focused test setup plan path is not a file: {setup_plan_path}")
    parsed = json.loads(setup_plan_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup plan must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup plan records must be JSON objects")

    docker_smoke_status = _docker_smoke_status_from_file(docker_smoke_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _check_focused_test_setup_record(
            record=record,
            docker_smoke_status=docker_smoke_status,
        )
        for record in records
    ]
    summary = summarize_focused_test_setup_readiness(
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        docker_smoke_status=docker_smoke_status,
        results=results,
    )
    write_focused_test_setup_readiness_outputs(
        output_dir=output_dir,
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_readiness(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    docker_smoke_status: str,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
) -> IssueCorpusFocusedTestSetupReadinessSummary:
    return IssueCorpusFocusedTestSetupReadinessSummary(
        setup_plan_path=str(setup_plan_path),
        docker_smoke_path=str(docker_smoke_path),
        docker_smoke_status=docker_smoke_status,
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        network_required_tasks=sum(1 for result in results if result.requires_network),
        sandbox_required_tasks=sum(1 for result in results if result.sandbox_required),
    )


def write_focused_test_setup_readiness_outputs(
    *,
    output_dir: Path,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
    summary: IssueCorpusFocusedTestSetupReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_readiness_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_readiness_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_readiness_results.csv").open(
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
                "setup_profile",
                "repo_path",
                "repo_exists",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "docker_smoke_status",
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
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "docker_smoke_status": result.docker_smoke_status,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_readiness_report.md").write_text(
        render_focused_test_setup_readiness_report(
            setup_plan_path=setup_plan_path,
            docker_smoke_path=docker_smoke_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def execute_focused_test_setups(
    *,
    readiness_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
    allow_warnings: bool = False,
    allow_dependency_installs: bool = False,
) -> tuple[
    list[IssueCorpusFocusedTestSetupExecutionResult],
    IssueCorpusFocusedTestSetupExecutionSummary,
]:
    if not readiness_path.exists():
        raise FileNotFoundError(
            f"focused test setup readiness does not exist: {readiness_path}"
        )
    if not readiness_path.is_file():
        raise ValueError(
            f"focused test setup readiness path is not a file: {readiness_path}"
        )
    parsed = json.loads(readiness_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("focused test setup readiness must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError("focused test setup readiness records must be JSON objects")
    if allow_dependency_installs and sandbox_mode != "docker":
        raise ValueError("--allow-dependency-installs requires --sandbox-mode docker")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "focused_test_setup_execution"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    policy = (
        FocusedSetupCommandPolicy()
        if allow_dependency_installs
        else CommandPolicy()
    )
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
        _execute_focused_test_setup_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            allow_warnings=allow_warnings,
            allow_dependency_installs=allow_dependency_installs,
        )
        for record in selected_records
    ]
    summary = summarize_focused_test_setup_execution(
        readiness_path=readiness_path,
        results=results,
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        allow_dependency_installs=allow_dependency_installs,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_focused_test_setup_execution_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_focused_test_setup_execution(
    *,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    dry_run: bool,
    allow_warnings: bool,
    allow_dependency_installs: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusFocusedTestSetupExecutionSummary:
    return IssueCorpusFocusedTestSetupExecutionSummary(
        readiness_path=str(readiness_path),
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        allow_dependency_installs=allow_dependency_installs,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"passed", "failed", "timed_out"}
        ),
        completed_tasks=sum(1 for result in results if result.status == "passed"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        skipped_tasks=sum(1 for result in results if result.status == "skipped"),
        command_count=sum(len(result.setup_commands) for result in results),
        attempted_commands=sum(
            1
            for result in results
            for command_result in result.command_results
            if command_result.status in {"passed", "failed", "timed_out"}
        ),
    )


def write_focused_test_setup_execution_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    summary: IssueCorpusFocusedTestSetupExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "focused_test_setup_execution_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_execution_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "focused_test_setup_execution_results.csv").open(
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
                "readiness_status",
                "setup_profile",
                "repo_path",
                "setup_commands",
                "validation_command",
                "requires_network",
                "sandbox_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "allow_dependency_installs",
                "command_results",
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
                    "readiness_status": result.readiness_status,
                    "setup_profile": result.setup_profile,
                    "repo_path": result.repo_path,
                    "setup_commands": ";".join(result.setup_commands),
                    "validation_command": result.validation_command,
                    "requires_network": result.requires_network,
                    "sandbox_required": result.sandbox_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "allow_dependency_installs": result.allow_dependency_installs,
                    "command_results": json.dumps(
                        [command.to_dict() for command in result.command_results],
                        sort_keys=True,
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "focused_test_setup_execution_report.md").write_text(
        render_focused_test_setup_execution_report(
            readiness_path=readiness_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


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
        raise ValueError(
            f"focused test setup execution path is not a file: {setup_execution_path}"
        )
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
    (output_dir / "focused_test_setup_validation_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "focused_test_setup_validation_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
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


def plan_public_issue_reproductions(
    *,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
    reproduction_specs_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionPlanResult],
    IssueCorpusPublicReproductionPlanSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    focused_records = (
        _load_json_record_list(focused_plan_path, label="focused test plan results")
        if focused_plan_path is not None and focused_plan_path.exists()
        else []
    )
    focused_by_task = _records_by_task_id(focused_records)
    reproduction_specs_by_task = (
        _load_public_issue_reproduction_specs(reproduction_specs_path)
        if reproduction_specs_path is not None
        else {}
    )
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _plan_public_issue_reproduction_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=reproduction_specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    summary = summarize_public_issue_reproduction_plan(
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
    )
    write_public_issue_reproduction_plan_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_plan(
    *,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> IssueCorpusPublicReproductionPlanSummary:
    return IssueCorpusPublicReproductionPlanSummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        planned_tasks=sum(1 for result in results if result.status == "planned"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(1 for result in results if result.manual_spec_required),
        command_count=sum(1 for result in results if result.reproduction_command),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
    )


def write_public_issue_reproduction_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
    summary: IssueCorpusPublicReproductionPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_reproduction_plan_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_reproduction_plan_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_reproduction_specs_template.json").write_text(
        json.dumps(
            _public_issue_reproduction_specs_template(results),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_reproduction_plan_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "focused_files",
                "fixture_paths",
                "expected_failure_signals",
                "manual_spec_required",
                "evidence",
                "blockers",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "focused_files": ";".join(result.focused_files),
                    "fixture_paths": ";".join(
                        _public_issue_fixture_paths(result.fixture_files)
                    ),
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_plan_report.md").write_text(
        render_public_issue_reproduction_plan_report(
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def validate_public_issue_reproduction_specs(
    *,
    specs_path: Path,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionSpecValidationResult],
    IssueCorpusPublicReproductionSpecValidationSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    focused_records = (
        _load_json_record_list(focused_plan_path, label="focused test plan results")
        if focused_plan_path is not None and focused_plan_path.exists()
        else []
    )
    focused_by_task = _records_by_task_id(focused_records)
    specs_by_task = _load_public_issue_reproduction_specs(specs_path)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    task_ids = {task_dir.name for task_dir in task_dirs}
    results = [
        _validate_public_issue_reproduction_spec_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    for extra_task_id in sorted(set(specs_by_task) - task_ids):
        results.append(
            IssueCorpusPublicReproductionSpecValidationResult(
                task_id=extra_task_id,
                repository=_optional_string(
                    specs_by_task[extra_task_id].get("repository")
                ),
                issue_url=_optional_string(specs_by_task[extra_task_id].get("issue_url")),
                status="blocked",
                spec_present=True,
                repo_path=None,
                repo_exists=False,
                reproduction_command=_optional_string(
                    specs_by_task[extra_task_id].get("command")
                ),
                command_source="reproduction_spec",
                policy_allowed=False,
                policy_reason=None,
                fixture_files=_normalize_public_issue_fixture_files(
                    specs_by_task[extra_task_id].get("fixture_files")
                )[0],
                expected_failure_signals=_string_list(
                    specs_by_task[extra_task_id].get("expected_failure_signals")
                ),
                errors=["reproduction spec task_id has no materialized task"],
                warnings=[],
                evidence=["reviewed reproduction spec found"],
                next_actions=[
                    "remove the extra spec or materialize the matching public issue task"
                ],
            )
        )
    summary = summarize_public_issue_reproduction_spec_validation(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        spec_count=len(specs_by_task),
        results=results,
    )
    write_public_issue_reproduction_spec_validation_outputs(
        output_dir=output_dir,
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_spec_validation(
    *,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    spec_count: int,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
) -> IssueCorpusPublicReproductionSpecValidationSummary:
    return IssueCorpusPublicReproductionSpecValidationSummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        specs_path=str(specs_path),
        tasks_dir=str(tasks_dir),
        focused_plan_path=str(focused_plan_path) if focused_plan_path is not None else None,
        task_count=len(results),
        spec_count=spec_count,
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        missing_spec_tasks=sum(1 for result in results if not result.spec_present),
        empty_signal_tasks=sum(
            1 for result in results if not result.expected_failure_signals
        ),
        policy_blocked_tasks=sum(
            1
            for result in results
            if result.reproduction_command and not result.policy_allowed
        ),
        extra_spec_tasks=sum(
            1
            for result in results
            if "reproduction spec task_id has no materialized task" in result.errors
        ),
        fixture_file_tasks=sum(1 for result in results if result.fixture_files),
        fixture_file_count=sum(len(result.fixture_files) for result in results),
        unsafe_fixture_tasks=sum(
            1
            for result in results
            if any("fixture_files" in error for error in result.errors)
        ),
    )


def write_public_issue_reproduction_spec_validation_outputs(
    *,
    output_dir: Path,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
    summary: IssueCorpusPublicReproductionSpecValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_reproduction_spec_validation_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_reproduction_spec_validation_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_reproduction_spec_validation_results.csv").open(
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
                "spec_present",
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "fixture_paths",
                "expected_failure_signals",
                "errors",
                "warnings",
                "evidence",
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
                    "spec_present": result.spec_present,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fixture_paths": ";".join(
                        _public_issue_fixture_paths(result.fixture_files)
                    ),
                    "expected_failure_signals": ";".join(
                        result.expected_failure_signals
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_spec_validation_report.md").write_text(
        render_public_issue_reproduction_spec_validation_report(
            specs_path=specs_path,
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def discover_public_issue_failure_signals(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicFailureSignalDiscoveryResult],
    IssueCorpusPublicFailureSignalDiscoverySummary,
]:
    records = _load_json_record_list(path=plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            network=sandbox_network,
        )
    )
    policy = CommandPolicy()
    run_logs_dir = output_dir / "public_issue_failure_signal_discovery_logs"
    results = [
        _discover_public_issue_failure_signal_record(
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
    summary = summarize_public_issue_failure_signal_discovery(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_failure_signal_discovery_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_failure_signal_discovery(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicFailureSignalDiscoverySummary:
    return IssueCorpusPublicFailureSignalDiscoverySummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"observed_failure", "passed", "timed_out", "failed"}
        ),
        observed_failure_tasks=sum(
            1 for result in results if result.status == "observed_failure"
        ),
        passed_tasks=sum(1 for result in results if result.status == "passed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        candidate_signal_tasks=sum(
            1 for result in results if result.candidate_failure_signals
        ),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def write_public_issue_failure_signal_discovery_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_failure_signal_discovery_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_failure_signal_discovery_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_failure_signal_discovery_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "candidate_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "candidate_failure_signals": ";".join(
                        result.candidate_failure_signals
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_failure_signal_discovery_report.md").write_text(
        render_public_issue_failure_signal_discovery_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _public_issue_reproduction_specs_template(
    results: list[IssueCorpusPublicReproductionPlanResult],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "claim_boundary": [
            "This template is for reviewed public issue reproduction criteria.",
            "Do not count a task as reproduced until execute-public-issue-reproductions records a nonzero exit and matches every expected failure signal.",
            "Keep commands within the normal PatchSmith command policy, such as python3 -m pytest.",
        ],
        "specs": [
            {
                "task_id": result.task_id,
                "repository": result.repository,
                "issue_url": result.issue_url,
                "command": result.reproduction_command,
                "fixture_files": [],
                "expected_failure_signals": [],
                "review_notes": (
                    "Fill after reviewing the issue-specific failing traceback, "
                    "assertion, or behavior mismatch."
                ),
            }
            for result in results
        ],
    }


def execute_public_issue_reproductions(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicReproductionExecutionResult],
    IssueCorpusPublicReproductionExecutionSummary,
]:
    records = _load_json_record_list(plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "public_issue_reproductions"
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
        _execute_public_issue_reproduction_record(
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
    summary = summarize_public_issue_reproduction_execution(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_reproduction_execution_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_reproduction_execution(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    dry_run: bool,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
) -> IssueCorpusPublicReproductionExecutionSummary:
    return IssueCorpusPublicReproductionExecutionSummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        reproduction_plan_path=str(plan_path),
        task_count=len(results),
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1
            for result in results
            if result.status in {"reproduced", "not_reproduced", "failed", "timed_out"}
        ),
        reproduced_tasks=sum(1 for result in results if result.status == "reproduced"),
        not_reproduced_tasks=sum(
            1 for result in results if result.status == "not_reproduced"
        ),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        timed_out_tasks=sum(1 for result in results if result.status == "timed_out"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        manual_spec_required_tasks=sum(
            1 for result in results if result.manual_spec_required
        ),
        policy_allowed_commands=sum(1 for result in results if result.policy_allowed),
        fixture_file_tasks=sum(1 for result in results if result.fixture_paths),
    )


def write_public_issue_reproduction_execution_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_reproduction_execution_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_reproduction_execution_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_reproduction_execution_results.csv").open(
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
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "expected_failure_signals",
                "manual_spec_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "matched_failure_signals",
                "missing_failure_signals",
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
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "expected_failure_signals": ";".join(
                        result.expected_failure_signals
                    ),
                    "manual_spec_required": result.manual_spec_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "matched_failure_signals": ";".join(
                        result.matched_failure_signals
                    ),
                    "missing_failure_signals": ";".join(
                        result.missing_failure_signals
                    ),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_execution_report.md").write_text(
        render_public_issue_reproduction_execution_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def check_public_issue_repair_readiness(
    *,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    reproduction_execution_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicRepairReadinessResult],
    IssueCorpusPublicRepairReadinessSummary,
]:
    focused_records = _load_json_record_list(
        focused_run_path, label="focused test run results"
    )
    diagnosis_records = _load_json_record_list(
        diagnosis_path, label="focused test diagnosis results"
    )
    setup_validation_records = _load_json_record_list(
        setup_validation_path, label="focused test setup validation results"
    )
    reproduction_execution_records = (
        _load_json_record_list(
            reproduction_execution_path,
            label="public issue reproduction execution results",
        )
        if reproduction_execution_path is not None
        and reproduction_execution_path.exists()
        else []
    )
    manifests = _load_public_issue_task_manifests(tasks_dir)
    diagnosis_by_task = _records_by_task_id(diagnosis_records)
    setup_validation_by_task = _records_by_task_id(setup_validation_records)
    reproduction_execution_by_task = _records_by_task_id(reproduction_execution_records)
    results = [
        _check_public_issue_repair_readiness_record(
            focused_record=record,
            diagnosis_record=diagnosis_by_task.get(_optional_string(record.get("task_id")) or ""),
            setup_validation_record=setup_validation_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            reproduction_execution_record=reproduction_execution_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
        )
        for record in focused_records
    ]
    summary = summarize_public_issue_repair_readiness(
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path
            if reproduction_execution_records
            else None
        ),
        results=results,
    )
    write_public_issue_repair_readiness_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path
            if reproduction_execution_records
            else None
        ),
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_repair_readiness(
    *,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
) -> IssueCorpusPublicRepairReadinessSummary:
    return IssueCorpusPublicRepairReadinessSummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        focused_run_path=str(focused_run_path),
        diagnosis_path=str(diagnosis_path),
        setup_validation_path=str(setup_validation_path),
        reproduction_execution_path=(
            str(reproduction_execution_path)
            if reproduction_execution_path is not None
            else None
        ),
        task_count=len(results),
        ready_tasks=sum(1 for result in results if result.status == "ready"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        repair_command_tasks=sum(1 for result in results if result.repair_command),
        passed_focused_tasks=sum(
            1 for result in results if result.focused_run_status == "passed"
        ),
        passed_setup_validation_tasks=sum(
            1 for result in results if result.setup_validation_status == "passed"
        ),
        reproduced_tasks=sum(
            1
            for result in results
            if result.reproduction_execution_status == "reproduced"
        ),
        missing_reproduction_tasks=sum(
            1
            for result in results
            if result.reproduction_execution_status != "reproduced"
        ),
    )


def write_public_issue_repair_readiness_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
    summary: IssueCorpusPublicRepairReadinessSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_repair_readiness_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_repair_readiness_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_repair_readiness_results.csv").open(
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
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "focused_run_status",
                "diagnosis_category",
                "setup_validation_status",
                "setup_failure_category",
                "reproduction_execution_status",
                "reproduction_stdout_path",
                "reproduction_stderr_path",
                "matched_failure_signals",
                "sandbox_mode",
                "sandbox_network",
                "evidence",
                "blockers",
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
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "focused_run_status": result.focused_run_status,
                    "diagnosis_category": result.diagnosis_category,
                    "setup_validation_status": result.setup_validation_status,
                    "setup_failure_category": result.setup_failure_category,
                    "reproduction_execution_status": (
                        result.reproduction_execution_status
                    ),
                    "reproduction_stdout_path": result.reproduction_stdout_path,
                    "reproduction_stderr_path": result.reproduction_stderr_path,
                    "matched_failure_signals": ";".join(
                        result.matched_failure_signals
                    ),
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_network": result.sandbox_network,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_readiness_report.md").write_text(
        render_public_issue_repair_readiness_report(
            tasks_dir=tasks_dir,
            focused_run_path=focused_run_path,
            diagnosis_path=diagnosis_path,
            setup_validation_path=setup_validation_path,
            reproduction_execution_path=reproduction_execution_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def execute_public_issue_repairs(
    *,
    readiness_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    runtime: str = "langgraph",
    planner: str = "fake_model",
    context_provider: str = "native_hybrid",
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    max_tasks: int | None = None,
    dry_run: bool = True,
    allow_warnings: bool = False,
) -> tuple[
    list[IssueCorpusPublicRepairAttemptResult],
    IssueCorpusPublicRepairAttemptSummary,
]:
    records = _load_json_record_list(
        readiness_path,
        label="public issue repair readiness results",
    )
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    manifests = _load_public_issue_task_manifests(tasks_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None
        if dry_run
        else RepairRunner(artifacts_dir=output_dir / "public_issue_repair_attempts")
    )
    results = [
        _execute_public_issue_repair_record(
            record=record,
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
            runner=runner,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            allow_warnings=allow_warnings,
        )
        for record in selected_records
    ]
    summary = summarize_public_issue_repair_attempts(
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
    )
    write_public_issue_repair_attempt_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def summarize_public_issue_repair_attempts(
    *,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    dry_run: bool,
    allow_warnings: bool,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
) -> IssueCorpusPublicRepairAttemptSummary:
    return IssueCorpusPublicRepairAttemptSummary(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        readiness_path=str(readiness_path),
        tasks_dir=str(tasks_dir) if tasks_dir is not None else None,
        task_count=len(results),
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        dry_run_tasks=sum(1 for result in results if result.status == "dry_run"),
        attempted_tasks=sum(
            1 for result in results if result.status in {"validated", "failed"}
        ),
        validated_tasks=sum(1 for result in results if result.status == "validated"),
        failed_tasks=sum(1 for result in results if result.status == "failed"),
        blocked_tasks=sum(1 for result in results if result.status == "blocked"),
        warning_tasks=sum(1 for result in results if result.status == "warning"),
        reproduced_input_tasks=sum(
            1
            for result in results
            if result.reproduction_execution_status == "reproduced"
        ),
    )


def write_public_issue_repair_attempt_outputs(
    *,
    output_dir: Path,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    summary: IssueCorpusPublicRepairAttemptSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "public_issue_repair_attempt_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "public_issue_repair_attempt_results.csv").open(
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
                "readiness_status",
                "repo_path",
                "repo_exists",
                "repair_command",
                "validation_command",
                "reproduction_execution_status",
                "runtime",
                "planner",
                "context_provider",
                "sandbox_mode",
                "sandbox_image",
                "dry_run",
                "run_id",
                "run_status",
                "report_path",
                "trace_path",
                "final_diff_path",
                "test_exit_code",
                "patch_generated",
                "errors",
                "warnings",
                "evidence",
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
                    "readiness_status": result.readiness_status,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "repair_command": result.repair_command,
                    "validation_command": result.validation_command,
                    "reproduction_execution_status": (
                        result.reproduction_execution_status
                    ),
                    "runtime": result.runtime,
                    "planner": result.planner,
                    "context_provider": result.context_provider,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "dry_run": result.dry_run,
                    "run_id": result.run_id,
                    "run_status": result.run_status,
                    "report_path": result.report_path,
                    "trace_path": result.trace_path,
                    "final_diff_path": result.final_diff_path,
                    "test_exit_code": result.test_exit_code,
                    "patch_generated": result.patch_generated,
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_repair_attempt_report.md").write_text(
        render_public_issue_repair_attempt_report(
            readiness_path=readiness_path,
            tasks_dir=tasks_dir,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def run_retrieval_evaluation(
    *,
    dataset_dir: Path,
    providers: list[str],
    output_dir: Path,
    top_k: int = 5,
) -> tuple[list[RetrievalEvalResult], list[RetrievalEvalSummary]]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[RetrievalEvalResult] = []

    for task in tasks:
        for provider in providers:
            result = evaluate_retrieval_task(
                task=task,
                provider=provider,
                output_dir=output_dir,
                top_k=top_k,
            )
            results.append(result)

    summaries = summarize_retrieval_results(results)
    write_retrieval_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summaries=summaries,
    )
    return results, summaries


def run_repair_evaluation(
    *,
    dataset_dir: Path,
    runtime: str,
    planner: str = "heuristic",
    max_retries: int = 0,
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> tuple[list[RepairEvalResult], RepairEvalSummary]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_artifacts_dir = output_dir / "run_artifacts"
    runner = RepairRunner(artifacts_dir=run_artifacts_dir)
    results: list[RepairEvalResult] = []

    for task in tasks:
        started = time.perf_counter()
        try:
            result = runner.run(
                RunRequest(
                    repo=str(task.repo),
                    issue_text=task.issue_text,
                    test_command=task.test_command,
                    runtime=runtime,
                    planner=planner,
                    max_retries=max_retries,
                    context_provider=context_provider,
                    retrieval_strategy=context_provider,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                )
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            final_diff = result.final_diff_path.read_text(encoding="utf-8")
            test_exit_code = result.test_result.exit_code if result.test_result else None
            usage = _model_usage_from_trace(result.trace_path)
            trace_metrics = _trace_metrics_from_trace(result.trace_path)
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status=result.status,
                    error=None,
                    patch_generated=bool(final_diff.strip()),
                    targeted_tests_passed=test_exit_code == 0,
                    test_exit_code=test_exit_code,
                    report_path=str(result.report_path),
                    trace_path=str(result.trace_path),
                    final_diff_path=str(result.final_diff_path),
                    retrieved_files=[context.path for context in result.retrieved_context],
                    latency_ms=latency_ms,
                    trace_event_count=trace_metrics["trace_event_count"],
                    runtime_node_count=trace_metrics["runtime_node_count"],
                    failed_trace_event_count=trace_metrics["failed_trace_event_count"],
                    retry_event_count=trace_metrics["retry_event_count"],
                    debuggability_score=trace_metrics["debuggability_score"],
                    model_provider=usage["model_provider"],
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                    estimated_cost_usd=usage["estimated_cost_usd"],
                )
            )
        except Exception as error:
            latency_ms = int((time.perf_counter() - started) * 1000)
            results.append(
                RepairEvalResult(
                    task_id=task.task_id,
                    runtime=runtime,
                    planner=planner,
                    context_provider=context_provider,
                    status="failed",
                    error=str(error),
                    patch_generated=False,
                    targeted_tests_passed=False,
                    test_exit_code=None,
                    report_path=None,
                    trace_path=None,
                    final_diff_path=None,
                    retrieved_files=[],
                    latency_ms=latency_ms,
                )
            )

    summary = summarize_repair_results(
        results,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
    )
    write_repair_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summary=summary,
    )
    return results, summary


def run_scaffold_comparison(
    *,
    dataset_dir: Path,
    variants: list[str],
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> list[ScaffoldComparisonResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_variants = [_scaffold_variant(name) for name in variants]
    comparison_results: list[ScaffoldComparisonResult] = []

    for variant in selected_variants:
        variant_output_dir = output_dir / variant.name
        _repair_results, summary = run_repair_evaluation(
            dataset_dir=dataset_dir,
            runtime=variant.runtime,
            planner=variant.planner,
            context_provider=context_provider,
            output_dir=variant_output_dir,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
        )
        comparison_results.append(
            ScaffoldComparisonResult(
                scaffold=variant.name,
                runtime=summary.runtime,
                planner=summary.planner,
                context_provider=summary.context_provider,
                attempted_tasks=summary.attempted_tasks,
                completed_tasks=summary.completed_tasks,
                patch_generated_rate=summary.patch_generated_rate,
                targeted_test_pass_rate=summary.targeted_test_pass_rate,
                avg_latency_ms=summary.avg_latency_ms,
                avg_trace_events=summary.avg_trace_events,
                avg_runtime_nodes=summary.avg_runtime_nodes,
                failed_trace_event_count=summary.failed_trace_event_count,
                avg_retry_events=summary.avg_retry_events,
                avg_debuggability_score=summary.avg_debuggability_score,
                model_provider=summary.model_provider,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                total_tokens=summary.total_tokens,
                estimated_cost_usd=summary.estimated_cost_usd,
                repair_report_path=str(variant_output_dir / "repair_report.md"),
            )
        )

    write_scaffold_comparison_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=comparison_results,
    )
    return comparison_results


def run_patch_search_evaluation(
    *,
    dataset_dir: Path,
    candidate_counts: list[int],
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> tuple[list[PatchSearchEvalResult], list[PatchSearchEvalSummary]]:
    tasks = load_seeded_tasks(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[PatchSearchEvalResult] = []

    for candidate_count in candidate_counts:
        if candidate_count < 1:
            raise ValueError("candidate counts must be positive")
        variant = f"candidates_{candidate_count}"
        for task in tasks:
            results.append(
                evaluate_patch_search_task(
                    task=task,
                    variant=variant,
                    candidate_count=candidate_count,
                    context_provider=context_provider,
                    output_dir=output_dir,
                    sandbox_mode=sandbox_mode,
                    sandbox_image=sandbox_image,
                )
            )

    summaries = summarize_patch_search_results(results)
    write_patch_search_eval_outputs(
        output_dir=output_dir,
        dataset_dir=dataset_dir,
        results=results,
        summaries=summaries,
    )
    return results, summaries


def summarize_repair_results(
    results: list[RepairEvalResult],
    *,
    runtime: str,
    planner: str,
    context_provider: str,
) -> RepairEvalSummary:
    completed = [result for result in results if result.status == "completed"]
    providers = sorted(
        {result.model_provider for result in completed if result.model_provider is not None}
    )
    return RepairEvalSummary(
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        attempted_tasks=len(results),
        completed_tasks=len(completed),
        patch_generated_rate=_average(
            1.0 if result.patch_generated else 0.0 for result in completed
        ),
        targeted_test_pass_rate=_average(
            1.0 if result.targeted_tests_passed else 0.0 for result in completed
        ),
        avg_latency_ms=_average(result.latency_ms for result in completed),
        avg_trace_events=_average(result.trace_event_count for result in completed),
        avg_runtime_nodes=_average(result.runtime_node_count for result in completed),
        failed_trace_event_count=sum(result.failed_trace_event_count for result in completed),
        avg_retry_events=_average(result.retry_event_count for result in completed),
        avg_debuggability_score=_average(result.debuggability_score for result in completed),
        model_provider=",".join(providers) if providers else None,
        input_tokens=_sum_optional(result.input_tokens for result in completed),
        output_tokens=_sum_optional(result.output_tokens for result in completed),
        total_tokens=_sum_optional(result.total_tokens for result in completed),
        estimated_cost_usd=_sum_optional_float(result.estimated_cost_usd for result in completed),
    )


def evaluate_retrieval_task(
    *,
    task: SeededTask,
    provider: str,
    output_dir: Path,
    top_k: int,
) -> RetrievalEvalResult:
    started = time.perf_counter()
    provider_artifacts = output_dir / "context_artifacts" / task.task_id / provider
    provider_artifacts.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix=f"patchsmith-eval-{task.task_id}-") as tmp_dir:
            repo_path = Path(tmp_dir) / "repo"
            snapshot = clone_or_copy_repository(str(task.repo), repo_path)
            if provider == "ctxhelm_cli":
                _ensure_git_repo(snapshot.repo_path)

            repo_index = index_repository(snapshot.repo_path)
            native_contexts = KeywordRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )
            hybrid_contexts = HybridRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )
            graph_contexts = GraphRetriever().retrieve(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                top_k=top_k,
            )

            if provider == "native":
                bundle = PatchSmithNativeBroker().prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = native_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "native_hybrid":
                bundle = PatchSmithNativeBroker(
                    HybridRetriever(), provider_name="patchsmith_native_hybrid"
                ).prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = hybrid_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "native_graph":
                bundle = PatchSmithNativeBroker(
                    GraphRetriever(), provider_name="patchsmith_native_graph"
                ).prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = graph_contexts
                related_tests = _related_tests_from_contexts(contexts, task.expected_related_tests)
            elif provider == "ctxhelm_cli":
                bundle = CtxhelmCliBroker().prepare(
                    ContextBrokerRequest(repo_path=snapshot.repo_path, task=task.issue_text),
                    repo_index=repo_index,
                    artifact_dir=provider_artifacts,
                )
                contexts = retrieved_context_from_bundle(
                    bundle=bundle,
                    repo_path=snapshot.repo_path,
                    fallback_contexts=[],
                    top_k=top_k,
                )
                related_tests = _related_tests_from_bundle(bundle)
            else:
                raise ValueError(f"unsupported context provider: {provider}")

            latency_ms = int((time.perf_counter() - started) * 1000)
            retrieved_files = [context.path for context in contexts]
            packing = summarize_context_pack(contexts)
            return RetrievalEvalResult(
                task_id=task.task_id,
                context_provider=provider,
                status="completed",
                error=None,
                retrieved_files=retrieved_files,
                related_test_files=related_tests,
                expected_touched_files=task.expected_touched_files,
                expected_related_tests=task.expected_related_tests,
                top1_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 1),
                top3_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 3),
                top5_touched_recall=top_k_recall(retrieved_files, task.expected_touched_files, 5),
                related_test_recall=recall(related_tests, task.expected_related_tests),
                latency_ms=latency_ms,
                context_count=packing.context_count,
                source_context_count=packing.source_context_count,
                test_context_count=packing.test_context_count,
                context_excerpt_chars=packing.excerpt_char_count,
                context_approx_tokens=packing.approx_token_count,
                fallback_used=bundle.fallback_used,
                source_text_logged=bundle.source_text_logged,
                source_free_violation=bundle.source_text_logged,
                raw_artifact_path=bundle.raw_artifact_path,
            )
    except (ContextBrokerError, ValueError, OSError, subprocess.CalledProcessError) as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalEvalResult(
            task_id=task.task_id,
            context_provider=provider,
            status="failed",
            error=str(error),
            retrieved_files=[],
            related_test_files=[],
            expected_touched_files=task.expected_touched_files,
            expected_related_tests=task.expected_related_tests,
            top1_touched_recall=0.0,
            top3_touched_recall=0.0,
            top5_touched_recall=0.0,
            related_test_recall=0.0,
            latency_ms=latency_ms,
            context_count=0,
            source_context_count=0,
            test_context_count=0,
            context_excerpt_chars=0,
            context_approx_tokens=0,
            fallback_used=False,
            source_text_logged=False,
            source_free_violation=False,
            raw_artifact_path=None,
        )


def evaluate_patch_search_task(
    *,
    task: SeededTask,
    variant: str,
    candidate_count: int,
    context_provider: str,
    output_dir: Path,
    sandbox_mode: str = "local",
    sandbox_image: str = "python:3.12-slim",
) -> PatchSearchEvalResult:
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix=f"patchsmith-search-{task.task_id}-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            retrieval_repo = tmp_path / "retrieval_repo"
            snapshot = clone_or_copy_repository(str(task.repo), retrieval_repo)
            repo_index = index_repository(snapshot.repo_path)
            contexts = _retrieve_for_patch_search(
                repo_path=snapshot.repo_path,
                repo_index=repo_index,
                issue_text=task.issue_text,
                context_provider=context_provider,
            )
            plan = HeuristicRepairPlanner().plan(
                issue_text=task.issue_text,
                retrieved_context=contexts,
            )
            if plan is None:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return PatchSearchEvalResult(
                    task_id=task.task_id,
                    variant=variant,
                    candidate_count=candidate_count,
                    status="no_plan",
                    success_at_1=False,
                    success_at_k=False,
                    selected_candidate_index=None,
                    selected_candidate_name=None,
                    selected_candidate_passed=False,
                    test_runs=0,
                    latency_ms=latency_ms,
                    candidate_results=[],
                    error="no heuristic repair plan",
                )

            candidate_plans = _patch_search_candidates(plan, candidate_count)
            candidate_results: list[PatchSearchCandidateResult] = []
            sandbox = create_sandbox_runner(mode=sandbox_mode, image=sandbox_image)
            for candidate_index, candidate_plan, risk_score, reason in candidate_plans:
                candidate_repo = tmp_path / f"candidate_{candidate_index}"
                clone_or_copy_repository(str(task.repo), candidate_repo)
                candidate_started = time.perf_counter()
                try:
                    edit = apply_text_replacement(
                        repo_path=candidate_repo,
                        relative_path=candidate_plan.path,
                        old=candidate_plan.old,
                        new=candidate_plan.new,
                    )
                    test_result = sandbox.run(
                        command=task.test_command,
                        workspace=candidate_repo,
                        timeout_seconds=60,
                    )
                    tests_passed = test_result.exit_code == 0
                    status = "tests_passed" if tests_passed else "tests_failed"
                    candidate_results.append(
                        PatchSearchCandidateResult(
                            candidate_index=candidate_index,
                            name=candidate_plan.name,
                            path=candidate_plan.path,
                            status=status,
                            test_exit_code=test_result.exit_code,
                            tests_passed=tests_passed,
                            diff=edit.diff,
                            duration_ms=int((time.perf_counter() - candidate_started) * 1000),
                            risk_score=risk_score,
                            reason=reason,
                        )
                    )
                except PatchSafetyError as error:
                    candidate_results.append(
                        PatchSearchCandidateResult(
                            candidate_index=candidate_index,
                            name=candidate_plan.name,
                            path=candidate_plan.path,
                            status="patch_rejected",
                            test_exit_code=None,
                            tests_passed=False,
                            diff="",
                            duration_ms=int((time.perf_counter() - candidate_started) * 1000),
                            risk_score=risk_score,
                            reason=reason,
                            error=str(error),
                        )
                    )

            selected = next(
                (candidate for candidate in candidate_results if candidate.tests_passed),
                None,
            )
            success_at_1 = bool(candidate_results and candidate_results[0].tests_passed)
            success_at_k = any(candidate.tests_passed for candidate in candidate_results)
            latency_ms = int((time.perf_counter() - started) * 1000)
            _write_patch_search_task_artifact(
                output_dir=output_dir,
                task_id=task.task_id,
                variant=variant,
                candidate_results=candidate_results,
            )
            return PatchSearchEvalResult(
                task_id=task.task_id,
                variant=variant,
                candidate_count=candidate_count,
                status="completed",
                success_at_1=success_at_1,
                success_at_k=success_at_k,
                selected_candidate_index=selected.candidate_index if selected else None,
                selected_candidate_name=selected.name if selected else None,
                selected_candidate_passed=bool(selected and selected.tests_passed),
                test_runs=sum(
                    1 for candidate in candidate_results if candidate.status != "patch_rejected"
                ),
                latency_ms=latency_ms,
                candidate_results=candidate_results,
            )
    except Exception as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return PatchSearchEvalResult(
            task_id=task.task_id,
            variant=variant,
            candidate_count=candidate_count,
            status="failed",
            success_at_1=False,
            success_at_k=False,
            selected_candidate_index=None,
            selected_candidate_name=None,
            selected_candidate_passed=False,
            test_runs=0,
            latency_ms=latency_ms,
            candidate_results=[],
            error=str(error),
        )


def summarize_retrieval_results(
    results: list[RetrievalEvalResult],
) -> list[RetrievalEvalSummary]:
    summaries: list[RetrievalEvalSummary] = []
    providers = sorted({result.context_provider for result in results})
    for provider in providers:
        provider_results = [result for result in results if result.context_provider == provider]
        completed = [result for result in provider_results if result.status == "completed"]
        summaries.append(
            RetrievalEvalSummary(
                provider=provider,
                attempted_tasks=len(provider_results),
                completed_tasks=len(completed),
                failed_tasks=len(provider_results) - len(completed),
                avg_top1_touched_recall=_average(
                    result.top1_touched_recall for result in completed
                ),
                avg_top3_touched_recall=_average(
                    result.top3_touched_recall for result in completed
                ),
                avg_top5_touched_recall=_average(
                    result.top5_touched_recall for result in completed
                ),
                avg_related_test_recall=_average(
                    result.related_test_recall for result in completed
                ),
                avg_latency_ms=_average(result.latency_ms for result in completed),
                avg_context_count=_average(result.context_count for result in completed),
                avg_source_context_count=_average(
                    result.source_context_count for result in completed
                ),
                avg_test_context_count=_average(
                    result.test_context_count for result in completed
                ),
                avg_context_excerpt_chars=_average(
                    result.context_excerpt_chars for result in completed
                ),
                avg_context_approx_tokens=_average(
                    result.context_approx_tokens for result in completed
                ),
                fallback_count=sum(1 for result in provider_results if result.fallback_used),
                source_free_violation_count=sum(
                    1 for result in provider_results if result.source_free_violation
                ),
            )
        )
    return summaries


def summarize_patch_search_results(
    results: list[PatchSearchEvalResult],
) -> list[PatchSearchEvalSummary]:
    summaries: list[PatchSearchEvalSummary] = []
    variants = sorted({result.variant for result in results})
    for variant in variants:
        variant_results = [result for result in results if result.variant == variant]
        completed = [result for result in variant_results if result.status == "completed"]
        candidate_count = max((result.candidate_count for result in variant_results), default=0)
        summaries.append(
            PatchSearchEvalSummary(
                variant=variant,
                candidate_count=candidate_count,
                attempted_tasks=len(variant_results),
                completed_tasks=len(completed),
                success_at_1_rate=_average(
                    1.0 if result.success_at_1 else 0.0 for result in completed
                ),
                success_at_k_rate=_average(
                    1.0 if result.success_at_k else 0.0 for result in completed
                ),
                selected_success_rate=_average(
                    1.0 if result.selected_candidate_passed else 0.0
                    for result in completed
                ),
                avg_latency_ms=_average(result.latency_ms for result in completed),
                avg_test_runs=_average(result.test_runs for result in completed),
            )
        )
    return summaries


def write_retrieval_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> None:
    results_json = output_dir / "results.json"
    results_csv = output_dir / "results.csv"
    summary_json = output_dir / "summary.json"
    report_path = output_dir / "report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].to_dict()) if results else [])
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retrieved_files"] = ";".join(result.retrieved_files)
                row["related_test_files"] = ";".join(result.related_test_files)
                row["expected_touched_files"] = ";".join(result.expected_touched_files)
                row["expected_related_tests"] = ";".join(result.expected_related_tests)
                writer.writerow(row)

    report_path.write_text(
        render_retrieval_eval_report(
            dataset_dir=dataset_dir,
            results=results,
            summaries=summaries,
        ),
        encoding="utf-8",
    )


def write_repair_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> None:
    results_json = output_dir / "repair_results.json"
    results_csv = output_dir / "repair_results.csv"
    summary_json = output_dir / "repair_summary.json"
    report_path = output_dir / "repair_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row["retrieved_files"] = ";".join(result.retrieved_files)
                writer.writerow(row)

    report_path.write_text(
        render_repair_eval_report(dataset_dir=dataset_dir, results=results, summary=summary),
        encoding="utf-8",
    )


def write_scaffold_comparison_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> None:
    results_json = output_dir / "scaffold_results.json"
    results_csv = output_dir / "scaffold_results.csv"
    report_path = output_dir / "scaffold_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(results[0].to_dict()) if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_dict())

    report_path.write_text(
        render_scaffold_comparison_report(dataset_dir=dataset_dir, results=results),
        encoding="utf-8",
    )


def write_patch_search_eval_outputs(
    *,
    output_dir: Path,
    dataset_dir: Path,
    results: list[PatchSearchEvalResult],
    summaries: list[PatchSearchEvalSummary],
) -> None:
    results_json = output_dir / "patch_search_results.json"
    results_csv = output_dir / "patch_search_results.csv"
    summary_json = output_dir / "patch_search_summary.json"
    report_path = output_dir / "patch_search_report.md"

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2),
        encoding="utf-8",
    )

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            key for key in results[0].to_dict() if key != "candidate_results"
        ] if results else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if results:
            writer.writeheader()
            for result in results:
                row = result.to_dict()
                row.pop("candidate_results", None)
                writer.writerow(row)

    report_path.write_text(
        render_patch_search_eval_report(
            dataset_dir=dataset_dir,
            results=results,
            summaries=summaries,
        ),
        encoding="utf-8",
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

    results_json.write_text(
        json.dumps([result.to_dict() for result in results], indent=2),
        encoding="utf-8",
    )
    summary_json.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")

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


def render_retrieval_eval_report(
    *,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{len({result.task_id for result in results})}`",
        f"- Lane count: `{len({result.context_provider for result in results})}`",
        "- Model cost: `$0.00` (retrieval-only evaluation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Provider | Attempted | Completed | Top-1 | Top-3 | Top-5 | Related Tests | "
            "Avg Ctx | Avg Src | Avg Test | Avg Tokens | Avg Latency ms | Fallbacks | "
            "Source-Free Violations |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.provider} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.avg_top1_touched_recall:.2f} | "
            f"{summary.avg_top3_touched_recall:.2f} | "
            f"{summary.avg_top5_touched_recall:.2f} | "
            f"{summary.avg_related_test_recall:.2f} | "
            f"{summary.avg_context_count:.1f} | "
            f"{summary.avg_source_context_count:.1f} | "
            f"{summary.avg_test_context_count:.1f} | "
            f"{summary.avg_context_approx_tokens:.0f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.fallback_count} | "
            f"{summary.source_free_violation_count} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Provider | Status | Top-1 | Top-3 | Top-5 | Related Tests | "
                "Ctx | Tokens | Retrieved Files | Error |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.context_provider} | "
            f"{result.status} | "
            f"{result.top1_touched_recall:.2f} | "
            f"{result.top3_touched_recall:.2f} | "
            f"{result.top5_touched_recall:.2f} | "
            f"{result.related_test_recall:.2f} | "
            f"{result.context_count} | "
            f"{result.context_approx_tokens} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures localization evidence only; it does not claim patch success.",
            "- Context providers are compared under the same task and repository snapshot.",
            "- Context token counts are approximate and use packed excerpt characters, not a model-specific tokenizer.",
            "- Source-bearing raw artifacts are kept under the experiment output directory and not copied into this public summary.",
            "",
        ]
    )
    return "\n".join(lines)


def render_seeded_dataset_validation_report(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> str:
    lines = [
        "# Seeded Dataset Validation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        (
            f"- Duplicate task IDs: `{', '.join(summary.duplicate_task_ids)}`"
            if summary.duplicate_task_ids
            else "- Duplicate task IDs: `none`"
        ),
        "",
        "## Results",
        "",
        "| Task | Status | Errors | Warnings | Expected Source | Expected Tests |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_touched_files) or 'none'} | "
            f"{', '.join(result.expected_related_tests) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            (
                "- Dataset validation checks metadata shape, required files, non-empty "
                "issues, and expected paths."
            ),
            (
                "- A valid dataset is required before retrieval or repair eval metrics are "
                "release evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_validation_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusEntryValidationResult],
    summary: IssueCorpusValidationSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Validation Report",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Corpus ID: `{summary.corpus_id or 'unknown'}`",
        f"- Entry count: `{summary.entry_count}`",
        f"- Valid entries: `{summary.valid_entries}`",
        f"- Invalid entries: `{summary.invalid_entries}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Repositories: `{', '.join(summary.repositories) or 'none'}`",
        f"- Languages: `{', '.join(summary.languages) or 'none'}`",
        f"- Task types: `{', '.join(summary.task_types) or 'none'}`",
        f"- Open issues at capture: `{summary.open_issue_count}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Issue | Status | Errors | Warnings | Workflow |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or 'unknown'} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_workflow) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This corpus proves that public issue candidates have been curated and validated.",
            "- It does not prove PatchSmith solved these issues until run artifacts exist for them.",
            "- Use this corpus as the next real-world evaluation lane after seeded-suite gates.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_repo_preflight_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusRepoPreflightResult],
    summary: IssueCorpusRepoPreflightSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Repository Preflight",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Repository count: `{summary.repository_count}`",
        f"- Reachable repositories: `{summary.reachable_repositories}`",
        f"- Unreachable repositories: `{summary.unreachable_repositories}`",
        f"- Issue count: `{summary.issue_count}`",
        f"- Average reachable latency: `{summary.avg_latency_ms:.1f}ms`",
        "",
        "## Results",
        "",
        "| Repository | Status | Default Branch | HEAD | Issues | Latency ms | Error |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.repository} | "
            f"{result.status} | "
            f"{result.default_branch or 'unknown'} | "
            f"{result.head_sha or 'unknown'} | "
            f"{result.issue_count} | "
            f"{result.latency_ms} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preflight proves repository reachability and records current HEAD metadata.",
            "- It does not clone source or run repair tasks.",
            "- Use this before converting public issue candidates into executable eval tasks.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_context_preview_report(
    *,
    corpus_path: Path,
    results: list[IssueCorpusContextPreviewResult],
    summary: IssueCorpusContextPreviewSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Context Preview",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Completed issues: `{summary.completed_issues}`",
        f"- Failed issues: `{summary.failed_issues}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Average context count: `{summary.avg_context_count:.1f}`",
        f"- Source-free summary: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Files | Contexts | Retrieved Files | Error |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.file_count} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This preview proves repository clone/index/retrieval plumbing on public issue candidates.",
            "- Retrieved source excerpts are intentionally omitted from this summary.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_issue_corpus_materialized_task_report(
    *,
    corpus_path: Path,
    context_preview_path: Path,
    results: list[IssueCorpusMaterializedTaskResult],
    summary: IssueCorpusMaterializedTaskSummary,
) -> str:
    lines = [
        "# Public Issue Corpus Materialized Tasks",
        "",
        f"- Corpus: `{corpus_path}`",
        f"- Context preview: `{context_preview_path}`",
        f"- Output: `{summary.output_dir}`",
        f"- Attempted issues: `{summary.attempted_issues}`",
        f"- Materialized tasks: `{summary.materialized_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Repositories: `{summary.repository_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Repository | Status | Commit | Contexts | Retrieved Files | Task Dir | Error |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.repository} | "
            f"{result.status} | "
            f"{(result.commit_hash or 'unknown')[:12]} | "
            f"{result.context_count} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.task_dir or 'none'} | "
            f"{result.error or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This materialization creates external-evaluation task manifests and runbooks.",
            "- Manifests intentionally omit source excerpts and issue body scraping.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_task_validation_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedTaskValidationResult],
    summary: IssueCorpusMaterializedTaskValidationSummary,
) -> str:
    lines = [
        "# Public Issue Materialized Task Validation",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        f"- Source-free manifests: `{str(summary.source_free).lower()}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Issue | Retrieved Files | Errors | Warnings |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"{result.issue_url or 'unknown'} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            "- This gate validates manifest shape, source-free context summaries, task files, local repository snapshots, and suggested run commands.",
            "- A valid manifest set is external-evaluation setup evidence, not repair-quality evidence.",
            "- Public issue reproduction and repair claims still require normal PatchSmith run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_run_readiness_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusMaterializedRunReadinessResult],
    summary: IssueCorpusMaterializedRunReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Materialized Run Readiness",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Allowed test commands: `{summary.allowed_test_commands}`",
        f"- Blocked test commands: `{summary.blocked_test_commands}`",
        "",
        "## Results",
        "",
        "| Task | Status | Risk | Repository | Files | Allowed Tests | Blocked Tests | Notes |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for result in results:
        notes = [*result.risk_notes, *result.errors, *result.warnings]
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.risk_level} | "
            f"{result.repository or 'unknown'} | "
            f"{result.file_count if result.file_count is not None else 'unknown'} | "
            f"{result.allowed_test_commands} | "
            f"{result.blocked_test_commands} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report checks run readiness without executing public repository tests.",
            "- `warning` means the task is runnable by policy but has cost, dependency, or scope risk.",
            "- It does not prove issue reproduction, patch generation, or test success.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_focused_test_plan_report(
    *,
    tasks_dir: Path,
    results: list[IssueCorpusFocusedTestPlanResult],
    summary: IssueCorpusFocusedTestPlanSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Plan",
        "",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned focused tasks: `{summary.planned_tasks}`",
        f"- Fallback tasks: `{summary.fallback_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Focused Files | Command | Policy | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.risk_notes, *result.errors, *result.warnings]
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"{', '.join(result.focused_files) or 'none'} | "
            f"`{result.command or 'none'}` | "
            f"{'allowed' if result.policy_allowed else result.policy_reason or 'not checked'} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans narrower pytest commands from retrieved test-like files.",
            "- Commands are policy-checked but not executed.",
            "- Passing these commands would still be targeted evidence, not full public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_materialized_issue_focused_test_run_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusFocusedTestRunResult],
    summary: IssueCorpusFocusedTestRunSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Run",
        "",
        f"- Plan path: `{plan_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        "",
        "## Results",
        "",
        "| Task | Status | Repository | Command | Exit | Duration | Logs | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        logs = "none"
        if result.stdout_path or result.stderr_path:
            logs = ", ".join(
                path
                for path in [result.stdout_path, result.stderr_path]
                if path is not None
            )
        exit_code = result.exit_code if result.exit_code is not None else "n/a"
        lines.append(
            "| "
            f"{result.task_id or 'unknown'} | "
            f"{result.status} | "
            f"{result.repository or 'unknown'} | "
            f"`{result.command or 'none'}` | "
            f"{exit_code} | "
            f"{result.duration_ms}ms | "
            f"{logs} | "
            f"{'; '.join(notes) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report executes the focused commands selected by the public issue task plan.",
            "- Passing tasks prove only that the planned focused test command is runnable in the current snapshot.",
            "- Failed or timed-out tasks are dependency, environment, or upstream-suite readiness signals unless paired with issue reproduction evidence.",
            "- This report does not prove issue reproduction, patch generation, or end-to-end repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_diagnosis_report(
    *,
    results_path: Path,
    results: list[IssueCorpusFocusedTestDiagnosisResult],
    summary: IssueCorpusFocusedTestDiagnosisSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Diagnosis",
        "",
        f"- Run results path: `{results_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Environment issue tasks: `{summary.environment_issue_tasks}`",
        f"- Dependency issue tasks: `{summary.dependency_issue_tasks}`",
        f"- Timeout tasks: `{summary.timeout_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Unknown failure tasks: `{summary.unknown_failure_tasks}`",
        "",
        "## Category Counts",
        "",
    ]
    if summary.category_counts:
        for category, count in summary.category_counts.items():
            lines.append(f"- `{category}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Task | Run Status | Category | Severity | Summary | Evidence | Next Actions |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.run_status or 'unknown')} | "
            f"{_markdown_table_text(result.category)} | "
            f"{_markdown_table_text(result.severity)} | "
            f"{_markdown_table_text(result.summary)} | "
            f"{_markdown_table_text('; '.join(result.evidence) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.suggested_next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report classifies focused test execution failures from saved stdout/stderr logs.",
            "- It is a dependency and environment readiness aid, not a patch-quality score.",
            "- Suggested actions must be executed only inside an approved sandbox and should not bypass command policy.",
            "- Public issue repair quality remains unproven until issue reproduction, patch generation, and passing validation are saved.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_plan_report(
    *,
    diagnosis_path: Path,
    results: list[IssueCorpusFocusedTestSetupPlanResult],
    summary: IssueCorpusFocusedTestSetupPlanSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Plan",
        "",
        f"- Diagnosis path: `{diagnosis_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned setup tasks: `{summary.planned_tasks}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Manual review tasks: `{summary.manual_review_tasks}`",
        f"- Dependency setup tasks: `{summary.dependency_setup_tasks}`",
        f"- Environment setup tasks: `{summary.environment_setup_tasks}`",
        f"- Network-required tasks: `{summary.network_required_tasks}`",
        f"- Sandbox-required tasks: `{summary.sandbox_required_tasks}`",
        "",
        "## Category Counts",
        "",
    ]
    if summary.category_counts:
        for category, count in summary.category_counts.items():
            lines.append(f"- `{category}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Task | Status | Profile | Setup Commands | Validation | Risk Notes |",
            "|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        setup_commands = "; ".join(result.setup_commands) if result.setup_commands else "none"
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(setup_commands)} | "
            f"{_markdown_table_text(result.validation_command or 'none')} | "
            f"{_markdown_table_text('; '.join(result.risk_notes) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans setup work from focused-test diagnosis categories.",
            "- Setup commands are not executed by this report and may require network access.",
            "- Run setup commands only in disposable, policy-approved sandboxes with no host secrets.",
            "- Passing setup does not prove public issue repair quality; it only prepares later reproduction and validation attempts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_readiness_report(
    *,
    setup_plan_path: Path,
    docker_smoke_path: Path,
    results: list[IssueCorpusFocusedTestSetupReadinessResult],
    summary: IssueCorpusFocusedTestSetupReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Readiness",
        "",
        f"- Setup plan path: `{setup_plan_path}`",
        f"- Docker smoke path: `{docker_smoke_path}`",
        f"- Docker smoke status: `{summary.docker_smoke_status}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Network-required tasks: `{summary.network_required_tasks}`",
        f"- Sandbox-required tasks: `{summary.sandbox_required_tasks}`",
        "",
        "## Results",
        "",
        "| Task | Status | Profile | Repository Snapshot | Docker | Notes | Next Actions |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text('present' if result.repo_exists else result.repo_path or 'missing')} | "
            f"{_markdown_table_text(result.docker_smoke_status)} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report checks whether focused public issue setup plans are ready to execute.",
            "- It does not execute setup commands, install dependencies, or run validation tests.",
            "- `blocked` means setup should not be attempted until the listed safety or environment issue is fixed.",
            "- Public issue repair quality remains unproven until setup, reproduction, patching, and validation are saved as run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_execution_report(
    *,
    readiness_path: Path,
    results: list[IssueCorpusFocusedTestSetupExecutionResult],
    summary: IssueCorpusFocusedTestSetupExecutionSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Execution",
        "",
        f"- Readiness path: `{readiness_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Allow warnings: `{str(summary.allow_warnings).lower()}`",
        (
            "- Allow dependency installs: "
            f"`{str(summary.allow_dependency_installs).lower()}`"
        ),
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Completed tasks: `{summary.completed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Skipped tasks: `{summary.skipped_tasks}`",
        f"- Setup commands: `{summary.command_count}`",
        f"- Attempted commands: `{summary.attempted_commands}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Readiness | Profile | Image | Network | Dependency Installs | "
            "Commands | Command Statuses | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        command_statuses = [
            f"{command.status}:{command.policy_reason or command.exit_code or 'n/a'}"
            for command in result.command_results
        ]
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.readiness_status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(result.sandbox_image)} | "
            f"{_markdown_table_text(result.sandbox_network)} | "
            f"{_markdown_table_text(str(result.allow_dependency_installs).lower())} | "
            f"{_markdown_table_text('; '.join(result.setup_commands) or 'none')} | "
            f"{_markdown_table_text('; '.join(command_statuses) or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Dry-run rows prove setup orchestration and command-policy checks, not dependency installation.",
            "- Blocked rows are stop conditions and must not be counted as public issue reproduction evidence.",
            "- Executed rows prove only setup command outcomes; repair quality still requires focused validation and normal run artifacts.",
            "- Commands must run only in disposable, policy-approved sandboxes with no host secrets.",
            "",
        ]
    )
    return "\n".join(lines)


def render_focused_test_setup_validation_report(
    *,
    setup_execution_path: Path,
    results: list[IssueCorpusFocusedTestSetupValidationResult],
    summary: IssueCorpusFocusedTestSetupValidationSummary,
) -> str:
    lines = [
        "# Public Issue Focused Test Setup Validation",
        "",
        f"- Setup execution path: `{setup_execution_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Skipped tasks: `{summary.skipped_tasks}`",
        f"- Failure categories: `{json.dumps(summary.failure_category_counts, sort_keys=True)}`",
        "",
        "## Results",
        "",
        "| Task | Status | Setup Status | Profile | Image | Validation Command | Command Status | Failure | Notes | Next Actions |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        command_status = (
            result.command_result.status
            if result.command_result is not None
            else "none"
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.setup_execution_status)} | "
            f"{_markdown_table_text(result.setup_profile)} | "
            f"{_markdown_table_text(result.sandbox_image)} | "
            f"{_markdown_table_text(result.validation_command or 'none')} | "
            f"{_markdown_table_text(command_status)} | "
            f"{_markdown_table_text(result.failure_category or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Dry-run rows prove validation command policy checks, not public issue reproduction.",
            "- Blocked rows mean setup has not reached a state where validation can run.",
            "- Passed validation proves the focused validation command runs after setup, not that a PatchSmith repair succeeded.",
            "- Repair-quality claims still require issue reproduction, patch generation, and saved normal PatchSmith run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_reproduction_plan_report(
    *,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
    summary: IssueCorpusPublicReproductionPlanSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Plan",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Focused plan path: `{focused_plan_path or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Planned tasks: `{summary.planned_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Manual-spec-required tasks: `{summary.manual_spec_required_tasks}`",
        f"- Candidate commands: `{summary.command_count}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        f"- Fixture files: `{summary.fixture_file_count}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Command Source | Command | Fixtures | "
            "Expected Failure Signals | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.blockers, *result.warnings]
        fixture_paths = "; ".join(_public_issue_fixture_paths(result.fixture_files))
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.command_source)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(fixture_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'manual spec required')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report plans public issue reproduction checks before repair attempts.",
            "- `planned` means an explicit expected failing signal is encoded and the command is policy-allowed.",
            "- `warning` means a candidate command exists but a reviewer still needs to encode the expected failing signal.",
            "- `blocked` means the reproduction command should not be run until the listed prerequisite is fixed.",
            "- Fixture files are written only to disposable execution workspaces; they do not modify source snapshots.",
            "- This report does not run tests, prove issue reproduction, generate patches, or call a live model provider.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_reproduction_spec_validation_report(
    *,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
    summary: IssueCorpusPublicReproductionSpecValidationSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Spec Validation",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Specs path: `{specs_path}`",
        f"- Tasks directory: `{tasks_dir}`",
        f"- Focused plan path: `{focused_plan_path or 'not provided'}`",
        f"- Task rows: `{summary.task_count}`",
        f"- Spec count: `{summary.spec_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Missing-spec tasks: `{summary.missing_spec_tasks}`",
        f"- Empty-signal tasks: `{summary.empty_signal_tasks}`",
        f"- Policy-blocked tasks: `{summary.policy_blocked_tasks}`",
        f"- Extra-spec tasks: `{summary.extra_spec_tasks}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        f"- Fixture files: `{summary.fixture_file_count}`",
        f"- Unsafe-fixture tasks: `{summary.unsafe_fixture_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Spec | Repository | Command Source | Command | "
            "Fixtures | Expected Failure Signals | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        fixture_paths = "; ".join(_public_issue_fixture_paths(result.fixture_files))
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text('present' if result.spec_present else 'missing')} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.command_source)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(fixture_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'missing')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report validates reviewed reproduction criteria before execution.",
            "- `ready` means a spec exists, the merged command is policy-allowed, and expected failure signals are non-empty.",
            "- `warning` means the spec can be reviewed further before execution.",
            "- `blocked` means the spec should not be used for reproduction execution until fixed.",
            "- Fixture files must be repository-relative, traversal-free, and are applied only to disposable execution workspaces.",
            "- This report does not execute reproduction commands or prove public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_failure_signal_discovery_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> str:
    lines = [
        "# Public Issue Failure Signal Discovery",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Reproduction plan path: `{plan_path}`",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Sandbox: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Observed-failure tasks: `{summary.observed_failure_tasks}`",
        f"- Passed tasks: `{summary.passed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Candidate-signal tasks: `{summary.candidate_signal_tasks}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Command | Exit Code | Candidate "
            "Signals | Fixtures | Logs | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        log_paths = "; ".join(
            path
            for path in [result.stdout_path, result.stderr_path]
            if path
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text(str(result.exit_code) if result.exit_code is not None else 'not run')} | "
            f"{_markdown_table_text('; '.join(result.candidate_failure_signals) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.fixture_paths) or 'none')} | "
            f"{_markdown_table_text(log_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report discovers candidate failure text for human review.",
            "- `observed_failure` means the candidate command failed and logs were saved; it does not prove issue reproduction.",
            "- Only `execute-public-issue-reproductions` with reviewed expected failure signals can count a task as reproduced.",
            "- `passed` means the candidate command did not expose a pre-repair failure and likely needs a more specific reproduction.",
            "- Fixture files, when present, are applied to a disposable copy before the candidate command runs.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_reproduction_execution_report(
    *,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> str:
    lines = [
        "# Public Issue Reproduction Execution",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Reproduction plan path: `{plan_path}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{summary.dry_run}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Sandbox network: `{summary.sandbox_network}`",
        f"- Timeout seconds: `{summary.timeout_seconds}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Reproduced tasks: `{summary.reproduced_tasks}`",
        f"- Not-reproduced tasks: `{summary.not_reproduced_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Timed-out tasks: `{summary.timed_out_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Manual-spec-required tasks: `{summary.manual_spec_required_tasks}`",
        f"- Policy-allowed commands: `{summary.policy_allowed_commands}`",
        f"- Fixture-file tasks: `{summary.fixture_file_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Plan Status | Command | Expected Signals | "
            "Matched Signals | Fixtures | Exit | Logs | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        log_paths = "; ".join(
            path
            for path in [result.stdout_path, result.stderr_path]
            if path is not None
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.reproduction_plan_status)} | "
            f"{_markdown_table_text(result.reproduction_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.expected_failure_signals) or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.matched_failure_signals) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.fixture_paths) or 'none')} | "
            f"{_markdown_table_text(str(result.exit_code) if result.exit_code is not None else 'not run')} | "
            f"{_markdown_table_text(log_paths or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report only executes commands from the public issue reproduction plan.",
            "- `blocked` means the command was not run because required safety or expected-failure criteria were missing.",
            "- `dry_run` means the command and expected failure signal passed preflight, but no repository code was executed.",
            "- `reproduced` means an executed command failed nonzero and all configured expected failure signals appeared in saved stdout/stderr.",
            "- Fixture files, when present, are applied to a disposable copy before the reproduction command runs.",
            "- This report does not generate patches, prove repair quality, or call a live model provider.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_repair_readiness_report(
    *,
    tasks_dir: Path | None,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    reproduction_execution_path: Path | None,
    results: list[IssueCorpusPublicRepairReadinessResult],
    summary: IssueCorpusPublicRepairReadinessSummary,
) -> str:
    lines = [
        "# Public Issue Repair Readiness",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Materialized tasks directory: `{tasks_dir or 'not provided'}`",
        f"- Focused run path: `{focused_run_path}`",
        f"- Diagnosis path: `{diagnosis_path}`",
        f"- Setup validation path: `{setup_validation_path}`",
        f"- Reproduction execution path: `{reproduction_execution_path or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Ready tasks: `{summary.ready_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Repair-command tasks: `{summary.repair_command_tasks}`",
        f"- Passed focused tasks: `{summary.passed_focused_tasks}`",
        f"- Passed setup-validation tasks: `{summary.passed_setup_validation_tasks}`",
        f"- Reproduced tasks: `{summary.reproduced_tasks}`",
        f"- Missing reproduction tasks: `{summary.missing_reproduction_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Focused Run | Diagnosis | Setup Validation | "
            "Reproduction | Repair Command | Evidence | Blockers | Warnings | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.focused_run_status or 'missing')} | "
            f"{_markdown_table_text(result.diagnosis_category or 'missing')} | "
            f"{_markdown_table_text(result.setup_validation_status or 'missing')} | "
            f"{_markdown_table_text(result.reproduction_execution_status or 'missing')} | "
            f"{_markdown_table_text(result.repair_command or 'missing')} | "
            f"{_markdown_table_text('; '.join(result.evidence) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.blockers) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.warnings) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report gates readiness for a later PatchSmith public issue repair attempt.",
            "- `ready` means focused validation, setup validation, repository snapshot, and a saved repair command are available.",
            "- `warning` means repair can be attempted only with explicit caveats, usually because the saved pre-repair command passed and does not prove issue reproduction.",
            "- `blocked` means do not attempt a public issue repair until the listed prerequisite is fixed.",
            "- This report does not execute PatchSmith repair, generate a patch, call a live model provider, or prove public issue repair quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_public_issue_repair_attempt_report(
    *,
    readiness_path: Path,
    tasks_dir: Path | None,
    results: list[IssueCorpusPublicRepairAttemptResult],
    summary: IssueCorpusPublicRepairAttemptSummary,
) -> str:
    lines = [
        "# Public Issue Repair Attempts",
        "",
        f"- Generated at: `{summary.generated_at}`",
        f"- Readiness path: `{readiness_path}`",
        f"- Materialized tasks directory: `{tasks_dir or 'not provided'}`",
        f"- Task count: `{summary.task_count}`",
        f"- Dry run: `{summary.dry_run}`",
        f"- Allow warnings: `{summary.allow_warnings}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Sandbox mode: `{summary.sandbox_mode}`",
        f"- Sandbox image: `{summary.sandbox_image}`",
        f"- Dry-run tasks: `{summary.dry_run_tasks}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Validated tasks: `{summary.validated_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Warning tasks: `{summary.warning_tasks}`",
        f"- Reproduced-input tasks: `{summary.reproduced_input_tasks}`",
        "",
        "## Results",
        "",
        (
            "| Task | Status | Repository | Readiness | Reproduction | Runtime | "
            "Test Exit | Patch | Run | Notes | Next Actions |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        notes = [*result.errors, *result.warnings]
        run_refs = "; ".join(
            path
            for path in [result.report_path, result.trace_path, result.final_diff_path]
            if path is not None
        )
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id or 'unknown')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.readiness_status)} | "
            f"{_markdown_table_text(result.reproduction_execution_status or 'missing')} | "
            f"{_markdown_table_text(result.runtime + '/' + result.planner)} | "
            f"{_markdown_table_text(str(result.test_exit_code) if result.test_exit_code is not None else 'not run')} | "
            f"{_markdown_table_text(str(result.patch_generated).lower())} | "
            f"{_markdown_table_text(run_refs or 'none')} | "
            f"{_markdown_table_text('; '.join(notes) or 'none')} | "
            f"{_markdown_table_text('; '.join(result.next_actions) or 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This gate consumes public repair-readiness evidence before launching PatchSmith runs.",
            "- `blocked` rows were not run and must not be counted as repair attempts.",
            "- `dry_run` rows prove only readiness and configuration checks.",
            "- `validated` rows mean PatchSmith produced run artifacts and the configured validation command exited zero.",
            "- This report does not prove live LLM quality unless non-offline provider metadata is present in the saved run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_repair_eval_report(
    *,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> str:
    input_tokens = summary.input_tokens if summary.input_tokens is not None else "n/a"
    output_tokens = summary.output_tokens if summary.output_tokens is not None else "n/a"
    total_tokens = summary.total_tokens if summary.total_tokens is not None else "n/a"
    lines = [
        "# Repair Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Completed tasks: `{summary.completed_tasks}`",
        f"- Model provider: `{summary.model_provider or 'none'}`",
        f"- Input tokens: `{input_tokens}`",
        f"- Output tokens: `{output_tokens}`",
        f"- Total tokens: `{total_tokens}`",
        f"- Estimated model cost: `{_format_cost(summary.estimated_cost_usd)}`",
        "",
        "## Summary",
        "",
        (
            "| Runtime | Planner | Context | Patch Generated | Targeted Tests Passed | "
            "Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | Failed Trace Events | "
            "Avg Retries | Debug Score | Input Tokens | Output Tokens | Est Cost |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| "
        f"{summary.runtime} | "
        f"{summary.planner} | "
        f"{summary.context_provider} | "
        f"{summary.patch_generated_rate:.2f} | "
        f"{summary.targeted_test_pass_rate:.2f} | "
        f"{summary.avg_latency_ms:.0f} | "
        f"{summary.avg_trace_events:.1f} | "
        f"{summary.avg_runtime_nodes:.1f} | "
        f"{summary.failed_trace_event_count} | "
        f"{summary.avg_retry_events:.1f} | "
        f"{summary.avg_debuggability_score:.1f} | "
        f"{summary.input_tokens if summary.input_tokens is not None else ''} | "
        f"{summary.output_tokens if summary.output_tokens is not None else ''} | "
        f"{_format_cost(summary.estimated_cost_usd)} |",
        "",
        "## Per-Task Results",
        "",
        (
            "| Task | Planner | Model Provider | Status | Patch Generated | Tests Passed | "
            "Exit Code | Trace Events | Runtime Nodes | Failed Trace Events | Retries | "
            "Debug Score | Tokens | Est Cost | Retrieved Files | Report | Error |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.planner} | "
            f"{result.model_provider or ''} | "
            f"{result.status} | "
            f"{int(result.patch_generated)} | "
            f"{int(result.targeted_tests_passed)} | "
            f"{result.test_exit_code if result.test_exit_code is not None else ''} | "
            f"{result.trace_event_count} | "
            f"{result.runtime_node_count} | "
            f"{result.failed_trace_event_count} | "
            f"{result.retry_event_count} | "
            f"{result.debuggability_score:.1f} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.report_path or ''} | "
            f"{(result.error or '').replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures seeded-task patch smoke behavior.",
            (
                "- Heuristic and fake-model planners should not be presented as autonomous "
                "coding-agent quality."
            ),
            (
                "- Use this runner to validate artifacts and gates before enabling a live "
                "model provider."
            ),
            "- Estimated cost is reported only when provider usage and configured rates exist.",
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "",
        ]
    )
    if summary.runtime == "deepagents":
        lines.insert(
            -1,
            (
                "- The `deepagents` runtime row is dependency-gated adapter evidence; "
                "local runs use offline compatibility mode unless the optional "
                "`deepagents` extra and live model provider are configured."
            ),
        )
    if summary.runtime == "openai_agents":
        lines.insert(
            -1,
            (
                "- The `openai_agents` runtime row is dependency-gated adapter evidence; "
                "local runs use offline compatibility mode unless the optional "
                "`openai-agents` extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def render_scaffold_comparison_report(
    *,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> str:
    lines = [
        "# Scaffold Comparison Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Scaffold count: `{len(results)}`",
        f"- Model cost: `{_format_cost(_sum_optional_float(result.estimated_cost_usd for result in results))}`",
        "",
        "## Summary",
        "",
        (
            "| Scaffold | Runtime | Planner | Context | Completed | Patch Generated | "
            "Targeted Tests Passed | Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | "
            "Failed Trace Events | Avg Retries | Debug Score | Model Provider | Tokens | Est Cost | Repair Report |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.scaffold} | "
            f"{result.runtime} | "
            f"{result.planner} | "
            f"{result.context_provider} | "
            f"{result.completed_tasks}/{result.attempted_tasks} | "
            f"{result.patch_generated_rate:.2f} | "
            f"{result.targeted_test_pass_rate:.2f} | "
            f"{result.avg_latency_ms:.0f} | "
            f"{result.avg_trace_events:.1f} | "
            f"{result.avg_runtime_nodes:.1f} | "
            f"{result.failed_trace_event_count} | "
            f"{result.avg_retry_events:.1f} | "
            f"{result.avg_debuggability_score:.1f} | "
            f"{result.model_provider or ''} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{result.repair_report_path} |"
        )

    best_resolved = max((result.targeted_test_pass_rate for result in results), default=0.0)
    best_scaffolds = [
        result.scaffold for result in results if result.targeted_test_pass_rate == best_resolved
    ]
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            (
                f"- Best targeted-test pass rate in this run: `{best_resolved:.2f}` "
                f"from `{', '.join(best_scaffolds) or 'none'}`."
            ),
            "- Agentless is the no-edit baseline and should not be treated as a repair scaffold.",
            (
                "- Heuristic and fake-model planners are deterministic seeded-task baselines; "
                "they do not prove autonomous coding-agent quality."
            ),
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "- Compare repair report traces before making a default-runtime decision.",
            "",
        ]
    )
    if any(result.scaffold == "deepagents" for result in results):
        lines.insert(
            -1,
            (
                "- The `deepagents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `deepagents` "
                "extra and live model provider are configured."
            ),
        )
    if any(result.scaffold == "openai_agents" for result in results):
        lines.insert(
            -1,
            (
                "- The `openai_agents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `openai-agents` "
                "extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def render_patch_search_eval_report(
    *,
    dataset_dir: Path,
    results: list[PatchSearchEvalResult],
    summaries: list[PatchSearchEvalSummary],
) -> str:
    lines = [
        "# Patch Search Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Variant count: `{len(summaries)}`",
        "- Model cost: `$0.00` (deterministic candidate generation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Variant | Candidates | Attempted | Completed | Success@1 | Success@k | "
            "Selected Success | Avg Latency ms | Avg Test Runs | Est Cost |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.variant} | "
            f"{summary.candidate_count} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.success_at_1_rate:.2f} | "
            f"{summary.success_at_k_rate:.2f} | "
            f"{summary.selected_success_rate:.2f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.avg_test_runs:.1f} | "
            f"{_format_cost(summary.estimated_cost_usd)} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Variant | Status | Success@1 | Success@k | Selected Candidate | "
                "Selected Passed | Test Runs | Latency ms | Error |"
            ),
            "|---|---|---|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for result in results:
        selected = (
            f"{result.selected_candidate_index}:{result.selected_candidate_name}"
            if result.selected_candidate_index is not None
            else "none"
        )
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.variant} | "
            f"{result.status} | "
            f"{int(result.success_at_1)} | "
            f"{int(result.success_at_k)} | "
            f"{selected} | "
            f"{int(result.selected_candidate_passed)} | "
            f"{result.test_runs} | "
            f"{result.latency_ms} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures deterministic patch-search infrastructure, not model diversity.",
            "- Each candidate is applied and tested in an isolated copy of the task repository.",
            "- The selector chooses the first candidate whose targeted tests pass.",
            "- Cost is zero because this lane currently uses heuristic candidate generation.",
            "",
        ]
    )
    return "\n".join(lines)


def top_k_recall(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    return recall(retrieved[:k], expected)


def recall(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    retrieved_set = set(retrieved)
    expected_set = set(expected)
    return len(retrieved_set & expected_set) / len(expected_set)


def _related_tests_from_contexts(
    contexts: list[RetrievedContext], expected_related_tests: list[str]
) -> list[str]:
    expected = set(expected_related_tests)
    return [context.path for context in contexts if context.path in expected]


def _related_tests_from_bundle(bundle: ContextBundle) -> list[str]:
    paths: list[str] = []
    for item in bundle.related_tests:
        path = item.get("path")
        if isinstance(path, str) and path not in paths:
            paths.append(path)
    return paths


def _retrieve_for_patch_search(
    *,
    repo_path: Path,
    repo_index: Any,
    issue_text: str,
    context_provider: str,
) -> list[RetrievedContext]:
    if context_provider == "native_graph":
        retriever = GraphRetriever()
    elif context_provider == "native_hybrid":
        retriever = HybridRetriever()
    else:
        retriever = KeywordRetriever()
    return retriever.retrieve(
        repo_path=repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
        top_k=5,
    )


def _patch_search_candidates(
    base_plan: RepairPlan,
    candidate_count: int,
) -> list[tuple[int, RepairPlan, float, str]]:
    candidates: list[tuple[int, RepairPlan, float, str]] = [
        (
            1,
            base_plan,
            0.2,
            "primary heuristic repair plan",
        )
    ]
    if candidate_count >= 2:
        candidates.append(
            (
                2,
                RepairPlan(
                    name=f"{base_plan.name}_noop_control",
                    path=base_plan.path,
                    old=base_plan.old,
                    new=base_plan.old,
                    summary="No-op control candidate for patch-search selection.",
                ),
                0.7,
                "no-op control candidate",
            )
        )
    if candidate_count >= 3:
        candidates.append(
            (
                3,
                RepairPlan(
                    name=f"{base_plan.name}_delete_control",
                    path=base_plan.path,
                    old=base_plan.old,
                    new="",
                    summary="Deletion control candidate for patch-search selection.",
                ),
                0.9,
                "high-risk deletion control candidate",
            )
        )
    while len(candidates) < candidate_count:
        next_index = len(candidates) + 1
        candidates.append(
            (
                next_index,
                RepairPlan(
                    name=f"{base_plan.name}_noop_control_{next_index}",
                    path=base_plan.path,
                    old=base_plan.old,
                    new=base_plan.old,
                    summary="Extra no-op control candidate for patch-search selection.",
                ),
                0.8,
                "extra no-op control candidate",
            )
        )
    return candidates[:candidate_count]


def _write_patch_search_task_artifact(
    *,
    output_dir: Path,
    task_id: str,
    variant: str,
    candidate_results: list[PatchSearchCandidateResult],
) -> None:
    task_dir = output_dir / "task_artifacts" / variant
    task_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = task_dir / f"{task_id}.json"
    artifact_path.write_text(
        json.dumps([candidate.to_dict() for candidate in candidate_results], indent=2),
        encoding="utf-8",
    )


def _ensure_git_repo(repo_path: Path) -> None:
    if (repo_path / ".git").exists():
        return
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=PatchSmith",
            "-c",
            "user.email=patchsmith@example.local",
            "commit",
            "-q",
            "-m",
            "seeded task snapshot",
        ],
        cwd=repo_path,
        check=True,
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
    failure_type = _expected_string(expected, "failure_type", errors)
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


def _validate_issue_corpus_entry(
    entry: Any,
    index: int,
) -> IssueCorpusEntryValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(entry, dict):
        return IssueCorpusEntryValidationResult(
            task_id=None,
            repository=None,
            issue_url=None,
            status="invalid",
            errors=[f"issues[{index}] must be an object"],
            warnings=[],
            language=None,
            task_type=None,
            state_at_capture=None,
            expected_workflow=[],
        )

    task_id = _required_entry_string(entry, "task_id", errors)
    repository = _required_entry_string(entry, "repository", errors)
    repo_url = _required_entry_string(entry, "repo_url", errors)
    issue_url = _required_entry_string(entry, "issue_url", errors)
    title = _required_entry_string(entry, "title", errors)
    language = _required_entry_string(entry, "language", errors)
    task_type = _required_entry_string(entry, "task_type", errors)
    state_at_capture = _required_entry_string(entry, "state_at_capture", errors)
    captured_at = _required_entry_string(entry, "captured_at", errors)
    expected_workflow = _entry_string_list(entry, "expected_workflow", errors)
    selection_reason = _required_entry_string(entry, "selection_reason", errors)

    if task_id and not task_id.replace("_", "").replace("-", "").isalnum():
        errors.append(f"task_id contains unsafe characters: {task_id}")
    if repository and "/" not in repository:
        errors.append(f"repository must use owner/name format: {repository}")
    if repo_url and not repo_url.startswith("https://github.com/"):
        errors.append(f"repo_url must be a GitHub URL: {repo_url}")
    if issue_url and not issue_url.startswith("https://github.com/"):
        errors.append(f"issue_url must be a GitHub URL: {issue_url}")
    if repository and issue_url:
        expected_prefix = f"https://github.com/{repository}/issues/"
        if not issue_url.startswith(expected_prefix):
            errors.append(f"issue_url does not match repository: {issue_url}")
    if repo_url and issue_url and "/issues/" in repo_url:
        errors.append("repo_url should point to the repository, not an issue")
    if state_at_capture and state_at_capture not in {"open", "closed"}:
        warnings.append(f"unexpected state_at_capture: {state_at_capture}")
    if language and language.lower() != "python":
        warnings.append(f"non-python issue corpus entry: {language}")
    if title and len(title) < 8:
        warnings.append("title is very short")
    if captured_at and "T" not in captured_at:
        warnings.append(f"captured_at should be an ISO timestamp: {captured_at}")
    if not selection_reason:
        warnings.append("selection_reason is empty")

    return IssueCorpusEntryValidationResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        language=language,
        task_type=task_type,
        state_at_capture=state_at_capture,
        expected_workflow=expected_workflow,
    )


def _validate_materialized_issue_task_dir(
    task_dir: Path,
) -> IssueCorpusMaterializedTaskValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = task_dir / "task_manifest.json"
    issue_path = task_dir / "issue.md"
    runbook_path = task_dir / "RUNBOOK.md"
    manifest: dict[str, Any] = {}

    if not manifest_path.exists():
        errors.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                errors.append("task_manifest.json must contain a JSON object")
            else:
                manifest = parsed
        except json.JSONDecodeError as error:
            errors.append(f"task_manifest.json is invalid JSON: {error.msg}")

    if not issue_path.exists():
        errors.append("missing issue.md")
    elif not issue_path.read_text(encoding="utf-8").strip():
        errors.append("issue.md is empty")
    elif "Claim Boundary" not in issue_path.read_text(encoding="utf-8"):
        warnings.append("issue.md does not include a Claim Boundary section")

    if not runbook_path.exists():
        errors.append("missing RUNBOOK.md")
    elif not runbook_path.read_text(encoding="utf-8").strip():
        errors.append("RUNBOOK.md is empty")
    elif "Suggested Commands" not in runbook_path.read_text(encoding="utf-8"):
        warnings.append("RUNBOOK.md does not include suggested commands")

    task_id = _manifest_string(manifest, "task_id", errors)
    version = manifest.get("task_manifest_version")
    if version != 1:
        errors.append(f"unsupported task_manifest_version: {version}")
    if task_id and task_id != task_dir.name:
        warnings.append(f"task_id does not match directory name: {task_id} != {task_dir.name}")

    issue = _manifest_object(manifest, "issue", errors)
    repository = _manifest_string(issue, "repository", errors, field_name="issue.repository")
    repo_url = _manifest_string(issue, "repo_url", errors, field_name="issue.repo_url")
    issue_url = _manifest_string(issue, "issue_url", errors, field_name="issue.issue_url")
    language = _manifest_string(issue, "language", errors, field_name="issue.language")
    expected_workflow = _string_list(issue.get("expected_workflow"))

    if repository and "/" not in repository:
        errors.append(f"issue.repository must use owner/name format: {repository}")
    if repo_url and not repo_url.startswith("https://github.com/") and not Path(repo_url).exists():
        errors.append(f"issue.repo_url must be a GitHub URL or local fixture path: {repo_url}")
    if issue_url and not issue_url.startswith("https://github.com/"):
        errors.append(f"issue.issue_url must be a GitHub URL: {issue_url}")
    if repository and issue_url and repository.count("/") == 1:
        expected_prefix = f"https://github.com/{repository}/issues/"
        if not issue_url.startswith(expected_prefix) and not repository.startswith("local/"):
            errors.append(f"issue.issue_url does not match repository: {issue_url}")
    if language and language.lower() != "python":
        warnings.append(f"non-python materialized task language: {language}")
    if not expected_workflow:
        warnings.append("issue.expected_workflow is empty")

    snapshot = _manifest_object(manifest, "repository_snapshot", errors)
    repo_path_value = _manifest_string(
        snapshot, "repo_path", errors, field_name="repository_snapshot.repo_path"
    )
    commit_hash = _manifest_string(
        snapshot, "commit_hash", errors, field_name="repository_snapshot.commit_hash"
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    file_count = snapshot.get("file_count")
    if repo_path_value:
        repo_path = Path(repo_path_value)
        if not repo_path.exists():
            errors.append(f"repository_snapshot.repo_path does not exist: {repo_path_value}")
        elif not repo_path.is_dir():
            errors.append(f"repository_snapshot.repo_path is not a directory: {repo_path_value}")
    if commit_hash and len(commit_hash) < 8:
        warnings.append("repository_snapshot.commit_hash is unusually short")
    if not isinstance(file_count, int) or file_count <= 0:
        errors.append("repository_snapshot.file_count must be a positive integer")
    if not test_commands:
        errors.append("repository_snapshot.test_commands must contain at least one command")
    elif not any("pytest" in command for command in test_commands):
        warnings.append("repository_snapshot.test_commands does not include pytest")

    retrieval = _manifest_object(manifest, "retrieval_preview", errors)
    context_provider = _manifest_string(
        retrieval, "context_provider", errors, field_name="retrieval_preview.context_provider"
    )
    context_count = retrieval.get("context_count")
    retrieved_files = _string_list(retrieval.get("retrieved_files"))
    top_contexts = retrieval.get("top_contexts")
    if context_provider not in {"native", "native_hybrid", "native_graph"}:
        errors.append(f"unsupported retrieval_preview.context_provider: {context_provider}")
    if not isinstance(context_count, int) or context_count <= 0:
        errors.append("retrieval_preview.context_count must be a positive integer")
    if not retrieved_files:
        errors.append("retrieval_preview.retrieved_files must not be empty")
    if not isinstance(top_contexts, list):
        errors.append("retrieval_preview.top_contexts must be a list")
    elif any(isinstance(context, dict) and "excerpt" in context for context in top_contexts):
        errors.append("retrieval_preview.top_contexts must be source-free")

    suggested_commands = _string_list(manifest.get("suggested_commands"))
    if not suggested_commands:
        errors.append("suggested_commands must contain at least one command")
    elif not any("patchsmith.cli run" in command for command in suggested_commands):
        errors.append("suggested_commands must include a patchsmith.cli run command")
    claim_boundary = _string_list(manifest.get("claim_boundary"))
    if not claim_boundary:
        errors.append("claim_boundary must not be empty")

    source_free = _manifest_is_source_free(manifest)
    if manifest.get("source_free") is not True:
        errors.append("source_free must be true")
    if not source_free:
        errors.append("manifest contains non-source-free excerpt fields")

    return IssueCorpusMaterializedTaskValidationResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status="invalid" if errors else "valid",
        errors=errors,
        warnings=warnings,
        manifest_path=str(manifest_path) if manifest_path.exists() else None,
        issue_path=str(issue_path) if issue_path.exists() else None,
        runbook_path=str(runbook_path) if runbook_path.exists() else None,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        retrieved_files=retrieved_files,
        suggested_commands=suggested_commands,
        source_free=source_free,
    )


def _check_materialized_issue_task_run_readiness(
    *,
    task_dir: Path,
    policy: CommandPolicy,
) -> IssueCorpusMaterializedRunReadinessResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.exists():
        errors.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                errors.append("task_manifest.json must contain a JSON object")
        except json.JSONDecodeError as error:
            errors.append(f"task_manifest.json is invalid JSON: {error.msg}")

    task_id = manifest.get("task_id") if isinstance(manifest.get("task_id"), str) else None
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    snapshot = (
        manifest.get("repository_snapshot")
        if isinstance(manifest.get("repository_snapshot"), dict)
        else {}
    )
    repository = issue.get("repository") if isinstance(issue.get("repository"), str) else None
    issue_url = issue.get("issue_url") if isinstance(issue.get("issue_url"), str) else None
    repo_path_value = (
        snapshot.get("repo_path") if isinstance(snapshot.get("repo_path"), str) else None
    )
    package_manager = (
        snapshot.get("package_manager")
        if isinstance(snapshot.get("package_manager"), str)
        else None
    )
    file_count = snapshot.get("file_count") if isinstance(snapshot.get("file_count"), int) else None
    test_commands = _string_list(snapshot.get("test_commands"))
    suggested_commands = _string_list(manifest.get("suggested_commands"))
    repo_exists = False
    workspace = Path.cwd()
    if repo_path_value:
        repo_path = Path(repo_path_value)
        repo_exists = repo_path.exists() and repo_path.is_dir()
        if repo_exists:
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("repository_snapshot.repo_path is missing")

    if not test_commands:
        errors.append("no test commands available")
    command_checks: list[dict[str, Any]] = []
    for command in test_commands:
        decision = policy.evaluate(command, workspace=workspace)
        command_checks.append(
            {
                "command": command,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "tokens": list(decision.tokens),
            }
        )
        if not decision.allowed:
            errors.append(f"test command rejected by policy: {command} ({decision.reason})")

    if not suggested_commands:
        warnings.append("no suggested patchsmith run command recorded")

    risk_level, risk_notes = _materialized_run_risk(
        file_count=file_count,
        test_commands=test_commands,
        package_manager=package_manager,
    )
    allowed_count = sum(1 for check in command_checks if check["allowed"])
    blocked_count = sum(1 for check in command_checks if not check["allowed"])
    status = "blocked" if errors else "warning" if warnings or risk_notes else "ready"
    return IssueCorpusMaterializedRunReadinessResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status=status,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        repo_exists=repo_exists,
        file_count=file_count,
        package_manager=package_manager,
        test_commands=test_commands,
        allowed_test_commands=allowed_count,
        blocked_test_commands=blocked_count,
        command_checks=command_checks,
        suggested_commands=suggested_commands,
        risk_level=risk_level,
        risk_notes=risk_notes,
        errors=errors,
        warnings=warnings,
    )


def _plan_materialized_issue_focused_test(
    *,
    task_dir: Path,
    policy: CommandPolicy,
    max_paths: int,
) -> IssueCorpusFocusedTestPlanResult:
    errors: list[str] = []
    warnings: list[str] = []
    risk_notes: list[str] = []
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.exists():
        errors.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                errors.append("task_manifest.json must contain a JSON object")
        except json.JSONDecodeError as error:
            errors.append(f"task_manifest.json is invalid JSON: {error.msg}")

    task_id = manifest.get("task_id") if isinstance(manifest.get("task_id"), str) else None
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    snapshot = (
        manifest.get("repository_snapshot")
        if isinstance(manifest.get("repository_snapshot"), dict)
        else {}
    )
    retrieval = (
        manifest.get("retrieval_preview")
        if isinstance(manifest.get("retrieval_preview"), dict)
        else {}
    )
    repository = issue.get("repository") if isinstance(issue.get("repository"), str) else None
    issue_url = issue.get("issue_url") if isinstance(issue.get("issue_url"), str) else None
    repo_path_value = (
        snapshot.get("repo_path") if isinstance(snapshot.get("repo_path"), str) else None
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    fallback_command = test_commands[0] if test_commands else None
    retrieved_files = _string_list(retrieval.get("retrieved_files"))
    focused_files = [
        path
        for path in retrieved_files
        if _is_materialized_test_candidate_path(path)
    ][: max(max_paths, 0)]

    repo_exists = False
    workspace = Path.cwd()
    if repo_path_value:
        repo_path = Path(repo_path_value)
        repo_exists = repo_path.exists() and repo_path.is_dir()
        if repo_exists:
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("repository_snapshot.repo_path is missing")

    if focused_files:
        missing_focused = [
            path for path in focused_files if repo_exists and not (workspace / path).is_file()
        ]
        if missing_focused:
            errors.append(f"focused test files do not exist: {', '.join(missing_focused)}")
        command = "python3 -m pytest " + " ".join(focused_files)
        status = "planned"
    elif fallback_command:
        command = fallback_command
        status = "fallback"
        warnings.append("no retrieved test-like file was available; using fallback test command")
    else:
        command = None
        status = "blocked"
        errors.append("no focused or fallback test command available")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"focused test command rejected by policy: {decision.reason}")

    if focused_files:
        risk_notes.append("focused command is derived from retrieved test-like files")
    if fallback_command and command == fallback_command:
        risk_notes.append("fallback command may run a broader test scope")
    if errors:
        status = "blocked"
    return IssueCorpusFocusedTestPlanResult(
        task_id=task_id,
        task_dir=str(task_dir),
        status=status,
        repository=repository,
        issue_url=issue_url,
        repo_path=repo_path_value,
        focused_files=focused_files,
        command=command,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        fallback_command=fallback_command,
        risk_notes=risk_notes,
        errors=errors,
        warnings=warnings,
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


def _diagnose_focused_test_run_record(
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
    logs = _focused_test_log_text(stdout_path=stdout_path, stderr_path=stderr_path)

    if run_status == "passed":
        return IssueCorpusFocusedTestDiagnosisResult(
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
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_matching_lines(logs, ["timed out", "timeout"], limit=2),
            suggested_next_actions=[
                "Run the focused command in a stricter isolated environment with an explicit timeout budget.",
                "Reduce the command to issue-specific tests before using it as repair validation.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if run_status == "blocked":
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_string_list(record.get("errors")) or _matching_lines(
                logs, ["blocked", "policy", "exit code"], limit=3
            ),
            suggested_next_actions=[
                "Fix the focused test plan or sandbox availability before running public issue repairs.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "_pytest._version" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_matching_lines(logs, ["_pytest._version", "ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Prepare the repository in an isolated environment using its documented build step before running tests.",
                "Record the setup command separately from repair validation; do not treat this as a patch failure.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "recursive dependency involving fixture" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_matching_lines(
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
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_matching_lines(logs, ["ModuleNotFoundError"], limit=3),
            suggested_next_actions=[
                "Resolve repository test dependencies in a sandbox before interpreting repair quality.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    if "ERROR at setup" in logs:
        return IssueCorpusFocusedTestDiagnosisResult(
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
            evidence=_matching_lines(logs, ["ERROR at setup"], limit=4),
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
        return IssueCorpusFocusedTestDiagnosisResult(
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
    return IssueCorpusFocusedTestDiagnosisResult(
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
        evidence=_last_nonempty_lines(logs, limit=4),
        suggested_next_actions=[
            "Inspect the saved stdout/stderr and add a narrower diagnosis before repair-quality claims.",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
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


def _check_focused_test_setup_record(
    *,
    record: dict[str, Any],
    docker_smoke_status: str,
) -> IssueCorpusFocusedTestSetupReadinessResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    setup_status = _optional_string(record.get("status")) or "unknown"
    repo_path = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if not repo_exists:
            errors.append(f"repository snapshot is not available: {repo_path}")
            next_actions.append("rerun public issue context preview or materialization")
    else:
        errors.append("setup plan is missing repo_path")
        next_actions.append("regenerate focused diagnosis and setup plan from run results")

    if setup_status == "manual_review":
        errors.append("setup plan requires manual review before execution")
    elif setup_status == "ready":
        if setup_commands:
            warnings.append("ready setup task unexpectedly includes setup commands")
    elif setup_status != "planned":
        warnings.append(f"setup plan status is {setup_status}")

    if setup_status == "planned" and not setup_commands:
        errors.append("planned setup task has no setup commands")
    if setup_status == "planned" and not validation_command:
        errors.append("planned setup task has no validation command")

    if sandbox_required and docker_smoke_status != "passed":
        errors.append(f"Docker sandbox smoke is {docker_smoke_status}")
        next_actions.append("start Docker, build the smoke image, and rerun docker-smoke")
    if requires_network:
        warnings.append("setup requires network access; use a controlled disposable build step")
        next_actions.append("review network access and dependency trust before setup execution")
    if sandbox_required:
        next_actions.append("execute setup only inside a disposable sandbox with no host secrets")

    status = "blocked" if errors else "warning" if warnings else "ready"
    if not next_actions and status == "ready":
        next_actions.append("run setup commands in the approved sandbox, then rerun validation")
    return IssueCorpusFocusedTestSetupReadinessResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        setup_profile=setup_profile,
        repo_path=repo_path,
        repo_exists=repo_exists,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        docker_smoke_status=docker_smoke_status,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_focused_test_setup_record(
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
    allow_warnings: bool,
    allow_dependency_installs: bool,
) -> IssueCorpusFocusedTestSetupExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    readiness_status = _optional_string(record.get("status")) or "unknown"
    setup_profile = _optional_string(record.get("setup_profile")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    setup_commands = _string_list(record.get("setup_commands"))
    validation_command = _optional_string(record.get("validation_command"))
    requires_network = bool(record.get("requires_network"))
    sandbox_required = bool(record.get("sandbox_required"))
    errors = _string_list(record.get("errors"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    command_results: list[IssueCorpusFocusedTestSetupCommandResult] = []

    workspace: Path | None = None
    if readiness_status == "blocked":
        errors.append("setup readiness is blocked")
    elif readiness_status == "warning" and not allow_warnings:
        errors.append("setup readiness is warning and --allow-warnings was not set")
    elif readiness_status not in {"ready", "warning"}:
        warnings.append(f"setup readiness status is {readiness_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("setup readiness record has no repo_path")

    if sandbox_required and sandbox_mode != "docker":
        warnings.append("setup requested Docker isolation but a non-Docker sandbox was selected")
    if requires_network and sandbox_mode == "docker":
        warnings.append(
            f"setup requires network access; Docker sandbox network is {sandbox_network}"
        )
        if not dry_run and sandbox_network == "none":
            errors.append("setup requires network but Docker sandbox network is none")

    if not setup_commands:
        status = "blocked" if errors else "skipped"
        if status == "skipped":
            next_actions.append("no setup commands were required; rerun focused validation")
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status=status,
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(next_actions),
        )

    if workspace is not None:
        for command in setup_commands:
            decision = policy.evaluate(command, workspace=workspace)
            command_results.append(
                IssueCorpusFocusedTestSetupCommandResult(
                    command=command,
                    status="dry_run" if decision.allowed else "policy_blocked",
                    exit_code=None,
                    timed_out=False,
                    duration_ms=0,
                    policy_allowed=decision.allowed,
                    policy_reason=decision.reason,
                    stdout_path=None,
                    stderr_path=None,
                )
            )
            if not decision.allowed:
                errors.append(f"setup command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "resolve setup-readiness and command-policy blockers before execution",
                ]
            ),
        )

    if dry_run:
        return IssueCorpusFocusedTestSetupExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            readiness_status=readiness_status,
            setup_profile=setup_profile,
            repo_path=repo_path_value,
            setup_commands=setup_commands,
            validation_command=validation_command,
            requires_network=requires_network,
            sandbox_required=sandbox_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            allow_dependency_installs=allow_dependency_installs,
            command_results=command_results,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute after reviewing dry-run evidence"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    command_results = []
    status = "passed"
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    for index, command in enumerate(setup_commands, start=1):
        command_result = runner.run(
            command=command,
            workspace=workspace,
            timeout_seconds=timeout_seconds,
        )
        command_dir = run_dir / f"command_{index:02d}"
        command_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = command_dir / "stdout.txt"
        stderr_path = command_dir / "stderr.txt"
        stdout_path.write_text(command_result.stdout, encoding="utf-8")
        stderr_path.write_text(command_result.stderr, encoding="utf-8")
        if not command_result.policy_decision.allowed:
            command_status = "policy_blocked"
            status = "blocked"
            errors.append(
                f"setup command rejected by policy: {command_result.policy_decision.reason}"
            )
        elif command_result.timed_out:
            command_status = "timed_out"
            status = "timed_out"
            warnings.append(f"setup command timed out after {timeout_seconds}s")
        elif command_result.exit_code == 0:
            command_status = "passed"
        else:
            command_status = "failed"
            status = "failed"
            warnings.append(f"setup command exited {command_result.exit_code}")
        command_results.append(
            IssueCorpusFocusedTestSetupCommandResult(
                command=command,
                status=command_status,
                exit_code=command_result.exit_code,
                timed_out=command_result.timed_out,
                duration_ms=command_result.duration_ms,
                policy_allowed=command_result.policy_decision.allowed,
                policy_reason=command_result.policy_decision.reason,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )
        )
        if command_status != "passed":
            break

    return IssueCorpusFocusedTestSetupExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        setup_profile=setup_profile,
        repo_path=repo_path_value,
        setup_commands=setup_commands,
        validation_command=validation_command,
        requires_network=requires_network,
        sandbox_required=sandbox_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        allow_dependency_installs=allow_dependency_installs,
        command_results=command_results,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(
            [*next_actions, "rerun focused validation command after successful setup"]
        ),
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
        errors.append(f"validation command rejected by policy: {command_result.policy_decision.reason}")
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


def _plan_public_issue_reproduction_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionPlanResult:
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []
    next_actions: list[str] = []

    if not manifest_path.exists():
        blockers.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            blockers.append(f"task_manifest.json is invalid JSON: {error.msg}")
        else:
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                blockers.append("task_manifest.json must contain a JSON object")

    task_id = _optional_string(manifest.get("task_id")) or task_dir.name
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    snapshot = (
        manifest.get("repository_snapshot")
        if isinstance(manifest.get("repository_snapshot"), dict)
        else {}
    )
    retrieval = (
        manifest.get("retrieval_preview")
        if isinstance(manifest.get("retrieval_preview"), dict)
        else {}
    )
    reproduction = (
        manifest.get("reproduction")
        if isinstance(manifest.get("reproduction"), dict)
        else {}
    )
    spec_reproduction = reproduction_spec if isinstance(reproduction_spec, dict) else {}
    repository = _optional_string(issue.get("repository"))
    issue_url = _optional_string(issue.get("issue_url"))
    repo_path = _optional_string(snapshot.get("repo_path")) or (
        _optional_string(focused_record.get("repo_path")) if focused_record else None
    )
    focused_files = (
        _string_list(focused_record.get("focused_files")) if focused_record else []
    )
    if not focused_files:
        focused_files = [
            path
            for path in _string_list(retrieval.get("retrieved_files"))
            if _is_materialized_test_candidate_path(path)
        ][:2]
    spec_command = _optional_string(spec_reproduction.get("command"))
    explicit_command = _optional_string(reproduction.get("command"))
    focused_command = (
        _optional_string(focused_record.get("command")) if focused_record else None
    )
    test_commands = _string_list(snapshot.get("test_commands"))
    if spec_command:
        command = spec_command
        command_source = "reproduction_spec"
        evidence.append("reproduction spec provides an explicit command")
    elif explicit_command:
        command = explicit_command
        command_source = "manifest_reproduction"
        evidence.append("manifest contains an explicit reproduction command")
    elif focused_command:
        command = focused_command
        command_source = "focused_test_plan"
        evidence.append("focused test plan provides the reproduction candidate command")
    elif test_commands:
        command = test_commands[0]
        command_source = "repository_test_command"
        warnings.append("using broad repository test command as reproduction candidate")
    else:
        command = None
        command_source = "missing"
        blockers.append("no reproduction or focused test command is available")

    spec_failure_signals = _string_list(
        spec_reproduction.get("expected_failure_signals")
    )
    manifest_failure_signals = _string_list(
        reproduction.get("expected_failure_signals")
    )
    expected_failure_signals = spec_failure_signals or manifest_failure_signals
    if "fixture_files" in spec_reproduction:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            spec_reproduction.get("fixture_files")
        )
        fixture_source = "reproduction spec"
    else:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            reproduction.get("fixture_files")
        )
        fixture_source = "task manifest"
    if fixture_errors:
        blockers.extend(fixture_errors)
    elif fixture_files:
        evidence.append(
            f"{fixture_source} provides {len(fixture_files)} temporary fixture file(s)"
        )
    manual_spec_required = not expected_failure_signals
    if expected_failure_signals:
        if spec_failure_signals:
            evidence.append("expected failing signal is encoded in the reproduction spec")
        else:
            evidence.append("expected failing signal is encoded in the task manifest")
    else:
        warnings.append("expected failing signal is not encoded")
        next_actions.append(
            "add issue-specific expected failure text, assertion, traceback, or exit criteria"
        )

    workspace = Path.cwd()
    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if repo_exists:
            workspace = repo
            evidence.append("repository snapshot exists")
        else:
            blockers.append(f"repository snapshot is missing: {repo_path}")
    else:
        blockers.append("repository_snapshot.repo_path is missing")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if decision.allowed:
            evidence.append("reproduction command is allowed by command policy")
        else:
            blockers.append(f"reproduction command rejected by policy: {decision.reason}")

    if focused_record is None and command_source not in {
        "manifest_reproduction",
        "reproduction_spec",
    }:
        warnings.append("focused test plan record is missing")
        next_actions.append("regenerate `plan-materialized-focused-tests` before execution")
    if command and not blockers and not manual_spec_required:
        next_actions.append("execute reproduction command and save failing stdout/stderr evidence")
    elif command and not blockers:
        next_actions.append("review and encode the expected failing signal before execution")

    status = "blocked" if blockers else "warning" if warnings else "planned"
    return IssueCorpusPublicReproductionPlanResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        reproduction_command=command,
        command_source=command_source,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        focused_files=focused_files,
        fixture_files=fixture_files,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        evidence=_dedupe_preserve_order(evidence),
        blockers=_dedupe_preserve_order(blockers),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _validate_public_issue_reproduction_spec_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionSpecValidationResult:
    planned = _plan_public_issue_reproduction_record(
        task_dir=task_dir,
        focused_record=focused_record,
        reproduction_spec=reproduction_spec,
        policy=policy,
    )
    errors = list(planned.blockers)
    warnings = list(planned.warnings)
    evidence = list(planned.evidence)
    next_actions = list(planned.next_actions)
    spec_present = reproduction_spec is not None

    if spec_present:
        evidence.append("reviewed reproduction spec found")
    else:
        errors.append("reviewed reproduction spec is missing")
        next_actions.append(
            "fill public_issue_reproduction_specs_template.json and rerun validation"
        )

    if not planned.expected_failure_signals:
        errors.append("expected_failure_signals is empty")
        next_actions.append(
            "encode at least one exact failing assertion, traceback, or behavior signal"
        )

    if not planned.reproduction_command:
        errors.append("reproduction command is missing")
    elif not planned.policy_allowed:
        errors.append(
            f"reproduction command rejected by policy: {planned.policy_reason or 'unknown'}"
        )

    if planned.command_source != "reproduction_spec":
        warnings.append(
            "reproduction spec does not override the command; using planned fallback command"
        )

    status = "blocked" if errors else "warning" if warnings else "ready"
    return IssueCorpusPublicReproductionSpecValidationResult(
        task_id=planned.task_id,
        repository=planned.repository,
        issue_url=planned.issue_url,
        status=status,
        spec_present=spec_present,
        repo_path=planned.repo_path,
        repo_exists=planned.repo_exists,
        reproduction_command=planned.reproduction_command,
        command_source=planned.command_source,
        policy_allowed=planned.policy_allowed,
        policy_reason=planned.policy_reason,
        fixture_files=planned.fixture_files,
        expected_failure_signals=planned.expected_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _discover_public_issue_failure_signal_record(
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
) -> IssueCorpusPublicFailureSignalDiscoveryResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    errors.extend(fixture_errors)
    policy_allowed = False
    policy_reason: str | None = None
    workspace: Path | None = None

    if plan_status == "blocked":
        errors.append("reproduction plan is blocked")
    elif plan_status not in {"planned", "warning"}:
        warnings.append(f"reproduction plan status is {plan_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("reproduction plan record has no repo_path")

    if not command:
        errors.append("reproduction command is missing")
    elif workspace is not None:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"reproduction command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve discovery blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "rerun with --execute to observe candidate failure logs",
                ]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_files:
            with tempfile.TemporaryDirectory(
                prefix="patchsmith-public-repro-fixtures-"
            ) as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(str(workspace), fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=fixture_files,
                )
                command_result = runner.run(
                    command=command,
                    workspace=snapshot.repo_path,
                    timeout_seconds=timeout_seconds,
                )
        else:
            command_result = runner.run(
                command=command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
    except (OSError, ValueError) as error:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(
                [*errors, f"failed to prepare fixture workspace: {error}"]
            ),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve fixture workspace preparation before execution"]
            ),
        )
    stdout_file = run_dir / "stdout.txt"
    stderr_file = run_dir / "stderr.txt"
    stdout_file.write_text(command_result.stdout, encoding="utf-8")
    stderr_file.write_text(command_result.stderr, encoding="utf-8")
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    candidate_failure_signals = _candidate_failure_signals_from_logs(combined_logs)
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason

    if not policy_allowed:
        status = "blocked"
        errors.append(
            f"reproduction command rejected by policy: {policy_reason or 'unknown'}"
        )
        next_actions.append("resolve command-policy blockers before discovery")
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"candidate command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif command_result.exit_code == 0:
        status = "passed"
        warnings.append("candidate command passed; no failure signal was observed")
        next_actions.append(
            "write or select a more specific issue reproduction before repair attempts"
        )
    elif candidate_failure_signals:
        status = "observed_failure"
        next_actions.append(
            "review candidate_failure_signals and copy exact issue-specific signals into reviewed specs"
        )
    else:
        status = "failed"
        warnings.append("candidate command failed but no concise failure signal was extracted")
        next_actions.append("inspect saved stdout/stderr and choose reviewed failure signals")

    return IssueCorpusPublicFailureSignalDiscoveryResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=str(stdout_file),
        stderr_path=str(stderr_file),
        fixture_paths=fixture_paths,
        candidate_failure_signals=candidate_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_public_issue_reproduction_record(
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
) -> IssueCorpusPublicReproductionExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    expected_failure_signals = _string_list(record.get("expected_failure_signals"))
    manual_spec_required = record.get("manual_spec_required") is True or not (
        expected_failure_signals
    )
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    errors.extend(fixture_errors)

    exit_code: int | None = None
    timed_out = False
    duration_ms = 0
    policy_allowed = False
    policy_reason: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    matched_failure_signals: list[str] = []
    missing_failure_signals = list(expected_failure_signals)

    workspace: Path | None = None
    if plan_status == "blocked":
        errors.append("reproduction plan is blocked")
    elif plan_status not in {"planned", "warning"}:
        warnings.append(f"reproduction plan status is {plan_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("reproduction plan record has no repo_path")

    if not command:
        errors.append("reproduction command is missing")
    elif workspace is not None:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"reproduction command rejected by policy: {decision.reason}")

    if manual_spec_required:
        errors.append("expected failing signal is not encoded")
        next_actions.append(
            "encode an issue-specific expected failure signal before executing reproduction"
        )

    if errors:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_paths=fixture_paths,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve reproduction blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_paths=fixture_paths,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute to save failing reproduction logs"]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_files:
            with tempfile.TemporaryDirectory(
                prefix="patchsmith-public-repro-fixtures-"
            ) as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(str(workspace), fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=fixture_files,
                )
                command_result = runner.run(
                    command=command,
                    workspace=snapshot.repo_path,
                    timeout_seconds=timeout_seconds,
                )
        else:
            command_result = runner.run(
                command=command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
    except (OSError, ValueError) as error:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_paths=fixture_paths,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=_dedupe_preserve_order(
                [*errors, f"failed to prepare fixture workspace: {error}"]
            ),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve fixture workspace preparation before execution"]
            ),
        )
    stdout_file = run_dir / "stdout.txt"
    stderr_file = run_dir / "stderr.txt"
    stdout_file.write_text(command_result.stdout, encoding="utf-8")
    stderr_file.write_text(command_result.stderr, encoding="utf-8")

    exit_code = command_result.exit_code
    timed_out = command_result.timed_out
    duration_ms = command_result.duration_ms
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason
    stdout_path = str(stdout_file)
    stderr_path = str(stderr_file)
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    matched_failure_signals = _matched_expected_failure_signals(
        combined_logs,
        expected_failure_signals,
    )
    matched_set = set(matched_failure_signals)
    missing_failure_signals = [
        signal for signal in expected_failure_signals if signal not in matched_set
    ]

    if not policy_allowed:
        status = "blocked"
        errors.append(
            f"reproduction command rejected by policy: {policy_reason or 'unknown'}"
        )
        next_actions.append("resolve command-policy blockers before execution")
    elif timed_out:
        status = "timed_out"
        warnings.append(f"reproduction command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif exit_code == 0:
        status = "not_reproduced"
        warnings.append("reproduction command passed; expected pre-repair failure was absent")
        next_actions.append(
            "confirm whether the issue is already fixed or update the reproduction command"
        )
    elif missing_failure_signals:
        status = "failed"
        warnings.append("reproduction command failed without all expected failure signals")
        next_actions.append(
            "inspect saved stdout/stderr and update expected failure criteria if appropriate"
        )
    else:
        status = "reproduced"
        next_actions.append("use the saved failing logs as pre-repair reproduction evidence")

    return IssueCorpusPublicReproductionExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        fixture_paths=fixture_paths,
        matched_failure_signals=matched_failure_signals,
        missing_failure_signals=missing_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _check_public_issue_repair_readiness_record(
    *,
    focused_record: dict[str, Any],
    diagnosis_record: dict[str, Any] | None,
    setup_validation_record: dict[str, Any] | None,
    reproduction_execution_record: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> IssueCorpusPublicRepairReadinessResult:
    task_id = _optional_string(focused_record.get("task_id"))
    repository = _optional_string(focused_record.get("repository"))
    issue_url = _optional_string(focused_record.get("issue_url"))
    repo_path = _optional_string(focused_record.get("repo_path"))
    focused_status = _optional_string(focused_record.get("status"))
    focused_command = _optional_string(focused_record.get("command"))
    diagnosis_category = (
        _optional_string(diagnosis_record.get("category"))
        if diagnosis_record is not None
        else None
    )
    diagnosis_severity = (
        _optional_string(diagnosis_record.get("severity"))
        if diagnosis_record is not None
        else None
    )
    setup_status = (
        _optional_string(setup_validation_record.get("status"))
        if setup_validation_record is not None
        else None
    )
    setup_failure_category = (
        _optional_string(setup_validation_record.get("failure_category"))
        if setup_validation_record is not None
        else None
    )
    validation_command = (
        _optional_string(setup_validation_record.get("validation_command"))
        if setup_validation_record is not None
        else focused_command
    )
    sandbox_mode = (
        _optional_string(setup_validation_record.get("sandbox_mode"))
        if setup_validation_record is not None
        else None
    )
    sandbox_network = (
        _optional_string(setup_validation_record.get("sandbox_network"))
        if setup_validation_record is not None
        else None
    )
    reproduction_execution_status = (
        _optional_string(reproduction_execution_record.get("status"))
        if reproduction_execution_record is not None
        else None
    )
    reproduction_stdout_path = (
        _optional_string(reproduction_execution_record.get("stdout_path"))
        if reproduction_execution_record is not None
        else None
    )
    reproduction_stderr_path = (
        _optional_string(reproduction_execution_record.get("stderr_path"))
        if reproduction_execution_record is not None
        else None
    )
    matched_failure_signals = (
        _string_list(reproduction_execution_record.get("matched_failure_signals"))
        if reproduction_execution_record is not None
        else []
    )
    repair_command = _first_manifest_repair_command(manifest)

    evidence: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if not task_id:
        blockers.append("focused run record has no task_id")
    if repo_path:
        repo_exists = Path(repo_path).is_dir()
        if repo_exists:
            evidence.append("repository snapshot exists")
        else:
            blockers.append(f"repository snapshot is missing: {repo_path}")
    else:
        repo_exists = False
        blockers.append("focused run record has no repo_path")

    if focused_status == "passed":
        evidence.append("focused validation command passed before repair")
        if reproduction_execution_status == "reproduced":
            evidence.append("separate reproduction execution provides failing pre-repair evidence")
        else:
            warnings.append(
                "pre-repair focused command passed; issue reproduction is not proven by saved evidence"
            )
            next_actions.append(
                "record an issue-specific failing reproduction or keep repair-quality claims scoped"
            )
    elif focused_status in {"failed", "timed_out"}:
        if diagnosis_category == "nonzero_exit":
            evidence.append("focused command failed with an unclassified nonzero exit")
            warnings.append(
                "focused command failed; confirm the failure reproduces the public issue before repair"
            )
            next_actions.append(
                "capture the expected failing assertion or traceback before using this as a repair target"
            )
        else:
            blockers.append(f"focused run status is {focused_status}")
            next_actions.append("resolve focused test execution before repair attempts")
    else:
        blockers.append(f"focused run status is {focused_status or 'missing'}")

    if diagnosis_record is None:
        blockers.append("focused diagnosis record is missing")
    elif diagnosis_category == "focused_test_passed":
        evidence.append("focused diagnosis confirms runnable validation")
    elif diagnosis_severity in {"dependency", "environment", "blocked"}:
        blockers.append(
            f"focused diagnosis is {diagnosis_category or 'unknown'} with {diagnosis_severity} severity"
        )
    else:
        warnings.append(f"focused diagnosis is {diagnosis_category or 'unknown'}")

    if setup_validation_record is None:
        blockers.append("setup validation record is missing")
    elif setup_status == "passed":
        evidence.append("post-setup validation command passed")
    elif setup_status == "dry_run":
        blockers.append("setup validation was only dry-run")
        next_actions.append("execute setup validation before repair attempts")
    else:
        blockers.append(f"setup validation status is {setup_status or 'missing'}")
        if setup_failure_category:
            blockers.append(f"setup validation failure category is {setup_failure_category}")

    if reproduction_execution_record is None:
        warnings.append("public issue reproduction execution record is missing")
        next_actions.append("run `execute-public-issue-reproductions` before repair attempts")
    elif reproduction_execution_status == "reproduced":
        evidence.append("public issue reproduction execution saved failing evidence")
        if reproduction_stdout_path:
            evidence.append(f"reproduction stdout saved: {reproduction_stdout_path}")
        if reproduction_stderr_path:
            evidence.append(f"reproduction stderr saved: {reproduction_stderr_path}")
        if matched_failure_signals:
            evidence.append(
                "matched reproduction signal: " + "; ".join(matched_failure_signals)
            )
    elif reproduction_execution_status == "dry_run":
        warnings.append("public issue reproduction execution is only dry-run")
        next_actions.append("rerun reproduction execution with --execute after review")
    elif reproduction_execution_status == "blocked":
        warnings.append("public issue reproduction execution is blocked")
        next_actions.append("resolve reproduction execution blockers before repair attempts")
    elif reproduction_execution_status == "not_reproduced":
        warnings.append("public issue reproduction command did not fail as expected")
        next_actions.append("confirm whether the issue is already fixed or update reproduction")
    else:
        warnings.append(
            f"public issue reproduction execution status is {reproduction_execution_status or 'missing'}"
        )
        next_actions.append("inspect reproduction execution logs before repair attempts")

    if repair_command:
        evidence.append("saved PatchSmith repair command is available")
    else:
        blockers.append("saved PatchSmith repair command is missing")
        next_actions.append("regenerate materialized public issue tasks with suggested commands")

    if validation_command:
        evidence.append("focused validation command is available")
    else:
        blockers.append("focused validation command is missing")

    if sandbox_mode == "docker":
        evidence.append(f"setup validation used Docker network {sandbox_network or 'unknown'}")
    if sandbox_network == "bridge":
        warnings.append("repair validation depends on Docker bridge networking")

    if not blockers and not next_actions:
        next_actions.append("run a bounded PatchSmith repair attempt and save normal run artifacts")
    elif not blockers:
        next_actions.append("run repair only after accepting the listed caveats")

    status = "blocked" if blockers else "warning" if warnings else "ready"
    return IssueCorpusPublicRepairReadinessResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        repair_command=repair_command,
        validation_command=validation_command,
        focused_run_status=focused_status,
        diagnosis_category=diagnosis_category,
        setup_validation_status=setup_status,
        setup_failure_category=setup_failure_category,
        reproduction_execution_status=reproduction_execution_status,
        reproduction_stdout_path=reproduction_stdout_path,
        reproduction_stderr_path=reproduction_stderr_path,
        matched_failure_signals=matched_failure_signals,
        sandbox_mode=sandbox_mode,
        sandbox_network=sandbox_network,
        evidence=_dedupe_preserve_order(evidence),
        blockers=_dedupe_preserve_order(blockers),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _execute_public_issue_repair_record(
    *,
    record: dict[str, Any],
    manifest: dict[str, Any] | None,
    runner: RepairRunner | None,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    dry_run: bool,
    allow_warnings: bool,
) -> IssueCorpusPublicRepairAttemptResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    readiness_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    repair_command = _optional_string(record.get("repair_command"))
    validation_command = _optional_string(record.get("validation_command"))
    reproduction_execution_status = _optional_string(
        record.get("reproduction_execution_status")
    )
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    evidence = _string_list(record.get("evidence"))
    next_actions = _string_list(record.get("next_actions"))
    run_id: str | None = None
    run_status: str | None = None
    report_path: str | None = None
    trace_path: str | None = None
    final_diff_path: str | None = None
    test_exit_code: int | None = None
    patch_generated = False

    repo_exists = False
    if repo_path_value:
        repo_path = Path(repo_path_value)
        repo_exists = repo_path.exists() and repo_path.is_dir()
        if not repo_exists:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("repair-readiness record has no repo_path")

    issue_text = _public_issue_repair_issue_text(manifest)
    if not issue_text:
        errors.append("materialized issue text is missing")
    if not repair_command:
        errors.append("repair command is missing")
    if not validation_command:
        errors.append("validation command is missing")
    if reproduction_execution_status != "reproduced":
        errors.append("public issue reproduction has not been proven")
        next_actions.append("execute reproduction and save failing logs before repair")
    if readiness_status == "blocked":
        errors.append("repair readiness is blocked")
    elif readiness_status == "warning" and not allow_warnings:
        errors.append("repair readiness is warning and --allow-warnings was not set")
    elif readiness_status not in {"ready", "warning"}:
        warnings.append(f"repair readiness status is {readiness_status}")

    if errors:
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status=run_status,
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order(evidence),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve public repair-attempt blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status=run_status,
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order(
                [*evidence, "repair attempt passed dry-run gating"]
            ),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute to launch PatchSmith repair"]
            ),
        )

    assert runner is not None
    assert repo_path_value is not None
    assert issue_text is not None
    try:
        run_result = runner.run(
            RunRequest(
                repo=repo_path_value,
                issue_text=issue_text,
                issue_url=issue_url,
                test_command=validation_command,
                runtime=runtime,
                planner=planner,
                context_provider=context_provider,
                sandbox_mode=sandbox_mode,
                sandbox_image=sandbox_image,
            )
        )
    except Exception as error:
        errors.append(f"PatchSmith repair run failed: {error}")
        return IssueCorpusPublicRepairAttemptResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="failed",
            readiness_status=readiness_status,
            repo_path=repo_path_value,
            repo_exists=repo_exists,
            repair_command=repair_command,
            validation_command=validation_command,
            reproduction_execution_status=reproduction_execution_status,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            dry_run=dry_run,
            run_id=run_id,
            run_status="failed",
            report_path=report_path,
            trace_path=trace_path,
            final_diff_path=final_diff_path,
            test_exit_code=test_exit_code,
            patch_generated=patch_generated,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            evidence=_dedupe_preserve_order(evidence),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "inspect the failed PatchSmith run before retrying"]
            ),
        )

    run_id = run_result.run_id
    run_status = run_result.status
    report_path = str(run_result.report_path)
    trace_path = str(run_result.trace_path)
    final_diff_path = str(run_result.final_diff_path)
    test_exit_code = (
        run_result.test_result.exit_code if run_result.test_result is not None else None
    )
    patch_generated = _path_has_text(run_result.final_diff_path)
    if patch_generated:
        evidence.append("PatchSmith generated a final diff")
    if test_exit_code == 0 and patch_generated:
        status = "validated"
        evidence.append("repair validation command exited zero")
        next_actions.append("review final diff and broaden validation before claims")
    elif test_exit_code == 0:
        status = "failed"
        warnings.append("repair validation passed but no patch was generated")
        next_actions.append("inspect saved run artifacts before claiming repair")
    else:
        status = "failed"
        warnings.append(f"repair validation exit code is {test_exit_code}")
        next_actions.append("inspect saved run artifacts before retrying or claiming repair")

    return IssueCorpusPublicRepairAttemptResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        repo_path=repo_path_value,
        repo_exists=repo_exists,
        repair_command=repair_command,
        validation_command=validation_command,
        reproduction_execution_status=reproduction_execution_status,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        dry_run=dry_run,
        run_id=run_id,
        run_status=run_status,
        report_path=report_path,
        trace_path=trace_path,
        final_diff_path=final_diff_path,
        test_exit_code=test_exit_code,
        patch_generated=patch_generated,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _first_manifest_repair_command(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    commands = _string_list(manifest.get("suggested_commands"))
    return commands[0] if commands else None


def _public_issue_repair_issue_text(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    issue_file = _optional_string(manifest.get("issue_file"))
    if issue_file:
        path = Path(issue_file)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    parts = [
        _optional_string(issue.get("title")),
        _optional_string(issue.get("task_type")),
        _optional_string(issue.get("selection_reason")),
    ]
    workflow = _string_list(issue.get("expected_workflow"))
    text = "\n".join(part for part in [*parts, *workflow] if part)
    return text or None


def _path_has_text(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _load_json_record_list(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError(f"{label} records must be JSON objects")
    return records


def _load_public_issue_reproduction_specs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"public issue reproduction specs do not exist: {path}")
    if not path.is_file():
        raise ValueError(f"public issue reproduction specs path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict) and isinstance(parsed.get("specs"), list):
        raw_records = parsed["specs"]
    elif isinstance(parsed, list):
        raw_records = parsed
    elif isinstance(parsed, dict):
        raw_records = []
        for task_id, record in parsed.items():
            if not isinstance(record, dict):
                raise ValueError(
                    "task-id keyed reproduction specs must map every task id to an object"
                )
            raw_records.append({**record, "task_id": task_id})
    else:
        raise ValueError("public issue reproduction specs must contain an object or list")

    specs: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            raise ValueError(f"reproduction spec #{index} must be a JSON object")
        task_id = _optional_string(raw_record.get("task_id"))
        if task_id is None:
            raise ValueError(f"reproduction spec #{index} is missing task_id")
        if task_id in specs:
            raise ValueError(f"duplicate reproduction spec for task_id: {task_id}")
        specs[task_id] = raw_record
    return specs


def _normalize_public_issue_fixture_files(
    value: Any,
) -> tuple[list[dict[str, str]], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["fixture_files must be a list"]

    fixture_files: list[dict[str, str]] = []
    errors: list[str] = []
    seen_paths: set[str] = set()
    for index, raw_fixture in enumerate(value, start=1):
        if not isinstance(raw_fixture, dict):
            errors.append(f"fixture_files[{index}] must be an object")
            continue
        raw_path = _optional_string(raw_fixture.get("path"))
        if raw_path is None or not raw_path.strip():
            errors.append(f"fixture_files[{index}].path is missing")
            continue
        path = Path(raw_path)
        normalized_path = path.as_posix()
        if path.is_absolute():
            errors.append(
                f"fixture_files[{index}].path must be repository-relative: {raw_path}"
            )
            continue
        if raw_path.endswith(("/", "\\")) or normalized_path in {"", "."}:
            errors.append(f"fixture_files[{index}].path must name a file: {raw_path}")
            continue
        if any(part in {"..", ""} for part in path.parts):
            errors.append(
                f"fixture_files[{index}].path cannot contain traversal: {raw_path}"
            )
            continue
        if any(part == ".git" for part in path.parts):
            errors.append(
                f"fixture_files[{index}].path cannot target Git metadata: {raw_path}"
            )
            continue
        if normalized_path in seen_paths:
            errors.append(f"fixture_files[{index}].path is duplicated: {normalized_path}")
            continue
        content = raw_fixture.get("content")
        if not isinstance(content, str):
            errors.append(f"fixture_files[{index}].content must be a string")
            continue
        content_size = len(content.encode("utf-8"))
        if content_size > PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES:
            errors.append(
                f"fixture_files[{index}].content exceeds "
                f"{PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES} bytes"
            )
            continue
        seen_paths.add(normalized_path)
        fixture_files.append({"path": normalized_path, "content": content})
    return fixture_files, errors


def _public_issue_fixture_paths(fixture_files: list[dict[str, str]]) -> list[str]:
    return [
        fixture["path"]
        for fixture in fixture_files
        if isinstance(fixture.get("path"), str) and fixture["path"]
    ]


def _write_public_issue_fixture_files(
    *,
    repo_path: Path,
    fixture_files: list[dict[str, str]],
) -> None:
    root = repo_path.resolve()
    for fixture in fixture_files:
        relative_path = Path(fixture["path"])
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError(
                f"fixture file escapes repository workspace: {fixture['path']}"
            ) from error
        if target.exists() and target.is_dir():
            raise IsADirectoryError(
                f"fixture file target is an existing directory: {fixture['path']}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fixture["content"], encoding="utf-8")


def _records_by_task_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = _optional_string(record.get("task_id"))
        if task_id:
            by_task[task_id] = record
    return by_task


def _load_public_issue_task_manifests(tasks_dir: Path | None) -> dict[str, dict[str, Any]]:
    if tasks_dir is None or not tasks_dir.exists() or not tasks_dir.is_dir():
        return {}
    manifests: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(tasks_dir.glob("*/task_manifest.json")):
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        task_id = _optional_string(parsed.get("task_id")) or manifest_path.parent.name
        manifests[task_id] = parsed
    return manifests


def _docker_smoke_status_from_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid"
    if not isinstance(parsed, dict):
        return "invalid"
    status = parsed.get("smoke_status")
    return status if isinstance(status, str) and status else "unknown"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _fixture_listing_command(focused_files: list[str]) -> str:
    if focused_files:
        return f"python3 -m pytest --fixtures {focused_files[0]}"
    return "python3 -m pytest --fixtures"


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


def _focused_test_log_text(*, stdout_path: str | None, stderr_path: str | None) -> str:
    parts: list[str] = []
    for path_value in [stdout_path, stderr_path]:
        if not path_value:
            continue
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _matching_lines(text: str, patterns: list[str], *, limit: int) -> list[str]:
    matches: list[str] = []
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered_line = stripped.lower()
        if any(pattern in lowered_line for pattern in lowered_patterns):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return matches


def _matched_expected_failure_signals(text: str, patterns: list[str]) -> list[str]:
    matched: list[str] = []
    lowered_text = text.lower()
    for pattern in patterns:
        if pattern.lower() in lowered_text:
            matched.append(pattern)
    return matched


def _candidate_failure_signals_from_logs(text: str, *, limit: int = 8) -> list[str]:
    exception_markers = (
        "assertionerror",
        "modulenotfounderror",
        "importerror",
        "nameerror",
        "typeerror",
        "valueerror",
        "no such file or directory",
    )
    matches: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if (
            lowered.startswith(("failed ", "error ", "e   ", "traceback"))
            or "error:" in lowered
            or any(marker in lowered for marker in exception_markers)
        ):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return _dedupe_preserve_order(matches)


def _last_nonempty_lines(text: str, *, limit: int) -> list[str]:
    lines = [line.strip()[:240] for line in text.splitlines() if line.strip()]
    return lines[-limit:]


def _issue_corpus_repositories(issues: list[Any]) -> list[tuple[str, str, int]]:
    repo_urls: dict[str, str] = {}
    issue_counts: dict[str, int] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        repository = issue.get("repository")
        repo_url = issue.get("repo_url")
        if not isinstance(repository, str) or not repository.strip():
            continue
        if not isinstance(repo_url, str) or not repo_url.strip():
            continue
        repository = repository.strip()
        repo_urls[repository] = repo_url.strip()
        issue_counts[repository] = issue_counts.get(repository, 0) + 1
    return [
        (repository, repo_urls[repository], issue_counts[repository])
        for repository in sorted(repo_urls)
    ]


def _preflight_issue_corpus_repository(
    *,
    repository: str,
    repo_url: str,
    issue_count: int,
    timeout_seconds: int,
) -> IssueCorpusRepoPreflightResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=None,
            head_sha=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(error),
            issue_count=issue_count,
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    default_branch, head_sha = _parse_ls_remote_head(completed.stdout)
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "git ls-remote failed"
        return IssueCorpusRepoPreflightResult(
            repository=repository,
            repo_url=repo_url,
            status="unreachable",
            default_branch=default_branch,
            head_sha=head_sha,
            latency_ms=latency_ms,
            error=error,
            issue_count=issue_count,
        )
    return IssueCorpusRepoPreflightResult(
        repository=repository,
        repo_url=repo_url,
        status="reachable",
        default_branch=default_branch,
        head_sha=head_sha,
        latency_ms=latency_ms,
        error=None,
        issue_count=issue_count,
    )


def _parse_ls_remote_head(output: str) -> tuple[str | None, str | None]:
    default_branch: str | None = None
    head_sha: str | None = None
    for line in output.splitlines():
        if line.startswith("ref:") and "\tHEAD" in line:
            ref = line.split()[1] if len(line.split()) >= 2 else ""
            prefix = "refs/heads/"
            default_branch = ref[len(prefix) :] if ref.startswith(prefix) else ref or None
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD":
            head_sha = parts[0]
    return default_branch, head_sha


def _issue_corpus_retriever(context_provider: str):
    if context_provider == "native":
        return KeywordRetriever()
    if context_provider == "native_hybrid":
        return HybridRetriever()
    if context_provider == "native_graph":
        return GraphRetriever()
    raise ValueError(f"unsupported issue-corpus context provider: {context_provider}")


def _issue_corpus_issue_text(issue: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in ("title", "task_type", "selection_reason"):
        value = issue.get(key)
        if isinstance(value, str):
            fields.append(value)
    workflow = issue.get("expected_workflow")
    if isinstance(workflow, list):
        fields.extend(item for item in workflow if isinstance(item, str))
    return "\n".join(fields)


def _source_free_context(context: RetrievedContext) -> dict[str, Any]:
    return {
        "path": context.path,
        "rank": context.rank,
        "score": context.score,
        "method": context.method,
        "matched_terms": context.matched_terms,
    }


def _issue_corpus_task_manifest(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
    corpus_id: str | None,
    task_dir: Path,
    issue_path: Path,
) -> dict[str, Any]:
    test_commands = _materialized_test_commands(preview)
    top_contexts = _source_free_preview_contexts(preview.get("top_contexts"))
    repo_ref = _optional_string(preview.get("repo_path")) or str(issue.get("repo_url", ""))
    manifest = {
        "task_manifest_version": 1,
        "task_id": str(issue.get("task_id", "unknown")),
        "source_corpus": corpus_id,
        "task_dir": str(task_dir),
        "issue_file": str(issue_path),
        "issue": {
            "source": issue.get("source"),
            "repository": issue.get("repository"),
            "repo_url": issue.get("repo_url"),
            "issue_url": issue.get("issue_url"),
            "issue_number": issue.get("issue_number"),
            "title": issue.get("title"),
            "language": issue.get("language"),
            "task_type": issue.get("task_type"),
            "state_at_capture": issue.get("state_at_capture"),
            "captured_at": issue.get("captured_at"),
            "selection_reason": issue.get("selection_reason"),
            "expected_workflow": _string_list(issue.get("expected_workflow")),
        },
        "repository_snapshot": {
            "repo_path": preview.get("repo_path"),
            "commit_hash": preview.get("commit_hash"),
            "branch": preview.get("branch"),
            "file_count": preview.get("file_count"),
            "language_summary": preview.get("language_summary") or {},
            "package_manager": preview.get("package_manager"),
            "test_commands": test_commands,
        },
        "retrieval_preview": {
            "context_provider": preview.get("context_provider"),
            "context_count": preview.get("context_count"),
            "retrieved_files": _string_list(preview.get("retrieved_files")),
            "top_contexts": top_contexts,
        },
        "suggested_commands": [
            (
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                f"--repo \"{repo_ref}\" "
                f"--issue-file \"{issue_path}\" "
                "--runtime langgraph "
                "--planner fake_model "
                "--context-provider native_hybrid "
                f"--test-command \"{test_commands[0]}\" "
                "--json"
            )
        ],
        "claim_boundary": [
            "This manifest prepares an external evaluation task.",
            "It does not prove issue reproduction, patch generation, or test success.",
            "It intentionally omits source excerpts and scraped issue body text.",
        ],
        "source_free": True,
    }
    manifest["source_free"] = _manifest_is_source_free(manifest)
    return manifest


def _render_materialized_issue(
    *,
    issue: dict[str, Any],
    preview: dict[str, Any],
) -> str:
    workflow = _string_list(issue.get("expected_workflow"))
    retrieved_files = _string_list(preview.get("retrieved_files"))
    lines = [
        f"# {issue.get('title') or issue.get('task_id') or 'Public Issue Task'}",
        "",
        f"- Task ID: `{issue.get('task_id', 'unknown')}`",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Repository URL: `{issue.get('repo_url', 'unknown')}`",
        f"- Captured state: `{issue.get('state_at_capture', 'unknown')}`",
        f"- Task type: `{issue.get('task_type', 'unknown')}`",
        f"- Context provider: `{preview.get('context_provider', 'unknown')}`",
        f"- Commit: `{preview.get('commit_hash') or 'unknown'}`",
        "",
        "## Expected Workflow",
        "",
    ]
    lines.extend(f"- {item}" for item in workflow)
    lines.extend(
        [
            "",
            "## Retrieved File Hints",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in retrieved_files)
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This file contains curated public issue metadata and retrieved-file hints.",
            "- It intentionally omits source excerpts and scraped issue body text.",
            "- It is not evidence that PatchSmith reproduced or repaired the issue.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_materialized_task_runbook(*, manifest: dict[str, Any]) -> str:
    issue = manifest.get("issue") if isinstance(manifest.get("issue"), dict) else {}
    snapshot = (
        manifest.get("repository_snapshot")
        if isinstance(manifest.get("repository_snapshot"), dict)
        else {}
    )
    retrieval = (
        manifest.get("retrieval_preview")
        if isinstance(manifest.get("retrieval_preview"), dict)
        else {}
    )
    commands = _string_list(manifest.get("suggested_commands"))
    lines = [
        f"# {manifest.get('task_id', 'Public Issue Task')} Runbook",
        "",
        "## Inputs",
        "",
        f"- Repository: `{issue.get('repository', 'unknown')}`",
        f"- Issue: `{issue.get('issue_url', 'unknown')}`",
        f"- Local repository snapshot: `{snapshot.get('repo_path') or 'unknown'}`",
        f"- Commit: `{snapshot.get('commit_hash') or 'unknown'}`",
        f"- Context provider: `{retrieval.get('context_provider') or 'unknown'}`",
        f"- Retrieved files: `{', '.join(_string_list(retrieval.get('retrieved_files'))) or 'none'}`",
        "",
        "## Suggested Commands",
        "",
    ]
    for command in commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(
        [
            "## Claim Boundary",
            "",
            "- Run this task only after confirming dependency and sandbox expectations.",
            "- A generated manifest is setup evidence, not solved-run evidence.",
            "- Save normal PatchSmith run artifacts before making repair-quality claims.",
            "",
        ]
    )
    return "\n".join(lines)


def _materialized_test_commands(preview: dict[str, Any]) -> list[str]:
    commands = _string_list(preview.get("test_commands"))
    return commands or ["python3 -m pytest"]


def _materialized_run_risk(
    *,
    file_count: int | None,
    test_commands: list[str],
    package_manager: str | None,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    level = "low"
    if file_count is None:
        notes.append("repository size is unknown")
        level = "medium"
    elif file_count >= 500:
        notes.append(f"large repository snapshot with {file_count} indexed files")
        level = "high"
    elif file_count >= 100:
        notes.append(f"medium repository snapshot with {file_count} indexed files")
        level = "medium"

    full_suite_commands = [
        command
        for command in test_commands
        if command.strip() in {"pytest", "python -m pytest", "python3 -m pytest"}
    ]
    if full_suite_commands:
        notes.append("suggested test command runs the full pytest suite")
        if level == "low":
            level = "medium"
    if package_manager is None:
        notes.append("package manager detection is unavailable")
        if level == "low":
            level = "medium"
    return level, notes


def _source_free_preview_contexts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    contexts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        contexts.append(
            {
                "path": item.get("path"),
                "rank": item.get("rank"),
                "score": item.get("score"),
                "method": item.get("method"),
                "matched_terms": _string_list(item.get("matched_terms")),
            }
        )
    return contexts


def _manifest_is_source_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            key != "excerpt" and _manifest_is_source_free(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return all(_manifest_is_source_free(item) for item in value)
    return True


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _markdown_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:500]


def _supplement_context_preview_source_neighbors(
    *,
    contexts: list[RetrievedContext],
    repo_index: Any,
    top_k: int,
    context_provider: str,
) -> list[RetrievedContext]:
    if top_k <= 0 or not contexts:
        return []
    existing_paths = {context.path for context in contexts}
    source_paths = {
        file.path
        for file in repo_index.files
        if isinstance(getattr(file, "path", None), str)
        and not _is_issue_corpus_test_path(file.path)
    }
    supplements: list[RetrievedContext] = []
    for context in contexts:
        if not _is_issue_corpus_test_path(context.path):
            continue
        for candidate in _source_neighbor_candidates(context.path, source_paths):
            if candidate in existing_paths:
                continue
            existing_paths.add(candidate)
            supplements.append(
                RetrievedContext(
                    path=candidate,
                    rank=0,
                    score=max(context.score - 0.001, 0.0),
                    method=f"{context_provider}_source_neighbor",
                    matched_terms=["source_neighbor", f"test:{context.path}"],
                    excerpt="",
                )
            )
            break
    if not supplements:
        return _rerank_contexts(contexts)

    if len(contexts) + len(supplements) <= top_k:
        return _rerank_contexts([*contexts, *supplements])

    non_test_contexts = [
        context for context in contexts if not _is_issue_corpus_test_path(context.path)
    ]
    if not non_test_contexts:
        kept_originals = contexts[: max(top_k - len(supplements), 0)]
        return _rerank_contexts([*kept_originals, *supplements[:top_k]])[:top_k]
    return _rerank_contexts(contexts[:top_k])


def _source_neighbor_candidates(test_path: str, source_paths: set[str]) -> list[str]:
    path = Path(test_path)
    name = path.name
    stem = path.stem
    normalized_stem = stem
    if normalized_stem.startswith("test_"):
        normalized_stem = normalized_stem[len("test_") :]
    if normalized_stem.endswith("_test"):
        normalized_stem = normalized_stem[: -len("_test")]

    stripped_parts = [
        part
        for part in path.parts
        if part not in {"tests", "test", "unit", "integration"}
    ]
    if stripped_parts:
        stripped_parts[-1] = f"{normalized_stem}{path.suffix}"
    relative_guess = Path(*stripped_parts) if stripped_parts else Path(f"{normalized_stem}.py")

    candidates = [
        f"src/{relative_guess.as_posix()}",
        f"lib/{relative_guess.as_posix()}",
        relative_guess.as_posix(),
        f"src/{normalized_stem}{path.suffix}",
        f"lib/{normalized_stem}{path.suffix}",
        f"{normalized_stem}{path.suffix}",
    ]
    candidates.extend(
        sorted(
            source_path
            for source_path in source_paths
            if Path(source_path).stem == normalized_stem
        )
    )
    deduped: list[str] = []
    for candidate in candidates:
        if candidate in source_paths and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _is_issue_corpus_test_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _is_materialized_test_candidate_path(path: str) -> bool:
    path_obj = Path(path)
    parts = path_obj.parts
    name = path_obj.name
    return (
        bool(parts)
        and parts[0] in {"tests", "test", "testing"}
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _rerank_contexts(contexts: list[RetrievedContext]) -> list[RetrievedContext]:
    return [replace(context, rank=index + 1) for index, context in enumerate(contexts)]


def _safe_artifact_name(value: str) -> str:
    sanitized = "".join(character if character.isalnum() else "_" for character in value)
    sanitized = "_".join(part for part in sanitized.split("_") if part)
    return sanitized or "unknown"


def _remove_artifact_dir(*, root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError(f"refusing to remove path outside artifact root: {target}") from error
    if target == root:
        raise ValueError("refusing to remove artifact root")
    shutil.rmtree(target)


def _required_entry_string(entry: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"entry missing non-empty string field: {key}")
        return None
    return value.strip()


def _entry_string_list(entry: dict[str, Any], key: str, errors: list[str]) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"entry missing non-empty string list field: {key}")
        return []
    results: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"entry field {key}[{index}] must be a non-empty string")
            continue
        results.append(item.strip())
    return results


def _expected_string(expected: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = expected.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"expected.json missing non-empty string field: {key}")
        return None
    return value.strip()


def _expected_string_list(
    expected: dict[str, Any],
    key: str,
    errors: list[str],
) -> list[str]:
    value = expected.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"expected.json missing non-empty string list field: {key}")
        return []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"expected.json field {key}[{index}] must be a non-empty string")
            continue
        paths.append(item.strip())
    return paths


def _manifest_string(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    field_name: str | None = None,
) -> str | None:
    value = manifest.get(key)
    name = field_name or key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return None
    return value.strip()


def _manifest_object(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _validate_expected_repo_file(
    repo_path: Path,
    relative_path: str,
    field_name: str,
    errors: list[str],
) -> None:
    if relative_path.startswith("/") or relative_path.startswith("../") or "/../" in relative_path:
        errors.append(f"{field_name} contains unsafe path: {relative_path}")
        return
    target = (repo_path / relative_path).resolve()
    try:
        target.relative_to(repo_path.resolve())
    except ValueError:
        errors.append(f"{field_name} escapes repo: {relative_path}")
        return
    if not target.is_file():
        errors.append(f"{field_name} path does not exist: {relative_path}")


def _duplicate_task_ids(results: list[SeededTaskValidationResult]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


def _duplicate_materialized_task_ids(
    results: list[IssueCorpusMaterializedTaskValidationResult],
) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


def _duplicate_issue_corpus_task_ids(
    results: list[IssueCorpusEntryValidationResult],
) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


def _with_validation_error(
    result: SeededTaskValidationResult,
    error: str,
) -> SeededTaskValidationResult:
    return SeededTaskValidationResult(
        task_dir=result.task_dir,
        task_id=result.task_id,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        issue_path=result.issue_path,
        repo_path=result.repo_path,
        expected_path=result.expected_path,
        expected_touched_files=result.expected_touched_files,
        expected_related_tests=result.expected_related_tests,
    )


def _with_materialized_validation_error(
    result: IssueCorpusMaterializedTaskValidationResult,
    error: str,
) -> IssueCorpusMaterializedTaskValidationResult:
    return IssueCorpusMaterializedTaskValidationResult(
        task_id=result.task_id,
        task_dir=result.task_dir,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        manifest_path=result.manifest_path,
        issue_path=result.issue_path,
        runbook_path=result.runbook_path,
        repository=result.repository,
        issue_url=result.issue_url,
        repo_path=result.repo_path,
        retrieved_files=result.retrieved_files,
        suggested_commands=result.suggested_commands,
        source_free=result.source_free,
    )


def _with_issue_corpus_error(
    result: IssueCorpusEntryValidationResult,
    error: str,
) -> IssueCorpusEntryValidationResult:
    return IssueCorpusEntryValidationResult(
        task_id=result.task_id,
        repository=result.repository,
        issue_url=result.issue_url,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        language=result.language,
        task_type=result.task_type,
        state_at_capture=result.state_at_capture,
        expected_workflow=result.expected_workflow,
    )


def _model_usage_from_trace(trace_path: Path) -> dict[str, Any]:
    providers: list[str] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    total_tokens: list[int] = []
    estimated_costs: list[float] = []

    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event, dict) else None
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            continue
        model_call = metadata.get("model_call")
        if not isinstance(model_call, dict):
            continue
        provider = model_call.get("provider")
        if isinstance(provider, str) and provider not in providers:
            providers.append(provider)
        _append_int(input_tokens, model_call.get("input_tokens"))
        _append_int(output_tokens, model_call.get("output_tokens"))
        _append_int(total_tokens, model_call.get("total_tokens"))
        _append_float(estimated_costs, model_call.get("estimated_cost_usd"))

    return {
        "model_provider": ",".join(providers) if providers else None,
        "input_tokens": sum(input_tokens) if input_tokens else None,
        "output_tokens": sum(output_tokens) if output_tokens else None,
        "total_tokens": sum(total_tokens) if total_tokens else None,
        "estimated_cost_usd": sum(estimated_costs) if estimated_costs else None,
    }


def _trace_metrics_from_trace(trace_path: Path) -> dict[str, Any]:
    events = _trace_events(trace_path)
    node_names = {
        str(event.get("node_name"))
        for event in events
        if isinstance(event.get("node_name"), str)
    }
    event_types = {
        str(event.get("event_type"))
        for event in events
        if isinstance(event.get("event_type"), str)
    }
    runtime_node_count = sum(
        1 for event in events if str(event.get("node_name", "")).startswith("runtime.")
    )
    failed_event_count = sum(
        1
        for event in events
        if str(event.get("status", "")).lower() in {"failed", "error"}
        or event.get("error") is not None
    )
    retry_event_count = sum(
        1
        for event in events
        if str(event.get("node_name", "")) == "runtime.retry"
        or str(event.get("event_type", "")) == "retry"
    )
    debuggability_score = 0.0
    if events:
        debuggability_score += 1.0
    if "retrieve" in node_names or "context_broker" in node_names:
        debuggability_score += 1.0
    if runtime_node_count:
        debuggability_score += 1.0
    if "test" in node_names:
        debuggability_score += 1.0
    if "repair_outcome" in event_types:
        debuggability_score += 1.0

    return {
        "trace_event_count": len(events),
        "runtime_node_count": runtime_node_count,
        "failed_trace_event_count": failed_event_count,
        "retry_event_count": retry_event_count,
        "debuggability_score": debuggability_score,
    }


def _trace_events(trace_path: Path) -> list[dict[str, Any]]:
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _scaffold_variant(name: str) -> ScaffoldVariant:
    try:
        return SCAFFOLD_VARIANTS[name]
    except KeyError as error:
        supported = ", ".join(sorted(SCAFFOLD_VARIANTS))
        raise ValueError(f"unsupported scaffold variant: {name}; supported: {supported}") from error


def _append_int(values: list[int], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        values.append(value)


def _append_float(values: list[float], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        values.append(float(value))


def _sum_optional(values: Any) -> int | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return sum(values_list)


def _sum_optional_float(values: Any) -> float | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return float(sum(values_list))


def _format_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "$0.00"
    return f"${value:.6f}"


def _average(values: Any) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)
