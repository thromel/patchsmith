from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_cli import AgentCliConfig
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.chat.transcript import record_chat_event
from patchsmith.session.store import read_transcript_rows

pytestmark = pytest.mark.unit


def test_record_chat_event_appends_runtime_transcript_row(tmp_path: Path) -> None:
    transcript_path = tmp_path / "artifacts" / "chat_sessions" / "session.jsonl"
    runtime = AgentChatRuntime(
        state=AgentChatState(
            session_id="session-1",
            transcript_path=transcript_path,
            config=AgentCliConfig(repo=str(tmp_path)),
        )
    )

    record_chat_event(runtime, "user_task", {"task": "fix parser"})

    rows = read_transcript_rows(transcript_path)

    assert rows == [
        {
            "event": "user_task",
            "payload": {"task": "fix parser"},
            "session_id": "session-1",
            "timestamp": rows[0]["timestamp"],
        }
    ]
