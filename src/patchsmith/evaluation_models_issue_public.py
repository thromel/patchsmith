"""Public issue reproduction and repair dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
    model_call_count: int | None = None
    model_response_count: int | None = None
    model_input_tokens: int | None = None
    model_output_tokens: int | None = None
    model_total_tokens: int | None = None
    estimated_model_cost_usd: float | None = None
    attempt_index: int = 1
    attempt_count: int = 1
    preflight_status: str = "not_applicable"
    preflight_gates: list[dict[str, str]] = field(default_factory=list)

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
    stop_on_validated: bool
    dry_run_tasks: int
    attempted_tasks: int
    validated_tasks: int
    failed_tasks: int
    blocked_tasks: int
    warning_tasks: int
    reproduced_input_tasks: int
    deepagents_max_context_files: int | None = None
    repeat_count: int = 1
    unique_task_count: int = 0
    tasks_with_validated_attempt: int = 0
    tasks_with_failed_attempts_only: int = 0
    validated_task_pass_at_n_rate: float = 0.0
    model_call_count: int | None = None
    model_response_count: int | None = None
    model_total_tokens: int | None = None
    estimated_model_cost_usd: float | None = None
    max_actual_model_responses: int | None = None
    max_actual_model_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
