from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from patchsmith.models import TraceEvent, new_id, utc_now_iso


class RunTrace:
    def __init__(self, *, run_id: str, trace_path: Path) -> None:
        self.run_id = run_id
        self.trace_path = trace_path
        self.events: list[TraceEvent] = []
        trace_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        node_name: str,
        event_type: str,
        status: str,
        input_summary: str = "",
        output_summary: str = "",
        payload: dict[str, Any] | None = None,
        error: str | None = None,
        latency_ms: int = 0,
    ) -> TraceEvent:
        now = utc_now_iso()
        event = TraceEvent(
            run_id=self.run_id,
            event_id=new_id(),
            node_name=node_name,
            event_type=event_type,
            status=status,
            started_at=now,
            completed_at=now,
            latency_ms=latency_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            payload=payload or {},
            error=error,
        )
        self.events.append(event)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict()) + "\n")
        return event

    def time_event(
        self,
        *,
        node_name: str,
        event_type: str,
        status: str,
        input_summary: str = "",
        output_summary: str = "",
        payload: dict[str, Any] | None = None,
        error: str | None = None,
        started: float,
    ) -> TraceEvent:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return self.emit(
            node_name=node_name,
            event_type=event_type,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            payload=payload,
            error=error,
            latency_ms=latency_ms,
        )

