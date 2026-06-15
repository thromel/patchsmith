"""Spec loading and input validation for complex benchmark suites."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from patchsmith.evaluation.complex.models import (
    ComplexBenchmarkSuiteConfig,
    ComplexBenchmarkSuitePreflight,
    ComplexBenchmarkSuiteSpec,
    ComplexBenchmarkSuiteThresholds,
)
from patchsmith.evaluation.complex.thresholds import (
    COMPLEX_BENCHMARK_SUITE_THRESHOLDS,
)

T = TypeVar("T")

DEFAULT_COMPLEX_BENCHMARK = "public_issue_repair_attempts"
DEFAULT_COMPLEX_SUITE_OUTPUT_DIR = Path(
    "artifacts/experiments/complex_deepagents_suite_v1"
)

def resolve_complex_benchmark_suite_thresholds(
    *,
    suite_spec: ComplexBenchmarkSuiteSpec | None = None,
    min_validation_rate: float | None = None,
    min_live_provider_tasks: int | None = None,
    min_unique_tasks: int | None = None,
    max_attempted_cost_per_validated_task_usd: float | None = None,
    max_attempted_tokens_per_validated_task: float | None = None,
    max_attempted_responses_per_validated_task: float | None = None,
    max_attempted_task_cost_usd: float | None = None,
    max_attempted_task_tokens: int | None = None,
    max_attempted_task_responses: int | None = None,
    max_selected_cost_per_validated_task_usd: float | None = None,
    max_selected_tokens_per_validated_task: float | None = None,
    max_selected_responses_per_validated_task: float | None = None,
    max_selected_virtual_files_per_validated_task: float | None = None,
    max_selected_tokens_per_virtual_file: float | None = None,
    max_selected_responses_per_virtual_file: float | None = None,
    min_selected_progress_score: float | None = None,
    min_selected_context_target_recall: float | None = None,
    min_selected_context_target_precision: float | None = None,
    max_selected_task_cost_usd: float | None = None,
    max_selected_task_tokens: int | None = None,
    max_selected_task_responses: int | None = None,
    max_live_cost_budget_overage_tasks: int | None = None,
    min_agent_trajectory_score: float | None = None,
    min_contextual_verifier_rate: float | None = None,
    min_process_quality_score: float | None = None,
    max_process_risky_validated_tasks: int | None = None,
    min_target_alignment_rate: float | None = None,
    min_repo_instructions_manifest_rate: float | None = None,
    min_repo_instructions_read_first_rate: float | None = None,
    min_acceptance_rubric_manifest_rate: float | None = None,
    min_acceptance_rubric_read_first_rate: float | None = None,
    min_acceptance_rubric_alignment_rate: float | None = None,
) -> ComplexBenchmarkSuiteThresholds:
    spec_thresholds = suite_spec.thresholds if suite_spec else None
    explicit_values = locals().copy()
    threshold_kwargs: dict[str, Any] = {}
    for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS:
        threshold_kwargs[threshold.name] = _explicit_or_spec(
            explicit_values[threshold.name],
            getattr(spec_thresholds, threshold.name) if spec_thresholds else None,
        )
    thresholds = ComplexBenchmarkSuiteThresholds(**threshold_kwargs)
    _validate_complex_benchmark_suite_thresholds(thresholds)
    return thresholds


def resolve_complex_benchmark_suite_config(
    *,
    suite_spec: ComplexBenchmarkSuiteSpec | None = None,
    attempt_dirs: tuple[Path, ...] | list[Path] | None = None,
    output_dir: Path | None = None,
    benchmark: str | None = None,
    min_validation_rate: float | None = None,
    min_live_provider_tasks: int | None = None,
    min_unique_tasks: int | None = None,
    max_attempted_cost_per_validated_task_usd: float | None = None,
    max_attempted_tokens_per_validated_task: float | None = None,
    max_attempted_responses_per_validated_task: float | None = None,
    max_attempted_task_cost_usd: float | None = None,
    max_attempted_task_tokens: int | None = None,
    max_attempted_task_responses: int | None = None,
    max_selected_cost_per_validated_task_usd: float | None = None,
    max_selected_tokens_per_validated_task: float | None = None,
    max_selected_responses_per_validated_task: float | None = None,
    max_selected_virtual_files_per_validated_task: float | None = None,
    max_selected_tokens_per_virtual_file: float | None = None,
    max_selected_responses_per_virtual_file: float | None = None,
    min_selected_progress_score: float | None = None,
    min_selected_context_target_recall: float | None = None,
    min_selected_context_target_precision: float | None = None,
    max_selected_task_cost_usd: float | None = None,
    max_selected_task_tokens: int | None = None,
    max_selected_task_responses: int | None = None,
    max_live_cost_budget_overage_tasks: int | None = None,
    min_agent_trajectory_score: float | None = None,
    min_contextual_verifier_rate: float | None = None,
    min_process_quality_score: float | None = None,
    max_process_risky_validated_tasks: int | None = None,
    min_target_alignment_rate: float | None = None,
    min_repo_instructions_manifest_rate: float | None = None,
    min_repo_instructions_read_first_rate: float | None = None,
    min_acceptance_rubric_manifest_rate: float | None = None,
    min_acceptance_rubric_read_first_rate: float | None = None,
    min_acceptance_rubric_alignment_rate: float | None = None,
    gate_requested: bool | None = None,
    default_output_dir: Path = DEFAULT_COMPLEX_SUITE_OUTPUT_DIR,
) -> ComplexBenchmarkSuiteConfig:
    explicit_values = locals().copy()
    threshold_kwargs: dict[str, Any] = {
        threshold.name: explicit_values[threshold.name]
        for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS
    }
    thresholds = resolve_complex_benchmark_suite_thresholds(
        suite_spec=suite_spec,
        **threshold_kwargs,
    )
    resolved_gate_requested = (
        gate_requested
        if gate_requested is not None
        else suite_spec is not None or thresholds.count > 0
    )
    return ComplexBenchmarkSuiteConfig(
        benchmark=(
            benchmark
            if benchmark
            else suite_spec.benchmark
            if suite_spec
            else DEFAULT_COMPLEX_BENCHMARK
        ),
        attempt_dirs=tuple(attempt_dirs or ())
        or (suite_spec.attempt_dirs if suite_spec else ()),
        output_dir=(
            output_dir
            or (suite_spec.output_dir if suite_spec and suite_spec.output_dir else None)
            or default_output_dir
        ),
        thresholds=thresholds,
        gate_requested=resolved_gate_requested,
    )


def load_complex_benchmark_suite_spec(path: Path) -> ComplexBenchmarkSuiteSpec:
    if not path.is_file():
        raise FileNotFoundError(f"complex benchmark suite spec does not exist: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"complex benchmark suite spec is invalid JSON: {path}") from error
    if not isinstance(parsed, dict):
        raise ValueError("complex benchmark suite spec must be a JSON object")

    benchmark = _optional_spec_string(parsed.get("benchmark")) or "public_issue_repair_attempts"
    attempt_dirs = _required_path_list(parsed.get("attempt_dirs"), "attempt_dirs")
    output_dir = _optional_spec_path(parsed.get("output_dir"), "output_dir")
    gate = parsed.get("gate", {})
    if gate is None:
        gate = {}
    if not isinstance(gate, dict):
        raise ValueError("complex benchmark suite spec field gate must be an object")

    return ComplexBenchmarkSuiteSpec(
        benchmark=benchmark,
        attempt_dirs=attempt_dirs,
        output_dir=output_dir,
        **_parse_complex_benchmark_suite_thresholds(gate),
    )


def validate_complex_benchmark_suite_inputs(
    *,
    attempt_dirs: list[Path],
    output_dir: Path,
    benchmark: str,
    gate_threshold_count: int = 0,
) -> ComplexBenchmarkSuitePreflight:
    errors: list[str] = []
    warnings: list[str] = []
    if not benchmark.strip():
        errors.append("benchmark must be non-empty")
    if not attempt_dirs:
        errors.append("at least one attempt directory is required")

    duplicate_attempt_dirs = _duplicate_paths(attempt_dirs)
    if duplicate_attempt_dirs:
        warnings.append(
            "duplicate attempt directories will be treated as repeated evidence: "
            + ", ".join(duplicate_attempt_dirs)
        )

    missing_attempt_dirs: list[str] = []
    missing_result_files: list[str] = []
    result_file_count = 0
    for attempt_dir in attempt_dirs:
        if not attempt_dir.is_dir():
            missing_attempt_dirs.append(str(attempt_dir))
            errors.append(f"attempt directory does not exist: {attempt_dir}")
            continue
        results_path = attempt_dir / "public_issue_repair_attempt_results.json"
        if not results_path.is_file():
            missing_result_files.append(str(results_path))
            errors.append(f"missing public issue attempt results: {results_path}")
            continue
        result_file_count += 1

    if output_dir.exists() and not output_dir.is_dir():
        errors.append(f"output path exists and is not a directory: {output_dir}")
    if output_dir in attempt_dirs:
        warnings.append("output directory is also listed as an attempt directory")

    return ComplexBenchmarkSuitePreflight(
        status="failed" if errors else "passed",
        benchmark=benchmark,
        attempt_dir_count=len(attempt_dirs),
        result_file_count=result_file_count,
        output_dir=str(output_dir),
        gate_threshold_count=gate_threshold_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
        missing_attempt_dirs=tuple(missing_attempt_dirs),
        missing_result_files=tuple(missing_result_files),
        duplicate_attempt_dirs=tuple(duplicate_attempt_dirs),
    )


def _explicit_or_spec(explicit_value: T | None, spec_value: T | None) -> T | None:
    return explicit_value if explicit_value is not None else spec_value


def _required_path_list(value: Any, field_name: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"complex benchmark suite spec field {field_name} must be a non-empty list")
    paths: list[Path] = []
    for index, item in enumerate(value):
        text = _optional_spec_string(item)
        if text is None:
            raise ValueError(
                f"complex benchmark suite spec field {field_name}[{index}] "
                "must be a non-empty string"
            )
        paths.append(Path(text))
    return tuple(paths)


def _duplicate_paths(paths: list[Path]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for path in paths:
        text = str(path)
        if text in seen and text not in duplicates:
            duplicates.append(text)
        seen.add(text)
    return tuple(duplicates)


def _optional_spec_path(value: Any, field_name: str) -> Path | None:
    if value is None:
        return None
    text = _optional_spec_string(value)
    if text is None:
        raise ValueError(
            f"complex benchmark suite spec field {field_name} must be a non-empty string"
        )
    return Path(text)


def _optional_spec_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_spec_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"complex benchmark suite spec field {field_name} must be a number")
    return float(value)


def _parse_complex_benchmark_suite_thresholds(gate: dict[str, Any]) -> dict[str, Any]:
    thresholds: dict[str, Any] = {}
    for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS:
        field_name = f"gate.{threshold.name}"
        if threshold.value_kind == "rate":
            thresholds[threshold.name] = _optional_spec_rate(
                gate.get(threshold.name),
                field_name,
            )
        elif threshold.value_kind == "nonnegative_float":
            thresholds[threshold.name] = _optional_spec_nonnegative_float(
                gate.get(threshold.name),
                field_name,
            )
        else:
            thresholds[threshold.name] = _optional_spec_nonnegative_int(
                gate.get(threshold.name),
                field_name,
            )
    return thresholds


def _optional_spec_rate(value: Any, field_name: str) -> float | None:
    parsed = _optional_spec_number(value, field_name)
    if parsed is None:
        return None
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(
            f"complex benchmark suite spec field {field_name} must be between 0 and 1"
        )
    return parsed


def _optional_spec_nonnegative_float(value: Any, field_name: str) -> float | None:
    parsed = _optional_spec_number(value, field_name)
    if parsed is None:
        return None
    if parsed < 0.0:
        raise ValueError(
            f"complex benchmark suite spec field {field_name} must be non-negative"
        )
    return parsed


def _optional_spec_nonnegative_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"complex benchmark suite spec field {field_name} must be an integer")
    if value < 0:
        raise ValueError(
            f"complex benchmark suite spec field {field_name} must be non-negative"
        )
    return value


def _validate_complex_benchmark_suite_thresholds(
    thresholds: ComplexBenchmarkSuiteThresholds,
) -> None:
    for threshold in COMPLEX_BENCHMARK_SUITE_THRESHOLDS:
        value = getattr(thresholds, threshold.name)
        if threshold.value_kind == "rate":
            _validate_optional_rate_threshold(value, threshold.name)
        elif threshold.value_kind == "nonnegative_float":
            _validate_optional_nonnegative_float_threshold(value, threshold.name)
        else:
            _validate_optional_nonnegative_int_threshold(value, threshold.name)


def _validate_optional_rate_threshold(value: object, field_name: str) -> None:
    if value is None:
        return
    parsed = _validate_number_threshold(value, field_name)
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(
            f"complex benchmark suite threshold {field_name} must be between 0 and 1"
        )


def _validate_optional_nonnegative_float_threshold(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return
    parsed = _validate_number_threshold(value, field_name)
    if parsed < 0.0:
        raise ValueError(
            f"complex benchmark suite threshold {field_name} must be non-negative"
        )


def _validate_optional_nonnegative_int_threshold(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"complex benchmark suite threshold {field_name} must be an integer"
        )
    if value < 0:
        raise ValueError(
            f"complex benchmark suite threshold {field_name} must be non-negative"
        )


def _validate_number_threshold(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(
            f"complex benchmark suite threshold {field_name} must be a number"
        )
    return float(value)
