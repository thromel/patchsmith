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
from patchsmith.agent_commands import (
    load_custom_command,
    render_custom_command_prompt,
)
from patchsmith.agent_hooks import (
    run_agent_hooks,
)
from patchsmith.chat.commands import ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.handlers.execution import handle_preflight_command
from patchsmith.chat.registry import chat_command_registry
from patchsmith.chat.routing import parse_slash_command, route_natural_command
from patchsmith.chat.session_payloads import (
    config_payload,
    last_run_value,
)
from patchsmith.chat.session_resume import runtime_from_transcript
from patchsmith.chat.state import AgentChatRuntime, AgentChatState
from patchsmith.chat.task_runner import ModelPreflightChecker, run_chat_task
from patchsmith.session.store import append_transcript_event
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

    write_line(output_stream, banner)
    write_line(output_stream, f"Session: {state.session_id}")
    write_line(output_stream, f"Transcript: {state.transcript_path}")
    write_line(output_stream, "Type /help for commands, /exit to quit.")
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
            write_line(
                output_stream,
                "Plan mode: running preflight only. Say 'go ahead' or use /run to execute.",
            )
            handle_preflight_command(
                runtime=runtime,
                argument=raw,
                output_stream=output_stream,
                context=ChatCommandContext(record=_record),
            )
            write_line(output_stream, f"Pending planned task: {raw}")
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
        write_line(output_stream, "Session ended.")
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
    write_line(output_stream, f"Unknown command: /{command}")
    write_line(output_stream, "Type /help for available commands.")
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
    write_line(output_stream, f"Running custom command: /{custom_command.name}")
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
        write_line(output_stream, f"Hook blocked {event}: {reason}")
        return not blocking
    return True


def _record(runtime: AgentChatRuntime, event: str, payload: dict[str, object]) -> None:
    append_transcript_event(
        runtime.state.transcript_path,
        session_id=runtime.state.session_id,
        event=event,
        payload=payload,
    )


def _default_session_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())
