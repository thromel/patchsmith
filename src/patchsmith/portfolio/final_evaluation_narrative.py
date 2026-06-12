"""Narrative decisions and limitations for final evaluation reports."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _failure_summary
from patchsmith.portfolio.models import (
    DemoReadinessReport,
    FinalEvaluationMetric,
    FinalEvaluationReport,
)


def final_evaluation_decisions(
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
        decisions.append(_patch_search_decision(patch_rows))
    if readiness.failure_categories:
        decisions.append(
            "Failure cases are preserved for review: "
            f"{_failure_summary(readiness.failure_categories)}."
        )
    decisions.extend(_adapter_decisions(deepagents_modes, openai_agents_modes))
    live_providers = _live_model_providers(readiness)
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


def final_evaluation_limitations(
    readiness: DemoReadinessReport,
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    package_runs = deepagents_modes.get("package_available", 0)
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    live_providers = _live_model_providers(readiness)
    deepagents_live_providers = [
        provider for provider in live_providers if provider == "deepagents_openai_chat"
    ]
    deepagents_limitation = (
        (
            "DeepAgents live-model evidence is present for "
            f"{', '.join(deepagents_live_providers)}, but it remains scoped to the saved "
            "seeded/public repair artifacts and is not broad autonomous repair quality."
        )
        if deepagents_live_providers
        else _uncalibrated_deepagents_limitation(package_runs)
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
    if not live_providers:
        limitations.append(
            "No non-offline model provider metadata was found; live LLM quality, token use, and cost remain uncalibrated."
        )
    if readiness.runs_requiring_attention:
        limitations.append(
            f"{readiness.runs_requiring_attention} saved runs still require attention; use them as failure-analysis material, not as hidden exclusions."
        )
    return limitations


def final_review_artifacts() -> list[str]:
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


def executive_conclusion(report: FinalEvaluationReport) -> str:
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


def _patch_search_decision(patch_rows: list[FinalEvaluationMetric]) -> str:
    seen_test_run_lanes: set[str] = set()
    test_run_parts: list[str] = []
    for metric in patch_rows:
        if not metric.secondary_metric or metric.lane in seen_test_run_lanes:
            continue
        seen_test_run_lanes.add(metric.lane)
        test_run_parts.append(f"{metric.lane} {metric.secondary_metric}")
    test_runs = "; ".join(test_run_parts)
    return (
        "Patch-search evidence should be framed as a cost tradeoff; "
        f"current candidate lanes report {test_runs}."
    )


def _adapter_decisions(
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
) -> list[str]:
    decisions: list[str] = []
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
    return decisions


def _live_model_providers(readiness: DemoReadinessReport) -> list[str]:
    return [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]


def _uncalibrated_deepagents_limitation(package_runs: int) -> str:
    if package_runs:
        return (
            "DeepAgents package-backed adapter smoke evidence exists, but live DeepAgents "
            "model execution remains uncalibrated."
        )
    return (
        "DeepAgents evidence is adapter compatibility evidence unless the optional "
        "package and live model provider are installed and reflected in saved artifacts."
    )


__all__ = [
    "executive_conclusion",
    "final_evaluation_decisions",
    "final_evaluation_limitations",
    "final_review_artifacts",
]
