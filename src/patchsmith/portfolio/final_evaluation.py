"""Portfolio final evaluation (split from portfolio.py)."""

from __future__ import annotations

from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability import (
    ExperimentMetricIndexEntry,
    build_artifact_index,
)
from patchsmith.portfolio._helpers import (
    _discover_deepagents_adapter_modes,
    _discover_openai_agents_adapter_modes,
    _failure_summary,
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.models import (
    DemoReadinessReport,
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
    metrics = [_final_metric(metric) for metric in index.metrics]
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
        decisions=_final_evaluation_decisions(
            readiness, metrics, deepagents_modes, openai_agents_modes
        ),
        limitations=_final_evaluation_limitations(readiness, deepagents_modes, openai_agents_modes),
        review_artifacts=_final_review_artifacts(),
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
        _executive_conclusion(report),
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


def _final_metric(metric: ExperimentMetricIndexEntry) -> FinalEvaluationMetric:
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


def _final_evaluation_decisions(
    readiness: DemoReadinessReport,
    metrics: list[FinalEvaluationMetric],
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    decisions = [
        (
            f"Portfolio evidence is `{readiness.readiness_status}` with "
            f"{readiness.experiment_count} experiments, {readiness.run_count} saved runs, "
            f"and {readiness.metric_count} normalized metric rows."
        ),
        (
            "Use the static dashboard, run-detail pages, failure report, readiness report, "
            "and demo script as the launch review surface before adding a hosted UI."
        ),
    ]
    retrieval_rows = [metric for metric in metrics if metric.kind == "retrieval"]
    if retrieval_rows:
        lanes = ", ".join(sorted({metric.lane for metric in retrieval_rows}))
        decisions.append(f"Retrieval evidence is available for these lanes: {lanes}.")
    repair_rows = [
        metric
        for metric in metrics
        if metric.kind in {"repair", "scaffold"}
        and "Targeted Tests Passed: 100%" in metric.primary_metric
    ]
    if repair_rows:
        lanes = ", ".join(sorted({metric.lane for metric in repair_rows}))
        decisions.append(
            f"Seeded repair/scaffold evidence shows targeted tests passing for: {lanes}."
        )
    patch_rows = [metric for metric in metrics if metric.kind == "patch_search"]
    if patch_rows:
        seen_test_run_lanes: set[str] = set()
        test_run_parts: list[str] = []
        for metric in patch_rows:
            if not metric.secondary_metric or metric.lane in seen_test_run_lanes:
                continue
            seen_test_run_lanes.add(metric.lane)
            test_run_parts.append(f"{metric.lane} {metric.secondary_metric}")
        test_runs = "; ".join(test_run_parts)
        decisions.append(
            "Patch-search evidence should be framed as a cost tradeoff; "
            f"current candidate lanes report {test_runs}."
        )
    if readiness.failure_categories:
        decisions.append(
            "Failure cases are preserved for review: "
            f"{_failure_summary(readiness.failure_categories)}."
        )
    package_runs = deepagents_modes.get("package_available", 0)
    compatibility_runs = deepagents_modes.get("compatibility_mode", 0)
    if package_runs:
        decisions.append(
            f"DeepAgents adapter evidence now includes {package_runs} package-backed "
            f"run(s) and {compatibility_runs} compatibility-mode run(s); this proves "
            "optional-package import compatibility, not live DeepAgents model quality."
        )
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    openai_agents_compatibility_runs = openai_agents_modes.get("compatibility_mode", 0)
    if openai_agents_package_runs:
        decisions.append(
            "OpenAI Agents adapter evidence now includes "
            f"{openai_agents_package_runs} package-backed run(s) and "
            f"{openai_agents_compatibility_runs} compatibility-mode run(s); this proves "
            "optional-package import compatibility, not live OpenAI Agents model quality."
        )
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        decisions.append(
            f"Live-provider evidence exists for {', '.join(live_providers)}; report cost "
            "and token usage next to any live-model quality claim."
        )
    else:
        decisions.append(
            "Do not claim live LLM calibration yet; saved provider metadata is offline-only."
        )
    return decisions


def _final_evaluation_limitations(
    readiness: DemoReadinessReport,
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    package_runs = deepagents_modes.get("package_available", 0)
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    deepagents_limitation = (
        "DeepAgents package-backed adapter smoke evidence exists, but live DeepAgents "
        "model execution remains uncalibrated."
        if package_runs
        else (
            "DeepAgents evidence is adapter compatibility evidence unless the optional "
            "package and live model provider are installed and reflected in saved artifacts."
        )
    )
    openai_agents_limitation = (
        "OpenAI Agents package-backed adapter smoke evidence exists, but live OpenAI "
        "Agents model execution remains uncalibrated."
        if openai_agents_package_runs
        else (
            "OpenAI Agents evidence is adapter compatibility evidence unless the optional "
            "package and live model provider are installed and reflected in saved artifacts."
        )
    )
    limitations = [
        "The seeded suite is intentionally small and controlled; it proves workflow plumbing and comparative instrumentation, not broad real-world coding-agent quality.",
        "Current public-demo mode should use seeded or preselected repositories until sandboxing is hardened for arbitrary untrusted repos.",
        deepagents_limitation,
        openai_agents_limitation,
    ]
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if not live_providers:
        limitations.append(
            "No non-offline model provider metadata was found; live LLM quality, token use, and cost remain uncalibrated."
        )
    if readiness.runs_requiring_attention:
        limitations.append(
            f"{readiness.runs_requiring_attention} saved runs still require attention; use them as failure-analysis material, not as hidden exclusions."
        )
    return limitations


def _final_review_artifacts() -> list[str]:
    return [
        "artifacts/experiments/index.html",
        "artifacts/experiments/index.md",
        "artifacts/experiments/failure_report.md",
        "artifacts/experiments/demo_readiness.md",
        "artifacts/experiments/calibration_readiness.md",
        "artifacts/experiments/live_calibration_plan.md",
        "artifacts/experiments/launch_blockers.md",
        "artifacts/experiments/demo_script.md",
        "artifacts/experiments/public_issue_corpus_v1/corpus_report.md",
        "artifacts/experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "artifacts/experiments/public_issue_corpus_v1/context_preview_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_task_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "artifacts/experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
        "artifacts/experiments/public_issue_corpus_v1/public_issue_repair_attempt_report.md",
        "artifacts/experiments/demo_media.md",
        "artifacts/experiments/demo_media.svg",
        "artifacts/experiments/demo_media.png",
        "artifacts/experiments/quality_gate.md",
        "artifacts/experiments/project_status.md",
        "artifacts/experiments/delivery_audit.md",
        "artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
        "artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
        "artifacts/experiments/retrieval_eval_v1/report.md",
    ]


def _executive_conclusion(report: FinalEvaluationReport) -> str:
    if report.readiness_status == "ready":
        return (
            "PatchSmith is ready for a portfolio demo with current saved evidence. "
            "Keep the demo scoped to the artifact set summarized here."
        )
    if report.readiness_status == "ready_with_caveats":
        return (
            "PatchSmith is ready for an offline portfolio demo with caveats. The saved "
            "artifacts support the issue-to-tested-patch research workflow, but live LLM "
            "calibration and arbitrary public execution should remain explicitly out of scope."
        )
    return (
        "PatchSmith is not ready for portfolio launch from the current saved artifacts; "
        "resolve the missing gates before recording a public demo."
    )


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
