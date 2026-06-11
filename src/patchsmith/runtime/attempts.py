from __future__ import annotations

from pathlib import Path

from patchsmith.models import CommandResult, RunRequest
from patchsmith.runtime.core import AgentResult
from patchsmith.sandbox import SandboxRunner
from patchsmith.tracing import RunTrace


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
        timeout_seconds=60,
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


def test_feedback_retry_budget(request: RunRequest) -> int:
    if request.runtime == "deepagents" and request.planner == "deepagents":
        return max(0, request.max_retries)
    return 0


def should_retry_with_test_feedback(
    *,
    request: RunRequest,
    agent_result: AgentResult,
    test_result: CommandResult | None,
    attempt: int,
    max_feedback_retries: int,
) -> bool:
    if test_feedback_retry_budget(request) == 0:
        return False
    if attempt > max_feedback_retries:
        return False
    if agent_result.status == "patch_generated":
        if test_result is None:
            return False
        return test_result.exit_code != 0
    if agent_result.status not in {"no_patch_generated", "failed"}:
        return False
    return test_result is None or test_result.exit_code != 0


def issue_with_test_feedback(
    *,
    original_issue: str,
    agent_status: str,
    agent_summary: str,
    test_result: CommandResult | None,
    final_diff: str,
    attempt: int,
) -> str:
    sections = [
        original_issue.strip(),
        (
            f"Previous DeepAgents repair attempt {attempt} did not validate. "
            "Repair the current workspace state with one bounded replacement. "
            "You may fix a prior bad patch or provide a different exact old span "
            "if the previous edit was rejected. Before choosing the next edit, "
            "check whether the previous patch is on the code path reached by the "
            "unchanged failure; if not, move the fix to the earlier branch, cache "
            "return, or dispatch point that controls the failing behavior."
        ),
        f"Previous agent status:\n{agent_status}",
        f"Previous agent summary:\n{_truncate_feedback(agent_summary)}",
    ]
    if test_result is not None:
        sections.extend(
            [
                f"Sandbox command:\n{test_result.command}",
                f"Sandbox exit code:\n{test_result.exit_code}",
                f"Sandbox stdout:\n{_truncate_feedback(test_result.stdout)}",
                f"Sandbox stderr:\n{_truncate_feedback(test_result.stderr)}",
            ]
        )
    sections.append(f"Current diff after failed attempt:\n{_truncate_feedback(final_diff)}")
    return "\n\n".join(sections)


def _truncate_feedback(text: str, limit: int = 4_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"
