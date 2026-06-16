"""Product release gate for repeatable local release checks."""

from __future__ import annotations

import shlex
import sys
import time
from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.evaluation.complex import load_complex_benchmark_results
from patchsmith.portfolio._helpers import _markdown_cell, _utc_now
from patchsmith.portfolio.command_checks import run_command_check
from patchsmith.portfolio.models import QualityGateCheck, ReleaseGateReport
from patchsmith.session.report import export_session_report
from patchsmith.session.store import append_transcript_event

DEFAULT_RELEASE_GATE_TIMEOUT_SECONDS = 900
REQUIRED_OWNERSHIP_BOUNDARY_REFERENCES = (
    "patchsmith.chat",
    "patchsmith.session",
    "patchsmith.cli",
    "patchsmith.deepagents_",
    "patchsmith.runtime",
    "patchsmith.evaluation.complex",
    "patchsmith.evaluation.issue_corpus",
    "patchsmith.portfolio",
    "patchsmith.context",
    "patchsmith.patching",
)


def build_release_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    logs_dir: Path | None = None,
    timeout_seconds: int = DEFAULT_RELEASE_GATE_TIMEOUT_SECONDS,
    include_unit_tests: bool = True,
    include_smoke: bool = True,
    include_build: bool = True,
    include_cli_help: bool = True,
    include_sample_transcript_export: bool = True,
    include_benchmark_validation: bool = True,
    benchmark_results_path: Path | None = None,
) -> ReleaseGateReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    logs_dir = (
        artifacts_dir / "experiments" / "release_gate_logs"
        if logs_dir is None
        else logs_dir.resolve()
    )
    benchmark_results_path = benchmark_results_path or (
        artifacts_dir
        / "experiments"
        / "complex_benchmark_suite"
        / "complex_benchmark_results.json"
    )
    checks = [
        *_command_checks(
            project_root=project_root,
            logs_dir=logs_dir,
            timeout_seconds=timeout_seconds,
            include_unit_tests=include_unit_tests,
            include_smoke=include_smoke,
            include_build=include_build,
            include_cli_help=include_cli_help,
        ),
        _ownership_docs_check(project_root=project_root),
        _sample_transcript_export_check(
            project_root=project_root,
            artifacts_dir=artifacts_dir,
            include=include_sample_transcript_export,
        ),
        _saved_benchmark_validation_check(
            project_root=project_root,
            benchmark_results_path=benchmark_results_path,
            include=include_benchmark_validation,
        ),
    ]
    status_counts = Counter(check.status for check in checks)
    return ReleaseGateReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        release_status=_release_gate_status(checks),
        passed_count=status_counts.get("passed", 0),
        failed_count=status_counts.get("failed", 0),
        skipped_count=status_counts.get("skipped", 0),
        checks=checks,
        review_artifacts=_release_gate_review_artifacts(
            project_root=project_root,
            artifacts_dir=artifacts_dir,
            benchmark_results_path=benchmark_results_path,
        ),
    )


