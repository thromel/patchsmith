from __future__ import annotations

from typing import TextIO

from patchsmith.agent_cli import (
    agent_diagnostic_payload,
    validate_agent_cli_config,
)
from patchsmith.chat.commands import ChatCommand, ChatCommandContext
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
        _write_line(output_stream, error)
        context.record(runtime, "doctor_error", {"message": error})
        return
    payload = agent_diagnostic_payload(
        config=runtime.state.config,
        runtime_config=runtime_config,
        apply_preflight=apply_preflight,
    )
    context.record(runtime, "doctor", payload)
    _write_line(output_stream, f"Doctor: {payload['status']}")
    _print_checks(payload["checks"], output_stream)


def _print_help(output_stream: TextIO) -> None:
    _write_line(output_stream, "Commands:")
    _write_line(output_stream, "  /help                 Show this help.")
    _write_line(output_stream, "  /status               Show session and last-run state.")
    _write_line(output_stream, "  /history              Show tasks run in this session.")
    _write_line(output_stream, "  /mode [act|plan]      Set plain-text behavior.")
    _write_line(output_stream, "  /run                  Execute the pending plan-mode task.")
    _write_line(output_stream, "  /timeline [n]         Show recent transcript events.")
    _write_line(output_stream, "  /next                 Recommend the next evidence-backed action.")
    _write_line(output_stream, "  /sessions             List resumable chat sessions.")
    _write_line(output_stream, "  /commands             List project custom slash commands.")
    _write_line(output_stream, "  /hooks                List project lifecycle hooks.")
    _write_line(output_stream, "  /agents               List project agent profiles.")
    _write_line(output_stream, "  /agent [name|clear]   Show, select, or clear an agent profile.")
    _write_line(output_stream, "  /instructions         Show, reload, or clear project instructions.")
    _write_line(output_stream, "  /memory               Show, add, reload, or clear project memory.")
    _write_line(output_stream, "  /plan ...             Show or update the session plan.")
    _write_line(output_stream, "  /feedback ...         Add, show, or clear session feedback.")
    _write_line(output_stream, "  /permissions          Show or change apply permissions.")
    _write_line(output_stream, "  /approve apply <why>  Approve applying a high-risk reviewed diff.")
    _write_line(output_stream, "  /reject apply <why>   Reject applying the current reviewed diff.")
    _write_line(output_stream, "  /cancel [plan]        Cancel the pending plan-mode task.")
    _write_line(output_stream, "  /clear                Clear in-memory session state.")
    _write_line(output_stream, "  /compact [note]       Compact task history into the transcript.")
    _write_line(output_stream, "  /checkpoint [label]   Save restorable session state.")
    _write_line(output_stream, "  /checkpoints          List saved session checkpoints.")
    _write_line(output_stream, "  /restore <id|label>   Restore a saved checkpoint.")
    _write_line(output_stream, "  /doctor               Check local agent readiness.")
    _write_line(output_stream, "  /cost                 Summarize transcript usage and cost.")
    _write_line(output_stream, "  /metrics              Show transcript process metrics.")
    _write_line(output_stream, "  /gate [profile]       Evaluate session evidence gates.")
    _write_line(output_stream, "  /trace, /evidence     Show last-run trace/report/diff evidence.")
    _write_line(output_stream, "  /export [path]        Export transcript summary as Markdown.")
    _write_line(output_stream, "  /context show         Show forced context hints.")
    _write_line(output_stream, "  /context add <path>   Add a repo-relative context hint.")
    _write_line(output_stream, "  /context remove <path> Remove a forced context hint.")
    _write_line(output_stream, "  /context clear        Clear forced context hints.")
    _write_line(output_stream, "  /model [id|clear]     Show or set the DeepAgents model override.")
    _write_line(output_stream, "  /budget ...           Show or set response/token caps.")
    _write_line(output_stream, "  /preflight <task>     Validate config without a model call.")
    _write_line(output_stream, "  /verify [command]     Run a policy-checked test command.")
    _write_line(output_stream, "  /run <task>           Run the DeepAgents repair loop.")
    _write_line(output_stream, "  /apply [check]        Dry-run-check or apply the reviewed diff.")
    _write_line(output_stream, "  /rewind, /undo        Reverse the last generated diff.")
    _write_line(output_stream, "  /diff [stat|show|review] Review the last generated diff.")
    _write_line(output_stream, "  /exit, /quit          End the session.")
    _write_line(
        output_stream,
        "In act mode, plain text runs /run <task>. In plan mode, plain text "
        "runs /preflight <task>; say 'go ahead' to run or 'cancel plan' to discard "
        "the pending planned task. "
        "Obvious phrases like 'what next?' route to commands.",
    )
    _write_line(
        output_stream,
        "Project commands are loaded from .patchsmith/commands/*.md.",
    )
    _write_line(
        output_stream,
        "Project hooks are loaded from .patchsmith/hooks.json.",
    )
    _write_line(
        output_stream,
        "Project agent profiles are loaded from .patchsmith/agents/*.md.",
    )
    _write_line(
        output_stream,
        "Project instructions are loaded from AGENTS.md/CLAUDE.md-style files.",
    )


def _print_checks(checks: object, output_stream: TextIO) -> None:
    if not isinstance(checks, list):
        return
    for check in checks:
        if isinstance(check, dict):
            _write_line(
                output_stream,
                f"- {check['name']}: {check['status']} - {check['message']}",
            )


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
