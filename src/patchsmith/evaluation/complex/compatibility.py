"""Compatibility readers for persisted complex benchmark artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

from patchsmith.artifacts import load_json
from patchsmith.evaluation_models import ComplexBenchmarkResult

_RESULT_FIELD_NAMES = {field.name for field in fields(ComplexBenchmarkResult)}
_STRING_TUPLE_FIELDS = {
    "patch_quality_codes",
    "patch_target_paths",
    "localized_target_paths",
    "retry_feedback_artifacts",
    "retry_labels",
    "retry_failure_classes",
    "deepagents_virtual_file_paths",
    "deepagents_context_budget_omitted_paths",
    "process_quality_flags",
}
_INT_DICT_FIELDS = {
    "retry_label_counts",
    "retry_failure_class_counts",
}


def load_complex_benchmark_results(path: Path) -> list[ComplexBenchmarkResult]:
    payload = load_json(path)
    if not isinstance(payload, list):
        return []
    results: list[ComplexBenchmarkResult] = []
    for row in payload:
        if isinstance(row, Mapping):
            results.append(complex_benchmark_result_from_dict(row))
    return results


def complex_benchmark_result_from_dict(
    row: Mapping[str, object],
) -> ComplexBenchmarkResult:
    values: dict[str, Any] = {}
    for key, value in row.items():
        if key not in _RESULT_FIELD_NAMES:
            continue
        if key in _STRING_TUPLE_FIELDS:
            values[key] = _string_tuple(value)
        elif key in _INT_DICT_FIELDS:
            values[key] = _int_dict(value)
        elif key == "preflight_gates":
            values[key] = _preflight_gates(value)
        else:
            values[key] = value
    return ComplexBenchmarkResult(**values)


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _int_dict(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            result[str(key)] = item
    return result


def _preflight_gates(value: object) -> list[dict[str, str]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    gates: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, Mapping):
            gates.append({str(key): str(field_value) for key, field_value in item.items()})
    return gates
