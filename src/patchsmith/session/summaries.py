from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.session.events import TranscriptEvent
from patchsmith.session.metrics import session_usage_payload
from patchsmith.session.store import read_known_transcript_events


@dataclass(frozen=True)
class AgentSessionSummary:
    session_id: str
    transcript_path: Path
    started_at: str | None
    updated_at: str | None
    repo: str | None
    task_count: int
    run_count: int
    validated_run_count: int
    run_error_count: int
    estimated_cost_usd: float
    last_run_id: str | None
    last_status: str | None


def list_session_summaries(artifacts_dir: Path) -> list[AgentSessionSummary]:
    transcript_dir = artifacts_dir / "chat_sessions"
    if not transcript_dir.is_dir():
        return []
    summaries = [
        session_summary(path)
        for path in sorted(transcript_dir.glob("*.jsonl"))
        if path.is_file()
    ]
    return sorted(
        summaries,
        key=lambda summary: summary.updated_at or summary.started_at or summary.session_id,
        reverse=True,
    )


def session_summary(transcript_path: Path) -> AgentSessionSummary:
    rows = read_known_transcript_events(transcript_path)
    usage = session_usage_payload(transcript_path)
    config = _latest_config(rows) or {}
    last_run = _latest_payload(rows, "run_result") or {}
    return AgentSessionSummary(
        session_id=_first_text(rows, "session_id") or transcript_path.stem,
        transcript_path=transcript_path,
        started_at=_first_text(rows, "timestamp"),
        updated_at=_last_text(rows, "timestamp"),
        repo=_optional_str(config.get("repo")),
        task_count=_int_field(usage, "task_count"),
        run_count=_int_field(usage, "run_count"),
        validated_run_count=_int_field(usage, "validated_run_count"),
        run_error_count=_int_field(usage, "run_error_count"),
        estimated_cost_usd=_float_field(usage, "estimated_cost_usd"),
        last_run_id=_optional_str(last_run.get("run_id")),
        last_status=_optional_str(last_run.get("status")),
    )


def format_session_summaries(summaries: list[AgentSessionSummary]) -> str:
    if not summaries:
        return "No chat sessions found."
    lines = [
        "Session | Updated | Tasks | Runs | Validated | Errors | Cost | Last",
        "--- | --- | ---: | ---: | ---: | ---: | ---: | ---",
    ]
    for summary in summaries:
        lines.append(
            " | ".join(
                [
                    summary.session_id,
                    summary.updated_at or "n/a",
                    str(summary.task_count),
                    str(summary.run_count),
                    str(summary.validated_run_count),
                    str(summary.run_error_count),
                    _format_cost(summary.estimated_cost_usd),
                    _last_label(summary),
                ]
            )
        )
    return "\n".join(lines)


def _latest_config(rows: list[TranscriptEvent]) -> dict[str, object] | None:
    config: dict[str, object] | None = None
    for row in rows:
        event = row.event
        payload = row.payload
        if event == "session_start":
            value = payload.get("config")
            if isinstance(value, dict):
                config = dict(value)
        elif event == "config_update" and config is not None:
            _apply_config_update(config, payload)
        elif event == "context_update" and config is not None:
            paths = payload.get("context_paths")
            if isinstance(paths, list):
                config["context_paths"] = [path for path in paths if isinstance(path, str)]
    return config


def _apply_config_update(
    config: dict[str, object],
    payload: dict[str, object],
) -> None:
    field = payload.get("field")
    if field == "deepagents_model":
        config["deepagents_model"] = payload.get("value")
    elif field == "resource_budget":
        config["max_model_responses"] = payload.get("max_model_responses")
        config["max_model_tokens"] = payload.get("max_model_tokens")
    elif field == "permissions":
        config["apply"] = payload.get("apply")
        config["allow_dirty_apply"] = payload.get("allow_dirty_apply")
    elif field == "agent_profile":
        for key in (
            "agent_profile",
            "agent_profile_path",
            "agent_profile_description",
            "agent_profile_instructions",
            "agent_profile_instruction_chars",
            "deepagents_model",
            "deepagents_subagents",
            "deepagents_max_context_files",
            "max_model_responses",
            "max_model_tokens",
            "top_k",
            "test_command",
            "context_paths",
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)
    elif field == "project_instructions":
        for key in (
            "load_agent_instructions",
            "instruction_paths",
            "agent_instruction_files",
            "agent_instructions",
            "agent_instruction_chars",
        ):
            if key in payload:
                config[key] = payload.get(key)


def _payloads(
    rows: list[TranscriptEvent],
    event: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for row in rows:
        if row.event != event:
            continue
        payloads.append(row.payload)
    return payloads


def _latest_payload(
    rows: list[TranscriptEvent],
    event: str,
) -> dict[str, object] | None:
    payloads = _payloads(rows, event)
    return payloads[-1] if payloads else None


def _first_text(rows: list[TranscriptEvent], key: str) -> str | None:
    for row in rows:
        value = _event_text_field(row, key)
        if value:
            return value
    return None


def _last_text(rows: list[TranscriptEvent], key: str) -> str | None:
    for row in reversed(rows):
        value = _event_text_field(row, key)
        if value:
            return value
    return None


def _event_text_field(row: TranscriptEvent, key: str) -> str | None:
    if key == "timestamp":
        return row.timestamp or None
    if key == "session_id":
        return row.session_id or None
    return None


def _int_field(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else 0


def _float_field(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else 0.0


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _last_label(summary: AgentSessionSummary) -> str:
    if summary.last_run_id is None:
        return "n/a"
    if summary.last_status is None:
        return summary.last_run_id
    return f"{summary.last_run_id} ({summary.last_status})"


def _format_cost(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"${float(value):.6f}"
