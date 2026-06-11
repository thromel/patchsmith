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
    source_hints: list[str]
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
    source_hints: list[str]
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
    fixture_files: list[dict[str, str]]
    fixture_paths: list[str]
    source_hints: list[str]
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
    validation_fixture_files: list[dict[str, str]]
    validation_fixture_paths: list[str]
    validation_source_hints: list[str]
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
    validation_fixture_paths: list[str]
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
    max_retries: int
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
