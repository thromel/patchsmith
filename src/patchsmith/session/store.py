from __future__ import annotations

import json
from pathlib import Path

from patchsmith.session.events import (
    TranscriptEvent,
    TranscriptRow,
    decode_transcript_row,
)


def append_transcript_event(
    path: Path,
    *,
    session_id: str,
    event: str,
    payload: dict[str, object],
    timestamp: str | None = None,
) -> TranscriptEvent:
    transcript_event = TranscriptEvent.create(
        session_id=session_id,
        event=event,
        payload=payload,
        timestamp=timestamp,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(transcript_event.to_dict(), sort_keys=True) + "\n")
    return transcript_event


def read_transcript_rows(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def read_transcript_events(path: Path) -> list[TranscriptRow]:
    return [decode_transcript_row(row) for row in read_transcript_rows(path)]


def read_known_transcript_events(path: Path) -> list[TranscriptEvent]:
    return [
        row
        for row in read_transcript_events(path)
        if isinstance(row, TranscriptEvent)
    ]
