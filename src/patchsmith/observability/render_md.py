"""Observability render md (split from observability.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.observability.discovery import _markdown_path, _run_detail_relative_path
from patchsmith.observability.models import (
    RECENT_RUN_LIMIT,
    ArtifactIndex,
    ExperimentMetricIndexEntry,
)


def render_artifact_index(
    index: ArtifactIndex,
    *,
    run_detail_output_dir: Path | None = None,
) -> str:
    lines = [
        "# PatchSmith Artifact Index",
        "",
        f"- Generated at: `{index.generated_at}`",
        f"- Artifacts directory: `{index.artifacts_dir}`",
        f"- Experiment count: `{index.experiment_count}`",
        f"- Run count: `{index.run_count}`",
        "",
        "## Experiments",
        "",
        ("| Experiment | Kind | Report | Summary | Results | Result Count | Runs | Updated |"),
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for entry in index.experiments:
        lines.append(
            "| "
            f"{entry.name} | "
            f"{entry.kind} | "
            f"{_markdown_path(entry.report_path)} | "
            f"{_markdown_path(entry.summary_path)} | "
            f"{_markdown_path(entry.results_path)} | "
            f"{entry.result_count if entry.result_count is not None else ''} | "
            f"{entry.run_count} | "
            f"{entry.updated_at or ''} |"
        )
    lines.extend(
        [
            "",
            f"## Research Metrics ({len(index.metrics)})",
            "",
            (
                "| Experiment | Kind | Lane | Tasks | Primary | Secondary | "
                "Latency | Cost | Risk | Report |"
            ),
            "|---|---|---|---:|---|---|---:|---:|---|---|",
        ]
    )
    for metric in index.metrics:
        lines.append(
            "| "
            f"{metric.experiment} | "
            f"{metric.kind} | "
            f"{metric.lane} | "
            f"{_metric_task_count(metric)} | "
            f"{_format_metric_pair(metric.primary_label, metric.primary_value)} | "
            f"{_format_metric_pair(metric.secondary_label, metric.secondary_value)} | "
            f"{_format_latency(metric.avg_latency_ms) if metric.avg_latency_ms is not None else ''} | "
            f"{_format_cost(metric.estimated_cost_usd)} | "
            f"{metric.risk_note or ''} | "
            f"{_markdown_path(metric.report_path)} |"
        )
    lines.extend(
        [
            "",
            f"## Recent Runs ({min(len(index.runs), RECENT_RUN_LIMIT)} of {len(index.runs)})",
            "",
            (
                "| Run | Experiment | Variant | Detail | Report | Trace | Diff | "
                "Stdout | Stderr | Updated |"
            ),
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in index.runs[:RECENT_RUN_LIMIT]:
        lines.append(
            "| "
            f"{run.run_id} | "
            f"{run.experiment or ''} | "
            f"{run.variant or ''} | "
            f"{_markdown_path(_run_detail_relative_path(index, run, run_detail_output_dir))} | "
            f"{_markdown_path(run.report_path)} | "
            f"{_markdown_path(run.trace_path)} | "
            f"{_markdown_path(run.diff_path)} | "
            f"{_markdown_path(run.stdout_path)} | "
            f"{_markdown_path(run.stderr_path)} | "
            f"{run.updated_at or ''} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This index is generated from saved local artifacts.",
            "- Reports remain the source of truth for metrics and decision notes.",
            "- Source-bearing raw context artifacts are not copied into this index.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_markdown_cell(value: str, *, max_chars: int = 160) -> str:
    normalized = " ".join(value.replace("|", "/").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _text_preview(
    path: str | None,
    *,
    artifacts_dir: Path,
    max_lines: int,
) -> str:
    if path is None:
        return ""
    try:
        lines = (artifacts_dir / path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    preview = lines[:max_lines]
    if len(lines) > max_lines:
        preview.append(f"... truncated {len(lines) - max_lines} lines ...")
    return "\n".join(preview)


def _joined(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _format_latency(latency_ms: float) -> str:
    if latency_ms >= 1000:
        return f"{latency_ms / 1000:.1f}s"
    return f"{latency_ms:.0f}ms"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _metric_task_count(metric: ExperimentMetricIndexEntry) -> str:
    if metric.task_count is None:
        return ""
    if metric.completed_count is None:
        return _format_int(metric.task_count)
    return f"{_format_int(metric.completed_count)}/{_format_int(metric.task_count)}"


def _format_metric_pair(label: str | None, value: int | float | str | None) -> str:
    if not label:
        return ""
    if value is None:
        return label
    return f"{label}: {_format_metric_value(label, value)}"


def _format_metric_value(label: str, value: int | float | str) -> str:
    if not isinstance(value, int | float):
        return str(value)
    normalized = label.lower()
    if any(
        token in normalized
        for token in (
            "recall",
            "related tests",
            "passed",
            "generated",
            "success",
            "valid",
        )
    ):
        return f"{value * 100:.0f}%"
    if isinstance(value, int):
        return _format_int(value)
    return f"{value:.1f}"


def _format_cost(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:.4f}" if 0 < value < 0.01 else f"${value:.2f}"
