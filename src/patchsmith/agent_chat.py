from __future__ import annotations

import sys
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from patchsmith.agent_apply import (
    AgentApplyResult,
    apply_agent_run_diff,
    check_agent_run_diff,
    reverse_agent_run_diff,
)
from patchsmith.agent_cli import (
    AgentCliConfig,
    config_with_loaded_agent_instructions,
)
from patchsmith.agent_commands import (
    load_custom_command,
    render_custom_command_prompt,
)
from patchsmith.agent_hooks import (
    run_agent_hooks,
)
from patchsmith.agent_plan import (
    AgentPlanItem,
    plan_items_from_payload,
)
from patchsmith.agent_session import (
    transcript_rows,
)
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.checkpoints import checkpoint_commands
from patchsmith.chat.handlers.context import context_commands
from patchsmith.chat.handlers.diff_apply import diff_apply_commands
from patchsmith.chat.handlers.execution import (
    execution_commands,
    handle_preflight_command,
)
from patchsmith.chat.handlers.memory import memory_instruction_commands
from patchsmith.chat.handlers.model_budget import model_budget_commands
from patchsmith.chat.handlers.permissions import permission_commands
from patchsmith.chat.handlers.project import project_commands
from patchsmith.chat.handlers.session_evidence import session_evidence_commands
from patchsmith.chat.handlers.session_plan import plan_feedback_commands
from patchsmith.chat.handlers.session_state import session_state_commands
from patchsmith.chat.handlers.system import system_commands
from patchsmith.chat.routing import parse_slash_command, route_natural_command
from patchsmith.chat.session_payloads import (
    apply_config_update,
    apply_result_from_payload,
    apply_result_from_state,
    chat_mode_from_payload,
    config_from_payload,
    config_payload,
    context_paths_from_payload,
    dict_or_none,
    feedback_items_from_update,
    last_run_value,
    optional_text,
    string_list_from_payload,
)
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.chat.task_runner import ModelPreflightChecker, run_chat_task
from patchsmith.session.store import append_transcript_event
from patchsmith.workflow import RepairRunner

_REGISTERED_CHAT_COMMANDS = build_command_registry(
    (
        *system_commands(),
        *memory_instruction_commands(),
        *context_commands(),
        *model_budget_commands(),
        *permission_commands(),
        *plan_feedback_commands(),
        *project_commands(),
        *session_evidence_commands(),
        *diff_apply_commands(),
        *execution_commands(),
        *checkpoint_commands(),
        *session_state_commands(),
    )
)


