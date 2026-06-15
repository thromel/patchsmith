from __future__ import annotations

from pathlib import Path
from typing import TextIO

from patchsmith.agent_evidence import (
    format_agent_run_evidence,
    summarize_agent_run_evidence,
)
from patchsmith.agent_session import (
    AgentSessionGateConfig,
    evaluate_session_gate,
    export_session_report,
    format_session_gate,
    format_session_metrics,
    format_session_recommendation,
    format_session_timeline,
    session_metrics,
    session_recommendation,
    session_timeline,
    session_usage_payload,
)
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.state import AgentChatRuntime


def session_evidence_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(name="cost", handler=handle_cost_command, usage="/cost"),
        ChatCommand(name="metrics", handler=handle_metrics_command, usage="/metrics"),
        ChatCommand(
            name="timeline",
            handler=handle_timeline_command,
            usage="/timeline [n]",
        ),
        ChatCommand(
            name="next",
            aliases=("recommend",),
            handler=handle_next_command,
            usage="/next",
        ),
        ChatCommand(
            name="gate",
            handler=handle_gate_command,
            usage="/gate [validated|clean|reviewed|applied|cost <usd>]",
        ),
        ChatCommand(
            name="trace",
            aliases=("evidence",),
            handler=handle_run_evidence_command,
            usage="/trace",
        ),
        ChatCommand(
            name="export",
            handler=handle_export_command,
            usage="/export [path]",
        ),
    )


def handle_cost_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    payload = session_usage_payload(runtime.state.transcript_path)
    context.record(runtime, "session_usage", payload)
    _write_line(output_stream, "Session usage:")
    _write_line(output_stream, f"Tasks: {payload['task_count']}")
    _write_line(output_stream, f"Runs: {payload['run_count']}")
    _write_line(output_stream, f"Validated runs: {payload['validated_run_count']}")
    _write_line(output_stream, f"Run errors: {payload['run_error_count']}")
    _write_line(output_stream, f"Model calls: {payload['model_call_count']}")
    _write_line(output_stream, f"Model responses: {payload['model_response_count']}")
    _write_line(output_stream, f"Model tokens: {payload['model_total_tokens']}")
    cost = payload["estimated_cost_usd"]
    if isinstance(cost, int | float):
        _write_line(output_stream, f"Estimated cost: ${cost:.6f}")
    else:
        _write_line(output_stream, "Estimated cost: n/a")


def handle_metrics_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    metrics = session_metrics(runtime.state.transcript_path)
    context.record(runtime, "session_metrics", metrics.to_dict())
    _write_line(output_stream, format_session_metrics(metrics))


def handle_timeline_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    limit = _parse_timeline_limit(argument, output_stream)
    if limit is None:
        return
    entries = session_timeline(runtime.state.transcript_path, limit=limit)
    context.record(
        runtime,
        "session_timeline",
        {
            "limit": limit,
            "entry_count": len(entries),
            "entries": [entry.to_dict() for entry in entries],
        },
    )
    _write_line(output_stream, format_session_timeline(entries))


def handle_next_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    recommendation = session_recommendation(runtime.state.transcript_path)
    context.record(runtime, "session_next", recommendation.to_dict())
    _write_line(output_stream, format_session_recommendation(recommendation))


def handle_gate_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    config, error = _chat_gate_config(argument)
    if error:
        _write_line(output_stream, error)
        _write_line(
            output_stream,
            "Usage: /gate [validated|clean|reviewed|applied|cost <usd>]",
        )
        return
    metrics = session_metrics(runtime.state.transcript_path)
    result = evaluate_session_gate(metrics, config)
    context.record(
        runtime,
        "session_gate",
        {
            "argument": argument.strip() or "validated",
            "gate": result.to_dict(),
        },
    )
    _write_line(output_stream, format_session_gate(result))


def handle_run_evidence_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if runtime.last_run_payload is None:
        _write_line(output_stream, "No run evidence is available.")
        return
    evidence = summarize_agent_run_evidence(runtime.last_run_payload)
    context.record(runtime, "run_evidence", evidence.to_dict())
    _write_line(output_stream, format_agent_run_evidence(evidence))


def handle_export_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    report_path = Path(argument).expanduser() if argument.strip() else None
    export = export_session_report(
        transcript_path=runtime.state.transcript_path,
        report_path=report_path,
    )
    context.record(
        runtime,
        "session_export",
        {
            "report_path": str(export.report_path),
            "transcript_path": str(export.transcript_path),
        },
    )
    _write_line(output_stream, f"Exported session report: {export.report_path}")


def _parse_timeline_limit(argument: str, output_stream: TextIO) -> int | None:
    value = argument.strip()
    if not value:
        return 20
    try:
        limit = int(value)
    except ValueError:
        _write_line(output_stream, "Usage: /timeline [1-100]")
        return None
    if limit < 1 or limit > 100:
        _write_line(output_stream, "timeline limit must be between 1 and 100.")
        return None
    return limit


def _chat_gate_config(argument: str) -> tuple[AgentSessionGateConfig, str | None]:
    parts = argument.split()
    if not parts:
        return AgentSessionGateConfig(require_validated_run=True), None
    mode = parts[0].lower()
    if mode == "validated" and len(parts) == 1:
        return AgentSessionGateConfig(require_validated_run=True), None
    if mode == "clean" and len(parts) == 1:
        return AgentSessionGateConfig(
            require_validated_run=True,
            min_validation_rate=1.0,
            max_run_errors=0,
        ), None
    if mode in {"reviewed", "promotable"} and len(parts) == 1:
        return AgentSessionGateConfig(
            require_validated_run=True,
            require_diff_review=True,
            require_ready_apply_check=True,
            min_validation_rate=1.0,
            max_high_risk_diff_reviews=0,
            max_run_errors=0,
        ), None
    if mode == "applied" and len(parts) == 1:
        return AgentSessionGateConfig(
            require_validated_run=True,
            min_apply_success_rate=1.0,
            max_run_errors=0,
        ), None
    if mode == "cost" and len(parts) == 2:
        try:
            max_cost = float(parts[1])
        except ValueError:
            return AgentSessionGateConfig(), "cost must be a number."
        if max_cost < 0:
            return AgentSessionGateConfig(), "cost must be non-negative."
        return AgentSessionGateConfig(
            require_validated_run=True,
            max_cost_per_validated_run_usd=max_cost,
            max_run_errors=0,
        ), None
    return AgentSessionGateConfig(), f"Unknown gate profile: {argument.strip()}"


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
