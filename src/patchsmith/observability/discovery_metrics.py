"""Metric extraction helpers for observability artifact discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.artifacts import load_json as _load_json
from patchsmith.observability.models import ExperimentMetricIndexEntry


def _experiment_metric_entries(
    *,
    experiment: str,
    kind: str,
    report_path: str | None,
    summary_path: Path | None,
    results_path: Path | None,
) -> list[ExperimentMetricIndexEntry]:
    payload = _load_json(summary_path)
    if payload is None and summary_path != results_path:
        payload = _load_json(results_path)
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        return []

    metrics: list[ExperimentMetricIndexEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric = _metric_entry_from_row(
            experiment=experiment,
            kind=kind,
            report_path=report_path,
            row=row,
        )
        if metric is not None:
            metrics.append(metric)
    return metrics


def _metric_entry_from_row(
    *,
    experiment: str,
    kind: str,
    report_path: str | None,
    row: dict[str, Any],
) -> ExperimentMetricIndexEntry | None:
    if "avg_top5_touched_recall" in row:
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(row.get("provider") or "provider"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Top-5 Recall",
            primary_value=_number_or_none(row.get("avg_top5_touched_recall")),
            secondary_label="Related Tests",
            secondary_value=_number_or_none(row.get("avg_related_test_recall")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=None,
            risk_note=_count_note(
                (
                    (_int_or_none(row.get("failed_tasks")), "failed"),
                    (_int_or_none(row.get("fallback_count")), "fallback"),
                    (
                        _int_or_none(row.get("source_free_violation_count")),
                        "source-free violations",
                    ),
                )
            ),
            report_path=report_path,
        )

    if "targeted_test_pass_rate" in row:
        lane = row.get("scaffold") or "/".join(
            str(value)
            for value in (
                row.get("runtime"),
                row.get("planner"),
                row.get("context_provider"),
            )
            if value
        )
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(lane or "repair"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Targeted Tests Passed",
            primary_value=_number_or_none(row.get("targeted_test_pass_rate")),
            secondary_label="Patch Generated",
            secondary_value=_number_or_none(row.get("patch_generated_rate")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=_number_or_none(row.get("estimated_cost_usd")),
            risk_note=_count_note(
                (
                    (_incomplete_count(row), "incomplete"),
                    (
                        _int_or_none(row.get("failed_trace_event_count")),
                        "failed trace events",
                    ),
                )
            ),
            report_path=report_path,
        )

    if "success_at_k_rate" in row:
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(row.get("variant") or "patch_search"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Success@k",
            primary_value=_number_or_none(row.get("success_at_k_rate")),
            secondary_label="Avg Test Runs",
            secondary_value=_number_or_none(row.get("avg_test_runs")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=_number_or_none(row.get("estimated_cost_usd")),
            risk_note=_count_note(((_incomplete_count(row), "incomplete"),)),
            report_path=report_path,
        )

    if "valid_tasks" in row and "task_count" in row:
        task_count = _int_or_none(row.get("task_count"))
        valid_tasks = _int_or_none(row.get("valid_tasks"))
        valid_rate = valid_tasks / task_count if valid_tasks is not None and task_count else None
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=Path(str(row.get("dataset_dir") or experiment)).name,
            task_count=task_count,
            completed_count=valid_tasks,
            primary_label="Valid Tasks",
            primary_value=valid_rate,
            secondary_label="Errors",
            secondary_value=_int_or_none(row.get("error_count")),
            avg_latency_ms=None,
            estimated_cost_usd=None,
            risk_note=_count_note(
                (
                    (_int_or_none(row.get("invalid_tasks")), "invalid"),
                    (_int_or_none(row.get("warning_count")), "warnings"),
                )
            ),
            report_path=report_path,
        )

    return None


def _count_note(counts: tuple[tuple[int | None, str], ...]) -> str | None:
    parts = [f"{count} {label}" for count, label in counts if count is not None]
    return "; ".join(parts) if parts else None


def _incomplete_count(row: dict[str, Any]) -> int | None:
    attempted = _int_or_none(row.get("attempted_tasks"))
    completed = _int_or_none(row.get("completed_tasks"))
    if attempted is None or completed is None:
        return None
    return max(0, attempted - completed)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


__all__ = [
    "_experiment_metric_entries",
    "_int_or_none",
    "_number_or_none",
]
