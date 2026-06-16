from __future__ import annotations

from pathlib import Path
from typing import TextIO

from patchsmith.agent_apply import (
    apply_agent_run_diff as default_apply_agent_run_diff,
)
from patchsmith.agent_apply import (
    check_agent_run_diff as default_check_agent_run_diff,
)
from patchsmith.agent_apply import (
    reverse_agent_run_diff as default_reverse_agent_run_diff,
)
from patchsmith.agent_diff import (
    format_agent_diff_preview,
    format_agent_diff_review,
    format_agent_diff_stat,
    review_agent_diff,
    summarize_agent_diff,
)
from patchsmith.chat.commands import (
    ApplyDiff,
    ChatCommand,
    ChatCommandContext,
    ReverseDiff,
)
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime
from patchsmith.session.events import TranscriptEvent
from patchsmith.session.store import read_known_transcript_events


def diff_apply_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="diff",
            handler=handle_diff_command,
            usage="/diff [path|stat|show [1-300]|review]",
        ),
        ChatCommand(
            name="apply",
            handler=handle_apply_command,
            usage="/apply [check]",
        ),
        ChatCommand(
            name="approve",
            handler=handle_approve_command,
            usage="/approve apply <reason>",
        ),
        ChatCommand(
            name="reject",
            handler=handle_reject_command,
            usage="/reject apply <reason>",
        ),
        ChatCommand(
            name="rewind",
            aliases=("undo",),
            handler=handle_rewind_command,
            usage="/rewind",
        ),
    )


def handle_diff_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    diff_path = last_diff_path(runtime)
    if diff_path is None:
        write_line(output_stream, "No run is available.")
        return
    action, _, rest = argument.partition(" ")
    action = action.strip().lower()
    if action in {"", "path"}:
        context.record(runtime, "diff_view", {"mode": "path", "diff_path": str(diff_path)})
        write_line(output_stream, f"Diff: {diff_path}")
        return
    if action == "stat":
        diff = summarize_agent_diff(diff_path, max_lines=0)
        context.record(runtime, "diff_view", {"mode": "stat", **diff.to_dict()})
        write_line(output_stream, format_agent_diff_stat(diff))
        return
    if action in {"show", "preview"}:
        max_lines = _parse_diff_preview_limit(rest.strip(), output_stream)
        if max_lines is None:
            return
        diff = summarize_agent_diff(diff_path, max_lines=max_lines)
        context.record(
            runtime,
            "diff_view",
            {
                "mode": "show",
                "max_lines": max_lines,
                **diff.to_dict(),
            },
        )
        write_line(output_stream, format_agent_diff_preview(diff))
        return
    if action == "review":
        review = review_agent_diff(diff_path)
        context.record(runtime, "diff_review", review.to_dict())
        write_line(output_stream, format_agent_diff_review(review))
        return
    write_line(output_stream, "Usage: /diff [path|stat|show [1-300]|review]")


def handle_apply_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action = argument.strip().lower()
    if action not in {"", "check", "dry-run", "dryrun"}:
        write_line(output_stream, "Usage: /apply [check]")
        return
    diff_path = last_diff_path(runtime)
    if diff_path is None:
        write_line(output_stream, "No run is available to apply.")
        return
    dry_run = action in {"check", "dry-run", "dryrun"}
    if not dry_run:
        guard = apply_guard(runtime=runtime, diff_path=diff_path)
        if guard is not None:
            context.record(runtime, "apply_blocked", guard)
            write_line(output_stream, f"Apply blocked: {guard['message']}")
            return
    if not _run_hooks(
        context,
        runtime=runtime,
        event="PreApply",
        payload={
            "repo": runtime.state.config.repo,
            "diff_path": str(diff_path),
            "allow_dirty_apply": runtime.state.config.allow_dirty_apply,
            "dry_run": dry_run,
            "matcher_target": str(diff_path),
        },
        output_stream=output_stream,
        blocking=True,
    ):
        return
    if dry_run:
        check_result = _check_agent_run_diff(context)(
            repo=runtime.state.config.repo,
            diff_path=diff_path,
            allow_dirty=runtime.state.config.allow_dirty_apply,
        )
        write_line(
            output_stream,
            f"Apply check: {check_result.status} - {check_result.message}",
        )
        context.record(runtime, "apply_check_result", check_result.to_dict())
        return
    apply_result = _apply_agent_run_diff(context)(
        repo=runtime.state.config.repo,
        diff_path=diff_path,
        allow_dirty=runtime.state.config.allow_dirty_apply,
    )
    runtime.last_apply = apply_result
    write_line(output_stream, f"Apply: {apply_result.status} - {apply_result.message}")
    context.record(runtime, "apply_result", apply_result.to_dict())
    _run_hooks(
        context,
        runtime=runtime,
        event="PostApply",
        payload={
            **apply_result.to_dict(),
            "matcher_target": apply_result.status,
        },
        output_stream=output_stream,
        blocking=False,
    )


