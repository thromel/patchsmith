"""Execution of a single sandboxed validation attempt.

This concern is intentionally separate from the retry-feedback generation in
:mod:`patchsmith.runtime.attempts`: running a command in the sandbox and
emitting its trace events does not depend on any of the retry classification,
labelling, or feedback-brief logic.
"""

from __future__ import annotations

from pathlib import Path

from patchsmith.models import CommandResult, RunRequest
from patchsmith.runtime.core import AgentResult
from patchsmith.sandbox import SandboxRunner
from patchsmith.tracing import RunTrace

# Wall-clock timeout for each sandboxed test command attempt.
SANDBOX_ATTEMPT_TIMEOUT_SECONDS = 60


def emit_agent_result_trace(
    *,
    trace: RunTrace,
    request: RunRequest,
    agent_result: AgentResult,
    attempt: int,
) -> None:
    trace.emit(
        node_name="runtime",
        event_type="agent_result",
        status=agent_result.status,
        output_summary=agent_result.summary,
        payload={
            "runtime": request.runtime,
            "planner": request.planner,
            "attempt": attempt,
            "patch_candidates": [
                candidate.to_dict() for candidate in agent_result.patch_candidates
            ],
        },
    )
    for runtime_event in agent_result.runtime_trace:
        trace.emit(
            node_name=f"runtime.{runtime_event.get('node', 'unknown')}",
            event_type="runtime_node",
            status=str(runtime_event.get("status", "completed")),
            output_summary=str(runtime_event.get("summary", "")),
            payload={
                "runtime": request.runtime,
                "planner": request.planner,
                "workflow_attempt": attempt,
                **runtime_event,
            },
        )


def run_sandbox_attempt(
    *,
    command: str | None,
    sandbox: SandboxRunner,
    repo_path: Path,
    logs_dir: Path,
    trace: RunTrace,
    request: RunRequest,
    attempt: int,
) -> CommandResult | None:
    if not command:
        trace.emit(
            node_name="test",
            event_type="sandbox_command",
            status="skipped",
            output_summary="no test command supplied or detected",
            payload={
                "attempt": attempt,
                "sandbox_mode": request.sandbox_mode,
            },
        )
        return None

    test_result = sandbox.run(
        command=command,
        workspace=repo_path,
        timeout_seconds=SANDBOX_ATTEMPT_TIMEOUT_SECONDS,
    )
    (logs_dir / "stdout.txt").write_text(test_result.stdout, encoding="utf-8")
    (logs_dir / "stderr.txt").write_text(test_result.stderr, encoding="utf-8")
    (logs_dir / f"stdout_attempt_{attempt}.txt").write_text(
        test_result.stdout,
        encoding="utf-8",
    )
    (logs_dir / f"stderr_attempt_{attempt}.txt").write_text(
        test_result.stderr,
        encoding="utf-8",
    )
    trace.emit(
        node_name="test",
        event_type="sandbox_command",
        status="completed" if test_result.exit_code == 0 else "failed",
        input_summary=command,
        output_summary=f"exit_code={test_result.exit_code}",
        payload={
            **test_result.to_dict(),
            "attempt": attempt,
            "sandbox_mode": request.sandbox_mode,
            "sandbox_image": request.sandbox_image if request.sandbox_mode == "docker" else None,
        },
        latency_ms=test_result.duration_ms,
    )
    return test_result
