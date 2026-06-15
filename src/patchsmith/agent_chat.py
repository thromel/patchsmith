from __future__ import annotations

import sys
from collections.abc import Callable
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
    AgentCliRun,
    agent_diagnostic_payload,
    agent_preflight_payload,
    config_with_loaded_agent_instructions,
    run_agent_once,
    run_result_payload,
    validate_agent_cli_config,
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
    agent_plan_context,
    plan_items_from_payload,
    plan_items_payload,
)
from patchsmith.agent_session import (
    transcript_rows,
)
from patchsmith.chat.commands import ChatCommandContext, build_command_registry
from patchsmith.chat.handlers.checkpoints import checkpoint_commands
from patchsmith.chat.handlers.context import context_commands
from patchsmith.chat.handlers.diff_apply import diff_apply_commands
from patchsmith.chat.handlers.execution import execution_commands
from patchsmith.chat.handlers.memory import memory_instruction_commands
from patchsmith.chat.handlers.model_budget import model_budget_commands
from patchsmith.chat.handlers.permissions import permission_commands
from patchsmith.chat.handlers.project import project_commands
from patchsmith.chat.handlers.session_evidence import session_evidence_commands
from patchsmith.chat.handlers.session_plan import (
    agent_feedback_context,
    plan_feedback_commands,
)
from patchsmith.chat.handlers.session_state import session_state_commands
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
from patchsmith.model_preflight import ModelPreflightResult
from patchsmith.models import CommandResult
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.session.store import append_transcript_event
from patchsmith.workflow import RepairRunner

ModelPreflightChecker = Callable[[AgentCliConfig], ModelPreflightResult]

