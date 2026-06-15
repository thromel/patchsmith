from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.session.store import read_transcript_rows


@dataclass(frozen=True)
class AgentSessionTimelineEntry:
    timestamp: str
    event: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "event": self.event,
            "summary": self.summary,
        }


def session_timeline(
    transcript_path: Path,
    *,
    limit: int = 20,
) -> list[AgentSessionTimelineEntry]:
    entries: list[AgentSessionTimelineEntry] = []
    for row in read_transcript_rows(transcript_path):
        event = row.get("event")
        payload = row.get("payload")
        timestamp = row.get("timestamp")
        if not isinstance(event, str):
            continue
        if not isinstance(timestamp, str):
            timestamp = "n/a"
        entries.append(
            AgentSessionTimelineEntry(
                timestamp=timestamp,
                event=event,
                summary=_event_summary(event, payload if isinstance(payload, dict) else {}),
            )
        )
    if limit <= 0:
        return entries
    return entries[-limit:]


def format_session_timeline(entries: list[AgentSessionTimelineEntry]) -> str:
    if not entries:
        return "No transcript events found."
    lines = [
        "Session timeline:",
        "Time | Event | Summary",
        "--- | --- | ---",
    ]
    for entry in entries:
        lines.append(
            " | ".join(
                [
                    _timeline_time(entry.timestamp),
                    entry.event,
                    entry.summary,
                ]
            )
        )
    return "\n".join(lines)


def _event_summary(event: str, payload: dict[str, object]) -> str:
    if event == "user_command":
        command = _plain_text(payload.get("command"))
        argument = _plain_text(payload.get("argument"))
        return _compact_text(f"/{command} {argument}".strip())
    if event == "user_task":
        return _compact_text(payload.get("task"))
    if event == "run_result":
        return _compact_text(
            " ".join(
                [
                    f"run={_plain_text(payload.get('run_id'))}",
                    f"status={_plain_text(payload.get('status'))}",
                    f"test={_plain_text(payload.get('test_exit_code'))}",
                    f"cost={_format_cost(payload.get('estimated_cost_usd'))}",
                ]
            )
        )
    if event == "run_error":
        return _compact_text(
            f"{_plain_text(payload.get('error_type'))}: {_plain_text(payload.get('message'))}"
        )
    if event == "verify_result":
        result = payload.get("result")
        verify_command = result.get("command") if isinstance(result, dict) else None
        exit_code = result.get("exit_code") if isinstance(result, dict) else None
        return _compact_text(
            " ".join(
                [
                    f"status={_plain_text(payload.get('status'))}",
                    f"exit={_plain_text(exit_code)}",
                    f"command={_plain_text(verify_command)}",
                ]
            )
        )
    if event == "diff_view":
        return _compact_text(
            " ".join(
                [
                    f"mode={_plain_text(payload.get('mode'))}",
                    f"files={_plain_text(payload.get('file_count'))}",
                    f"lines=+{_plain_text(payload.get('additions'))}/-{_plain_text(payload.get('deletions'))}",
                    f"shown={_plain_text(payload.get('shown_lines'))}/{_plain_text(payload.get('total_lines'))}",
                ]
            )
        )
    if event == "diff_review":
        return _compact_text(
            " ".join(
                [
                    f"risk={_plain_text(payload.get('risk_level'))}",
                    f"decision={_plain_text(payload.get('decision'))}",
                    f"confirm={_plain_text(payload.get('confirmation_required'))}",
                    f"findings={_list_count(payload.get('findings'))}",
                ]
            )
        )
    if event == "preflight":
        return _compact_text(f"status={_plain_text(payload.get('status'))}")
    if event == "run_preflight":
        preflight = payload.get("preflight")
        status = preflight.get("status") if isinstance(preflight, dict) else None
        checks = preflight.get("checks") if isinstance(preflight, dict) else None
        return _compact_text(
            " ".join(
                [
                    f"status={_plain_text(status)}",
                    f"checks={_list_count(checks)}",
                ]
            )
        )
    if event == "config_update":
        return _config_update_summary(payload)
    if event == "context_update":
        return _compact_text(
            " ".join(
                [
                    f"action={_plain_text(payload.get('action'))}",
                    f"path={_plain_text(payload.get('context_path'))}",
                    f"count={_list_count(payload.get('context_paths'))}",
                ]
            )
        )
    if event == "feedback_update":
        return _compact_text(
            " ".join(
                [
                    f"action={_plain_text(payload.get('action'))}",
                    f"item={_plain_text(payload.get('item'))}",
                    f"count={_list_count(payload.get('items'))}",
                ]
            )
        )
    if event == "plan_update":
        return _compact_text(
            " ".join(
                [
                    f"action={_plain_text(payload.get('action'))}",
                    f"count={_list_count(payload.get('items'))}",
                ]
            )
        )
    if event == "apply_result" or event == "apply_check_result" or event == "rewind_result":
        return _compact_text(
            f"status={_plain_text(payload.get('status'))} applied={_plain_text(payload.get('applied'))}"
        )
    if event == "apply_approval":
        return _compact_text(
            " ".join(
                [
                    f"risk={_plain_text(payload.get('risk_level'))}",
                    f"reason={_compact_text(payload.get('reason'), limit=80)}",
                ]
            )
        )
    if event == "apply_rejection":
        return _compact_text(
            " ".join(
                [
                    f"risk={_plain_text(payload.get('risk_level'))}",
                    f"reason={_compact_text(payload.get('reason'), limit=80)}",
                ]
            )
        )
    if event == "apply_blocked":
        return _compact_text(
            " ".join(
                [
                    f"reason={_plain_text(payload.get('reason_code'))}",
                    f"diff={_plain_text(payload.get('diff_path'))}",
                ]
            )
        )
    if event == "apply_auto_deferred":
        return _compact_text(
            " ".join(
                [
                    f"run={_plain_text(payload.get('run_id'))}",
                    f"reason={_plain_text(payload.get('reason_code'))}",
                ]
            )
        )
    if event == "session_gate":
        gate = payload.get("gate")
        status = gate.get("status") if isinstance(gate, dict) else None
        return _compact_text(
            f"profile={_plain_text(payload.get('argument'))} status={_plain_text(status)}"
        )
    if event == "run_evidence":
        return _compact_text(
            " ".join(
                [
                    f"run={_plain_text(payload.get('run_id'))}",
                    f"trace_events={_plain_text(payload.get('trace_event_count'))}",
                    f"diff_files={_plain_text(payload.get('diff_file_count'))}",
                ]
            )
        )
    if event == "session_checkpoint":
        return _compact_text(
            " ".join(
                [
                    f"id={_plain_text(payload.get('checkpoint_id'))}",
                    f"label={_plain_text(payload.get('label'))}",
                    f"last_run={_plain_text(payload.get('last_run_id'))}",
                ]
            )
        )
    if event == "session_restore":
        return _compact_text(
            f"id={_plain_text(payload.get('checkpoint_id'))} label={_plain_text(payload.get('label'))}"
        )
    if event == "session_timeline":
        return _compact_text(f"limit={_plain_text(payload.get('limit'))}")
    if event == "session_next":
        return _compact_text(payload.get("action"))
    if event == "hook_result":
        return _compact_text(
            f"event={_plain_text(payload.get('event'))} status={_plain_text(payload.get('status'))}"
        )
    if event == "custom_command":
        return _compact_text(f"/{_plain_text(payload.get('command'))}")
    if event == "session_start" or event == "session_resume":
        return _compact_text(f"repo={_config_value(payload, 'repo')}")
    if event == "session_end":
        return _compact_text(f"reason={_plain_text(payload.get('reason'))}")
    return _compact_text(payload)


