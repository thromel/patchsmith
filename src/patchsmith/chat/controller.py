from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from patchsmith.agent_apply import (
    apply_agent_run_diff,
    check_agent_run_diff,
    reverse_agent_run_diff,
)
from patchsmith.agent_cli import (
    AgentCliConfig,
    config_with_loaded_agent_instructions,
)
from patchsmith.chat.commands import ChatCommandContext
from patchsmith.chat.custom_commands import handle_custom_command
from patchsmith.chat.formatting import write_line
from patchsmith.chat.handlers.execution import handle_preflight_command
from patchsmith.chat.hooks import run_chat_hooks
from patchsmith.chat.registry import chat_command_registry
from patchsmith.chat.routing import parse_slash_command, route_natural_command
from patchsmith.chat.session_payloads import (
    config_payload,
    last_run_value,
)
from patchsmith.chat.session_resume import runtime_from_transcript
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.chat.task_runner import ModelPreflightChecker, run_chat_task
from patchsmith.chat.transcript import record_chat_event
from patchsmith.workflow import RepairRunner

_REGISTERED_CHAT_COMMANDS = chat_command_registry()


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
        runtime = runtime_from_transcript(state=state, fallback_config=config)
        if runtime is None:
            write_line(output_stream, f"Cannot resume missing session: {state.session_id}")
            write_line(output_stream, f"Expected transcript: {state.transcript_path}")
            return 2
        record_chat_event(
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
        record_chat_event(runtime, "session_start", {"config": config_payload(state.config)})
        banner = "PatchSmith Chat"

    write_line(output_stream, banner)
    write_line(output_stream, f"Session: {state.session_id}")
    write_line(output_stream, f"Transcript: {state.transcript_path}")
    write_line(output_stream, "Type /help for commands, /exit to quit.")
    if not run_chat_hooks(
        runtime=runtime,
        event="SessionStart",
        payload={
            "resume": resume,
            "config": config_payload(runtime.state.config),
        },
        output_stream=output_stream,
        blocking=True,
    ):
        record_chat_event(runtime, "session_end", {"reason": "session_start_hook_blocked"})
        return 2

    if initial_prompt.strip():
        run_chat_task(
            runtime=runtime,
            task=initial_prompt.strip(),
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
            record=record_chat_event,
            run_hooks=run_chat_hooks,
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
            record_chat_event(
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
            record_chat_event(runtime, "plan_mode_task", {"task": raw, "pending": True})
            write_line(
                output_stream,
                "Plan mode: running preflight only. Say 'go ahead' or use /run to execute.",
            )
            handle_preflight_command(
                runtime=runtime,
                argument=raw,
                output_stream=output_stream,
                context=ChatCommandContext(record=record_chat_event),
            )
            write_line(output_stream, f"Pending planned task: {raw}")
            continue
        run_chat_task(
            runtime=runtime,
            task=raw,
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
            record=record_chat_event,
            run_hooks=run_chat_hooks,
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
            record=record_chat_event,
            run_hooks=run_chat_hooks,
        )

    return ChatCommandContext(
        record=record_chat_event,
        run_hooks=run_chat_hooks,
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
    record_chat_event(runtime, "user_command", {"command": command, "argument": argument})
    context = _chat_command_context(
        runner_cls=runner_cls,
        model_preflight_checker=model_preflight_checker,
    )
    if command in {"exit", "quit"}:
        write_line(output_stream, "Session ended.")
        _end_session(runtime=runtime, reason=command, output_stream=output_stream)
        return False
    registered_command = _REGISTERED_CHAT_COMMANDS.get(command)
    if registered_command is not None:
        registered_command.handler(
            runtime=runtime,
            argument=argument,
            output_stream=output_stream,
            context=context,
        )
        return True
    if handle_custom_command(
        runtime=runtime,
        command=command,
        argument=argument,
        output_stream=output_stream,
        context=context,
    ):
        return True
    write_line(output_stream, f"Unknown command: /{command}")
    write_line(output_stream, "Type /help for available commands.")
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
    record_chat_event(runtime, "session_end", {"reason": reason})
    run_chat_hooks(
        runtime=runtime,
        event="SessionEnd",
        payload={"reason": reason},
        output_stream=output_stream,
        blocking=False,
    )


def _default_session_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())
