"""Markdown rendering for complex benchmark summaries."""

from __future__ import annotations

import shlex
from pathlib import Path

from patchsmith.evaluation.complex.followups import (
    complex_followup_candidates as _followup_candidates,
)
from patchsmith.evaluation.complex.selection import select_attempts as _select_attempts
from patchsmith.evaluation_models import (
    ComplexBenchmarkFollowupCandidate,
    ComplexBenchmarkResult,
    ComplexBenchmarkSelection,
    ComplexBenchmarkSummary,
)
from patchsmith.public_issue_report_helpers import _markdown_table_text

__all__ = [
    "render_complex_benchmark_report",
    "render_complex_benchmark_suite_report",
    "render_complex_followup_runbook",
]


def render_complex_followup_runbook(
    followup_candidates: list[ComplexBenchmarkFollowupCandidate],
) -> str:
    lines = [
        "# Complex Benchmark Follow-up Runbook",
        "",
        "This runbook is generated from saved complex benchmark artifacts. It does not run repairs, execute tests, or call model providers.",
        "",
    ]
    if not followup_candidates:
        lines.extend(
            [
                "No follow-up candidates were selected from the saved artifacts.",
                "",
                "## Claim Boundary",
                "",
                "- A clean runbook means there were no rule-selected follow-up rows, not that the benchmark is complete.",
                "- Live LLM claims still require non-offline provider metadata in saved traces.",
                "",
            ]
        )
        return "\n".join(lines)

    for index, candidate in enumerate(followup_candidates, start=1):
        lines.extend(
            [
                f"## {index}. {candidate.task_id}",
                "",
                f"- Action: `{candidate.action}`",
                f"- Suggested profile: `{candidate.suggested_profile}`",
                f"- Priority: `{candidate.priority}`",
                f"- Reasons: `{', '.join(candidate.reasons) or 'none'}`",
                f"- Strict status: `{candidate.strict_status}`",
                f"- Failure class: `{candidate.failure_class}`",
                f"- Harness layer: `{candidate.harness_layer}`",
                f"- Process quality: `{candidate.process_quality_label}`",
                f"- Responses: `{candidate.response_count if candidate.response_count is not None else 'n/a'}`",
                f"- Tokens: `{candidate.total_tokens if candidate.total_tokens is not None else 'n/a'}`",
                f"- Estimated cost: `{_format_cost(candidate.estimated_cost_usd)}`",
                "",
                "### Required Environment",
                "",
                "```bash",
                *[
                    f"export {key}={shlex.quote(value)}"
                    for key, value in sorted(candidate.recommended_env.items())
                ],
                "```",
                "",
                "### Live Run",
                "",
                "```bash",
                _shell_command(candidate.recommended_command),
                "```",
                "",
                "### Validation",
                "",
                "```bash",
                _shell_command(candidate.validation_command),
                "```",
                "",
                "### Success Criteria",
                "",
            ]
        )
        lines.extend(f"- `{criterion}`" for criterion in candidate.success_criteria)
        if candidate.report_path:
            lines.extend(["", f"Source report: `{candidate.report_path}`"])
        if candidate.trace_path:
            lines.append(f"Source trace: `{candidate.trace_path}`")
        lines.append("")

    lines.extend(
        [
            "## Claim Boundary",
            "",
            "- These commands are deterministic recommendations from saved artifacts; they are not live evidence until executed.",
            "- Treat a follow-up as successful only after the validation command passes on the newly generated artifacts.",
            "- Keep provider keys out of committed files and pass them through the environment.",
            "",
        ]
    )
    return "\n".join(lines)


