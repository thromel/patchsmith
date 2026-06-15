from __future__ import annotations

from pathlib import Path
from typing import TextIO

from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.preflight import preflight_payload, print_checks
from patchsmith.chat.state import AgentChatRuntime
from patchsmith.models import CommandResult
from patchsmith.sandbox import create_sandbox_runner


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
    if not argument:
        write_line(output_stream, "Usage: /preflight <task>")
        return
    payload, error = preflight_payload(
        config=runtime.state.config,
        task=argument,
    )
    if error:
        write_line(output_stream, error)
        context.record(runtime, "preflight_error", {"message": error})
        return
    context.record(runtime, "preflight", payload)
    write_line(output_stream, f"Preflight: {payload['status']}")
    print_checks(payload["checks"], output_stream)


def handle_verify_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    command = argument.strip() or runtime.state.config.test_command
    if not command:
        write_line(output_stream, "Usage: /verify <allowed-test-command>")
        write_line(output_stream, "No test command is configured for this session.")
        return
    sandbox = create_sandbox_runner(
        mode=runtime.state.config.sandbox_mode,
        image=runtime.state.config.sandbox_image,
    )
    result = sandbox.run(
        command=command,
        workspace=Path(runtime.state.config.repo),
        timeout_seconds=60,
    )
    payload: dict[str, object] = {
        "sandbox_mode": runtime.state.config.sandbox_mode,
        "sandbox_image": runtime.state.config.sandbox_image,
        "result": result.to_dict(),
        "status": _verify_status(result),
    }
    context.record(runtime, "verify_result", payload)
    write_line(output_stream, f"Verify: {payload['status']}")
    write_line(output_stream, f"Command: {result.command}")
    exit_code = result.exit_code if result.exit_code is not None else "n/a"
    write_line(output_stream, f"Exit code: {exit_code}")
    write_line(output_stream, f"Duration: {result.duration_ms} ms")
    if not result.policy_decision.allowed:
        write_line(output_stream, f"Policy: blocked - {result.policy_decision.reason}")
    if result.timed_out:
        write_line(output_stream, "Timed out: true")
    _print_verify_output("stdout", result.stdout, output_stream)
    _print_verify_output("stderr", result.stderr, output_stream)


def handle_run_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    if not argument and runtime.pending_planned_task is None:
        write_line(output_stream, "No pending planned task. Usage: /run <task>")
        return
    task = argument or runtime.pending_planned_task or ""
    if not argument:
        context.record(runtime, "plan_mode_approval", {"task": task})
        runtime.pending_planned_task = None
        write_line(output_stream, f"Approved planned task: {task}")
    if context.run_task is None:
        raise RuntimeError("run task handler is not configured")
    context.run_task(
        runtime=runtime,
        task=task,
        output_stream=output_stream,
    )


def _verify_status(result: CommandResult) -> str:
    if not result.policy_decision.allowed:
        return "blocked"
    if result.timed_out:
        return "timed_out"
    if result.exit_code == 0:
        return "passed"
    return "failed"


def _print_verify_output(label: str, text: str, output_stream: TextIO) -> None:
    value = text.strip()
    if not value:
        return
    write_line(output_stream, f"{label}: {_truncate_line(value)}")


def _truncate_line(text: str, limit: int = 240) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return single_line[: limit - 3].rstrip() + "..."
