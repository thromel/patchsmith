"""Data models for complex benchmark suite configuration and gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from patchsmith.evaluation.complex.thresholds import (
    complex_threshold_count,
    complex_threshold_kwargs_from_object,
)
from patchsmith.evaluation_models import ComplexBenchmarkSummary


@dataclass(frozen=True)
class ComplexBenchmarkSuiteGate:
    status: str
    failures: tuple[str, ...] = ()
    min_validation_rate: float | None = None
    min_live_provider_tasks: int | None = None
    min_unique_tasks: int | None = None
    max_attempted_cost_per_validated_task_usd: float | None = None
    max_attempted_tokens_per_validated_task: float | None = None
    max_attempted_responses_per_validated_task: float | None = None
    max_attempted_task_cost_usd: float | None = None
    max_attempted_task_tokens: int | None = None
    max_attempted_task_responses: int | None = None
    max_selected_cost_per_validated_task_usd: float | None = None
    max_selected_tokens_per_validated_task: float | None = None
    max_selected_responses_per_validated_task: float | None = None
    max_selected_virtual_files_per_validated_task: float | None = None
    max_selected_tokens_per_virtual_file: float | None = None
    max_selected_responses_per_virtual_file: float | None = None
    min_selected_progress_score: float | None = None
    min_selected_context_target_recall: float | None = None
    min_selected_context_target_precision: float | None = None
    max_selected_task_cost_usd: float | None = None
    max_selected_task_tokens: int | None = None
    max_selected_task_responses: int | None = None
    max_live_cost_budget_overage_tasks: int | None = None
    min_agent_trajectory_score: float | None = None
    min_contextual_verifier_rate: float | None = None
    min_process_quality_score: float | None = None
    max_process_risky_validated_tasks: int | None = None
    min_target_alignment_rate: float | None = None
    min_repo_instructions_manifest_rate: float | None = None
    min_repo_instructions_read_first_rate: float | None = None
    min_acceptance_rubric_manifest_rate: float | None = None
    min_acceptance_rubric_read_first_rate: float | None = None
    min_acceptance_rubric_alignment_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexBenchmarkSuiteThresholds:
    min_validation_rate: float | None = None
    min_live_provider_tasks: int | None = None
    min_unique_tasks: int | None = None
    max_attempted_cost_per_validated_task_usd: float | None = None
    max_attempted_tokens_per_validated_task: float | None = None
    max_attempted_responses_per_validated_task: float | None = None
    max_attempted_task_cost_usd: float | None = None
    max_attempted_task_tokens: int | None = None
    max_attempted_task_responses: int | None = None
    max_selected_cost_per_validated_task_usd: float | None = None
    max_selected_tokens_per_validated_task: float | None = None
    max_selected_responses_per_validated_task: float | None = None
    max_selected_virtual_files_per_validated_task: float | None = None
    max_selected_tokens_per_virtual_file: float | None = None
    max_selected_responses_per_virtual_file: float | None = None
    min_selected_progress_score: float | None = None
    min_selected_context_target_recall: float | None = None
    min_selected_context_target_precision: float | None = None
    max_selected_task_cost_usd: float | None = None
    max_selected_task_tokens: int | None = None
    max_selected_task_responses: int | None = None
    max_live_cost_budget_overage_tasks: int | None = None
    min_agent_trajectory_score: float | None = None
    min_contextual_verifier_rate: float | None = None
    min_process_quality_score: float | None = None
    max_process_risky_validated_tasks: int | None = None
    min_target_alignment_rate: float | None = None
    min_repo_instructions_manifest_rate: float | None = None
    min_repo_instructions_read_first_rate: float | None = None
    min_acceptance_rubric_manifest_rate: float | None = None
    min_acceptance_rubric_read_first_rate: float | None = None
    min_acceptance_rubric_alignment_rate: float | None = None

    @property
    def count(self) -> int:
        return complex_threshold_count(self)

    def gate(self, summary: ComplexBenchmarkSummary) -> ComplexBenchmarkSuiteGate:
        from patchsmith.evaluation.complex.gates import (
            complex_benchmark_suite_gate,
        )

        return complex_benchmark_suite_gate(
            summary,
            **complex_threshold_kwargs_from_object(self),
        )


@dataclass(frozen=True)
class ComplexBenchmarkSuiteSpec:
    benchmark: str
    attempt_dirs: tuple[Path, ...]
    output_dir: Path | None = None
    min_validation_rate: float | None = None
    min_live_provider_tasks: int | None = None
    min_unique_tasks: int | None = None
    max_attempted_cost_per_validated_task_usd: float | None = None
    max_attempted_tokens_per_validated_task: float | None = None
    max_attempted_responses_per_validated_task: float | None = None
    max_attempted_task_cost_usd: float | None = None
    max_attempted_task_tokens: int | None = None
    max_attempted_task_responses: int | None = None
    max_selected_cost_per_validated_task_usd: float | None = None
    max_selected_tokens_per_validated_task: float | None = None
    max_selected_responses_per_validated_task: float | None = None
    max_selected_virtual_files_per_validated_task: float | None = None
    max_selected_tokens_per_virtual_file: float | None = None
    max_selected_responses_per_virtual_file: float | None = None
    min_selected_progress_score: float | None = None
    min_selected_context_target_recall: float | None = None
    min_selected_context_target_precision: float | None = None
    max_selected_task_cost_usd: float | None = None
    max_selected_task_tokens: int | None = None
    max_selected_task_responses: int | None = None
    max_live_cost_budget_overage_tasks: int | None = None
    min_agent_trajectory_score: float | None = None
    min_contextual_verifier_rate: float | None = None
    min_process_quality_score: float | None = None
    max_process_risky_validated_tasks: int | None = None
    min_target_alignment_rate: float | None = None
    min_repo_instructions_manifest_rate: float | None = None
    min_repo_instructions_read_first_rate: float | None = None
    min_acceptance_rubric_manifest_rate: float | None = None
    min_acceptance_rubric_read_first_rate: float | None = None
    min_acceptance_rubric_alignment_rate: float | None = None

    @property
    def thresholds(self) -> ComplexBenchmarkSuiteThresholds:
        return ComplexBenchmarkSuiteThresholds(
            **complex_threshold_kwargs_from_object(self)
        )


@dataclass(frozen=True)
class ComplexBenchmarkSuiteConfig:
    benchmark: str
    attempt_dirs: tuple[Path, ...]
    output_dir: Path
    thresholds: ComplexBenchmarkSuiteThresholds
    gate_requested: bool


@dataclass(frozen=True)
class ComplexBenchmarkSuitePreflight:
    status: str
    benchmark: str
    attempt_dir_count: int
    result_file_count: int
    output_dir: str
    gate_threshold_count: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_attempt_dirs: tuple[str, ...] = ()
    missing_result_files: tuple[str, ...] = ()
    duplicate_attempt_dirs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
