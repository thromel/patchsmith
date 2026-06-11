from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation_models import (
    RetrievalEvalResult,
    RetrievalEvalSummary,
    SeededDatasetValidationSummary,
    SeededTaskValidationResult,
)


def render_retrieval_eval_report(
    *,
    dataset_dir: Path,
    results: list[RetrievalEvalResult],
    summaries: list[RetrievalEvalSummary],
) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{len({result.task_id for result in results})}`",
        f"- Lane count: `{len({result.context_provider for result in results})}`",
        "- Model cost: `$0.00` (retrieval-only evaluation; no model calls)",
        "",
        "## Summary",
        "",
        (
            "| Provider | Attempted | Completed | Top-1 | Top-3 | Top-5 | Related Tests | "
            "Avg Ctx | Avg Src | Avg Test | Avg Tokens | Avg Latency ms | Fallbacks | "
            "Source-Free Violations |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.provider} | "
            f"{summary.attempted_tasks} | "
            f"{summary.completed_tasks} | "
            f"{summary.avg_top1_touched_recall:.2f} | "
            f"{summary.avg_top3_touched_recall:.2f} | "
            f"{summary.avg_top5_touched_recall:.2f} | "
            f"{summary.avg_related_test_recall:.2f} | "
            f"{summary.avg_context_count:.1f} | "
            f"{summary.avg_source_context_count:.1f} | "
            f"{summary.avg_test_context_count:.1f} | "
            f"{summary.avg_context_approx_tokens:.0f} | "
            f"{summary.avg_latency_ms:.0f} | "
            f"{summary.fallback_count} | "
            f"{summary.source_free_violation_count} |"
        )

    lines.extend(
        [
            "",
            "## Per-Task Results",
            "",
            (
                "| Task | Provider | Status | Top-1 | Top-3 | Top-5 | Related Tests | "
                "Ctx | Tokens | Retrieved Files | Error |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"{result.task_id} | "
            f"{result.context_provider} | "
            f"{result.status} | "
            f"{result.top1_touched_recall:.2f} | "
            f"{result.top3_touched_recall:.2f} | "
            f"{result.top5_touched_recall:.2f} | "
            f"{result.related_test_recall:.2f} | "
            f"{result.context_count} | "
            f"{result.context_approx_tokens} | "
            f"{', '.join(result.retrieved_files) or 'none'} | "
            f"{(result.error or '').replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- This report measures localization evidence only; it does not claim patch success.",
            "- Context providers are compared under the same task and repository snapshot.",
            "- Context token counts are approximate and use packed excerpt characters, not a model-specific tokenizer.",
            "- Source-bearing raw artifacts are kept under the experiment output directory and not copied into this public summary.",
            "",
        ]
    )
    return "\n".join(lines)


def render_seeded_dataset_validation_report(
    *,
    dataset_dir: Path,
    results: list[SeededTaskValidationResult],
    summary: SeededDatasetValidationSummary,
) -> str:
    lines = [
        "# Seeded Dataset Validation Report",
        "",
        f"- Dataset: `{dataset_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Valid tasks: `{summary.valid_tasks}`",
        f"- Invalid tasks: `{summary.invalid_tasks}`",
        f"- Error count: `{summary.error_count}`",
        f"- Warning count: `{summary.warning_count}`",
        (
            f"- Duplicate task IDs: `{', '.join(summary.duplicate_task_ids)}`"
            if summary.duplicate_task_ids
            else "- Duplicate task IDs: `none`"
        ),
        "",
        "## Results",
        "",
        "| Task | Status | Errors | Warnings | Expected Source | Expected Tests |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.task_id or result.task_dir} | "
            f"{result.status} | "
            f"{'; '.join(result.errors) or 'none'} | "
            f"{'; '.join(result.warnings) or 'none'} | "
            f"{', '.join(result.expected_touched_files) or 'none'} | "
            f"{', '.join(result.expected_related_tests) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            (
                "- Dataset validation checks metadata shape, required files, non-empty "
                "issues, and expected paths."
            ),
            (
                "- A valid dataset is required before retrieval or repair eval metrics are "
                "release evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)
