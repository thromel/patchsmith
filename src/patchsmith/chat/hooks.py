from __future__ import annotations

from typing import TextIO

from patchsmith.agent_hooks import run_agent_hooks
from patchsmith.chat.commands import ChatEventRecorder
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime
from patchsmith.chat.transcript import record_chat_event


def run_chat_hooks(
    *,
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
    output_stream: TextIO,
    blocking: bool,
    record: ChatEventRecorder = record_chat_event,
) -> bool:
    hook_payload = {
        "session_id": runtime.state.session_id,
        "transcript_path": str(runtime.state.transcript_path),
        **payload,
    }
    result = run_agent_hooks(
        repo=runtime.state.config.repo,
        event=event,
        payload=hook_payload,
    )
    if result.runs:
        record(runtime, "hook_result", result.to_dict())
    if result.blocked:
        reason = result.block_reason or f"{event} blocked by hook"
        write_line(output_stream, f"Hook blocked {event}: {reason}")
        return not blocking
    return True
