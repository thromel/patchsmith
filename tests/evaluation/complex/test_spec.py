from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.models import (
    ComplexBenchmarkSuiteGate,
    ComplexBenchmarkSuiteSpec,
    ComplexBenchmarkSuiteThresholds,
)
from patchsmith.evaluation.complex.spec import (
    DEFAULT_COMPLEX_BENCHMARK,
    load_complex_benchmark_suite_spec,
    resolve_complex_benchmark_suite_config,
    resolve_complex_benchmark_suite_thresholds,
    validate_complex_benchmark_suite_inputs,
)
from patchsmith.evaluation.complex.thresholds import (
    COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES,
)
from patchsmith.evaluation.runners import complex as runner_complex

pytestmark = pytest.mark.unit


def test_threshold_registry_matches_model_fields() -> None:
    threshold_names = set(COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES)

    assert tuple(field.name for field in fields(ComplexBenchmarkSuiteThresholds)) == (
        COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES
    )
    assert (
        tuple(
            field.name
            for field in fields(ComplexBenchmarkSuiteSpec)
            if field.name in threshold_names
        )
        == COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES
    )
    assert (
        tuple(
            field.name
            for field in fields(ComplexBenchmarkSuiteGate)
            if field.name in threshold_names
        )
        == COMPLEX_BENCHMARK_SUITE_THRESHOLD_NAMES
    )


def test_load_complex_benchmark_suite_spec_parses_thresholds(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt"
    output_dir = tmp_path / "out"
    spec_path = tmp_path / "suite.json"
    spec_path.write_text(
        json.dumps(
            {
                "benchmark": "public_issue_repair_attempts",
                "attempt_dirs": [str(attempt_dir)],
                "output_dir": str(output_dir),
                "gate": {
                    "min_validation_rate": 0.9,
                    "min_live_provider_tasks": 2,
                    "max_selected_tokens_per_virtual_file": 250.0,
                    "min_acceptance_rubric_alignment_rate": 0.8,
                },
            }
        ),
        encoding="utf-8",
    )

    spec = load_complex_benchmark_suite_spec(spec_path)

    assert spec.benchmark == "public_issue_repair_attempts"
    assert spec.attempt_dirs == (attempt_dir,)
    assert spec.output_dir == output_dir
    assert spec.thresholds.min_validation_rate == 0.9
    assert spec.thresholds.min_live_provider_tasks == 2
    assert spec.thresholds.max_selected_tokens_per_virtual_file == 250.0
    assert spec.thresholds.min_acceptance_rubric_alignment_rate == 0.8
    assert spec.thresholds.count == 4


def test_resolve_complex_benchmark_suite_config_prefers_explicit_overrides(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "suite.json"
    spec_attempt = tmp_path / "spec_attempt"
    explicit_attempt = tmp_path / "explicit_attempt"
    spec_path.write_text(
        json.dumps(
            {
                "benchmark": "spec_benchmark",
                "attempt_dirs": [str(spec_attempt)],
                "output_dir": str(tmp_path / "spec_out"),
                "gate": {
                    "min_validation_rate": 0.5,
                    "min_unique_tasks": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    config = resolve_complex_benchmark_suite_config(
        suite_spec=load_complex_benchmark_suite_spec(spec_path),
        attempt_dirs=[explicit_attempt],
        output_dir=tmp_path / "explicit_out",
        benchmark="explicit_benchmark",
        min_validation_rate=0.95,
    )

    assert config.benchmark == "explicit_benchmark"
    assert config.attempt_dirs == (explicit_attempt,)
    assert config.output_dir == tmp_path / "explicit_out"
    assert config.gate_requested is True
    assert config.thresholds.min_validation_rate == 0.95
    assert config.thresholds.min_unique_tasks == 1


def test_validate_complex_benchmark_suite_inputs_reports_missing_and_duplicates(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempt"
    preflight = validate_complex_benchmark_suite_inputs(
        attempt_dirs=[attempt_dir, attempt_dir],
        output_dir=tmp_path / "out",
        benchmark=DEFAULT_COMPLEX_BENCHMARK,
        gate_threshold_count=1,
    )

    assert preflight.status == "failed"
    assert preflight.attempt_dir_count == 2
    assert preflight.result_file_count == 0
    assert preflight.missing_attempt_dirs == (str(attempt_dir), str(attempt_dir))
    assert preflight.duplicate_attempt_dirs == (str(attempt_dir),)
    assert preflight.gate_threshold_count == 1


def test_threshold_validation_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="min_validation_rate must be between 0 and 1"):
        resolve_complex_benchmark_suite_thresholds(min_validation_rate=1.1)

    with pytest.raises(ValueError, match="max_selected_task_tokens must be an integer"):
        resolve_complex_benchmark_suite_thresholds(
            max_selected_task_tokens=1.5,  # type: ignore[arg-type]
        )


def test_runner_keeps_legacy_suite_spec_exports() -> None:
    assert runner_complex.load_complex_benchmark_suite_spec is (load_complex_benchmark_suite_spec)
    assert runner_complex.resolve_complex_benchmark_suite_config is (
        resolve_complex_benchmark_suite_config
    )
    assert runner_complex.validate_complex_benchmark_suite_inputs is (
        validate_complex_benchmark_suite_inputs
    )
