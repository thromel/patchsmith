from __future__ import annotations

from typing import TextIO

from patchsmith.agent_cli import (
    agent_diagnostic_payload,
    validate_agent_cli_config,
)
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
from patchsmith.chat.formatting import write_line
from patchsmith.chat.state import AgentChatRuntime


def system_commands() -> tuple[ChatCommand, ...]:
    return (
        ChatCommand(name="help", handler=handle_help_command, usage="/help"),
        ChatCommand(name="doctor", handler=handle_doctor_command, usage="/doctor"),
    )


def handle_help_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    _print_help(output_stream)


def handle_doctor_command(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
    context: ChatCommandContext,
) -> None:
    runtime_config, apply_preflight, error = validate_agent_cli_config(
        runtime.state.config,
        require_apply_ready=False,
    )
    if error:
        write_line(output_stream, error)
        context.record(runtime, "doctor_error", {"message": error})
        return
    payload = agent_diagnostic_payload(
        config=runtime.state.config,
        runtime_config=runtime_config,
        apply_preflight=apply_preflight,
    )
    context.record(runtime, "doctor", payload)
    write_line(output_stream, f"Doctor: {payload['status']}")
    _print_checks(payload["checks"], output_stream)


def _print_help(output_stream: TextIO) -> None:
    write_line(output_stream, "Commands:")
    write_line(output_stream, "  /help                 Show this help.")
    write_line(output_stream, "  /status               Show session and last-run state.")
    write_line(output_stream, "  /history              Show tasks run in this session.")
    write_line(output_stream, "  /mode [act|plan]      Set plain-text behavior.")
    write_line(output_stream, "  /run                  Execute the pending plan-mode task.")
    write_line(output_stream, "  /timeline [n]         Show recent transcript events.")
    write_line(output_stream, "  /next                 Recommend the next evidence-backed action.")
    write_line(output_stream, "  /sessions             List resumable chat sessions.")
    write_line(output_stream, "  /commands             List project custom slash commands.")
    write_line(output_stream, "  /hooks                List project lifecycle hooks.")
    write_line(output_stream, "  /agents               List project agent profiles.")
    write_line(output_stream, "  /agent [name|clear]   Show, select, or clear an agent profile.")
    write_line(
        output_stream, "  /instructions         Show, reload, or clear project instructions."
    )
    write_line(output_stream, "  /memory               Show, add, reload, or clear project memory.")
    write_line(output_stream, "  /plan ...             Show or update the session plan.")
    write_line(output_stream, "  /feedback ...         Add, show, or clear session feedback.")
    write_line(output_stream, "  /permissions          Show or change apply permissions.")
    write_line(output_stream, "  /approve apply <why>  Approve applying a high-risk reviewed diff.")
    write_line(output_stream, "  /reject apply <why>   Reject applying the current reviewed diff.")
    write_line(output_stream, "  /cancel [plan]        Cancel the pending plan-mode task.")
    write_line(output_stream, "  /clear                Clear in-memory session state.")
    write_line(output_stream, "  /compact [note]       Compact task history into the transcript.")
    write_line(output_stream, "  /checkpoint [label]   Save restorable session state.")
    write_line(output_stream, "  /checkpoints          List saved session checkpoints.")
    write_line(output_stream, "  /restore <id|label>   Restore a saved checkpoint.")
    write_line(output_stream, "  /doctor               Check local agent readiness.")
    write_line(output_stream, "  /cost                 Summarize transcript usage and cost.")
    write_line(output_stream, "  /metrics              Show transcript process metrics.")
    write_line(output_stream, "  /gate [profile]       Evaluate session evidence gates.")
    write_line(output_stream, "  /trace, /evidence     Show last-run trace/report/diff evidence.")
    write_line(output_stream, "  /export [path]        Export transcript summary as Markdown.")
    write_line(output_stream, "  /context show         Show forced context hints.")
    write_line(output_stream, "  /context add <path>   Add a repo-relative context hint.")
    write_line(output_stream, "  /context remove <path> Remove a forced context hint.")
    write_line(output_stream, "  /context clear        Clear forced context hints.")
    write_line(output_stream, "  /model [id|clear]     Show or set the DeepAgents model override.")
    write_line(output_stream, "  /budget ...           Show or set response/token caps.")
    write_line(output_stream, "  /preflight <task>     Validate config without a model call.")
    write_line(output_stream, "  /verify [command]     Run a policy-checked test command.")
    write_line(output_stream, "  /run <task>           Run the DeepAgents repair loop.")
    write_line(output_stream, "  /apply [check]        Dry-run-check or apply the reviewed diff.")
    write_line(output_stream, "  /rewind, /undo        Reverse the last generated diff.")
    write_line(output_stream, "  /diff [stat|show|review] Review the last generated diff.")
    write_line(output_stream, "  /exit, /quit          End the session.")
    write_line(
        output_stream,
        "In act mode, plain text runs /run <task>. In plan mode, plain text "
        "runs /preflight <task>; say 'go ahead' to run or 'cancel plan' to discard "
        "the pending planned task. "
        "Obvious phrases like 'what next?' route to commands.",
    )
    write_line(
        output_stream,
        "Project commands are loaded from .patchsmith/commands/*.md.",
    )
    write_line(
        output_stream,
        "Project hooks are loaded from .patchsmith/hooks.json.",
    )
    write_line(
        output_stream,
        "Project agent profiles are loaded from .patchsmith/agents/*.md.",
    )
    write_line(
        output_stream,
        "Project instructions are loaded from AGENTS.md/CLAUDE.md-style files.",
    )


def _print_checks(checks: object, output_stream: TextIO) -> None:
    if not isinstance(checks, list):
        return
    for check in checks:
        if isinstance(check, dict):
            write_line(
                output_stream,
                f"- {check['name']}: {check['status']} - {check['message']}",
            )