def handle_approve_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, reason = argument.strip().partition(" ")
    if action.lower() != "apply" or not reason.strip():
        write_line(output_stream, "Usage: /approve apply <reason>")
        return
    diff_path = last_diff_path(runtime)
    if diff_path is None:
        write_line(output_stream, "No run is available to approve.")
        return
    approval, error = apply_approval_payload(
        runtime=runtime,
        diff_path=diff_path,
        reason=reason.strip(),
    )
    if error is not None:
        write_line(output_stream, error)
        return
    context.record(runtime, "apply_approval", approval)
    write_line(
        output_stream,
        f"Apply approved: {approval['risk_level']} - {approval['reason']}",
    )


def handle_reject_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    action, _, reason = argument.strip().partition(" ")
    if action.lower() != "apply" or not reason.strip():
        write_line(output_stream, "Usage: /reject apply <reason>")
        return
    diff_path = last_diff_path(runtime)
    if diff_path is None:
        write_line(output_stream, "No run is available to reject.")
        return
    rejection, error = apply_decision_payload(
        runtime=runtime,
        diff_path=diff_path,
        status="rejected",
        reason=reason.strip(),
    )
    if error is not None:
        write_line(output_stream, error.replace("approve", "reject"))
        return
    context.record(runtime, "apply_rejection", rejection)
    write_line(
        output_stream,
        f"Apply rejected: {rejection['risk_level']} - {rejection['reason']}",
    )


def handle_rewind_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if argument.strip():
        write_line(output_stream, "Usage: /rewind")
        return
    diff_path = last_diff_path(runtime)
    if diff_path is None:
        write_line(output_stream, "No run is available to rewind.")
        return
    if not _run_hooks(
        context,
        runtime=runtime,
        event="PreRewind",
        payload={
            "repo": runtime.state.config.repo,
            "diff_path": str(diff_path),
            "matcher_target": str(diff_path),
        },
        output_stream=output_stream,
        blocking=True,
    ):
        return
    rewind_result = _reverse_agent_run_diff(context)(
        repo=runtime.state.config.repo,
        diff_path=diff_path,
    )
    runtime.last_rewind = rewind_result
    write_line(
        output_stream,
        f"Rewind: {rewind_result.status} - {rewind_result.message}",
    )
    context.record(runtime, "rewind_result", rewind_result.to_dict())
    _run_hooks(
        context,
        runtime=runtime,
        event="PostRewind",
        payload={
            **rewind_result.to_dict(),
            "matcher_target": rewind_result.status,
        },
        output_stream=output_stream,
        blocking=False,
    )


def last_diff_path(runtime: AgentChatRuntime) -> Path | None:
    if runtime.last_run is not None:
        return Path(runtime.last_run.final_diff_path)
    if runtime.last_run_payload is None:
        return None
    value = runtime.last_run_payload.get("final_diff_path")
    return Path(value) if isinstance(value, str) and value else None


def apply_guard(
    *,
    runtime: AgentChatRuntime,
    diff_path: Path,
) -> dict[str, object] | None:
    rows = read_known_transcript_events(runtime.state.transcript_path)
    run_index = _latest_event_index(rows, "run_result")
    review_index, review_payload = _latest_event_with_path(
        rows=rows,
        event="diff_review",
        diff_path=diff_path,
    )
    if review_index < run_index:
        return _apply_block_payload(
            diff_path=diff_path,
            reason_code="missing_diff_review",
            message="run /diff review before /apply.",
        )
    check_index, check_payload = _latest_event_with_path(
        rows=rows,
        event="apply_check_result",
        diff_path=diff_path,
    )
    if check_index < review_index:
        return _apply_block_payload(
            diff_path=diff_path,
            reason_code="missing_apply_check",
            message="run /apply check after /diff review before /apply.",
        )
    if check_payload.get("status") != "ready":
        status = check_payload.get("status") or "missing"
        return _apply_block_payload(
            diff_path=diff_path,
            reason_code="apply_check_not_ready",
            message=f"latest /apply check is {status}; fix it before /apply.",
        )
    rejection_index, rejection_payload = _latest_event_with_path(
        rows=rows,
        event="apply_rejection",
        diff_path=diff_path,
    )
    approval_index, _approval_payload = _latest_event_with_path(
        rows=rows,
        event="apply_approval",
        diff_path=diff_path,
    )
    if rejection_index >= check_index and rejection_index > approval_index:
        reason = rejection_payload.get("reason") or "no reason recorded"
        return _apply_block_payload(
            diff_path=diff_path,
            reason_code="apply_rejected",
            message=f"latest apply decision rejected this diff: {reason}",
        )
    if (
        review_payload.get("risk_level") == "high"
        or review_payload.get("confirmation_required") is True
    ) and approval_index < check_index:
        return _apply_block_payload(
            diff_path=diff_path,
            reason_code="missing_apply_approval",
            message=(
                "latest /diff review is high risk; run /approve apply <reason> before /apply."
            ),
        )
    return None