_REGISTERED_CHAT_COMMANDS = build_command_registry(
    (
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
        _handle_task(
            runtime=runtime,
            task=initial_prompt.strip(),
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
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
            _handle_preflight(
                runtime=runtime,
                task=raw,
                output_stream=output_stream,
            )
            _write_line(output_stream, f"Pending planned task: {raw}")
            continue
        _handle_task(
            runtime=runtime,
            task=raw,
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
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
        _handle_task(
            runtime=runtime,
            task=task,
            output_stream=output_stream,
            runner_cls=runner_cls,
            model_preflight_checker=model_preflight_checker,
        )

    return ChatCommandContext(
        record=_record,
        run_hooks=_run_chat_hooks,
        apply_agent_run_diff=apply_agent_run_diff,
        check_agent_run_diff=check_agent_run_diff,
        reverse_agent_run_diff=reverse_agent_run_diff,
        run_task=run_task,
        preflight_task=_handle_preflight,
        verify_command=_handle_verify,
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
    if command == "help":
        _print_help(output_stream)
        return True
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
    if command == "doctor":
        _handle_doctor(runtime=runtime, output_stream=output_stream)
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


def _handle_preflight(
    *,
    runtime: AgentChatRuntime,
    task: str,
    output_stream: TextIO,
) -> None:
    if not task:
        _write_line(output_stream, "Usage: /preflight <task>")
        return
    payload, error = _preflight_payload(runtime=runtime, task=task)
    if error:
        _write_line(output_stream, error)
        _record(runtime, "preflight_error", {"message": error})
        return
    _record(runtime, "preflight", payload)
    _write_line(output_stream, f"Preflight: {payload['status']}")
    _print_checks(payload["checks"], output_stream)


def _preflight_payload(
    *,
    runtime: AgentChatRuntime,
    task: str,
) -> tuple[dict[str, object], str | None]:
    runtime_config, apply_preflight, error = validate_agent_cli_config(
        runtime.state.config,
        require_apply_ready=False,
    )
    if error:
        return {}, error
    return (
        agent_preflight_payload(
            config=runtime.state.config,
            issue_text=task,
            runtime_config=runtime_config,
            apply_preflight=apply_preflight,
        ),
        None,
    )


def _handle_verify(
    *,
    runtime: AgentChatRuntime,
    argument: str,
    output_stream: TextIO,
) -> None:
    command = argument.strip() or runtime.state.config.test_command
    if not command:
        _write_line(output_stream, "Usage: /verify <allowed-test-command>")
        _write_line(output_stream, "No test command is configured for this session.")
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
    _record(runtime, "verify_result", payload)
    _write_line(output_stream, f"Verify: {payload['status']}")
    _write_line(output_stream, f"Command: {result.command}")
    exit_code = result.exit_code if result.exit_code is not None else "n/a"
    _write_line(output_stream, f"Exit code: {exit_code}")
    _write_line(output_stream, f"Duration: {result.duration_ms} ms")
    if not result.policy_decision.allowed:
        _write_line(output_stream, f"Policy: blocked - {result.policy_decision.reason}")
    if result.timed_out:
        _write_line(output_stream, "Timed out: true")
    _print_verify_output("stdout", result.stdout, output_stream)
    _print_verify_output("stderr", result.stderr, output_stream)


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
    _write_line(output_stream, f"{label}: {_truncate_line(value)}")


def _truncate_line(text: str, limit: int = 240) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return single_line[: limit - 3].rstrip() + "..."


def _handle_doctor(
    *,
    runtime: AgentChatRuntime,
    output_stream: TextIO,
) -> None:
    runtime_config, apply_preflight, error = validate_agent_cli_config(
        runtime.state.config,
        require_apply_ready=False,
    )
    if error:
        _write_line(output_stream, error)
        _record(runtime, "doctor_error", {"message": error})
        return
    payload = agent_diagnostic_payload(
        config=runtime.state.config,
        runtime_config=runtime_config,
        apply_preflight=apply_preflight,
    )
    _record(runtime, "doctor", payload)
    _write_line(output_stream, f"Doctor: {payload['status']}")
    _print_checks(payload["checks"], output_stream)


def _print_checks(checks: object, output_stream: TextIO) -> None:
    if not isinstance(checks, list):
        return
    for check in checks:
        if isinstance(check, dict):
            _write_line(
                output_stream,
                f"- {check['name']}: {check['status']} - {check['message']}",
            )


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
    _handle_task(
        runtime=runtime,
        task=prompt,
        output_stream=output_stream,
        runner_cls=runner_cls,
        model_preflight_checker=model_preflight_checker,
    )
    return True


def _handle_task(
    *,
    runtime: AgentChatRuntime,
    task: str,
    output_stream: TextIO,
    runner_cls: type[RepairRunner],
    model_preflight_checker: ModelPreflightChecker | None,
) -> None:
    plan_payload = plan_items_payload(runtime.plan_items or [])
    feedback_payload = list(runtime.feedback_items or [])
    if not _run_chat_hooks(
        runtime=runtime,
        event="UserPromptSubmit",
        payload={
            "task": task,
            "plan_items": plan_payload,
            "feedback_items": feedback_payload,
            "matcher_target": task,
        },
        output_stream=output_stream,
        blocking=True,
    ):
        return
    if not _run_chat_hooks(
        runtime=runtime,
        event="PreRun",
        payload={
            "task": task,
            "plan_items": plan_payload,
            "feedback_items": feedback_payload,
            "config": config_payload(runtime.state.config),
            "matcher_target": task,
        },
        output_stream=output_stream,
        blocking=True,
    ):
        return
    runtime.pending_planned_task = None
    runtime.last_task = task
    if runtime.history is not None:
        runtime.history.append(task)
    _record(
        runtime,
        "user_task",
        {
            "task": task,
            "plan_items": plan_payload,
            "feedback_items": feedback_payload,
        },
    )
    issue_text = _task_with_session_context(runtime=runtime, task=task)
    run_preflight, preflight_error = _preflight_payload(runtime=runtime, task=issue_text)
    if preflight_error:
        _write_line(output_stream, preflight_error)
        _record(
            runtime,
            "run_preflight_error",
            {"task": task, "message": preflight_error},
        )
        return
    _record(
        runtime,
        "run_preflight",
        {
            "task": task,
            "preflight": run_preflight,
        },
    )
    _write_line(output_stream, f"Run preflight: {run_preflight['status']}")
    if model_preflight_checker is not None and not _run_model_preflight(
        runtime=runtime,
        output_stream=output_stream,
        model_preflight_checker=model_preflight_checker,
    ):
        return
    _write_line(output_stream, "Running PatchSmith agent...")
    try:
        chat_run = run_agent_once(
            config=_chat_run_config(runtime.state.config),
            issue_text=issue_text,
            runner_cls=runner_cls,
        )
    except Exception as exc:
        message = str(exc)
        _write_line(output_stream, message)
        _record(
            runtime,
            "run_error",
            {"message": message, "error_type": type(exc).__name__},
        )
        return
    runtime.last_run = chat_run.result
    runtime.last_apply = chat_run.apply_result
    _print_run_summary(chat_run=chat_run, output_stream=output_stream)
    payload = run_result_payload(
        chat_run.result,
        runtime="deepagents",
        planner="deepagents",
        apply_result=chat_run.apply_result,
    )
    runtime.last_run_payload = payload
    _record(
        runtime,
        "run_result",
        payload,
    )
    if runtime.state.config.apply:
        deferred_payload: dict[str, object] = {
            "status": "deferred",
            "reason_code": "interactive_apply_requires_review",
            "run_id": chat_run.result.run_id,
            "diff_path": str(chat_run.result.final_diff_path),
            "message": (
                "interactive auto-apply is deferred until /diff review, "
                "/apply check, and /apply"
            ),
        }
        _record(runtime, "apply_auto_deferred", deferred_payload)
        _write_line(
            output_stream,
            "Auto apply deferred: run /diff review, /apply check, then /apply.",
        )
    _run_chat_hooks(
        runtime=runtime,
        event="PostRun",
        payload={
            "task": task,
            "plan_items": plan_payload,
            "feedback_items": feedback_payload,
            "run_id": chat_run.result.run_id,
            "status": chat_run.result.status,
            "test_exit_code": (
                chat_run.result.test_result.exit_code
                if chat_run.result.test_result is not None
                else None
            ),
            "report_path": str(chat_run.result.report_path),
            "trace_path": str(chat_run.result.trace_path),
            "final_diff_path": str(chat_run.result.final_diff_path),
            "matcher_target": chat_run.result.status,
        },
        output_stream=output_stream,
        blocking=False,
    )


def _run_model_preflight(
    *,
    runtime: AgentChatRuntime,
    output_stream: TextIO,
    model_preflight_checker: ModelPreflightChecker,
) -> bool:
    result = model_preflight_checker(runtime.state.config)
    payload = result.to_dict()
    _record(runtime, "model_preflight", payload)
    if result.available:
        _write_line(output_stream, f"Model preflight: {result.status} ({result.model})")
        return True
    _write_line(output_stream, f"Model preflight: {result.status} ({result.model})")
    if result.suggestions:
        _write_line(output_stream, "Model suggestions: " + ", ".join(result.suggestions))
    if result.error:
        _write_line(output_stream, f"Model preflight blocked: {result.error}")
    else:
        _write_line(output_stream, "Model preflight blocked: requested model is unavailable.")
    return False


def _chat_run_config(config: AgentCliConfig) -> AgentCliConfig:
    if not config.apply and not config.allow_dirty_apply:
        return config
    return dataclass_replace(config, apply=False, allow_dirty_apply=False)


def _task_with_session_context(*, runtime: AgentChatRuntime, task: str) -> str:
    sections = [
        section
        for section in (
            agent_plan_context(runtime.plan_items or []).strip(),
            agent_feedback_context(runtime.feedback_items or []).strip(),
        )
        if section
    ]
    if not sections:
        return task
    return "\n\n".join([*sections, f"Task:\n{task.strip()}"]).rstrip()


def _print_run_summary(*, chat_run: AgentCliRun, output_stream: TextIO) -> None:
    result = chat_run.result
    _write_line(output_stream, f"Run ID: {result.run_id}")
    _write_line(output_stream, f"Status: {result.status}")
    _write_line(output_stream, f"Report: {result.report_path}")
    _write_line(output_stream, f"Trace: {result.trace_path}")
    _write_line(output_stream, f"Diff: {result.final_diff_path}")
    if result.test_result:
        _write_line(output_stream, f"Test exit code: {result.test_result.exit_code}")
    if chat_run.apply_result is not None:
        _write_line(
            output_stream,
            f"Apply: {chat_run.apply_result.status} - {chat_run.apply_result.message}",
        )


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
