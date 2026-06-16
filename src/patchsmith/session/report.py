from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from patchsmith.session.events import TranscriptEvent
from patchsmith.session.metrics import session_metrics, session_usage_payload
from patchsmith.session.store import read_known_transcript_events


@dataclass(frozen=True)
class AgentSessionExport:
    transcript_path: Path
    report_path: Path


def export_session_report(
    *,
    transcript_path: Path,
    report_path: Path | None = None,
) -> AgentSessionExport:
    resolved_report_path = report_path or transcript_path.with_suffix(".md")
    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_path.write_text(
        session_markdown_report(transcript_path),
        encoding="utf-8",
    )
    return AgentSessionExport(
        transcript_path=transcript_path,
        report_path=resolved_report_path,
    )


def session_markdown_report(transcript_path: Path) -> str:
    rows = read_known_transcript_events(transcript_path)
    usage = session_usage_payload(transcript_path)
    metrics = session_metrics(transcript_path)
    session_id = _first_text(rows, "session_id") or transcript_path.stem
    config = _latest_config(rows)
    last_run = _latest_payload(rows, "run_result")
    last_error = _latest_payload(rows, "run_error")
    lines = [
        "# PatchSmith Chat Session",
        "",
        f"- Session: `{session_id}`",
        f"- Transcript: `{transcript_path}`",
        f"- Exported at: `{datetime.now(UTC).isoformat()}`",
    ]
    if config is not None:
        lines.extend(_config_lines(config))
    lines.extend(
        [
            "",
            "## Usage",
            "",
            f"- Tasks: `{usage['task_count']}`",
            f"- Runs: `{usage['run_count']}`",
            f"- Validated runs: `{usage['validated_run_count']}`",
            f"- Run errors: `{usage['run_error_count']}`",
            f"- Model calls: `{usage['model_call_count']}`",
            f"- Model responses: `{usage['model_response_count']}`",
            f"- Model tokens: `{usage['model_total_tokens']}`",
            f"- Estimated cost: `{_format_cost(usage['estimated_cost_usd'])}`",
            "",
            "## Process Metrics",
            "",
            f"- Validation rate: `{_format_rate(metrics.validation_rate)}`",
            f"- Preflight-to-run rate: `{_format_rate(metrics.preflight_to_run_rate)}`",
            f"- Apply success rate: `{_format_rate(metrics.apply_success_rate)}`",
            f"- Cost per validated run: `{_format_cost(metrics.cost_per_validated_run_usd)}`",
            f"- Preflights: `{metrics.preflight_count}`",
            f"- Passed preflights: `{metrics.preflight_passed_count}`",
            f"- Run preflights: `{metrics.run_preflight_count}`",
            f"- Passed run preflights: `{metrics.run_preflight_passed_count}`",
            f"- Model preflights: `{metrics.model_preflight_count}`",
            f"- Passed model preflights: `{metrics.model_preflight_passed_count}`",
            f"- Blocked model preflights: `{metrics.model_preflight_blocked_count}`",
            f"- Verify runs: `{metrics.verify_count}`",
            f"- Passed verify runs: `{metrics.verify_passed_count}`",
            f"- Diff views: `{metrics.diff_view_count}`",
            f"- Diff reviews: `{metrics.diff_review_count}`",
            f"- High-risk diff reviews: `{metrics.diff_review_high_count}`",
            f"- Current diff reviews: `{metrics.current_diff_review_count}`",
            (
                "- Current high-risk diff reviews: "
                f"`{metrics.current_diff_review_high_count}`"
            ),
            f"- Apply checks: `{metrics.apply_check_count}`",
            f"- Ready apply checks: `{metrics.apply_check_ready_count}`",
            (
                "- Current ready apply checks: "
                f"`{metrics.current_apply_check_ready_count}`"
            ),
            f"- Apply approvals: `{metrics.apply_approval_count}`",
            f"- High-risk apply approvals: `{metrics.high_risk_apply_approval_count}`",
            f"- Apply rejections: `{metrics.apply_rejection_count}`",
            f"- High-risk apply rejections: `{metrics.high_risk_apply_rejection_count}`",
            f"- Blocked applies: `{metrics.apply_block_count}`",
            f"- Deferred auto applies: `{metrics.apply_auto_deferred_count}`",
            f"- Apply attempts: `{metrics.apply_attempt_count}`",
            f"- Applied diffs: `{metrics.apply_success_count}`",
            f"- Rewind attempts: `{metrics.rewind_attempt_count}`",
            f"- Reverted diffs: `{metrics.rewind_success_count}`",
            f"- Rewind success rate: `{_format_rate(metrics.rewind_success_rate)}`",
            f"- Custom commands: `{metrics.custom_command_count}`",
            f"- Hook runs: `{metrics.hook_run_count}`",
            f"- Hook blocks: `{metrics.hook_block_count}`",
            f"- Context updates: `{metrics.context_update_count}`",
            f"- Permission updates: `{metrics.permission_update_count}`",
            f"- Model updates: `{metrics.model_update_count}`",
            f"- Budget updates: `{metrics.budget_update_count}`",
            f"- Agent profile updates: `{metrics.agent_profile_update_count}`",
            f"- Instruction updates: `{metrics.instruction_update_count}`",
            f"- Instruction views: `{metrics.instruction_view_count}`",
            f"- Memory views: `{metrics.memory_view_count}`",
            f"- Plan updates: `{metrics.plan_update_count}`",
            f"- Plan views: `{metrics.plan_view_count}`",
            f"- Feedback updates: `{metrics.feedback_update_count}`",
            f"- Feedback views: `{metrics.feedback_view_count}`",
            f"- Session gates: `{metrics.session_gate_count}`",
            f"- Failed session gates: `{metrics.session_gate_failure_count}`",
            f"- Run evidence views: `{metrics.run_evidence_count}`",
            f"- Checkpoints: `{metrics.checkpoint_count}`",
            f"- Restores: `{metrics.restore_count}`",
            f"- Timeline views: `{metrics.timeline_view_count}`",
            f"- Next recommendations: `{metrics.next_view_count}`",
            "",
            "## Runs",
            "",
        ]
    )
    run_payloads = _payloads(rows, "run_result")
    if run_payloads:
        for payload in run_payloads:
            lines.extend(_run_lines(payload))
    else:
        lines.append("- No completed runs recorded.")
    run_errors = _payloads(rows, "run_error")
    if run_errors:
        lines.extend(["", "## Run Errors", ""])
        for payload in run_errors:
            lines.append(
                "- "
                f"{_inline_text(payload.get('error_type'))}: "
                f"{_inline_text(payload.get('message'))}"
            )
    lines.extend(["", "## Tasks", ""])
    tasks = _payloads(rows, "user_task")
    if tasks:
        for index, payload in enumerate(tasks, start=1):
            lines.append(f"{index}. {_plain_text(payload.get('task'))}")
    else:
        lines.append("- No tasks recorded.")
    lines.extend(["", "## Context, Plan, And Config Events", ""])
    context_events = [
        row
        for row in rows
        if row.event
        in {
            "context_update",
            "config_update",
            "instruction_view",
            "memory_view",
            "plan_update",
            "plan_view",
            "feedback_update",
            "feedback_view",
            "session_gate",
            "session_checkpoint",
            "session_restore",
            "session_timeline",
            "session_next",
            "run_preflight",
            "verify_result",
            "diff_view",
            "diff_review",
            "apply_check_result",
            "apply_approval",
            "apply_rejection",
            "apply_blocked",
            "apply_auto_deferred",
        }
    ]
    if context_events:
        for row in context_events:
            lines.append(_event_line(row))
    else:
        lines.append("- No context, plan, or config changes recorded.")
    if last_run is not None or last_error is not None:
        lines.extend(["", "## Latest State", ""])
        if last_run is not None:
            lines.extend(_latest_run_lines(last_run))
        if last_error is not None:
            lines.append(f"- Last error: `{_plain_text(last_error.get('message'))}`")
    return "\n".join(lines).rstrip() + "\n"


