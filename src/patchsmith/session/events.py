from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class TranscriptEvent:
    timestamp: str
    session_id: str
    event: str
    payload: dict[str, object]

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        event: str,
        payload: dict[str, object],
        timestamp: str | None = None,
    ) -> TranscriptEvent:
        return cls(
            timestamp=timestamp or datetime.now(UTC).isoformat(),
            session_id=session_id,
            event=event,
            payload=payload,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "event": self.event,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class UnknownTranscriptEvent:
    raw: dict[str, object]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return dict(self.raw)


TranscriptRow = TranscriptEvent | UnknownTranscriptEvent


def decode_transcript_row(row: dict[str, object]) -> TranscriptRow:
    event = row.get("event")
    payload = row.get("payload")
    if not isinstance(event, str):
        return UnknownTranscriptEvent(raw=row, reason="missing_event")
    if not isinstance(payload, dict):
        return UnknownTranscriptEvent(raw=row, reason="invalid_payload")
    timestamp = row.get("timestamp")
    session_id = row.get("session_id")
    return TranscriptEvent(
        timestamp=timestamp if isinstance(timestamp, str) else "",
        session_id=session_id if isinstance(session_id, str) else "",
        event=event,
        payload=payload,
    )