def render_complex_benchmark_suite_report(
    *,
    attempt_summaries: list[ComplexBenchmarkSummary],
    aggregate_summary: ComplexBenchmarkSummary,
    followup_candidates: list[ComplexBenchmarkFollowupCandidate] | None = None,
) -> str:
    ranked_followups = list(followup_candidates or [])
    lines = [
        "# Complex Benchmark Suite Report",
        "",
        f"- Benchmark: `{aggregate_summary.benchmark}`",
        f"- Attempt directories: `{len(attempt_summaries)}`",
        f"- Task rows: `{aggregate_summary.task_count}`",
        f"- Unique tasks: `{aggregate_summary.unique_task_count}`",
        f"- Attempted tasks: `{aggregate_summary.attempted_tasks}`",
        f"- Validated tasks: `{aggregate_summary.validated_tasks}`",
        f"- Validation rate: `{aggregate_summary.validation_rate:.2f}`",
        f"- Validated task pass@N rate: `{aggregate_summary.validated_task_pass_at_n_rate:.2f}`",
        f"- Average progress score: `{aggregate_summary.avg_progress_score:.2f}`",
        f"- Selected progress score: `{aggregate_summary.selected_avg_progress_score:.2f}`",
        f"- Partial-progress failed tasks: `{aggregate_summary.partial_progress_tasks}`",
        f"- Failure class counts: `{_format_label_counts(aggregate_summary.failure_class_counts)}`",
        f"- Selected failure class counts: `{_format_label_counts(aggregate_summary.selected_failure_class_counts)}`",
        f"- Harness layer counts: `{_format_label_counts(aggregate_summary.harness_layer_counts)}`",
        f"- Selected harness layer counts: `{_format_label_counts(aggregate_summary.selected_harness_layer_counts)}`",
        f"- Live-provider tasks: `{aggregate_summary.live_provider_tasks}`",
        f"- Model provider: `{aggregate_summary.model_provider or 'n/a'}`",
        f"- Model responses: `{aggregate_summary.response_count if aggregate_summary.response_count is not None else 'n/a'}`",
        f"- Total tokens: `{aggregate_summary.total_tokens if aggregate_summary.total_tokens is not None else 'n/a'}`",
        f"- Estimated model cost: `{_format_cost(aggregate_summary.estimated_cost_usd)}`",
        f"- Live cost-budgeted tasks: `{aggregate_summary.live_cost_budgeted_tasks}`",
        f"- Live cost budget overage tasks: `{aggregate_summary.live_cost_budget_overage_tasks}`",
        f"- Max live cost budget overage: `{_format_cost(aggregate_summary.max_live_cost_budget_overage_usd)}`",
        f"- Selected cost per validated task: `{_format_cost(aggregate_summary.selected_cost_per_validated_task_usd)}`",
        f"- Selected tokens per validated task: `{_format_number(aggregate_summary.selected_tokens_per_validated_task)}`",
        f"- Selected responses per validated task: `{_format_number(aggregate_summary.selected_responses_per_validated_task)}`",
        f"- Selected virtual files: `{aggregate_summary.selected_virtual_file_count if aggregate_summary.selected_virtual_file_count is not None else 'n/a'}`",
        f"- Selected virtual files per validated task: `{_format_number(aggregate_summary.selected_virtual_files_per_validated_task)}`",
        f"- Selected tokens per virtual file: `{_format_number(aggregate_summary.selected_tokens_per_virtual_file)}`",
        f"- Selected responses per virtual file: `{_format_number(aggregate_summary.selected_responses_per_virtual_file)}`",
        f"- Selected context-target available tasks: `{aggregate_summary.selected_context_target_available_tasks}`",
        f"- Selected context-target covered tasks: `{aggregate_summary.selected_context_target_covered_tasks}`",
        f"- Selected context-target recall: `{_format_number(aggregate_summary.selected_context_target_recall)}`",
        f"- Selected context-target precision: `{_format_number(aggregate_summary.selected_context_target_precision)}`",
        f"- Max attempted task cost: `{_format_cost(aggregate_summary.max_attempted_task_cost_usd)}`",
        f"- Max attempted task tokens: `{aggregate_summary.max_attempted_task_tokens if aggregate_summary.max_attempted_task_tokens is not None else 'n/a'}`",
        f"- Max attempted task responses: `{aggregate_summary.max_attempted_task_responses if aggregate_summary.max_attempted_task_responses is not None else 'n/a'}`",
        f"- Max selected task cost: `{_format_cost(aggregate_summary.max_selected_task_cost_usd)}`",
        f"- Max selected task tokens: `{aggregate_summary.max_selected_task_tokens if aggregate_summary.max_selected_task_tokens is not None else 'n/a'}`",
        f"- Max selected task responses: `{aggregate_summary.max_selected_task_responses if aggregate_summary.max_selected_task_responses is not None else 'n/a'}`",
        f"- Average DeepAgents virtual files: `{aggregate_summary.avg_deepagents_virtual_file_count:.2f}`",
        f"- Context-budgeted tasks: `{aggregate_summary.context_budgeted_tasks}`",
        f"- Repo-instructions manifest tasks: `{aggregate_summary.repo_instructions_manifest_tasks}`",
        f"- Repo-instructions read-first rate: `{aggregate_summary.repo_instructions_read_first_rate:.2f}`",
        f"- Resource-budgeted tasks: `{aggregate_summary.resource_budgeted_tasks}`",
        f"- Resource-budget read-first rate: `{aggregate_summary.resource_budget_read_first_rate:.2f}`",
        f"- Average resource response cap: `{aggregate_summary.avg_resource_budget_max_model_responses:.2f}`",
        f"- Average resource token cap: `{aggregate_summary.avg_resource_budget_max_model_tokens:.2f}`",
        f"- Average agent trajectory: `{aggregate_summary.avg_agent_trajectory_score:.2f}`",
        f"- Average process quality: `{aggregate_summary.avg_process_quality_score:.2f}`",
        f"- Process quality labels: `{_format_label_counts(aggregate_summary.process_quality_label_counts)}`",
        f"- Process quality flags: `{_format_label_counts(aggregate_summary.process_quality_flag_counts)}`",
        f"- Process-risky validated tasks: `{aggregate_summary.process_risky_validated_tasks}`",
        f"- Target alignment rate: `{aggregate_summary.target_alignment_rate:.2f}`",
        f"- Target alignment available tasks: `{aggregate_summary.target_alignment_available_tasks}`",
        f"- Retry label counts: `{_format_label_counts(aggregate_summary.retry_label_counts)}`",
        f"- Retry failure class counts: `{_format_label_counts(aggregate_summary.retry_failure_class_counts)}`",
        "",
        "## Attempt Directories",
        "",
        (
            "| Attempt Directory | Tasks | Attempted | Validated | Validation | Pass@N | "
            "Progress | Failure Classes | Selected Failure Classes | Harness Layers | Selected Harness Layers | Retry Failure Classes | Process Quality | Process Flags | Provider | Responses | Tokens | Cost | Cost/Validated | Virtual Files | Budgeted | "
            "Cost Overage Tasks | Max Cost Overage | Trajectory | Target Alignment |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in attempt_summaries:
        lines.append(
            "| "
            f"{_markdown_table_text(summary.attempt_dir)} | "
            f"{summary.task_count} | "
            f"{summary.attempted_tasks} | "
            f"{summary.validated_tasks} | "
            f"{summary.validation_rate:.2f} | "
            f"{summary.validated_task_pass_at_n_rate:.2f} | "
            f"{summary.selected_avg_progress_score:.2f} | "
            f"{_markdown_table_text(_format_label_counts(summary.failure_class_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.selected_failure_class_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.harness_layer_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.selected_harness_layer_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.retry_failure_class_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.process_quality_label_counts))} | "
            f"{_markdown_table_text(_format_label_counts(summary.process_quality_flag_counts))} | "
            f"{_markdown_table_text(summary.model_provider or 'n/a')} | "
            f"{summary.response_count if summary.response_count is not None else ''} | "
            f"{summary.total_tokens if summary.total_tokens is not None else ''} | "
            f"{_format_cost(summary.estimated_cost_usd)} | "
            f"{_format_cost(summary.selected_cost_per_validated_task_usd)} | "
            f"{summary.avg_deepagents_virtual_file_count:.2f} | "
            f"{summary.context_budgeted_tasks} | "
            f"{summary.live_cost_budget_overage_tasks} | "
            f"{_format_cost(summary.max_live_cost_budget_overage_usd)} | "
            f"{summary.avg_agent_trajectory_score:.2f} | "
            f"{summary.target_alignment_rate:.2f} |"
        )
    if ranked_followups:
        lines.extend(
            [
                "",
                "## Follow-up Candidates",
                "",
                (
                    "| Task | Attempt | Action | Profile | Priority | Reasons | Strict Status | Failure Class | "
                    "Harness Layer | Process Quality | Retry Failures | Responses | Tokens | Cost | Report |"
                ),
                "|---|---|---|---|---:|---|---|---|---|---|---|---:|---:|---:|---|",
            ]
        )
        for candidate in ranked_followups:
            lines.append(
                "| "
                f"{_markdown_table_text(candidate.task_id)} | "
                f"{_markdown_table_text(f'{candidate.attempt_index}/{candidate.attempt_count}')} | "
                f"{_markdown_table_text(candidate.action)} | "
                f"{_markdown_table_text(candidate.suggested_profile)} | "
                f"{candidate.priority} | "
                f"{_markdown_table_text(','.join(candidate.reasons))} | "
                f"{_markdown_table_text(candidate.strict_status)} | "
                f"{_markdown_table_text(candidate.failure_class)} | "
                f"{_markdown_table_text(candidate.harness_layer)} | "
                f"{_markdown_table_text(candidate.process_quality_label)} | "
                f"{_markdown_table_text(','.join(candidate.retry_failure_classes))} | "
                f"{candidate.response_count if candidate.response_count is not None else ''} | "
                f"{candidate.total_tokens if candidate.total_tokens is not None else ''} | "
                f"{_format_cost(candidate.estimated_cost_usd)} | "
                f"{_markdown_table_text(candidate.report_path or '')} |"
            )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This suite aggregates saved complex benchmark artifacts; it does not run repairs or call model providers.",
            "- Aggregate validation and cost metrics are computed from the saved per-attempt traces and strict quality-gated statuses.",
            "- Failure classes are deterministic artifact labels for benchmark triage, not human root-cause annotations.",
            "- Live cost budget overage compares actual saved model cost against the configured preflight `max_live_cost_usd`; it is a post-run signal, not a spend prevention mechanism.",
            "- Duplicate task IDs across attempt directories are treated as repeat evidence for pass@N and selected-attempt accounting.",
            "- Follow-up candidates are deterministic saved-artifact rows worth rerunning or inspecting before the next live A/B lane; action/profile recommendations are rule-based from strict status, harness layer, process risk, retry failures, target alignment, and spend.",
            "- Live LLM claims still require non-offline provider metadata in the saved traces.",
            "",
        ]
    )
    return "\n".join(lines)