def _config_lines(config: dict[str, object]) -> list[str]:
    return [
        f"- Repo: `{_plain_text(config.get('repo'))}`",
        f"- Test command: `{_plain_text(config.get('test_command'))}`",
        f"- Context provider: `{_plain_text(config.get('context_provider'))}`",
        f"- Context paths: `{_plain_text(config.get('context_paths'))}`",
        f"- Agent profile: `{_plain_text(config.get('agent_profile'))}`",
        f"- Project instruction files: `{_plain_text(config.get('agent_instruction_files'))}`",
        f"- Model override: `{_plain_text(config.get('deepagents_model'))}`",
        f"- Apply after run: `{_plain_text(config.get('apply'))}`",
        f"- Dirty apply allowed: `{_plain_text(config.get('allow_dirty_apply'))}`",
        "- Budget: "
        f"`responses={_plain_text(config.get('max_model_responses'))}, "
        f"tokens={_plain_text(config.get('max_model_tokens'))}`",
    ]


def _run_lines(payload: dict[str, object]) -> list[str]:
    run_id = _plain_text(payload.get("run_id"))
    status = _plain_text(payload.get("status"))
    test_exit_code = _plain_text(payload.get("test_exit_code"))
    return [
        f"- `{run_id}`: status `{status}`, test exit `{test_exit_code}`",
        f"  - Report: `{_plain_text(payload.get('report_path'))}`",
        f"  - Trace: `{_plain_text(payload.get('trace_path'))}`",
        f"  - Diff: `{_plain_text(payload.get('final_diff_path'))}`",
        f"  - Model responses: `{_plain_text(payload.get('model_response_count'))}`",
        f"  - Model tokens: `{_plain_text(payload.get('model_total_tokens'))}`",
        f"  - Estimated cost: `{_format_cost(payload.get('estimated_cost_usd'))}`",
    ]


