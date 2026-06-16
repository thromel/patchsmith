from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from patchsmith.models import CommandResult
from patchsmith.security import CommandPolicy


@dataclass(frozen=True)
class DockerSandboxAvailability:
    available: bool
    errors: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SandboxRunner(Protocol):
    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        """Run a policy-checked command in a workspace."""


def _timeout_output(value: bytes | str | None) -> str:
    """Normalize TimeoutExpired output, which is bytes|str|None even with text=True."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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
                stdout=_timeout_output(error.stdout),
                stderr=_timeout_output(error.stderr),
                duration_ms=duration_ms,
                timed_out=True,
                policy_decision=decision,
            )


class DockerSandboxRunner:
    """Docker-backed command runner for stronger process and environment isolation."""

    def __init__(
        self,
        *,
        image: str = "python:3.12-slim",
        policy: CommandPolicy | None = None,
        docker_binary: str = "docker",
        network: str = "none",
        cpus: str = "2",
        memory: str = "2g",
    ) -> None:
        self.image = image
        self.policy = policy or CommandPolicy()
        self.docker_binary = docker_binary
        self.network = network
        self.cpus = cpus
        self.memory = memory

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

        container_name = f"patchsmith-{uuid.uuid4().hex[:12]}"
        docker_command = self._docker_command(
            workspace=workspace,
            container_name=container_name,
            command_tokens=decision.tokens,
        )
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                docker_command,
                env=_docker_host_env(),
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
            _remove_container(self.docker_binary, container_name)
            duration_ms = int((time.perf_counter() - started) * 1000)
            return CommandResult(
                command=command,
                exit_code=None,
                stdout=_timeout_output(error.stdout),
                stderr=_timeout_output(error.stderr),
                duration_ms=duration_ms,
                timed_out=True,
                policy_decision=decision,
            )
        except OSError as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return CommandResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr=f"docker sandbox failed to start: {error}",
                duration_ms=duration_ms,
                timed_out=False,
                policy_decision=decision,
            )

    def _docker_command(
        self,
        *,
        workspace: Path,
        container_name: str,
        command_tokens: tuple[str, ...],
    ) -> list[str]:
        user_args = _docker_user_args()
        return [
            self.docker_binary,
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            container_name,
            "--network",
            self.network,
            "--cpus",
            self.cpus,
            "--memory",
            self.memory,
            "--pids-limit",
            "256",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--workdir",
            "/workspace",
            "--volume",
            f"{workspace}:/workspace",
            "--env",
            "HOME=/workspace",
            "--env",
            "PYTHONPATH=/workspace/src",
            "--env",
            "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYTEST=9.0.0",
            *user_args,
            self.image,
            *command_tokens,
        ]


def create_sandbox_runner(
    *,
    mode: str,
    image: str = "python:3.12-slim",
    policy: CommandPolicy | None = None,
    network: str = "none",
) -> SandboxRunner:
    if mode == "local":
        return LocalSandboxRunner(policy=policy)
    if mode == "docker":
        return DockerSandboxRunner(image=image, policy=policy, network=network)
    raise ValueError(f"unsupported sandbox mode: {mode}")


def check_docker_sandbox_availability(
    *,
    image: str,
    docker_binary: str = "docker",
    timeout_seconds: int = 10,
) -> DockerSandboxAvailability:
    daemon = _run_docker_preflight_command(
        [docker_binary, "version", "--format", "{{.Server.Version}}"],
        timeout_seconds=timeout_seconds,
    )
    if daemon.returncode != 0:
        message = daemon.stderr.strip() or daemon.stdout.strip() or "no output"
        return DockerSandboxAvailability(
            available=False,
            errors=(f"`{docker_binary} version` failed: {message}",),
            next_actions=("Start Docker Desktop or point DOCKER_HOST at a reachable daemon.",),
        )
    image_check = _run_docker_preflight_command(
        [docker_binary, "image", "inspect", image],
        timeout_seconds=timeout_seconds,
    )
    if image_check.returncode != 0:
        message = image_check.stderr.strip() or image_check.stdout.strip() or "image not found"
        return DockerSandboxAvailability(
            available=False,
            errors=(f"`{image}` is not available locally: {message}",),
            evidence=(
                f"Docker server version `{daemon.stdout.strip() or 'unknown'}` is reachable.",
            ),
            next_actions=(f"Run `docker build -f docker/seeded-smoke.Dockerfile -t {image} .`.",),
        )
    return DockerSandboxAvailability(
        available=True,
        evidence=(
            f"Docker server version `{daemon.stdout.strip() or 'unknown'}` is reachable.",
            f"`{image}` is available locally.",
        ),
    )


def _sanitized_env(workspace: Path) -> dict[str, str]:
    env = {
        "HOME": str(workspace),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(workspace / "src"),
        "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYTEST": "9.0.0",
    }
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def _docker_host_env() -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "")}
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _run_docker_preflight_command(
    command: list[str],
    *,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_docker_host_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(
            command,
            returncode=127,
            stdout="",
            stderr=str(error),
        )


def _docker_user_args() -> list[str]:
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        return ["--user", f"{os.getuid()}:{os.getgid()}"]
    return []


def _remove_container(docker_binary: str, container_name: str) -> None:
    subprocess.run(
        [docker_binary, "rm", "-f", container_name],
        check=False,
        capture_output=True,
        text=True,
        env=_docker_host_env(),
    )
