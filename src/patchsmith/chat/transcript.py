from __future__ import annotations

from patchsmith.chat.state import AgentChatRuntime
from patchsmith.session.store import append_transcript_event


def record_chat_event(
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
) -> None:
    append_transcript_event(
        runtime.state.transcript_path,
        session_id=runtime.state.session_id,
        event=event,
        payload=payload,
    )
