"""Portfolio quality gate (split from portfolio.py)."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from collections import Counter
from pathlib import Path

from patchsmith.artifacts import safe_artifact_name
from patchsmith.portfolio._helpers import _markdown_cell, _utc_now
from patchsmith.portfolio.models import QualityGateCheck, QualityGateReport


def build_quality_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    logs_dir: Path | None = None,
    timeout_seconds: int = 180,
    include_tests: bool = True,
    include_build: bool = True,
) -> QualityGateReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    logs_dir = (
        artifacts_dir / "experiments" / "quality_gate_logs"
        if logs_dir is None
        else logs_dir.resolve()
    )
    build_outdir = Path("/tmp/patchsmith-quality-gate-dist")
    commands: list[tuple[str, list[str] | None, str]] = [
        (
            "Compile Python sources",
            ["python3", "-m", "compileall", "-q", "src/patchsmith", "tests"],
            "Python compileall finished successfully.",
        ),
        (
            "Whitespace diff check",
            ["git", "diff", "--check"],
            "Git diff whitespace check passed.",
        ),
        (
            "Pytest suite",
            ["python3", "-m", "pytest", "-q"] if include_tests else None,
            "Pytest completed successfully.",
        ),
        (
            "Package build",
            [
                "uv",
                "run",
                "--with",
                "build",
                "--no-project",
                "python",
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                str(build_outdir),
            ]
            if include_build
            else None,
            "Source distribution and wheel build completed successfully.",
        ),
    ]
    checks = [
        _run_quality_gate_check(
            name=name,
            command=command,
            success_summary=success_summary,
            project_root=project_root,
            logs_dir=logs_dir,
            timeout_seconds=timeout_seconds,
        )
        for name, command, success_summary in commands
    ]
    status_counts = Counter(check.status for check in checks)
    return QualityGateReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        quality_status=_quality_gate_status(checks),
        passed_count=status_counts.get("passed", 0),
        failed_count=status_counts.get("failed", 0),
        skipped_count=status_counts.get("skipped", 0),
        checks=checks,
    )


def write_quality_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    logs_dir: Path | None = None,
    timeout_seconds: int = 180,
    include_tests: bool = True,
    include_build: bool = True,
) -> QualityGateReport:
    report = build_quality_gate_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        logs_dir=logs_dir,
        timeout_seconds=timeout_seconds,
        include_tests=include_tests,
        include_build=include_build,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_quality_gate_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_quality_gate_report(report: QualityGateReport) -> str:
    lines = [
        "# PatchSmith Quality Gate Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Quality status: `{report.quality_status}`",
        f"- Passed checks: `{report.passed_count}`",
        f"- Failed checks: `{report.failed_count}`",
        f"- Skipped checks: `{report.skipped_count}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Exit | Duration | Command | Stdout | Stderr | Summary |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{check.exit_code if check.exit_code is not None else ''} | "
            f"{check.duration_ms}ms | "
            f"{_markdown_cell(shlex.join(check.command))} | "
            f"{_markdown_cell(check.stdout_path or '')} | "
            f"{_markdown_cell(check.stderr_path or '')} | "
            f"{_markdown_cell(check.summary)} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- A passed quality gate proves local command execution for this checkout.",
            "- It does not prove Docker sandbox availability or live LLM calibration.",
            "- Release readiness still depends on release hygiene and launch blocker artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_quality_gate_check(
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


def _quality_gate_status(checks: list[QualityGateCheck]) -> str:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"