def _latest_run_lines(payload: dict[str, object]) -> list[str]:
    return [
        f"- Last run: `{_plain_text(payload.get('run_id'))}`",
        f"- Last status: `{_plain_text(payload.get('status'))}`",
        f"- Last report: `{_plain_text(payload.get('report_path'))}`",
        f"- Last diff: `{_plain_text(payload.get('final_diff_path'))}`",
    ]


def _event_line(row: TranscriptEvent) -> str:
    return f"- `{row.event}`: `{_plain_text(row.payload)}`"


def _latest_config(rows: list[TranscriptEvent]) -> dict[str, object] | None:
    config: dict[str, object] | None = None
    for row in rows:
        event = row.event
        payload = row.payload
        if event == "session_start":
            value = payload.get("config")
            if isinstance(value, dict):
                config = dict(value)
        elif event == "config_update" and config is not None:
            _apply_config_update(config, payload)
        elif event == "context_update" and config is not None:
            paths = payload.get("context_paths")
            if isinstance(paths, list):
                config["context_paths"] = [path for path in paths if isinstance(path, str)]
    return config


def _apply_config_update(
    config: dict[str, object],
    payload: dict[str, object],
) -> None:
    field = payload.get("field")
    if field == "deepagents_model":
        config["deepagents_model"] = payload.get("value")
    elif field == "resource_budget":
        config["max_model_responses"] = payload.get("max_model_responses")
        config["max_model_tokens"] = payload.get("max_model_tokens")
    elif field == "permissions":
        config["apply"] = payload.get("apply")
        config["allow_dirty_apply"] = payload.get("allow_dirty_apply")
    elif field == "agent_profile":
        for key in (
            "agent_profile",
            "agent_profile_path",
            "agent_profile_description",
            "agent_profile_instructions",
            "agent_profile_instruction_chars",
            "deepagents_model",
            "deepagents_subagents",
            "deepagents_max_context_files",
            "max_model_responses",
            "max_model_tokens",
            "top_k",
            "test_command",
            "context_paths",
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)
    elif field == "project_instructions":
        for key in (
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)


def _payloads(
    rows: list[TranscriptEvent],
    event: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for row in rows:
        if row.event != event:
            continue
        payloads.append(row.payload)
    return payloads


def _latest_payload(
    rows: list[TranscriptEvent],
    event: str,
) -> dict[str, object] | None:
    payloads = _payloads(rows, event)
    return payloads[-1] if payloads else None


def _first_text(rows: list[TranscriptEvent], key: str) -> str | None:
    for row in rows:
        value = _event_text_field(row, key)
        if value:
            return value
    return None


def _event_text_field(row: TranscriptEvent, key: str) -> str | None:
    if key == "timestamp":
        return row.timestamp or None
    if key == "session_id":
        return row.session_id or None
    return None


def _format_rate(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.2%}"


def _format_cost(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"${float(value):.6f}"


def _inline_text(value: object) -> str:
    return _plain_text(value).replace("\n", " ")


def _plain_text(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return str(value)
