from __future__ import annotations

from typing import TextIO

from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.state import AgentChatRuntime


def execution_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(
            name="preflight",
            handler=handle_preflight_command,
            usage="/preflight <task>",
        ),
        ChatCommand(
            name="verify",
            handler=handle_verify_command,
            usage="/verify [command]",
        ),
        ChatCommand(
            name="run",
            handler=handle_run_command,
            usage="/run <task>",
        ),
    )


def handle_preflight_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if context.preflight_task is None:
        raise RuntimeError("preflight task handler is not configured")
    context.preflight_task(
        runtime=runtime,
        task=argument,
        output_stream=output_stream,
    )


def handle_verify_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if context.verify_command is None:
        raise RuntimeError("verify command handler is not configured")
    context.verify_command(
        runtime=runtime,
        argument=argument,
        output_stream=output_stream,
    )


def handle_run_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if not argument and runtime.pending_planned_task is None:
        _write_line(output_stream, "No pending planned task. Usage: /run <task>")
        return
    task = argument or runtime.pending_planned_task or ""
    if not argument:
        context.record(runtime, "plan_mode_approval", {"task": task})
        runtime.pending_planned_task = None
        _write_line(output_stream, f"Approved planned task: {task}")
    if context.run_task is None:
        raise RuntimeError("run task handler is not configured")
    context.run_task(
        runtime=runtime,
        task=task,
        output_stream=output_stream,
    )


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
