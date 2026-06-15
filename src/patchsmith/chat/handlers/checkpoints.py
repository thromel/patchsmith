from __future__ import annotations

from pathlib import Path
from typing import TextIO
from uuid import uuid4

from patchsmith.agent_session import transcript_rows
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.session_payloads import (
    checkpoint_state_payload,
    last_run_value,
    restore_checkpoint_state,
)
from patchsmith.chat.state import AgentChatRuntime


def checkpoint_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="checkpoint",
            handler=handle_checkpoint_command,
            usage="/checkpoint [label]",
        ),
        ChatCommand(
            name="checkpoints",
            handler=handle_checkpoints_command,
            usage="/checkpoints",
        ),
        ChatCommand(
            name="restore",
            handler=handle_restore_command,
            usage="/restore <checkpoint-id-or-label>",
        ),
    )


def handle_checkpoint_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    payload = _checkpoint_payload(runtime=runtime, label=argument)
    context.record(runtime, "session_checkpoint", payload)
    label_text = f" ({payload['label']})" if payload["label"] else ""
    _write_line(output_stream, f"Checkpoint saved: {payload['checkpoint_id']}{label_text}")


def handle_checkpoints_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    checkpoints = _checkpoint_payloads(runtime.state.transcript_path)
    context.record(runtime, "session_checkpoint_list", {"count": len(checkpoints)})
    _write_line(output_stream, _format_checkpoints(checkpoints))


def handle_restore_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    value = argument.strip()
    if not value:
        _write_line(output_stream, "Usage: /restore <checkpoint-id-or-label>")
        return
    checkpoint = _find_checkpoint(runtime.state.transcript_path, value)
    if checkpoint is None:
        _write_line(output_stream, f"Checkpoint not found: {value}")
        return
    state = checkpoint.get("state")
    if not isinstance(state, dict):
        _write_line(output_stream, f"Checkpoint has no restorable state: {value}")
        return
    restore_checkpoint_state(runtime=runtime, state=state)
    payload = {
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "label": checkpoint.get("label"),
        "state": state,
    }
    context.record(runtime, "session_restore", payload)
    label_text = f" ({checkpoint['label']})" if checkpoint.get("label") else ""
    _write_line(output_stream, f"Restored checkpoint: {checkpoint['checkpoint_id']}{label_text}")


def _checkpoint_payload(
    *,
    runtime: AgentChatRuntime,
    label: str,
) -> dict[str, object]:
    state = checkpoint_state_payload(runtime)
    checkpoint_label = label.strip() or None
    return {
        "checkpoint_id": f"ckpt-{uuid4().hex[:8]}",
        "label": checkpoint_label,
        "history_count": len(runtime.history or []),
        "plan_count": len(runtime.plan_items or []),
        "last_run_id": last_run_value(runtime, "run_id"),
        "state": state,
    }


def _checkpoint_payloads(transcript_path: Path) -> list[dict[str, object]]:
    checkpoints: list[dict[str, object]] = []
    for row in transcript_rows(transcript_path):
        if row.get("event") != "session_checkpoint":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        checkpoint = dict(payload)
        timestamp = row.get("timestamp")
        if isinstance(timestamp, str):
            checkpoint["timestamp"] = timestamp
        checkpoints.append(checkpoint)
    return checkpoints


def _find_checkpoint(transcript_path: Path, selector: str) -> dict[str, object] | None:
    for checkpoint in reversed(_checkpoint_payloads(transcript_path)):
        checkpoint_id = checkpoint.get("checkpoint_id")
        label = checkpoint.get("label")
        if checkpoint_id == selector or label == selector:
            return checkpoint
    return None


def _format_checkpoints(checkpoints: list[dict[str, object]]) -> str:
    if not checkpoints:
        return "No checkpoints found."
    lines = [
        "Checkpoints:",
        "ID | Label | Tasks | Plan | Last run | Saved",
        "--- | --- | ---: | ---: | --- | ---",
    ]
    for checkpoint in checkpoints:
        lines.append(
            " | ".join(
                [
                    _checkpoint_text(checkpoint.get("checkpoint_id")),
                    _checkpoint_text(checkpoint.get("label")),
                    _checkpoint_text(checkpoint.get("history_count")),
                    _checkpoint_text(checkpoint.get("plan_count")),
                    _checkpoint_text(checkpoint.get("last_run_id")),
                    _checkpoint_text(checkpoint.get("timestamp")),
                ]
            )
        )
    return "\n".join(lines)


def _checkpoint_text(value: object) -> str:
    return "n/a" if value is None else str(value)


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
