"""Benchmark evaluation dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
    patch_quality_severity: str | None = None
    patch_quality_warning: bool = False
    trace_event_count: int = 0
    runtime_node_count: int = 0
    failed_trace_event_count: int = 0
    retry_event_count: int = 0
    retry_labels: tuple[str, ...] = ()
    retry_label_counts: dict[str, int] = field(default_factory=dict)
    debuggability_score: float = 0.0
    agent_trajectory_score: float = 0.0
    todo_planning: bool = False
    constrained_filesystem: bool = False
    specialist_review: bool = False
    guardrails: bool = False
    structured_output: bool = False
    retry_feedback: bool = False
    patch_diagnostics: bool = False
    contextual_verifier: bool = False
    process_quality_label: str = "unscored"
    process_quality_score: float = 0.0
    process_quality_flags: tuple[str, ...] = ()
    model_provider: str | None = None
    response_count: int | None = None
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
    retry_label_counts: dict[str, int] = field(default_factory=dict)
    patch_quality_warning_rate: float = 0.0
    avg_debuggability_score: float = 0.0
    avg_agent_trajectory_score: float = 0.0
    todo_planning_rate: float = 0.0
    constrained_filesystem_rate: float = 0.0
    specialist_review_rate: float = 0.0
    guardrails_rate: float = 0.0
    structured_output_rate: float = 0.0
    retry_feedback_rate: float = 0.0
    patch_diagnostics_rate: float = 0.0
    contextual_verifier_rate: float = 0.0
    model_provider: str | None = None
    response_count: int | None = None
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
    retry_label_counts: dict[str, int]
    avg_debuggability_score: float
    avg_agent_trajectory_score: float
    todo_planning_rate: float
    constrained_filesystem_rate: float
    specialist_review_rate: float
    guardrails_rate: float
    structured_output_rate: float
    retry_feedback_rate: float
    patch_diagnostics_rate: float
    contextual_verifier_rate: float
    model_provider: str | None
    response_count: int | None
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
    "deepagents": ScaffoldVariant("deepagents", "deepagents", "heuristic"),
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


@dataclass(frozen=True)
class ComplexBenchmarkResult:
    task_id: str
    repository: str | None
    issue_url: str | None
    status: str
    strict_status: str
    runtime: str
    planner: str
    context_provider: str
    reproduced: bool
    patch_generated: bool
    validation_passed: bool
    test_exit_code: int | None
    trace_path: str | None
    report_path: str | None
    progress_score: float = 0.0
    progress_stage: str = "not_started"
    failure_class: str = "unknown"
    harness_layer: str = "unknown"
    patch_quality_severity: str | None = None
    patch_quality_warning: bool = False
    patch_quality_codes: tuple[str, ...] = ()
    patch_target_paths: tuple[str, ...] = ()
    localized_target_paths: tuple[str, ...] = ()
    target_alignment_status: str = "unavailable"
    patch_target_aligned: bool | None = None
    retry_feedback_artifacts: tuple[str, ...] = ()
    retry_feedback_artifact_count: int = 0
    retry_labels: tuple[str, ...] = ()
    retry_label_counts: dict[str, int] = field(default_factory=dict)
    retry_failure_classes: tuple[str, ...] = ()
    retry_failure_class_counts: dict[str, int] = field(default_factory=dict)
    deepagents_virtual_file_count: int | None = None
    deepagents_virtual_file_paths: tuple[str, ...] = ()
    deepagents_max_context_files: int | None = None
    deepagents_context_budgeted: bool = False
    deepagents_context_budget_manifest_path: str | None = None
    deepagents_context_budget_manifest_read_first: bool = False
    deepagents_context_budget_omitted_file_count: int | None = None
    deepagents_context_budget_omitted_paths: tuple[str, ...] = ()
    deepagents_repo_map_manifest_path: str | None = None
    deepagents_repo_map_manifest_read_first: bool = False
    deepagents_repo_instructions_manifest_path: str | None = None
    deepagents_repo_instructions_manifest_read_first: bool = False
    deepagents_acceptance_rubric_manifest_path: str | None = None
    deepagents_acceptance_rubric_manifest_read_first: bool = False
    deepagents_acceptance_rubric_aligned: bool | None = None
    deepagents_repair_interface_manifest_path: str | None = None
    deepagents_repair_interface_manifest_read_first: bool = False
    deepagents_resource_budgeted: bool = False
    deepagents_resource_budget_read_first: bool = False
    deepagents_resource_budget_max_model_responses: int | None = None
    deepagents_resource_budget_max_model_tokens: int | None = None
    trace_event_count: int = 0
    runtime_node_count: int = 0
    failed_trace_event_count: int = 0
    retry_event_count: int = 0
    debuggability_score: float = 0.0
    agent_trajectory_score: float = 0.0
    todo_planning: bool = False
    constrained_filesystem: bool = False
    specialist_review: bool = False
    guardrails: bool = False
    structured_output: bool = False
    retry_feedback: bool = False
    patch_diagnostics: bool = False
    contextual_verifier: bool = False
    process_quality_label: str = "unscored"
    process_quality_score: float = 0.0
    process_quality_flags: tuple[str, ...] = ()
    model_provider: str | None = None
    response_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    live_cost_budget_usd: float | None = None
    live_cost_budget_overage: bool = False
    live_cost_budget_overage_usd: float | None = None
    attempt_index: int = 1
    attempt_count: int = 1
    preflight_status: str = "not_applicable"
    preflight_gates: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexBenchmarkSelection:
    task_id: str
    selected_attempt_index: int
    selected_attempt_count: int
    status: str
    strict_status: str
    validation_passed: bool
    patch_quality_severity: str | None
    patch_quality_codes: tuple[str, ...]
    retry_event_count: int
    response_count: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    agent_trajectory_score: float
    report_path: str | None
    selection_reason: str
    progress_score: float = 0.0
    progress_stage: str = "not_started"
    failure_class: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexBenchmarkFollowupCandidate:
    task_id: str
    attempt_index: int
    attempt_count: int
    action: str
    suggested_profile: str
    recommended_command: tuple[str, ...]
    recommended_env: dict[str, str]
    validation_command: tuple[str, ...]
    success_criteria: tuple[str, ...]
    status: str
    strict_status: str
    failure_class: str
    harness_layer: str
    process_quality_label: str
    priority: int
    reasons: tuple[str, ...]
    retry_failure_classes: tuple[str, ...]
    response_count: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    report_path: str | None
    trace_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexBenchmarkSummary:
    benchmark: str
    attempt_dir: str
    task_count: int
    attempted_tasks: int
    reproduced_tasks: int
    validated_tasks: int
    failed_tasks: int
    blocked_tasks: int
    preflight_passed_tasks: int
    preflight_skipped_tasks: int
    preflight_blocked_tasks: int
    sandbox_preflight_blocked_tasks: int
    model_preflight_blocked_tasks: int
    budget_preflight_blocked_tasks: int
    patch_generated_rate: float
    validation_rate: float
    reproduced_input_rate: float
    avg_trace_events: float
    avg_runtime_nodes: float
    failed_trace_event_count: int
    avg_retry_events: float
    retry_feedback_artifact_tasks: int
    retry_feedback_artifact_count: int
    retry_label_counts: dict[str, int]
    retry_failure_class_counts: dict[str, int]
    avg_deepagents_virtual_file_count: float
    context_budgeted_tasks: int
    context_budget_manifest_tasks: int
    context_budget_omitted_file_count: int
    avg_context_budget_omitted_files: float
    repo_map_manifest_tasks: int
    repo_instructions_manifest_tasks: int
    repo_instructions_read_first_rate: float
    acceptance_rubric_manifest_tasks: int
    acceptance_rubric_read_first_rate: float
    acceptance_rubric_aligned_tasks: int
    acceptance_rubric_alignment_rate: float
    repair_interface_manifest_tasks: int
    repair_interface_read_first_rate: float
    avg_deepagents_max_context_files: float
    resource_budgeted_tasks: int
    resource_budget_read_first_rate: float
    avg_resource_budget_max_model_responses: float
    avg_resource_budget_max_model_tokens: float
    quality_warning_tasks: int
    quality_warning_rate: float
    target_alignment_available_tasks: int
    target_aligned_tasks: int
    target_misaligned_tasks: int
    target_alignment_rate: float
    avg_debuggability_score: float
    avg_agent_trajectory_score: float
    todo_planning_rate: float
    constrained_filesystem_rate: float
    specialist_review_rate: float
    guardrails_rate: float
    structured_output_rate: float
    retry_feedback_rate: float
    patch_diagnostics_rate: float
    contextual_verifier_rate: float
    avg_process_quality_score: float
    process_quality_label_counts: dict[str, int]
    process_quality_flag_counts: dict[str, int]
    process_risky_validated_tasks: int
    live_provider_tasks: int
    live_cost_budgeted_tasks: int = 0
    live_cost_budget_overage_tasks: int = 0
    max_live_cost_budget_overage_usd: float | None = None
    model_provider: str | None = None
    response_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    attempted_cost_per_validated_task_usd: float | None = None
    attempted_tokens_per_validated_task: float | None = None
    attempted_responses_per_validated_task: float | None = None
    max_attempted_task_cost_usd: float | None = None
    max_attempted_task_tokens: int | None = None
    max_attempted_task_responses: int | None = None
    repeat_count: int = 1
    unique_task_count: int = 0
    unique_attempted_tasks: int = 0
    tasks_with_validated_attempt: int = 0
    tasks_with_failed_attempts_only: int = 0
    validated_task_pass_at_n_rate: float = 0.0
    selected_attempt_count: int = 0
    selected_validated_tasks: int = 0
    selected_validation_rate: float = 0.0
    selected_total_tokens: int | None = None
    selected_response_count: int | None = None
    selected_estimated_cost_usd: float | None = None
    selected_virtual_file_count: int | None = None
    selected_virtual_files_per_validated_task: float | None = None
    selected_tokens_per_virtual_file: float | None = None
    selected_responses_per_virtual_file: float | None = None
    selected_context_target_available_tasks: int = 0
    selected_context_target_covered_tasks: int = 0
    selected_context_target_recall: float | None = None
    selected_context_target_precision: float | None = None
    selected_cost_per_validated_task_usd: float | None = None
    selected_tokens_per_validated_task: float | None = None
    selected_responses_per_validated_task: float | None = None
    max_selected_task_cost_usd: float | None = None
    max_selected_task_tokens: int | None = None
    max_selected_task_responses: int | None = None
    partial_progress_tasks: int = 0
    avg_progress_score: float = 0.0
    selected_avg_progress_score: float = 0.0
    failure_class_counts: dict[str, int] = field(default_factory=dict)
    selected_failure_class_counts: dict[str, int] = field(default_factory=dict)
    harness_layer_counts: dict[str, int] = field(default_factory=dict)
    selected_harness_layer_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