def render_complex_benchmark_report(
    *,
    attempt_dir: Path,
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection] | None = None,
    followup_candidates: list[ComplexBenchmarkFollowupCandidate] | None = None,
    summary: ComplexBenchmarkSummary,
) -> str:
    selected_attempts = list(selections or _select_attempts(results))
    ranked_followups = list(followup_candidates or _followup_candidates(results))
    lines = [
        "# Complex Benchmark Report",
        "",
        f"- Benchmark: `{summary.benchmark}`",
        f"- Attempt artifacts: `{attempt_dir}`",
        f"- Task count: `{summary.task_count}`",
        f"- Unique task count: `{summary.unique_task_count}`",
        f"- Repeat count: `{summary.repeat_count}`",
        f"- Attempted tasks: `{summary.attempted_tasks}`",
        f"- Unique attempted tasks: `{summary.unique_attempted_tasks}`",
        f"- Reproduced input tasks: `{summary.reproduced_tasks}`",
        f"- Validated tasks: `{summary.validated_tasks}`",
        f"- Failed tasks: `{summary.failed_tasks}`",
        f"- Blocked tasks: `{summary.blocked_tasks}`",
        f"- Preflight passed tasks: `{summary.preflight_passed_tasks}`",
        f"- Preflight skipped tasks: `{summary.preflight_skipped_tasks}`",
        f"- Preflight blocked tasks: `{summary.preflight_blocked_tasks}`",
        f"- Sandbox preflight blocked tasks: `{summary.sandbox_preflight_blocked_tasks}`",
        f"- Model preflight blocked tasks: `{summary.model_preflight_blocked_tasks}`",
        f"- Budget preflight blocked tasks: `{summary.budget_preflight_blocked_tasks}`",
        f"- Patch generated rate: `{summary.patch_generated_rate:.2f}`",
        f"- Validation rate: `{summary.validation_rate:.2f}`",
        f"- Average progress score: `{summary.avg_progress_score:.2f}`",
        f"- Selected progress score: `{summary.selected_avg_progress_score:.2f}`",
        f"- Partial-progress failed tasks: `{summary.partial_progress_tasks}`",
        f"- Failure class counts: `{_format_label_counts(summary.failure_class_counts)}`",
        f"- Selected failure class counts: `{_format_label_counts(summary.selected_failure_class_counts)}`",
        f"- Harness layer counts: `{_format_label_counts(summary.harness_layer_counts)}`",
        f"- Selected harness layer counts: `{_format_label_counts(summary.selected_harness_layer_counts)}`",
        f"- Tasks with validated attempt: `{summary.tasks_with_validated_attempt}`",
        f"- Tasks with failed attempts only: `{summary.tasks_with_failed_attempts_only}`",
        f"- Validated task pass@N rate: `{summary.validated_task_pass_at_n_rate:.2f}`",
        f"- Selected attempts: `{summary.selected_attempt_count}`",
        f"- Selected validated tasks: `{summary.selected_validated_tasks}`",
        f"- Selected validation rate: `{summary.selected_validation_rate:.2f}`",
        f"- Selected model cost: `{_format_cost(summary.selected_estimated_cost_usd)}`",
        f"- Live-provider tasks: `{summary.live_provider_tasks}`",
        f"- Model provider: `{summary.model_provider or 'n/a'}`",
        f"- Model responses: `{summary.response_count if summary.response_count is not None else 'n/a'}`",
        f"- Total tokens: `{summary.total_tokens if summary.total_tokens is not None else 'n/a'}`",
        f"- Estimated model cost: `{_format_cost(summary.estimated_cost_usd)}`",
        f"- Live cost-budgeted tasks: `{summary.live_cost_budgeted_tasks}`",
        f"- Live cost budget overage tasks: `{summary.live_cost_budget_overage_tasks}`",
        f"- Max live cost budget overage: `{_format_cost(summary.max_live_cost_budget_overage_usd)}`",
        f"- Attempted cost per validated task: `{_format_cost(summary.attempted_cost_per_validated_task_usd)}`",
        f"- Attempted tokens per validated task: `{_format_number(summary.attempted_tokens_per_validated_task)}`",
        f"- Attempted responses per validated task: `{_format_number(summary.attempted_responses_per_validated_task)}`",
        f"- Selected cost per validated task: `{_format_cost(summary.selected_cost_per_validated_task_usd)}`",
        f"- Selected tokens per validated task: `{_format_number(summary.selected_tokens_per_validated_task)}`",
        f"- Selected responses per validated task: `{_format_number(summary.selected_responses_per_validated_task)}`",
        f"- Selected virtual files: `{summary.selected_virtual_file_count if summary.selected_virtual_file_count is not None else 'n/a'}`",
        f"- Selected virtual files per validated task: `{_format_number(summary.selected_virtual_files_per_validated_task)}`",
        f"- Selected tokens per virtual file: `{_format_number(summary.selected_tokens_per_virtual_file)}`",
        f"- Selected responses per virtual file: `{_format_number(summary.selected_responses_per_virtual_file)}`",
        f"- Selected context-target available tasks: `{summary.selected_context_target_available_tasks}`",
        f"- Selected context-target covered tasks: `{summary.selected_context_target_covered_tasks}`",
        f"- Selected context-target recall: `{_format_number(summary.selected_context_target_recall)}`",
        f"- Selected context-target precision: `{_format_number(summary.selected_context_target_precision)}`",
        f"- Max attempted task cost: `{_format_cost(summary.max_attempted_task_cost_usd)}`",
        f"- Max attempted task tokens: `{summary.max_attempted_task_tokens if summary.max_attempted_task_tokens is not None else 'n/a'}`",
        f"- Max attempted task responses: `{summary.max_attempted_task_responses if summary.max_attempted_task_responses is not None else 'n/a'}`",
        f"- Max selected task cost: `{_format_cost(summary.max_selected_task_cost_usd)}`",
        f"- Max selected task tokens: `{summary.max_selected_task_tokens if summary.max_selected_task_tokens is not None else 'n/a'}`",
        f"- Max selected task responses: `{summary.max_selected_task_responses if summary.max_selected_task_responses is not None else 'n/a'}`",
        f"- Average DeepAgents virtual files: `{summary.avg_deepagents_virtual_file_count:.2f}`",
        f"- Context-budgeted tasks: `{summary.context_budgeted_tasks}`",
        f"- Context-budget manifest tasks: `{summary.context_budget_manifest_tasks}`",
        f"- Context-budget omitted files: `{summary.context_budget_omitted_file_count}`",
        f"- Average context-budget omitted files: `{summary.avg_context_budget_omitted_files:.2f}`",
        f"- Repo-map manifest tasks: `{summary.repo_map_manifest_tasks}`",
        f"- Repo-instructions manifest tasks: `{summary.repo_instructions_manifest_tasks}`",
        f"- Repo-instructions read-first rate: `{summary.repo_instructions_read_first_rate:.2f}`",
        f"- Acceptance-rubric manifest tasks: `{summary.acceptance_rubric_manifest_tasks}`",
        f"- Acceptance-rubric read-first rate: `{summary.acceptance_rubric_read_first_rate:.2f}`",
        f"- Acceptance-rubric aligned tasks: `{summary.acceptance_rubric_aligned_tasks}`",
        f"- Acceptance-rubric alignment rate: `{summary.acceptance_rubric_alignment_rate:.2f}`",
        f"- Repair-interface manifest tasks: `{summary.repair_interface_manifest_tasks}`",
        f"- Repair-interface read-first rate: `{summary.repair_interface_read_first_rate:.2f}`",
        f"- Average DeepAgents context cap: `{summary.avg_deepagents_max_context_files:.2f}`",
        f"- Resource-budgeted tasks: `{summary.resource_budgeted_tasks}`",
        f"- Resource-budget read-first rate: `{summary.resource_budget_read_first_rate:.2f}`",
        f"- Average resource response cap: `{summary.avg_resource_budget_max_model_responses:.2f}`",
        f"- Average resource token cap: `{summary.avg_resource_budget_max_model_tokens:.2f}`",
        f"- Average agent trajectory: `{summary.avg_agent_trajectory_score:.2f}`",
        f"- Todo planning rate: `{summary.todo_planning_rate:.2f}`",
        f"- Constrained filesystem rate: `{summary.constrained_filesystem_rate:.2f}`",
        f"- Specialist review rate: `{summary.specialist_review_rate:.2f}`",
        f"- Guardrails rate: `{summary.guardrails_rate:.2f}`",
        f"- Structured output rate: `{summary.structured_output_rate:.2f}`",
        f"- Retry feedback rate: `{summary.retry_feedback_rate:.2f}`",
        f"- Patch diagnostics rate: `{summary.patch_diagnostics_rate:.2f}`",
        f"- Contextual verifier rate: `{summary.contextual_verifier_rate:.2f}`",
        f"- Average process quality: `{summary.avg_process_quality_score:.2f}`",
        f"- Process quality labels: `{_format_label_counts(summary.process_quality_label_counts)}`",
        f"- Process quality flags: `{_format_label_counts(summary.process_quality_flag_counts)}`",
        f"- Process-risky validated tasks: `{summary.process_risky_validated_tasks}`",
        f"- Target alignment available tasks: `{summary.target_alignment_available_tasks}`",
        f"- Target aligned tasks: `{summary.target_aligned_tasks}`",
        f"- Target misaligned tasks: `{summary.target_misaligned_tasks}`",
        f"- Target alignment rate: `{summary.target_alignment_rate:.2f}`",
        f"- Retry feedback artifact tasks: `{summary.retry_feedback_artifact_tasks}`",
        f"- Retry feedback artifacts: `{summary.retry_feedback_artifact_count}`",
        f"- Retry label counts: `{_format_label_counts(summary.retry_label_counts)}`",
        f"- Retry failure class counts: `{_format_label_counts(summary.retry_failure_class_counts)}`",
        f"- Quality warning tasks: `{summary.quality_warning_tasks}`",
        f"- Quality warning rate: `{summary.quality_warning_rate:.2f}`",
        "",
        "## Results",
        "",
        (
            "| Task | Attempt | Raw Status | Strict Status | Repository | Runtime | Reproduced | Patch | Tests | "
            "Progress | Stage | Failure Class | Harness Layer | Preflight | Trace Events | Runtime Nodes | Retries | Retry Artifacts | "
            "Retry Labels | Retry Failure Classes | Quality | Quality Codes | Target Alignment | Patch Targets | Localized Targets | "
            "Virtual Files | Context Cap | Budget Manifest | Omitted Files | Repo Map | Repo Instructions | Acceptance Rubric | Rubric Aligned | Repair Interface | Resource Budget | Resource Read First | Response Cap | Token Cap | Agent Trajectory | Trajectory Signals | Process Quality | Process Flags | Provider | Responses | Tokens | Cost | Budget Cap | Budget Overage | Report |"
        ),
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---:|---:|---|---:|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{_markdown_table_text(result.task_id)} | "
            f"{_markdown_table_text(f'{result.attempt_index}/{result.attempt_count}')} | "
            f"{_markdown_table_text(result.status)} | "
            f"{_markdown_table_text(result.strict_status)} | "
            f"{_markdown_table_text(result.repository or 'unknown')} | "
            f"{_markdown_table_text(result.runtime + '/' + result.planner)} | "
            f"{_markdown_table_text(str(result.reproduced).lower())} | "
            f"{_markdown_table_text(str(result.patch_generated).lower())} | "
            f"{_markdown_table_text(str(result.validation_passed).lower())} | "
            f"{result.progress_score:.2f} | "
            f"{_markdown_table_text(result.progress_stage)} | "
            f"{_markdown_table_text(result.failure_class)} | "
            f"{_markdown_table_text(result.harness_layer)} | "
            f"{_markdown_table_text(_preflight_summary(result))} | "
            f"{result.trace_event_count} | "
            f"{result.runtime_node_count} | "
            f"{result.retry_event_count} | "
            f"{result.retry_feedback_artifact_count} | "
            f"{_markdown_table_text(','.join(result.retry_labels))} | "
            f"{_markdown_table_text(','.join(result.retry_failure_classes))} | "
            f"{_markdown_table_text(result.patch_quality_severity or '')} | "
            f"{_markdown_table_text(','.join(result.patch_quality_codes))} | "
            f"{_markdown_table_text(result.target_alignment_status)} | "
            f"{_markdown_table_text(','.join(result.patch_target_paths))} | "
            f"{_markdown_table_text(','.join(result.localized_target_paths))} | "
            f"{result.deepagents_virtual_file_count if result.deepagents_virtual_file_count is not None else ''} | "
            f"{result.deepagents_max_context_files if result.deepagents_max_context_files is not None else ''} | "
            f"{_markdown_table_text(result.deepagents_context_budget_manifest_path or '')} | "
            f"{result.deepagents_context_budget_omitted_file_count if result.deepagents_context_budget_omitted_file_count is not None else ''} | "
            f"{_markdown_table_text(result.deepagents_repo_map_manifest_path or '')} | "
            f"{_markdown_table_text(result.deepagents_repo_instructions_manifest_path or '')} | "
            f"{_markdown_table_text(result.deepagents_acceptance_rubric_manifest_path or '')} | "
            f"{_markdown_table_text(_optional_bool_text(result.deepagents_acceptance_rubric_aligned))} | "
            f"{_markdown_table_text(result.deepagents_repair_interface_manifest_path or '')} | "
            f"{_markdown_table_text(str(result.deepagents_resource_budgeted).lower())} | "
            f"{_markdown_table_text(str(result.deepagents_resource_budget_read_first).lower())} | "
            f"{result.deepagents_resource_budget_max_model_responses if result.deepagents_resource_budget_max_model_responses is not None else ''} | "
            f"{result.deepagents_resource_budget_max_model_tokens if result.deepagents_resource_budget_max_model_tokens is not None else ''} | "
            f"{result.agent_trajectory_score:.2f} | "
            f"{_markdown_table_text(_trajectory_signal_summary(result))} | "
            f"{_markdown_table_text(result.process_quality_label)} | "
            f"{_markdown_table_text(','.join(result.process_quality_flags))} | "
            f"{_markdown_table_text(result.model_provider or '')} | "
            f"{result.response_count if result.response_count is not None else ''} | "
            f"{result.total_tokens if result.total_tokens is not None else ''} | "
            f"{_format_cost(result.estimated_cost_usd)} | "
            f"{_format_cost(result.live_cost_budget_usd)} | "
            f"{_format_cost(result.live_cost_budget_overage_usd)} | "
            f"{_markdown_table_text(result.report_path or '')} |"
        )
    if selected_attempts:
        lines.extend(
            [
                "",
                "## Selected Attempts",
                "",
                (
                    "| Task | Selected Attempt | Raw Status | Strict Status | Tests | Quality | Quality Codes | Retries | "
                    "Progress | Stage | Failure Class | Responses | Tokens | Cost | Agent Trajectory | Selection Basis | Report |"
                ),
                "|---|---|---|---|---:|---|---|---:|---:|---|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for selection in selected_attempts:
            lines.append(
                "| "
                f"{_markdown_table_text(selection.task_id)} | "
                f"{_markdown_table_text(f'{selection.selected_attempt_index}/{selection.selected_attempt_count}')} | "
                f"{_markdown_table_text(selection.status)} | "
                f"{_markdown_table_text(selection.strict_status)} | "
                f"{_markdown_table_text(str(selection.validation_passed).lower())} | "
                f"{_markdown_table_text(selection.patch_quality_severity or '')} | "
                f"{_markdown_table_text(','.join(selection.patch_quality_codes))} | "
                f"{selection.retry_event_count} | "
                f"{selection.progress_score:.2f} | "
                f"{_markdown_table_text(selection.progress_stage)} | "
                f"{_markdown_table_text(selection.failure_class)} | "
                f"{selection.response_count if selection.response_count is not None else ''} | "
                f"{selection.total_tokens if selection.total_tokens is not None else ''} | "
                f"{_format_cost(selection.estimated_cost_usd)} | "
                f"{selection.agent_trajectory_score:.2f} | "
                f"{_markdown_table_text(selection.selection_reason)} | "
                f"{_markdown_table_text(selection.report_path or '')} |"
            )
    if ranked_followups:
        lines.extend(
            [
                "",
                "## Follow-up Candidates",
                "",
                (
                    "| Task | Attempt | Action | Profile | Priority | Reasons | Strict Status | Failure Class | "
                    "Harness Layer | Process Quality | Retry Failures | Responses | Tokens | Cost | Report |"
                ),
                "|---|---|---|---|---:|---|---|---|---|---|---|---:|---:|---:|---|",
            ]
        )
        for candidate in ranked_followups:
            lines.append(
                "| "
                f"{_markdown_table_text(candidate.task_id)} | "
                f"{_markdown_table_text(f'{candidate.attempt_index}/{candidate.attempt_count}')} | "
                f"{_markdown_table_text(candidate.action)} | "
                f"{_markdown_table_text(candidate.suggested_profile)} | "
                f"{candidate.priority} | "
                f"{_markdown_table_text(','.join(candidate.reasons))} | "
                f"{_markdown_table_text(candidate.strict_status)} | "
                f"{_markdown_table_text(candidate.failure_class)} | "
                f"{_markdown_table_text(candidate.harness_layer)} | "
                f"{_markdown_table_text(candidate.process_quality_label)} | "
                f"{_markdown_table_text(','.join(candidate.retry_failure_classes))} | "
                f"{candidate.response_count if candidate.response_count is not None else ''} | "
                f"{candidate.total_tokens if candidate.total_tokens is not None else ''} | "
                f"{_format_cost(candidate.estimated_cost_usd)} | "
                f"{_markdown_table_text(candidate.report_path or '')} |"
            )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This report summarizes completed public-issue repair-attempt artifacts.",
            "- It does not clone repositories, execute tests, or call a model provider.",
            "- `validated` means the saved repair-attempt validation command exited zero and final patch quality was not high-risk.",
            "- `raw status` preserves the saved attempt result; `strict status` applies the benchmark quality gate.",
            "- `failure class` is a deterministic artifact label for benchmark triage, not a human root-cause annotation.",
            "- `preflight` summarizes saved environment/model gates from the repair-attempt artifact; preflight-blocked rows were not model repair attempts.",
            "- Live cost budget overage compares actual saved model cost against the configured preflight `max_live_cost_usd`; it is a post-run signal, not a spend prevention mechanism.",
            "- Row-level validation rate counts repeated attempts separately using strict quality-gated validation.",
            "- Pass@N counts a unique task as validated when at least one repeated attempt is cleanly validated.",
            "- Selected attempts are chosen deterministically from saved evidence: strict validation first, then progress score, patch quality, target alignment, patch presence, retry count, failure trace count, cost, tokens, and trajectory.",
            "- Follow-up candidates are deterministic saved-artifact rows worth rerunning or inspecting before the next live A/B lane; action/profile recommendations are rule-based from strict status, harness layer, process risk, retry failures, target alignment, and spend.",
            "- Passing tests with high-risk final patch quality are reported as quality warnings and do not count as clean validation.",
            "- Live LLM quality claims require non-offline provider metadata in the saved traces.",
            "",
        ]
    )
    return "\n".join(lines)


def _shell_command(command: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _preflight_summary(result: ComplexBenchmarkResult) -> str:
    gates = result.preflight_gates or []
    if not gates:
        return result.preflight_status
    gate_summary = "; ".join(
        f"{gate.get('name', 'gate')}:{gate.get('status', 'unknown')}"
        for gate in gates
    )
    return f"{result.preflight_status} ({gate_summary})"


def _optional_bool_text(value: bool | None) -> str:
    if value is None:
        return ""
    return str(value).lower()


def _trajectory_signal_summary(result: ComplexBenchmarkResult) -> str:
    signals = [
        ("todo", result.todo_planning),
        ("filesystem", result.constrained_filesystem),
        ("review", result.specialist_review),
        ("guardrails", result.guardrails),
        ("structured", result.structured_output),
        ("retry", result.retry_feedback),
        ("diagnostics", result.patch_diagnostics),
        ("verifier", result.contextual_verifier),
    ]
    return ",".join(name for name, enabled in signals if enabled)


def _format_cost(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.6f}"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _format_label_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{label}={count}" for label, count in sorted(counts.items()))