def write_release_gate_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    logs_dir: Path | None = None,
    timeout_seconds: int = DEFAULT_RELEASE_GATE_TIMEOUT_SECONDS,
    include_unit_tests: bool = True,
    include_smoke: bool = True,
    include_build: bool = True,
    include_cli_help: bool = True,
    include_sample_transcript_export: bool = True,
    include_benchmark_validation: bool = True,
    benchmark_results_path: Path | None = None,
) -> ReleaseGateReport:
    report = build_release_gate_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        logs_dir=logs_dir,
        timeout_seconds=timeout_seconds,
        include_unit_tests=include_unit_tests,
        include_smoke=include_smoke,
        include_build=include_build,
        include_cli_help=include_cli_help,
        include_sample_transcript_export=include_sample_transcript_export,
        include_benchmark_validation=include_benchmark_validation,
        benchmark_results_path=benchmark_results_path,
    )
    write_markdown(output_path, render_release_gate_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_release_gate_report(report: ReleaseGateReport) -> str:
    lines = [
        "# PatchSmith Release Gate Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Release status: `{report.release_status}`",
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
            "## Review Artifacts",
            "",
        ]
    )
    if report.review_artifacts:
        lines.extend(f"- `{artifact}`" for artifact in report.review_artifacts)
    else:
        lines.append("- No review artifacts were produced.")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- A passed release gate proves this checkout passed the configured local checks.",
            "- It does not prove live-provider solve rate, Docker availability, or CI status.",
            "- Skipped checks must be resolved before using the report as release evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _command_checks(
    *,
    project_root: Path,
    logs_dir: Path,
    timeout_seconds: int,
    include_unit_tests: bool,
    include_smoke: bool,
    include_build: bool,
    include_cli_help: bool,
) -> list[QualityGateCheck]:
    build_outdir = Path("/tmp/patchsmith-release-gate-dist")
    commands: list[tuple[str, list[str] | None, str]] = [
        (
            "Unit test suite",
            [sys.executable, "-m", "pytest", "-q"] if include_unit_tests else None,
            "Full pytest suite completed successfully.",
        ),
        (
            "Focused smoke lane",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/chat/test_session_resume.py",
                "tests/session/test_transcript_migration.py",
                "tests/evaluation/complex/test_compatibility.py",
            ]
            if include_smoke
            else None,
            "Focused smoke lane completed successfully.",
        ),
        (
            "Package build",
            [
                "uv",
                "run",
                "--with",
                "build",
                "--with",
                "hatchling>=1.27",
                "--no-project",
                "python",
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(build_outdir),
            ]
            if include_build
            else None,
            "Source distribution and wheel build completed successfully.",
        ),
        (
            "CLI help snapshot",
            [sys.executable, "-m", "patchsmith.cli", "--help"] if include_cli_help else None,
            "Top-level CLI help rendered successfully.",
        ),
        (
            "Agent CLI help snapshot",
            (
                [sys.executable, "-m", "patchsmith.cli", "agent", "--help"]
                if include_cli_help
                else None
            ),
            "Agent CLI help rendered successfully.",
        ),
        (
            "Chat CLI help snapshot",
            (
                [sys.executable, "-m", "patchsmith.cli", "chat", "--help"]
                if include_cli_help
                else None
            ),
            "Chat CLI help rendered successfully.",
        ),
    ]
    return [
        run_command_check(
            name=name,
            command=command,
            success_summary=success_summary,
            project_root=project_root,
            logs_dir=logs_dir,
            timeout_seconds=timeout_seconds,
        )
        for name, command, success_summary in commands
    ]


def _sample_transcript_export_check(
    *,
    project_root: Path,
    artifacts_dir: Path,
    include: bool,
) -> QualityGateCheck:
    if not include:
        return _in_process_check(
            name="Sample transcript export",
            command=["internal", "sample-transcript-export"],
            project_root=project_root,
            status="skipped",
            summary="Skipped by request.",
        )
    started = time.perf_counter()
    transcript_path = artifacts_dir / "experiments" / "release_gate" / "sample_session.jsonl"
    report_path = artifacts_dir / "experiments" / "release_gate" / "sample_session.md"
    try:
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        if transcript_path.exists():
            transcript_path.unlink()
        append_transcript_event(
            transcript_path,
            session_id="release-gate-sample",
            event="user_task",
            payload={"task": "validate release transcript export"},
            timestamp="2026-06-16T00:00:00+00:00",
        )
        append_transcript_event(
            transcript_path,
            session_id="release-gate-sample",
            event="run_result",
            payload={"run_id": "sample-run", "status": "completed", "test_exit_code": 0},
            timestamp="2026-06-16T00:00:01+00:00",
        )
        export_session_report(transcript_path=transcript_path, report_path=report_path)
    except OSError as error:
        return _in_process_check(
            name="Sample transcript export",
            command=["internal", "sample-transcript-export"],
            project_root=project_root,
            status="failed",
            duration_ms=_duration_ms(started),
            summary=f"{type(error).__name__}: {error}",
        )
    return _in_process_check(
        name="Sample transcript export",
        command=["internal", "sample-transcript-export"],
        project_root=project_root,
        status="passed",
        duration_ms=_duration_ms(started),
        summary=f"Exported sample transcript report to {report_path}.",
    )


