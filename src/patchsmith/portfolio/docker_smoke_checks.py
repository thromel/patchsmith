"""Docker smoke preflight checks and environment helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from patchsmith.portfolio.models import DockerSmokeCheck


def docker_daemon_check(docker_binary: str) -> DockerSmokeCheck:
    try:
        result = subprocess.run(
            [docker_binary, "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DockerSmokeCheck(
            name="Docker Daemon",
            status="missing",
            evidence=f"Docker daemon check failed: {error}.",
            next_action="Start Docker Desktop or point DOCKER_HOST at a reachable daemon.",
        )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "no output"
        return DockerSmokeCheck(
            name="Docker Daemon",
            status="missing",
            evidence=f"`{docker_binary} version` failed: {stderr}",
            next_action="Start Docker Desktop or point DOCKER_HOST at a reachable daemon.",
        )
    version = result.stdout.strip() or "unknown"
    return DockerSmokeCheck(
        name="Docker Daemon",
        status="passed",
        evidence=f"Docker server version `{version}` is reachable.",
        next_action="No action needed.",
    )


def docker_image_check(docker_binary: str, image: str) -> DockerSmokeCheck:
    try:
        result = subprocess.run(
            [docker_binary, "image", "inspect", image],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DockerSmokeCheck(
            name="Smoke Image",
            status="missing",
            evidence=f"Docker image inspection failed: {error}.",
            next_action=f"Build `{image}` before running the smoke.",
        )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "image not found"
        return DockerSmokeCheck(
            name="Smoke Image",
            status="missing",
            evidence=f"`{image}` is not available locally: {stderr}",
            next_action=f"Run `docker build -f docker/seeded-smoke.Dockerfile -t {image} .`.",
        )
    return DockerSmokeCheck(
        name="Smoke Image",
        status="passed",
        evidence=f"`{image}` is available locally.",
        next_action="No action needed.",
    )


def docker_environment_snapshot(docker_binary: str) -> dict[str, str]:
    home_socket = Path.home() / ".docker" / "run" / "docker.sock"
    default_socket = Path("/var/run/docker.sock")
    docker_desktop_paths = [
        Path("/Applications/Docker.app"),
        Path.home() / "Applications" / "Docker.app",
    ]
    return {
        "docker_binary": docker_binary,
        "docker_cli_path": shutil.which(docker_binary) or "missing",
        "DOCKER_HOST": os.environ.get("DOCKER_HOST", "unset"),
        "DOCKER_CONTEXT": os.environ.get("DOCKER_CONTEXT", "unset"),
        "DOCKER_CONFIG": os.environ.get("DOCKER_CONFIG", "unset"),
        "docker_desktop_application": (
            "exists" if any(path.exists() for path in docker_desktop_paths) else "missing"
        ),
        "colima_binary": shutil.which("colima") or "missing",
        str(home_socket): "exists" if home_socket.exists() else "missing",
        str(default_socket): "exists" if default_socket.exists() else "missing",
    }


def docker_remediation_commands(
    *,
    docker_binary: str,
    build_command: str,
    smoke_command: str,
    environment: dict[str, str],
) -> list[str]:
    commands = [
        f"{docker_binary} context ls",
        f"{docker_binary} version",
    ]
    if environment.get("docker_desktop_application") == "exists":
        commands.append("open -a Docker")
    if environment.get("colima_binary", "missing") != "missing":
        commands.append("colima start")
    commands.extend([build_command, smoke_command])
    return commands


def docker_smoke_status(checks: list[DockerSmokeCheck]) -> str:
    statuses = [check.status for check in checks]
    if "failed" in statuses:
        return "failed"
    if "missing" in statuses:
        return "not_available"
    if "skipped" in statuses:
        return "skipped"
    return "passed"


__all__ = [
    "docker_daemon_check",
    "docker_environment_snapshot",
    "docker_image_check",
    "docker_remediation_commands",
    "docker_smoke_status",
]
