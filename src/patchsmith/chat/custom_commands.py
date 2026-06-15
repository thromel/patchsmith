from __future__ import annotations

from typing import TextIO

from patchsmith.agent_commands import (
    load_custom_command,
    render_custom_command_prompt,
)
from patchsmith.chat.commands import ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def handle_custom_command(
    *,
    runtime: AgentChatRuntime,
    command: str,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> bool:
    custom_command = load_custom_command(runtime.state.config.repo, command)
    if custom_command is None:
        return False
    prompt = render_custom_command_prompt(custom_command, argument)
    if context.run_hooks is not None and not context.run_hooks(
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
    context.record(
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
    if context.run_task is None:
        write_line(output_stream, "Custom command cannot run without a task runner.")
        return True
    context.run_task(
        runtime=runtime,
        task=prompt,
        output_stream=output_stream,
    )
    return True
