"""Portfolio final evaluation (split from portfolio.py)."""

from __future__ import annotations

from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability import build_artifact_index
from patchsmith.portfolio._helpers import (
    _discover_deepagents_adapter_modes,
    _discover_openai_agents_adapter_modes,
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.final_evaluation_metrics import final_evaluation_metric
from patchsmith.portfolio.final_evaluation_narrative import (
    executive_conclusion,
    final_evaluation_decisions,
    final_evaluation_limitations,
    final_review_artifacts,
)
from patchsmith.portfolio.models import (
    FinalEvaluationMetric,
    FinalEvaluationReport,
)


def build_final_evaluation_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    metrics = [final_evaluation_metric(metric) for metric in index.metrics]
    deepagents_modes = _discover_deepagents_adapter_modes(Path(index.artifacts_dir))
    openai_agents_modes = _discover_openai_agents_adapter_modes(Path(index.artifacts_dir))
    return FinalEvaluationReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_now(),
        readiness_status=readiness.readiness_status,
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        runs_requiring_attention=readiness.runs_requiring_attention,
        failure_categories=readiness.failure_categories,
        model_providers=readiness.model_providers,
        deepagents_package_run_count=deepagents_modes.get("package_available", 0),
        deepagents_compatibility_run_count=deepagents_modes.get("compatibility_mode", 0),
        openai_agents_package_run_count=openai_agents_modes.get("package_available", 0),
        openai_agents_compatibility_run_count=openai_agents_modes.get("compatibility_mode", 0),
        metrics=metrics,
        decisions=final_evaluation_decisions(
            readiness, metrics, deepagents_modes, openai_agents_modes
        ),
        limitations=final_evaluation_limitations(readiness, deepagents_modes, openai_agents_modes),
        review_artifacts=final_review_artifacts(),
    )


def write_final_evaluation_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    report = build_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    write_markdown(output_path, render_final_evaluation_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_final_evaluation_report(report: FinalEvaluationReport) -> str:
    lines = [
        "# PatchSmith Final Evaluation Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Experiment count: `{report.experiment_count}`",
        f"- Saved run count: `{report.run_count}`",
        f"- Normalized metric rows: `{report.metric_count}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- OpenAI Agents package-backed runs: `{report.openai_agents_package_run_count}`",
        (
            "- OpenAI Agents compatibility-mode runs: "
            f"`{report.openai_agents_compatibility_run_count}`"
        ),
        "",
        "## Executive Conclusion",
        "",
        executive_conclusion(report),
        "",
        "## Metric Evidence",
        "",
        (
            "| Experiment | Kind | Lane | Tasks | Primary | Secondary | Latency | "
            "Cost | Risk Note | Report |"
        ),
        "|---|---|---|---:|---|---|---:|---:|---|---|",
    ]
    for metric in report.metrics:
        lines.append(
            "| "
            f"{metric.experiment} | "
            f"{metric.kind} | "
            f"{metric.lane} | "
            f"{_task_count_cell(metric)} | "
            f"{metric.primary_metric} | "
            f"{metric.secondary_metric} | "
            f"{_latency_cell(metric.avg_latency_ms)} | "
            f"{_cost_cell(metric.estimated_cost_usd)} | "
            f"{_markdown_cell(metric.risk_note or '')} | "
            f"{_path_cell(metric.report_path)} |"
        )

    lines.extend(["", "## Decisions", ""])
    for decision in report.decisions:
        lines.append(f"- {decision}")

    lines.extend(["", "## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")

    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")

    lines.extend(
        [
            "",
            "## Public Claim Boundary",
            "",
            (
                "This report supports an offline seeded-suite portfolio demo. It does not "
                "claim live LLM quality unless saved artifacts include non-offline provider "
                "metadata and corresponding cost/token evidence."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _task_count_cell(metric: FinalEvaluationMetric) -> str:
    if metric.task_count is None:
        return ""
    if metric.completed_count is None:
        return str(metric.task_count)
    return f"{metric.completed_count}/{metric.task_count}"


def _latency_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.0f}ms"


def _cost_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:.4f}"


def _path_cell(path: str | None) -> str:
    if path is None:
        return ""
    return f"`{path}`"
