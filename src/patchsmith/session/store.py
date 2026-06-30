from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from patchsmith.session.events import (
    TranscriptEvent,
    TranscriptRow,
    decode_transcript_row,
)

# Bounded cache of parsed transcript rows keyed by (path, mtime_ns, size).
# Chat commands frequently parse the same transcript multiple times between
# appends (e.g. /cost then /metrics, or the apply guard reading twice). The
# mtime/size key invalidates automatically whenever the transcript is appended
# to. Callers must treat returned rows as read-only.
_TRANSCRIPT_ROWS_CACHE_MAX_ENTRIES = 64
_TRANSCRIPT_ROWS_CACHE: OrderedDict[tuple[str, int, int], list[dict[str, object]]] = OrderedDict()


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
    try:
        stat = path.stat()
    except OSError:
        return []
    cache_key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _TRANSCRIPT_ROWS_CACHE.get(cache_key)
    if cached is not None:
        _TRANSCRIPT_ROWS_CACHE.move_to_end(cache_key)
        return list(cached)
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
    _TRANSCRIPT_ROWS_CACHE[cache_key] = rows
    _TRANSCRIPT_ROWS_CACHE.move_to_end(cache_key)
    while len(_TRANSCRIPT_ROWS_CACHE) > _TRANSCRIPT_ROWS_CACHE_MAX_ENTRIES:
        _TRANSCRIPT_ROWS_CACHE.popitem(last=False)
    return list(rows)


def read_transcript_events(path: Path) -> list[TranscriptRow]:
    return [decode_transcript_row(row) for row in read_transcript_rows(path)]


def read_known_transcript_events(path: Path) -> list[TranscriptEvent]:
    return [row for row in read_transcript_events(path) if isinstance(row, TranscriptEvent)]
