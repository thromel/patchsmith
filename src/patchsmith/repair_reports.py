from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.artifacts import format_cost as _format_cost
from patchsmith.evaluation_models import (
    PatchSearchEvalResult,
    PatchSearchEvalSummary,
    RepairEvalResult,
    RepairEvalSummary,
    ScaffoldComparisonResult,
)


def _sum_optional_float(values: Any) -> float | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return float(sum(values_list))


def render_repair_eval_report(
    *,
    dataset_dir: Path,
    results: list[RepairEvalResult],
    summary: RepairEvalSummary,
) -> str:
    input_tokens = summary.input_tokens if summary.input_tokens is not None else "n/a"
    output_tokens = summary.output_tokens if summary.output_tokens is not None else "n/a"
    total_tokens = summary.total_tokens if summary.total_tokens is not None else "n/a"
    lines = [
        "# Repair Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Runtime: `{summary.runtime}`",
        f"- Planner: `{summary.planner}`",
        f"- Context provider: `{summary.context_provider}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Completed tasks: `{summary.completed_tasks}`",
        f"- Model provider: `{summary.model_provider or 'none'}`",
        f"- Input tokens: `{input_tokens}`",
        f"- Output tokens: `{output_tokens}`",
        f"- Total tokens: `{total_tokens}`",
        f"- Estimated model cost: `{_format_cost(summary.estimated_cost_usd)}`",
        "",
        "## Summary",
        "",
        (
            "| Runtime | Planner | Context | Patch Generated | Targeted Tests Passed | "
            "Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | Failed Trace Events | "
            "Avg Retries | Debug Score | Input Tokens | Output Tokens | Est Cost |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| "
        f"{summary.runtime} | "
        f"{summary.planner} | "
        f"{summary.context_provider} | "
        f"{summary.patch_generated_rate:.2f} | "
        f"{summary.targeted_test_pass_rate:.2f} | "
        f"{summary.avg_latency_ms:.0f} | "
        f"{summary.avg_trace_events:.1f} | "
        f"{summary.avg_runtime_nodes:.1f} | "
        f"{summary.failed_trace_event_count} | "
        f"{summary.avg_retry_events:.1f} | "
        f"{summary.avg_debuggability_score:.1f} | "
        f"{summary.input_tokens if summary.input_tokens is not None else ''} | "
        f"{summary.output_tokens if summary.output_tokens is not None else ''} | "
        f"{_format_cost(summary.estimated_cost_usd)} |",
        "",
        "## Per-Task Results",
        "",
        (
            "| Task | Planner | Model Provider | Status | Patch Generated | Tests Passed | "
            "Exit Code | Trace Events | Runtime Nodes | Failed Trace Events | Retries | "
            "Debug Score | Tokens | Est Cost | Retrieved Files | Report | Error |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.planner} | "
            f"{result.model_provider or ''} | "
            f"{result.status} | "
            f"{int(result.patch_generated)} | "
            f"{int(result.targeted_tests_passed)} | "
            f"{result.test_exit_code if result.test_exit_code is not None else ''} | "
            f"{result.trace_event_count} | "
            f"{result.runtime_node_count} | "
            f"{result.failed_trace_event_count} | "
            f"{result.retry_event_count} | "
            f"{result.debuggability_score:.1f} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{result.report_path or ''} | "
            f"{(result.error or '').replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures seeded-task patch smoke behavior.",
            (
                "- Heuristic and fake-model planners should not be presented as autonomous "
                "coding-agent quality."
            ),
            (
                "- Use this runner to validate artifacts and gates before enabling a live "
                "model provider."
            ),
            "- Estimated cost is reported only when provider usage and configured rates exist.",
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "",
        ]
    )
    if summary.runtime == "deepagents":
        if _is_live_model_provider(summary.model_provider):
            lines.insert(
                -1,
                (
                    "- The `deepagents` runtime row includes live model-provider "
                    f"evidence (`{summary.model_provider}`) with token and cost "
                    "metadata when reported; it is still seeded-task smoke evidence, "
                    "not broad production repair quality."
                ),
            )
        else:
            lines.insert(
                -1,
                (
                    "- The `deepagents` runtime row is dependency-gated adapter evidence; "
                    "local runs use offline compatibility mode unless the optional "
                    "`deepagents` extra and live model provider are configured."
                ),
            )
    if summary.runtime == "openai_agents":
        lines.insert(
            -1,
            (
                "- The `openai_agents` runtime row is dependency-gated adapter evidence; "
                "local runs use offline compatibility mode unless the optional "
                "`openai-agents` extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def _is_live_model_provider(provider: str | None) -> bool:
    return bool(provider and not provider.startswith("offline_"))


def render_scaffold_comparison_report(
    *,
    dataset_dir: Path,
    results: list[ScaffoldComparisonResult],
) -> str:
    lines = [
        "# Scaffold Comparison Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Scaffold count: `{len(results)}`",
        f"- Model cost: `{_format_cost(_sum_optional_float(result.estimated_cost_usd for result in results))}`",
        "",
        "## Summary",
        "",
        (
            "| Scaffold | Runtime | Planner | Context | Completed | Patch Generated | "
            "Targeted Tests Passed | Avg Latency ms | Avg Trace Events | Avg Runtime Nodes | "
            "Failed Trace Events | Avg Retries | Debug Score | Model Provider | Tokens | Est Cost | Repair Report |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.scaffold} | "
            f"{result.runtime} | "
            f"{result.planner} | "
            f"{result.context_provider} | "
            f"{result.completed_tasks}/{result.attempted_tasks} | "
            f"{result.patch_generated_rate:.2f} | "
            f"{result.targeted_test_pass_rate:.2f} | "
            f"{result.avg_latency_ms:.0f} | "
            f"{result.avg_trace_events:.1f} | "
            f"{result.avg_runtime_nodes:.1f} | "
            f"{result.failed_trace_event_count} | "
            f"{result.avg_retry_events:.1f} | "
            f"{result.avg_debuggability_score:.1f} | "
            f"{result.model_provider or ''} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{result.repair_report_path} |"
        )

    best_resolved = max((result.targeted_test_pass_rate for result in results), default=0.0)
    best_scaffolds = [
        result.scaffold for result in results if result.targeted_test_pass_rate == best_resolved
    ]
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            (
                f"- Best targeted-test pass rate in this run: `{best_resolved:.2f}` "
                f"from `{', '.join(best_scaffolds) or 'none'}`."
            ),
            "- Agentless is the no-edit baseline and should not be treated as a repair scaffold.",
            (
                "- Heuristic and fake-model planners are deterministic seeded-task baselines; "
                "they do not prove autonomous coding-agent quality."
            ),
            (
                "- Debug score is a 0-5 trace-completeness heuristic: trace, context, "
                "runtime-node, test, and repair-outcome visibility."
            ),
            "- Compare repair report traces before making a default-runtime decision.",
            "",
        ]
    )
    if any(result.scaffold == "deepagents" for result in results):
        lines.insert(
            -1,
            (
                "- The `deepagents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `deepagents` "
                "extra and live model provider are configured."
            ),
        )
    if any(result.scaffold == "openai_agents" for result in results):
        lines.insert(
            -1,
            (
                "- The `openai_agents` row is dependency-gated adapter evidence; local "
                "runs use offline compatibility mode unless the optional `openai-agents` "
                "extra and live model provider are configured."
            ),
        )
    return "\n".join(lines)


def render_patch_search_eval_report(
    *,
    dataset_dir: Path,
    results: list[PatchSearchEvalResult],
    summaries: list[PatchSearchEvalSummary],
) -> str:
    lines = [
        "# Patch Search Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Variant count: `{len(summaries)}`",
        "- Model cost: `$0.00` (deterministic candidate generation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Variant | Candidates | Attempted | Completed | Success@1 | Success@k | "
            "Selected Success | Avg Latency ms | Avg Test Runs | Est Cost |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.variant} | "
            f"{summary.candidate_count} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.success_at_1_rate:.2f} | "
            f"{summary.success_at_k_rate:.2f} | "
            f"{summary.selected_success_rate:.2f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.avg_test_runs:.1f} | "
            f"{_format_cost(summary.estimated_cost_usd)} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Variant | Status | Success@1 | Success@k | Selected Candidate | "
                "Selected Passed | Test Runs | Latency ms | Error |"
            ),
            "|---|---|---|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for result in results:
        selected = (
            f"{result.selected_candidate_index}:{result.selected_candidate_name}"
            if result.selected_candidate_index is not None
            else "none"
        )
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.variant} | "
            f"{result.status} | "
            f"{int(result.success_at_1)} | "
            f"{int(result.success_at_k)} | "
            f"{selected} | "
            f"{int(result.selected_candidate_passed)} | "
            f"{result.test_runs} | "
            f"{result.latency_ms} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures deterministic patch-search infrastructure, not model diversity.",
            "- Each candidate is applied and tested in an isolated copy of the task repository.",
            "- The selector chooses the first candidate whose targeted tests pass.",
            "- Cost is zero because this lane currently uses heuristic candidate generation.",
            "",
        ]
    )
    return "\n".join(lines)
