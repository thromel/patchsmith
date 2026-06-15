"""Threshold registry for complex benchmark suites."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

ComplexThresholdKind = Literal["rate", "nonnegative_float", "nonnegative_int"]


@dataclass(frozen=True)
class ComplexBenchmarkThreshold:
    name: str
    value_kind: ComplexThresholdKind
    cli_help: str

    @property
    def cli_flag(self) -> str:
        return "--" + self.name.replace("_", "-")


COMPLEX_BENCHMARK_SUITE_THRESHOLDS: tuple[ComplexBenchmarkThreshold, ...] = (
    ComplexBenchmarkThreshold(
        name="min_validation_rate",
        value_kind="rate",
        cli_help="Fail when aggregate validation rate is below this threshold.",
    ),
    ComplexBenchmarkThreshold(
        name="min_live_provider_tasks",
        value_kind="nonnegative_int",
        cli_help=(
            "Fail when fewer than this many attempted rows contain live-provider "
            "metadata."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_unique_tasks",
        value_kind="nonnegative_int",
        cli_help="Fail when fewer than this many unique task IDs are represented.",
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_cost_per_validated_task_usd",
        value_kind="nonnegative_float",
        cli_help="Fail when attempted cost per validated task exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_tokens_per_validated_task",
        value_kind="nonnegative_float",
        cli_help="Fail when attempted tokens per validated task exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_responses_per_validated_task",
        value_kind="nonnegative_float",
        cli_help=(
            "Fail when attempted model responses per validated task exceeds this cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_task_cost_usd",
        value_kind="nonnegative_float",
        cli_help="Fail when any attempted task cost exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_task_tokens",
        value_kind="nonnegative_int",
        cli_help="Fail when any attempted task token count exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_attempted_task_responses",
        value_kind="nonnegative_int",
        cli_help="Fail when any attempted task response count exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_cost_per_validated_task_usd",
        value_kind="nonnegative_float",
        cli_help="Fail when selected cost per validated task exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_tokens_per_validated_task",
        value_kind="nonnegative_float",
        cli_help="Fail when selected tokens per validated task exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_responses_per_validated_task",
        value_kind="nonnegative_float",
        cli_help=(
            "Fail when selected model responses per validated task exceeds this cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_virtual_files_per_validated_task",
        value_kind="nonnegative_float",
        cli_help=(
            "Fail when selected DeepAgents virtual files per validated task exceeds "
            "this cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_tokens_per_virtual_file",
        value_kind="nonnegative_float",
        cli_help=(
            "Fail when selected model tokens per DeepAgents virtual file exceeds "
            "this cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_responses_per_virtual_file",
        value_kind="nonnegative_float",
        cli_help=(
            "Fail when selected model responses per DeepAgents virtual file exceeds "
            "this cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_selected_progress_score",
        value_kind="rate",
        cli_help=(
            "Fail when selected-attempt partial progress score is below this "
            "threshold."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_selected_context_target_recall",
        value_kind="rate",
        cli_help="Fail when selected context-target recall is below this rate.",
    ),
    ComplexBenchmarkThreshold(
        name="min_selected_context_target_precision",
        value_kind="rate",
        cli_help="Fail when selected context-target precision is below this rate.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_task_cost_usd",
        value_kind="nonnegative_float",
        cli_help="Fail when any selected task cost exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_task_tokens",
        value_kind="nonnegative_int",
        cli_help="Fail when any selected task token count exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_selected_task_responses",
        value_kind="nonnegative_int",
        cli_help="Fail when any selected task response count exceeds this cap.",
    ),
    ComplexBenchmarkThreshold(
        name="max_live_cost_budget_overage_tasks",
        value_kind="nonnegative_int",
        cli_help=(
            "Fail when more than this many attempted rows exceed their configured "
            "live cost budget cap."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_agent_trajectory_score",
        value_kind="rate",
        cli_help="Fail when average agent trajectory score is below this threshold.",
    ),
    ComplexBenchmarkThreshold(
        name="min_contextual_verifier_rate",
        value_kind="rate",
        cli_help=(
            "Fail when contextual-verifier trajectory coverage is below this rate."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_process_quality_score",
        value_kind="rate",
        cli_help=(
            "Fail when average trace-derived process quality is below this threshold."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="max_process_risky_validated_tasks",
        value_kind="nonnegative_int",
        cli_help="Fail when more than this many validated tasks are process-risky.",
    ),
    ComplexBenchmarkThreshold(
        name="min_target_alignment_rate",
        value_kind="rate",
        cli_help="Fail when target-aligned patch rate is below this threshold.",
    ),
    ComplexBenchmarkThreshold(
        name="min_repo_instructions_manifest_rate",
        value_kind="rate",
        cli_help=(
            "Fail when scoped repo-instructions manifest coverage is below this rate."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_repo_instructions_read_first_rate",
        value_kind="rate",
        cli_help=(
            "Fail when scoped repo-instructions read-first rate is below this rate."
        ),
    ),
    ComplexBenchmarkThreshold(
        name="min_acceptance_rubric_manifest_rate",
        value_kind="rate",
        cli_help="Fail when acceptance-rubric manifest coverage is below this rate.",
    ),
    ComplexBenchmarkThreshold(
        name="min_acceptance_rubric_read_first_rate",
        value_kind="rate",
        cli_help="Fail when acceptance-rubric read-first rate is below this rate.",
    ),
    ComplexBenchmarkThreshold(
        name="min_acceptance_rubric_alignment_rate",
        value_kind="rate",
        cli_help="Fail when rubric-backed patch alignment is below this rate.",
    ),
)

COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES: tuple[str, ...] = tuple(
    threshold.name for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS
)


def complex_threshold_kwargs_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return {
        name: mapping.get(name)
        for name in COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES
    }


def complex_threshold_kwargs_from_object(source: object) -> dict[str, Any]:
    return {
        name: getattr(source, name)
        for name in COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES
    }


def complex_threshold_count(source: object) -> int:
    return sum(
        1
        for value in complex_threshold_kwargs_from_object(source).values()
        if value is not None
    )
