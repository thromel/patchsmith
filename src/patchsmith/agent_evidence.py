from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentRunEvidence:
    run_id: str | None
    status: str | None
    test_exit_code: int | None
    report_path: str | None
    trace_path: str | None
    final_diff_path: str | None
    report_exists: bool
    trace_exists: bool
    diff_exists: bool
    report_bytes: int | None
    trace_bytes: int | None
    diff_bytes: int | None
    trace_event_count: int
    trace_status_counts: tuple[tuple[str, int], ...]
    trace_node_counts: tuple[tuple[str, int], ...]
    failed_trace_event_count: int
    diff_file_count: int
    diff_changed_files: tuple[str, ...]
    diff_additions: int
    diff_deletions: int
    model_call_count: int | None
    model_response_count: int | None
    model_total_tokens: int | None
    estimated_cost_usd: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "test_exit_code": self.test_exit_code,
            "report_path": self.report_path,
            "trace_path": self.trace_path,
            "final_diff_path": self.final_diff_path,
            "report_exists": self.report_exists,
            "trace_exists": self.trace_exists,
            "diff_exists": self.diff_exists,
            "report_bytes": self.report_bytes,
            "trace_bytes": self.trace_bytes,
            "diff_bytes": self.diff_bytes,
            "trace_event_count": self.trace_event_count,
            "trace_status_counts": dict(self.trace_status_counts),
            "trace_node_counts": dict(self.trace_node_counts),
            "failed_trace_event_count": self.failed_trace_event_count,
            "diff_file_count": self.diff_file_count,
            "diff_changed_files": list(self.diff_changed_files),
            "diff_additions": self.diff_additions,
            "diff_deletions": self.diff_deletions,
            "model_call_count": self.model_call_count,
            "model_response_count": self.model_response_count,
            "model_total_tokens": self.model_total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass(frozen=True)
class _PathStats:
    path: str | None
    exists: bool
    bytes: int | None


@dataclass(frozen=True)
class _DiffStats:
    file_count: int
    changed_files: tuple[str, ...]
    additions: int
    deletions: int


def summarize_agent_run_evidence(
    run_payload: Mapping[str, object],
) -> AgentRunEvidence:
    report = _path_stats(_optional_str(run_payload.get("report_path")))
    trace = _path_stats(_optional_str(run_payload.get("trace_path")))
    diff = _path_stats(_optional_str(run_payload.get("final_diff_path")))

    trace_events = _read_trace_events(trace.path)
    trace_status_counts = _top_counts(_trace_status(event) for event in trace_events)
    trace_node_counts = _top_counts(_trace_node(event) for event in trace_events)
    failed_events = sum(1 for event in trace_events if _trace_event_failed(event))
    diff_stats = _diff_stats(diff.path)

    return AgentRunEvidence(
        run_id=_optional_str(run_payload.get("run_id")),
        status=_optional_str(run_payload.get("status")),
        test_exit_code=_optional_int(run_payload.get("test_exit_code")),
        report_path=report.path,
        trace_path=trace.path,
        final_diff_path=diff.path,
        report_exists=report.exists,
        trace_exists=trace.exists,
        diff_exists=diff.exists,
        report_bytes=report.bytes,
        trace_bytes=trace.bytes,
        diff_bytes=diff.bytes,
        trace_event_count=len(trace_events),
        trace_status_counts=trace_status_counts,
        trace_node_counts=trace_node_counts,
        failed_trace_event_count=failed_events,
        diff_file_count=diff_stats.file_count,
        diff_changed_files=diff_stats.changed_files,
        diff_additions=diff_stats.additions,
        diff_deletions=diff_stats.deletions,
        model_call_count=_optional_int(run_payload.get("model_call_count")),
        model_response_count=_optional_int(run_payload.get("model_response_count")),
        model_total_tokens=_optional_int(run_payload.get("model_total_tokens")),
        estimated_cost_usd=_optional_float(run_payload.get("estimated_cost_usd")),
    )


