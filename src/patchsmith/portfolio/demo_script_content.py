"""Demo script sections, caveats, and rehearsal commands."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _failure_summary, _provider_summary
from patchsmith.portfolio.models import DemoReadinessReport, DemoScriptSection


def demo_script_sections(readiness: DemoReadinessReport) -> list[DemoScriptSection]:
    failure_summary = _failure_summary(readiness.failure_categories)
    provider_summary = _provider_summary(readiness.model_providers)
    return [
        DemoScriptSection(
            title="Problem And Thesis",
            duration_seconds=25,
            on_screen="README project summary and architecture overview.",
            artifact="README.md",
            narration=(
                "PatchSmith is an AI software-maintenance agent and evaluation lab. "
                "The point of the demo is not a single lucky patch; it is a repeatable "
                "issue-to-tested-diff workflow with retrieval, orchestration, sandboxed "
                "tests, saved traces, and honest evaluation artifacts."
            ),
        ),
        DemoScriptSection(
            title="Evidence Dashboard",
            duration_seconds=35,
            on_screen="Open the static artifact dashboard and scan metrics.",
            artifact="artifacts/experiments/index.html",
            narration=(
                f"The current artifact set has {readiness.experiment_count} experiments, "
                f"{readiness.run_count} saved runs, and {readiness.metric_count} normalized "
                "metric rows. Use this screen to show retrieval, repair, scaffold, graph, "
                "and patch-search evidence from one review surface."
            ),
        ),
        DemoScriptSection(
            title="Runtime Comparison",
            duration_seconds=40,
            on_screen="Open scaffold comparison and explain the lanes.",
            artifact="artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
            narration=(
                "The scaffold comparison keeps Agentless, heuristic, LangGraph, "
                "LangGraph fake-model, DeepAgents, and OpenAI Agents SDK adapters "
                "under the same seeded task set and context provider. The important "
                "interview story is that quality, latency, trace complexity, and "
                "debuggability are measured together instead of treated as separate "
                "anecdotes."
            ),
        ),
        DemoScriptSection(
            title="Patch Search Cost Tradeoff",
            duration_seconds=30,
            on_screen="Open patch-search report and compare one versus three candidates.",
            artifact="artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
            narration=(
                "Patch search is included as a research mode. On the current easy seeded "
                "suite, three candidates do not improve success over one candidate, but "
                "they add test runs and latency. That result is useful because it prevents "
                "over-selling patch search before harder tasks justify the cost."
            ),
        ),
        DemoScriptSection(
            title="Failure Transparency",
            duration_seconds=35,
            on_screen="Open the failure report and show grouped failures.",
            artifact="artifacts/experiments/failure_report.md",
            narration=(
                f"The failure report keeps failure cases visible: {failure_summary}. "
                "For the current artifacts, most failures are expected Agentless control "
                "runs with no patch generated. This is exactly the kind of evidence a "
                "research demo should preserve rather than hide."
            ),
        ),
        DemoScriptSection(
            title="Caveats And Close",
            duration_seconds=25,
            on_screen="Open demo readiness report and state the launch status.",
            artifact="artifacts/experiments/demo_readiness.md",
            narration=(
                f"The readiness status is {readiness.readiness_status}. Provider evidence "
                f"is {provider_summary}. The correct closing claim is that the offline "
                "seeded-suite demo is coherent, while live LLM calibration remains a "
                "separate credential-gated step unless non-offline provider metadata is present."
            ),
        ),
    ]


def demo_script_caveat(readiness: DemoReadinessReport) -> str:
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        return f"Live provider metadata found: {', '.join(live_providers)}."
    return (
        "Current model evidence is offline only; live LLM calibration must be run "
        "separately before making live-provider claims."
    )


def demo_script_rehearsal_commands() -> list[str]:
    return [
        (
            "PYTHONPATH=src python3 -m patchsmith.cli index-artifacts "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/index.md "
            "--json-output artifacts/experiments/index.json "
            "--html-output artifacts/experiments/index.html "
            "--run-detail-output-dir artifacts/experiments/run-details --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli inspect-failures "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/failure_report.md "
            "--json-output artifacts/experiments/failure_report.json "
            "--max-runs 0 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-readiness "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_readiness.md "
            "--json-output artifacts/experiments/demo_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-script "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_script.md "
            "--json-output artifacts/experiments/demo_script.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-media "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_media.md "
            "--svg-output artifacts/experiments/demo_media.svg "
            "--png-output artifacts/experiments/demo_media.png "
            "--json-output artifacts/experiments/demo_media.json --json"
        ),
    ]


__all__ = [
    "demo_script_caveat",
    "demo_script_rehearsal_commands",
    "demo_script_sections",
]
