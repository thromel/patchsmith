from __future__ import annotations

from typing import Any

from patchsmith.analysis import RepairOutcomeAnalysis
from patchsmith.context_packing import summarize_context_pack
from patchsmith.models import (
    CommandResult,
    RepositorySnapshot,
    RetrievedContext,
    RunRequest,
    TraceEvent,
)


def render_run_report(
    *,
    run_id: str,
    request: RunRequest,
    snapshot: RepositorySnapshot,
    retrieved_context: list[RetrievedContext],
    test_result: CommandResult | None,
    final_diff: str,
    trace_events: list[TraceEvent],
    status: str,
    patch_status: str = "not_configured",
    patch_summary: str = "",
    repair_analysis: RepairOutcomeAnalysis | None = None,
) -> str:
    lines: list[str] = [
        "# PatchSmith Run Report",
        "",
        "## Summary",
        "",
        f"- Run ID: `{run_id}`",
        f"- Status: `{status}`",
        f"- Runtime: `{request.runtime}`",
        f"- Planner: `{request.planner}`",
        f"- Retrieval: `{request.retrieval_strategy}`",
        f"- Patch generation: `{patch_status}`",
        "",
        patch_summary
        or (
            "This MVP scaffold verifies ingestion, indexing, retrieval, command policy, "
            "test execution, trace capture, and report generation. Model-backed patch generation "
            "is intentionally left behind the runtime boundary for the next milestone."
        ),
        "",
        "## Input",
        "",
        f"- Repository: `{request.repo}`",
        f"- Issue URL: `{request.issue_url or 'n/a'}`",
        "",
        "```text",
        request.issue_text.strip(),
        "```",
        "",
        "## Repository Snapshot",
        "",
        f"- Commit: `{snapshot.commit_hash}`",
        f"- Branch: `{snapshot.branch or 'n/a'}`",
        f"- File count: `{snapshot.file_count}`",
        f"- Package manager: `{snapshot.package_manager or 'unknown'}`",
        f"- Candidate test commands: `{', '.join(snapshot.test_commands) or 'none'}`",
        f"- Language summary: `{snapshot.language_summary}`",
        "",
        "## Retrieved Context",
        "",
    ]

    if retrieved_context:
        packing = summarize_context_pack(retrieved_context)
        lines.extend(
            [
                "### Context Packing",
                "",
                f"- Context count: `{packing.context_count}`",
                f"- Source contexts: `{packing.source_context_count}`",
                f"- Test contexts: `{packing.test_context_count}`",
                f"- Excerpt characters: `{packing.excerpt_char_count}`",
                f"- Approximate tokens: `{packing.approx_token_count}`",
                f"- Methods: `{packing.method_counts}`",
                "",
            ]
        )
        for context in retrieved_context:
            lines.extend(
                [
                    f"### {context.rank}. `{context.path}`",
                    "",
                    f"- Method: `{context.method}`",
                    f"- Score: `{context.score:.2f}`",
                    f"- Matched terms: `{', '.join(context.matched_terms) or 'none'}`",
                    "",
                    "```text",
                    context.excerpt.strip(),
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["No retrieved context.", ""])

    lines.extend(["## Test Results", ""])
    if test_result:
        lines.extend(
            [
                f"- Command: `{test_result.command}`",
                f"- Policy: `{test_result.policy_decision.reason}`",
                f"- Exit code: `{test_result.exit_code}`",
                f"- Duration: `{test_result.duration_ms}ms`",
                f"- Timed out: `{test_result.timed_out}`",
                "",
                "### Stdout",
                "",
                "```text",
                _truncate(test_result.stdout),
                "```",
                "",
                "### Stderr",
                "",
                "```text",
                _truncate(test_result.stderr),
                "```",
                "",
            ]
        )
    else:
        lines.extend(["No test command was supplied or detected.", ""])

    model_usage = _model_usage_from_trace(trace_events)
    lines.extend(
        [
            "## Final Diff",
            "",
            "```diff",
            final_diff.strip() or "# No diff generated.",
            "```",
            "",
            "## Cost and Latency",
            "",
            f"- Model calls: `{model_usage['call_count']}`",
            f"- Model provider: `{model_usage['model_provider'] or 'none'}`",
            f"- Input tokens: `{model_usage['input_tokens'] or 'n/a'}`",
            f"- Output tokens: `{model_usage['output_tokens'] or 'n/a'}`",
            f"- Total tokens: `{model_usage['total_tokens'] or 'n/a'}`",
            f"- Estimated model cost: `{_format_cost(model_usage['estimated_cost_usd'])}`",
            "- Runtime latency is available in trace events.",
            "",
            "## Repair Analysis",
            "",
            f"- Status: `{repair_analysis.status if repair_analysis else 'not_available'}`",
            f"- Verdict: `{repair_analysis.verdict if repair_analysis else 'inspection_complete'}`",
            (
                f"- Patch generated: `{repair_analysis.patch_generated}`"
                if repair_analysis
                else "- Patch generated: `unknown`"
            ),
            (
                f"- Tests passed: `{repair_analysis.tests_passed}`"
                if repair_analysis
                else "- Tests passed: `unknown`"
            ),
            (
                f"- Failure category: `{repair_analysis.failure_category or 'n/a'}`"
                if repair_analysis
                else "- Failure category: `n/a`"
            ),
            (
                f"- Next action: {repair_analysis.next_action}"
                if repair_analysis
                else "- Next action: Inspect trace events."
            ),
            "",
            "## Trace Summary",
            "",
        ]
    )

    for event in trace_events:
        lines.append(
            f"- `{event.node_name}` `{event.event_type}` `{event.status}` "
            f"({event.latency_ms}ms): {event.output_summary or event.input_summary}"
        )

    lines.extend(
        [
            "",
            "## Risk Notes",
            "",
            "- The current runner is a development-only local sandbox wrapper with command policy.",
            "- Docker isolation is documented but not implemented in this first scaffold.",
            "- No external write actions are performed.",
            "",
            "## Final Verdict",
            "",
            f"`{repair_analysis.verdict if repair_analysis else 'inspection_complete'}`",
            "",
        ]
    )
    return "\n".join(lines)


def _truncate(value: str, max_chars: int = 6000) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "\n...[truncated]"


def _model_usage_from_trace(trace_events: list[TraceEvent]) -> dict[str, Any]:
    providers: list[str] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    total_tokens: list[int] = []
    estimated_costs: list[float] = []
    call_count = 0

    for event in trace_events:
        metadata = event.payload.get("metadata")
        if not isinstance(metadata, dict):
            continue
        model_call = metadata.get("model_call")
        if not isinstance(model_call, dict):
            continue
        call_count += 1
        provider = model_call.get("provider")
        if isinstance(provider, str) and provider not in providers:
            providers.append(provider)
        _append_int(input_tokens, model_call.get("input_tokens"))
        _append_int(output_tokens, model_call.get("output_tokens"))
        _append_int(total_tokens, model_call.get("total_tokens"))
        _append_float(estimated_costs, model_call.get("estimated_cost_usd"))

    return {
        "call_count": call_count,
        "model_provider": ",".join(providers) if providers else None,
        "input_tokens": sum(input_tokens) if input_tokens else None,
        "output_tokens": sum(output_tokens) if output_tokens else None,
        "total_tokens": sum(total_tokens) if total_tokens else None,
        "estimated_cost_usd": sum(estimated_costs) if estimated_costs else None,
    }


def _append_int(values: list[int], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        values.append(value)


def _append_float(values: list[float], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        values.append(float(value))


def _format_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "$0.00"
    return f"${value:.6f}"