def _ownership_docs_check(*, project_root: Path) -> QualityGateCheck:
    started = time.perf_counter()
    docs_path = project_root / "docs" / "23_product_boundary_ownership.md"
    if not docs_path.is_file():
        return _in_process_check(
            name="Product boundary ownership docs",
            command=["internal", "ownership-docs"],
            project_root=project_root,
            status="failed",
            duration_ms=_duration_ms(started),
            summary=f"Missing ownership docs: {docs_path}.",
        )
    try:
        text = docs_path.read_text(encoding="utf-8")
    except OSError as error:
        return _in_process_check(
            name="Product boundary ownership docs",
            command=["internal", "ownership-docs"],
            project_root=project_root,
            status="failed",
            duration_ms=_duration_ms(started),
            summary=f"{type(error).__name__}: {error}",
        )
    missing = [
        reference
        for reference in REQUIRED_OWNERSHIP_BOUNDARY_REFERENCES
        if reference not in text
    ]
    if missing:
        return _in_process_check(
            name="Product boundary ownership docs",
            command=["internal", "ownership-docs"],
            project_root=project_root,
            status="failed",
            duration_ms=_duration_ms(started),
            summary="Missing boundary references: " + ", ".join(missing) + ".",
        )
    return _in_process_check(
        name="Product boundary ownership docs",
        command=["internal", "ownership-docs"],
        project_root=project_root,
        status="passed",
        duration_ms=_duration_ms(started),
        summary=(
            f"Ownership docs cover {len(REQUIRED_OWNERSHIP_BOUNDARY_REFERENCES)} "
            "required boundary references."
        ),
    )


def _saved_benchmark_validation_check(
    *,
    project_root: Path,
    benchmark_results_path: Path,
    include: bool,
) -> QualityGateCheck:
    if not include:
        return _in_process_check(
            name="Saved benchmark suite validation",
            command=["internal", "saved-benchmark-validation"],
            project_root=project_root,
            status="skipped",
            summary="Skipped by request.",
        )
    started = time.perf_counter()
    if not benchmark_results_path.is_file():
        return _in_process_check(
            name="Saved benchmark suite validation",
            command=["internal", "saved-benchmark-validation"],
            project_root=project_root,
            status="skipped",
            duration_ms=_duration_ms(started),
            summary=f"No saved complex benchmark results found at {benchmark_results_path}.",
        )
    results = load_complex_benchmark_results(benchmark_results_path)
    if not results:
        return _in_process_check(
            name="Saved benchmark suite validation",
            command=["internal", "saved-benchmark-validation"],
            project_root=project_root,
            status="failed",
            duration_ms=_duration_ms(started),
            summary=f"No valid complex benchmark rows loaded from {benchmark_results_path}.",
        )
    validated = sum(1 for result in results if result.validation_passed)
    return _in_process_check(
        name="Saved benchmark suite validation",
        command=["internal", "saved-benchmark-validation"],
        project_root=project_root,
        status="passed",
        duration_ms=_duration_ms(started),
        summary=(
            f"Loaded {len(results)} saved complex benchmark row(s); "
            f"{validated} validated."
        ),
    )


def _in_process_check(
    *,
    name: str,
    command: list[str],
    project_root: Path,
    status: str,
    summary: str,
    duration_ms: int = 0,
) -> QualityGateCheck:
    return QualityGateCheck(
        name=name,
        status=status,
        command=command,
        cwd=str(project_root),
        exit_code=0 if status == "passed" else None,
        duration_ms=duration_ms,
        stdout_path=None,
        stderr_path=None,
        summary=summary,
    )


def _release_gate_review_artifacts(
    *,
    project_root: Path,
    artifacts_dir: Path,
    benchmark_results_path: Path,
) -> list[str]:
    candidates = [
        project_root / "docs" / "23_product_boundary_ownership.md",
        artifacts_dir / "experiments" / "release_gate" / "sample_session.jsonl",
        artifacts_dir / "experiments" / "release_gate" / "sample_session.md",
        benchmark_results_path,
    ]
    return [str(path) for path in candidates if path.exists()]


def _release_gate_status(checks: list[QualityGateCheck]) -> str:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
