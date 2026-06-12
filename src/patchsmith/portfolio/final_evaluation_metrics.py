"""Metric conversion helpers for final evaluation reports."""

from __future__ import annotations

from patchsmith.observability import ExperimentMetricIndexEntry
from patchsmith.portfolio.models import FinalEvaluationMetric


def final_evaluation_metric(metric: ExperimentMetricIndexEntry) -> FinalEvaluationMetric:
    return FinalEvaluationMetric(
        experiment=metric.experiment,
        kind=metric.kind,
        lane=metric.lane,
        task_count=metric.task_count,
        completed_count=metric.completed_count,
        primary_metric=_metric_label_value(metric.primary_label, metric.primary_value),
        secondary_metric=_metric_label_value(
            metric.secondary_label,
            metric.secondary_value,
        ),
        avg_latency_ms=metric.avg_latency_ms,
        estimated_cost_usd=metric.estimated_cost_usd,
        risk_note=metric.risk_note,
        report_path=metric.report_path,
    )


def _metric_label_value(label: str | None, value: int | float | str | None) -> str:
    if label is None and value is None:
        return ""
    if label is None:
        return _metric_value("", value)
    return f"{label}: {_metric_value(label, value)}"


def _metric_value(label: str, value: int | float | str | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    normalized_label = label.lower()
    if "avg test runs" in normalized_label:
        if isinstance(value, int) or float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}"
    if (
        any(
            token in normalized_label
            for token in (
                "recall",
                "related tests",
                "passed",
                "generated",
                "success",
                "valid",
            )
        )
        and 0 <= value <= 1
    ):
        return f"{value * 100:.0f}%"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


__all__ = ["final_evaluation_metric"]