def run_chat_session(
    *,
    config: AgentCliConfig,
    initial_prompt: str = "",
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    runner_cls: type[RepairRunner] = RepairRunner,
    model_preflight_checker: ModelPreflightChecker | None = None,
    session_id: str | None = None,
    resume: bool = False,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    state = _new_state(config=config, session_id=session_id)
    if resume:
        runtime = _runtime_from_transcript(state=state, fallback_config=config)
        if runtime is None:
            _write_line(output_stream, f"Cannot resume missing session: {state.session_id}")
            _write_line(output_stream, f"Expected transcript: {state.transcript_path}")
            return 2
        _record(
            runtime,
            "session_resume",
            {
                "config": config_payload(runtime.state.config),
                "history_count": len(runtime.history or []),
                "last_run_id": last_run_value(runtime, "run_id"),
            },
        )
        banner = "PatchSmith Chat (resumed)"
    else:
        runtime = AgentChatRuntime(state=state)
        _record(runtime, "session_start", {"config": config_payload(state.config)})
        banner = "PatchSmith Chat"

    _write_line(output_stream, banner)
    _write_line(output_stream, f"Session: {state.session_id}")
    _write_line(output_stream, f"Transcript: {state.transcript_path}")
    _write_line(output_stream, "Type /help for commands, /exit to quit.")
    if not _run_chat_hooks(
        runtime=runtime,
        event="SessionStart",
        payload={
            "resume": resume,
            "config": config_payload(runtime.state.config),
        },
        output_stream=output_stream,
        blocking=True,
    ):
        _record(runtime, "session_end", {"reason": "session_start_hook_blocked"})
        return 2

    if initial_prompt.strip():
        run_chat_task(
            runtime=runtime,
            task=initial_prompt.strip(),
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
            record=_record,
            run_hooks=_run_chat_hooks,
        )

    while True:
        line = _read_input(input_stream=input_stream, output_stream=output_stream)
        if line is None:
            _end_session(runtime=runtime, reason="eof", output_stream=output_stream)
            return 0
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("/"):
            should_continue = _handle_slash_command(
                runtime=runtime,
                raw=raw,
                output_stream=output_stream,
                runner_cls=runner_cls,
                model_preflight_checker=model_preflight_checker,
            )
            if not should_continue:
                return 0
            continue
        routed_command = route_natural_command(raw)
        if routed_command is not None:
            _record(
                runtime,
                "natural_command",
                {"raw": raw, "routed_command": routed_command},
            )
            should_continue = _handle_slash_command(
                runtime=runtime,
                raw=routed_command,
                output_stream=output_stream,
                runner_cls=runner_cls,
                model_preflight_checker=model_preflight_checker,
            )
            if not should_continue:
                return 0
            continue
        if runtime.chat_mode == "plan":
            runtime.pending_planned_task = raw
            _record(runtime, "plan_mode_task", {"task": raw, "pending": True})
            _write_line(
                output_stream,
                "Plan mode: running preflight only. Say 'go ahead' or use /run to execute.",
            )
            handle_preflight_command(
                runtime=runtime,
                argument=raw,
                output_stream=output_stream,
                context=ChatCommandContext(record=_record),
            )
            _write_line(output_stream, f"Pending planned task: {raw}")
            continue
        run_chat_task(
            runtime=runtime,
            task=raw,
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
            record=_record,
            run_hooks=_run_chat_hooks,
        )


def _new_state(*, config: AgentCliConfig, session_id: str | None) -> AgentChatState:
    config = config_with_loaded_agent_instructions(config)
    resolved_session_id = session_id or _default_session_id()
    transcript_dir = Path(config.artifacts_dir) / "chat_sessions"
    transcript_path = transcript_dir / f"{resolved_session_id}.jsonl"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    return AgentChatState(
        session_id=resolved_session_id,
        transcript_path=transcript_path,
        config=config,
    )


def _chat_command_context(
    *,
    runner_cls: type[RepairRunner],
    model_preflight_checker: ModelPreflightChecker | None,
) -> ChatCommandContext:
    def run_task(
        *,
        runtime: AgentChatRuntime,
        task: str,
        output_stream: TextIO,
    ) -> None:
        run_chat_task(
            runtime=runtime,
            task=task,
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
            record=_record,
            run_hooks=_run_chat_hooks,
        )

    return ChatCommandContext(
        record=_record,
        run_hooks=_run_chat_hooks,
        apply_agent_run_diff=apply_agent_run_diff,
        check_agent_run_diff=check_agent_run_diff,
        reverse_agent_run_diff=reverse_agent_run_diff,
        run_task=run_task,
    )


def _handle_slash_command(
    *,
    runtime: AgentChatRuntime,
    raw: str,
    output_stream: TextIO,
    runner_cls: type[RepairRunner],
    model_preflight_checker: ModelPreflightChecker | None,
) -> bool:
    command, argument = parse_slash_command(raw)
    _record(runtime, "user_command", {"command": command, "argument": argument})
    if command in {"exit", "quit"}:
        _write_line(output_stream, "Session ended.")
        _end_session(runtime=runtime, reason=command, output_stream=output_stream)
        return False
    registered_command = _REGISTERED_CHAT_COMMANDS.get(command)
    if registered_command is not None:
        registered_command.handler(
            runtime=runtime,
            argument=argument,
            output_stream=output_stream,
            context=_chat_command_context(
                runner_cls=runner_cls,
                model_preflight_checker=model_preflight_checker,
            ),
        )
        return True
    if _handle_custom_command(
        runtime=runtime,
        command=command,
        argument=argument,
        output_stream=output_stream,
        runner_cls=runner_cls,
        model_preflight_checker=model_preflight_checker,
    ):
        return True
    _write_line(output_stream, f"Unknown command: /{command}")
    _write_line(output_stream, "Type /help for available commands.")
    return True


def _handle_custom_command(
    *,
    runtime: AgentChatRuntime,
    command: str,
    argument: str,
    output_stream: TextIO,
    runner_cls: type[RepairRunner],
    model_preflight_checker: ModelPreflightChecker | None,
) -> bool:
    custom_command = load_custom_command(runtime.state.config.repo, command)
    if custom_command is None:
        return False
    prompt = render_custom_command_prompt(custom_command, argument)
    if not _run_chat_hooks(
        runtime=runtime,
        event="UserPromptExpansion",
        payload={
            "command": custom_command.name,
            "argument": argument,
            "command_path": str(custom_command.path),
            "prompt_chars": len(prompt),
            "matcher_target": custom_command.name,
        },
        output_stream=output_stream,
        blocking=True,
    ):
        return True
    _record(
        runtime,
        "custom_command",
        {
            "command": custom_command.name,
            "argument": argument,
            "command_path": str(custom_command.path),
            "prompt_chars": len(prompt),
        },
    )
    _write_line(output_stream, f"Running custom command: /{custom_command.name}")
    run_chat_task(
        runtime=runtime,
        task=prompt,
        output_stream=output_stream,
        runner_cls=runner_cls,
        model_preflight_checker=model_preflight_checker,
        record=_record,
        run_hooks=_run_chat_hooks,
    )
    return True


def _read_input(*, input_stream: TextIO, output_stream: TextIO) -> str | None:
    if _is_tty(input_stream):
        output_stream.write("patchsmith> ")
        output_stream.flush()
    line = input_stream.readline()
    if line == "":
        return None
    return line


def _end_session(
    *,
    runtime: AgentChatRuntime,
    reason: str,
    output_stream: TextIO,
) -> None:
    _record(runtime, "session_end", {"reason": reason})
    _run_chat_hooks(
        runtime=runtime,
        event="SessionEnd",
        payload={"reason": reason},
        output_stream=output_stream,
        blocking=False,
    )


def _run_chat_hooks(
    *,
    runtime: AgentChatRuntime,
    event: str,
    payload: dict[str, object],
    output_stream: TextIO,
    blocking: bool,
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
        _record(runtime, "hook_result", result.to_dict())
    if result.blocked:
        reason = result.block_reason or f"{event} blocked by hook"
        _write_line(output_stream, f"Hook blocked {event}: {reason}")
        return not blocking
    return True


def _record(runtime: AgentChatRuntime, event: str, payload: dict[str, object]) -> None:
    append_transcript_event(
        runtime.state.transcript_path,
        session_id=runtime.state.session_id,
        event=event,
        payload=payload,
    )


def _runtime_from_transcript(
    *,
    state: AgentChatState,
    fallback_config: AgentCliConfig,
) -> AgentChatRuntime | None:
    if not state.transcript_path.is_file():
        return None
    config = fallback_config
    history: list[str] = []
    last_run_payload: dict[str, object] | None = None
    last_apply: AgentApplyResult | None = None
    last_rewind: AgentApplyResult | None = None
    compaction_summary: dict[str, object] | None = None
    plan_items: list[AgentPlanItem] = []
    feedback_items: list[str] = []
    chat_mode = "act"
    pending_planned_task: str | None = None
    for row in transcript_rows(state.transcript_path):
        event = row.get("event")
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if event == "session_start":
            config_payload = payload.get("config")
            if isinstance(config_payload, dict):
                config = config_from_payload(config_payload, config)
        elif event == "context_update":
            context_paths = context_paths_from_payload(payload)
            if context_paths is not None:
                config = dataclass_replace(config, context_paths=context_paths)
        elif event == "config_update":
            config = apply_config_update(config, payload)
        elif event == "chat_mode_update":
            chat_mode = chat_mode_from_payload(payload.get("mode"))
        elif event == "plan_mode_task":
            pending_planned_task = optional_text(payload.get("task"))
        elif event in {"plan_mode_approval", "plan_mode_cancel"}:
            pending_planned_task = None
        elif event == "plan_update":
            plan_items = plan_items_from_payload(payload.get("items"))
        elif event == "feedback_update":
            feedback_items = feedback_items_from_update(
                current=feedback_items,
                payload=payload,
            )
        elif event == "user_task":
            task = payload.get("task")
            if isinstance(task, str):
                history.append(task)
                pending_planned_task = None
        elif event == "run_result":
            last_run_payload = dict(payload)
        elif event == "apply_result":
            last_apply = apply_result_from_payload(payload)
        elif event == "rewind_result":
            last_rewind = apply_result_from_payload(payload)
        elif event == "session_compact":
            history = []
            compaction_summary = dict(payload)
        elif event == "session_clear":
            history = []
            plan_items = []
            feedback_items = []
            last_run_payload = None
            last_apply = None
            last_rewind = None
            compaction_summary = None
            pending_planned_task = None
        elif event == "session_restore":
            state_payload = payload.get("state")
            if isinstance(state_payload, dict):
                config_payload = state_payload.get("config")
                if isinstance(config_payload, dict):
                    config = config_from_payload(config_payload, config)
                history = string_list_from_payload(state_payload.get("history"))
                plan_items = plan_items_from_payload(state_payload.get("plan_items"))
                feedback_items = string_list_from_payload(
                    state_payload.get("feedback_items")
                )
                last_run_payload = dict_or_none(state_payload.get("last_run_payload"))
                last_apply = apply_result_from_state(state_payload.get("last_apply"))
                last_rewind = apply_result_from_state(
                    state_payload.get("last_rewind")
                )
                chat_mode = chat_mode_from_payload(state_payload.get("chat_mode"))
                pending_planned_task = optional_text(
                    state_payload.get("pending_planned_task")
                )
                compaction_summary = dict_or_none(
                    state_payload.get("compaction_summary")
                )
    return AgentChatRuntime(
        state=dataclass_replace(state, config=config),
        chat_mode=chat_mode,
        pending_planned_task=pending_planned_task,
        history=history,
        last_run_payload=last_run_payload,
        last_apply=last_apply,
        last_rewind=last_rewind,
        compaction_summary=compaction_summary,
        plan_items=plan_items,
        feedback_items=feedback_items,
    )


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()


def _default_session_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())
