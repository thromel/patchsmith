"""Shared command-check execution for portfolio gates."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from patchsmith.artifacts import safe_artifact_name
from patchsmith.portfolio.models import QualityGateCheck


def run_command_check(
    *,
    name: str,
    command: list[str] | None,
    success_summary: str,
    project_root: Path,
    logs_dir: Path,
    timeout_seconds: int,
) -> QualityGateCheck:
    safe_name = safe_artifact_name(name, lowercase=True, fallback="artifact")
    stdout_path = logs_dir / f"{safe_name}_stdout.txt"
    stderr_path = logs_dir / f"{safe_name}_stderr.txt"
    if command is None:
        return QualityGateCheck(
            name=name,
            status="skipped",
            command=[],
            cwd=str(project_root),
            exit_code=None,
            duration_ms=0,
            stdout_path=None,
            stderr_path=None,
            summary="Skipped by request.",
        )
    logs_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        status = "passed" if result.returncode == 0 else "failed"
        summary = success_summary if status == "passed" else f"Command exited {result.returncode}."
        return QualityGateCheck(
            name=name,
            status=status,
            command=command,
            cwd=str(project_root),
            exit_code=result.returncode,
            duration_ms=duration_ms,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            summary=summary,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = getattr(error, "stdout", "") or ""
        stderr = getattr(error, "stderr", "") or str(error)
        stdout_path.write_text(str(stdout), encoding="utf-8")
        stderr_path.write_text(str(stderr), encoding="utf-8")
        return QualityGateCheck(
            name=name,
            status="failed",
            command=command,
            cwd=str(project_root),
            exit_code=None,
            duration_ms=duration_ms,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            summary=f"{type(error).__name__}: {error}",
        )
