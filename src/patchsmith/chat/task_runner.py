from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace as dataclass_replace
from typing import TextIO

from patchsmith.agent_cli import (
    AgentCliConfig,
    AgentCliRun,
    run_agent_once,
    run_result_payload,
)
from patchsmith.agent_plan import agent_plan_context, plan_items_payload
from patchsmith.chat.commands import ChatEventRecorder, ChatHookRunner
from patchsmith.chat.formatting import write_line
from patchsmith.chat.handlers.session_plan import agent_feedback_context
from patchsmith.chat.preflight import preflight_payload
from patchsmith.chat.session_payloads import config_payload
from patchsmith.chat.state import AgentChatRuntime
from patchsmith.model_preflight import ModelPreflightResult
from patchsmith.workflow import RepairRunner

ModelPreflightChecker = Callable[[AgentCliConfig], ModelPreflightResult]


def run_chat_task(
    *,
    runtime: AgentChatRuntime,
    task: str,
    output_stream: TextIO,
    runner_cls: type[RepairRunner],
    model_preflight_checker: ModelPreflightChecker | None,
    record: ChatEventRecorder,
    run_hooks: ChatHookRunner,
) -> None:
    plan_payload = plan_items_payload(runtime.plan_items or [])
    feedback_payload = list(runtime.feedback_items or [])
    if not run_hooks(
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
    if not run_hooks(
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
    record(
        runtime,
        "user_task",
        {
            "task": task,
            "plan_items": plan_payload,
            "feedback_items": feedback_payload,
        },
    )
    issue_text = _task_with_session_context(runtime=runtime, task=task)
    run_preflight, preflight_error = preflight_payload(
        config=runtime.state.config,
        task=issue_text,
    )
    if preflight_error:
        write_line(output_stream, preflight_error)
        record(
            runtime,
            "run_preflight_error",
            {"task": task, "message": preflight_error},
        )
        return
    record(
        runtime,
        "run_preflight",
        {
            "task": task,
            "preflight": run_preflight,
        },
    )
    write_line(output_stream, f"Run preflight: {run_preflight['status']}")
    if model_preflight_checker is not None and not _run_model_preflight(
        runtime=runtime,
        output_stream=output_stream,
        model_preflight_checker=model_preflight_checker,
        record=record,
    ):
        return
    write_line(output_stream, "Running PatchSmith agent...")
    try:
        chat_run = run_agent_once(
            config=_chat_run_config(runtime.state.config),
            issue_text=issue_text,
            runner_cls=runner_cls,
        )
    except Exception as exc:
        message = str(exc)
        write_line(output_stream, message)
        record(
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
    record(
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
        record(runtime, "apply_auto_deferred", deferred_payload)
        write_line(
            output_stream,
            "Auto apply deferred: run /diff review, /apply check, then /apply.",
        )
    run_hooks(
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
    record: ChatEventRecorder,
) -> bool:
    result = model_preflight_checker(runtime.state.config)
    payload = result.to_dict()
    record(runtime, "model_preflight", payload)
    if result.available:
        write_line(output_stream, f"Model preflight: {result.status} ({result.model})")
        return True
    write_line(output_stream, f"Model preflight: {result.status} ({result.model})")
    if result.suggestions:
        write_line(output_stream, "Model suggestions: " + ", ".join(result.suggestions))
    if result.error:
        write_line(output_stream, f"Model preflight blocked: {result.error}")
    else:
        write_line(output_stream, "Model preflight blocked: requested model is unavailable.")
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
    write_line(output_stream, f"Run ID: {result.run_id}")
    write_line(output_stream, f"Status: {result.status}")
    write_line(output_stream, f"Report: {result.report_path}")
    write_line(output_stream, f"Trace: {result.trace_path}")
    write_line(output_stream, f"Diff: {result.final_diff_path}")
    if result.test_result:
        write_line(output_stream, f"Test exit code: {result.test_result.exit_code}")
    if chat_run.apply_result is not None:
        write_line(
            output_stream,
            f"Apply: {chat_run.apply_result.status} - {chat_run.apply_result.message}",
        )
