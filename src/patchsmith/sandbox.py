from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from patchsmith.models import CommandResult
from patchsmith.security import CommandPolicy


class LocalSandboxRunner:
    """Development-only command runner with policy checks.

    The project safety docs call for Docker isolation. This runner is intentionally
    narrow and exists so the MVP lifecycle can be tested against seeded local repos.
    """

    def __init__(self, policy: CommandPolicy | None = None) -> None:
        self.policy = policy or CommandPolicy()

    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        workspace = workspace.resolve()
        decision = self.policy.evaluate(command, workspace=workspace)
        if not decision.allowed:
            return CommandResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr=decision.reason,
                duration_ms=0,
                timed_out=False,
                policy_decision=decision,
            )

        started = time.perf_counter()
        env = _sanitized_env(workspace)
        try:
            completed = subprocess.run(
                list(decision.tokens),
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return CommandResult(
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=duration_ms,
                timed_out=False,
                policy_decision=decision,
            )
        except subprocess.TimeoutExpired as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return CommandResult(
                command=command,
                exit_code=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "",
                duration_ms=duration_ms,
                timed_out=True,
                policy_decision=decision,
            )


def _sanitized_env(workspace: Path) -> dict[str, str]:
    env = {
        "HOME": str(workspace),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(workspace / "src"),
    }
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env