def format_agent_run_evidence(evidence: AgentRunEvidence) -> str:
    lines = [
        f"Run evidence: {evidence.run_id or 'n/a'}",
        f"- Status: {evidence.status or 'n/a'}",
        f"- Test exit code: {_format_optional(evidence.test_exit_code)}",
        (
            "- Report: "
            f"{_format_artifact(evidence.report_path, evidence.report_exists, evidence.report_bytes)}"
        ),
        (
            "- Trace: "
            f"{_format_artifact(evidence.trace_path, evidence.trace_exists, evidence.trace_bytes)}"
        ),
        f"- Trace events: {evidence.trace_event_count}",
        f"- Trace statuses: {_format_counts(evidence.trace_status_counts)}",
        f"- Trace nodes: {_format_counts(evidence.trace_node_counts)}",
        f"- Failed trace events: {evidence.failed_trace_event_count}",
        (
            "- Diff: "
            f"{_format_artifact(evidence.final_diff_path, evidence.diff_exists, evidence.diff_bytes)}"
        ),
        f"- Diff files: {evidence.diff_file_count}",
        f"- Diff lines: +{evidence.diff_additions} / -{evidence.diff_deletions}",
    ]
    if evidence.diff_changed_files:
        lines.append(f"- Changed files: {', '.join(evidence.diff_changed_files[:5])}")
    lines.extend(
        [
            f"- Model calls: {_format_optional(evidence.model_call_count)}",
            f"- Model responses: {_format_optional(evidence.model_response_count)}",
            f"- Model tokens: {_format_optional(evidence.model_total_tokens)}",
            f"- Estimated cost: {_format_cost(evidence.estimated_cost_usd)}",
        ]
    )
    return "\n".join(lines)


def _path_stats(raw_path: str | None) -> _PathStats:
    if not raw_path:
        return _PathStats(path=None, exists=False, bytes=None)
    path = Path(raw_path)
    if not path.is_file():
        return _PathStats(path=raw_path, exists=False, bytes=None)
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    return _PathStats(path=raw_path, exists=True, bytes=size)


def _read_trace_events(raw_path: str | None) -> list[dict[str, Any]]:
    if not raw_path:
        return []
    path = Path(raw_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.extend(_json_events(parsed))
    return events


def _json_events(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _trace_status(event: Mapping[str, Any]) -> str:
    status = event.get("status")
    if isinstance(status, str) and status:
        return status
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload_status = payload.get("status")
        if isinstance(payload_status, str) and payload_status:
            return payload_status
    return "unknown"


def _trace_node(event: Mapping[str, Any]) -> str:
    for key in ("node_name", "node", "event_type", "event", "type"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _trace_event_failed(event: Mapping[str, Any]) -> bool:
    status = _trace_status(event).lower()
    return status in {"failed", "error", "blocked"} or event.get("error") is not None


def _diff_stats(raw_path: str | None) -> _DiffStats:
    if not raw_path:
        return _DiffStats(file_count=0, changed_files=(), additions=0, deletions=0)
    path = Path(raw_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return _DiffStats(file_count=0, changed_files=(), additions=0, deletions=0)
    changed_files: list[str] = []
    additions = 0
    deletions = 0
    for line in lines:
        if line.startswith("diff --git "):
            changed = _changed_file_from_diff_header(line)
            if changed and changed not in changed_files:
                changed_files.append(changed)
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return _DiffStats(
        file_count=len(changed_files),
        changed_files=tuple(changed_files),
        additions=additions,
        deletions=deletions,
    )


def _changed_file_from_diff_header(line: str) -> str | None:
    parts = line.split()
    if len(parts) < 4:
        return None
    candidate = parts[3]
    if candidate.startswith("b/"):
        return candidate[2:]
    return candidate


def _top_counts(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counter = Counter(value for value in values if isinstance(value, str) and value)
    return tuple(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:8])


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None


def _format_artifact(path: str | None, exists: bool, size: int | None) -> str:
    if not path:
        return "n/a"
    status = "exists" if exists else "missing"
    if size is None:
        return f"{path} ({status})"
    return f"{path} ({status}, {size} bytes)"


def _format_counts(counts: tuple[tuple[str, int], ...]) -> str:
    if not counts:
        return "n/a"
    return ", ".join(f"{label}={count}" for label, count in counts)


def _format_optional(value: object) -> str:
    return str(value) if value is not None else "n/a"


def _format_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.6f}"