def apply_approval_payload(
    *,
    runtime: AgentChatRuntime,
    diff_path: Path,
    reason: str,
) -> tuple[dict[str, object], str | None]:
    return apply_decision_payload(
        runtime=runtime,
        diff_path=diff_path,
        status="approved",
        reason=reason,
    )


def apply_decision_payload(
    *,
    runtime: AgentChatRuntime,
    diff_path: Path,
    status: str,
    reason: str,
) -> tuple[dict[str, object], str | None]:
    rows = read_known_transcript_events(runtime.state.transcript_path)
    run_index = _latest_event_index(rows, "run_result")
    review_index, review_payload = _latest_event_with_path(
        rows=rows,
        event="diff_review",
        diff_path=diff_path,
    )
    if review_index < run_index:
        return {}, "Run /diff review before /approve apply."
    check_index, check_payload = _latest_event_with_path(
        rows=rows,
        event="apply_check_result",
        diff_path=diff_path,
    )
    if check_index < review_index:
        return {}, "Run /apply check after /diff review before /approve apply."
    if check_payload.get("status") != "ready":
        check_status = check_payload.get("status") or "missing"
        return {}, f"Latest /apply check is {check_status}; fix it before approving apply."
    return (
        {
            "action": "apply",
            "status": status,
            "reason": reason,
            "diff_path": str(diff_path),
            "risk_level": review_payload.get("risk_level"),
            "confirmation_required": review_payload.get("confirmation_required"),
            "apply_check_status": check_payload.get("status"),
        },
        None,
    )


def _parse_diff_preview_limit(raw: str, output_stream: TextIO) -> int | None:
    if not raw:
        return 80
    try:
        value = int(raw)
    except ValueError:
        write_line(output_stream, "Usage: /diff show [1-300]")
        return None
    if value < 1 or value > 300:
        write_line(output_stream, "diff preview line limit must be between 1 and 300.")
        return None
    return value


def _apply_block_payload(
    *,
    diff_path: Path,
    reason_code: str,
    message: str,
) -> dict[str, object]:
    return {
        "status": "blocked",
        "reason_code": reason_code,
        "message": message,
        "diff_path": str(diff_path),
    }


def _latest_event_with_path(
    *,
    rows: list[TranscriptEvent],
    event: str,
    diff_path: Path,
) -> tuple[int, dict[str, object]]:
    expected_path = str(diff_path)
    expected_resolved = str(diff_path.resolve())
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if row.event != event:
            continue
        payload = row.payload
        raw_path = payload.get("diff_path") or payload.get("path")
        if raw_path not in {expected_path, expected_resolved}:
            continue
        return index, payload
    return -1, {}


def _latest_event_index(rows: list[TranscriptEvent], event: str) -> int:
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].event == event:
            return index
    return -1


def _run_hooks(
    context: ChatCommandContext,
    *,
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
    output_stream: TextIO,
    blocking: bool,
) -> bool:
    if context.run_hooks is None:
        return True
    return context.run_hooks(
        runtime=runtime,
        event=event,
        payload=payload,
        output_stream=output_stream,
        blocking=blocking,
    )


def _apply_agent_run_diff(context: ChatCommandContext) -> ApplyDiff:
    return context.apply_agent_run_diff or default_apply_agent_run_diff


def _check_agent_run_diff(context: ChatCommandContext) -> ApplyDiff:
    return context.check_agent_run_diff or default_check_agent_run_diff


def _reverse_agent_run_diff(context: ChatCommandContext) -> ReverseDiff:
    return context.reverse_agent_run_diff or default_reverse_agent_run_diff