def _config_update_summary(payload: dict[str, object]) -> str:
    field = _plain_text(payload.get("field"))
    if field == "deepagents_model":
        return _compact_text(f"field={field} value={_plain_text(payload.get('value'))}")
    if field == "resource_budget":
        return _compact_text(
            " ".join(
                [
                    "field=resource_budget",
                    f"responses={_plain_text(payload.get('max_model_responses'))}",
                    f"tokens={_plain_text(payload.get('max_model_tokens'))}",
                ]
            )
        )
    if field == "permissions":
        return _compact_text(
            " ".join(
                [
                    "field=permissions",
                    f"apply={_plain_text(payload.get('apply'))}",
                    f"dirty={_plain_text(payload.get('allow_dirty_apply'))}",
                ]
            )
        )
    if field == "agent_profile":
        return _compact_text(
            f"field=agent_profile name={_plain_text(payload.get('agent_profile'))}"
        )
    if field == "project_instructions":
        return _compact_text(
            " ".join(
                [
                    "field=project_instructions",
                    f"files={_list_count(payload.get('agent_instruction_files'))}",
                    f"chars={_plain_text(payload.get('agent_instruction_chars'))}",
                ]
            )
        )
    return _compact_text(f"field={field}")


def _config_value(payload: dict[str, object], key: str) -> str:
    config = payload.get("config")
    if isinstance(config, dict):
        return _plain_text(config.get(key))
    return _plain_text(payload.get(key))


def _list_count(value: object) -> str:
    if isinstance(value, list):
        return str(len(value))
    return "n/a"


def _timeline_time(timestamp: str) -> str:
    if len(timestamp) >= 19:
        return timestamp[:19]
    return timestamp


def _compact_text(value: object, *, limit: int = 120) -> str:
    text = _inline_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_cost(value: object) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"${float(value):.6f}"


def _inline_text(value: object) -> str:
    return _plain_text(value).replace("\n", " ")


def _plain_text(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return str(value)
