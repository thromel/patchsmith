"""Portfolio docker smoke (split from portfolio.py)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import _markdown_cell, _utc_now
from patchsmith.portfolio.models import DockerSmokeCheck, DockerSmokeReport


def build_docker_smoke_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    image: str = "patchsmith-seeded-smoke:py312",
    task_dir: Path | None = None,
    test_command: str = "python3 -m pytest",
    runtime: str = "heuristic",
    context_provider: str = "native_hybrid",
    docker_binary: str = "docker",
    run_seeded: bool = True,
) -> DockerSmokeReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    task_dir = (
        project_root / "evals" / "tasks" / "seeded_bugs_v1" / "task_001_logic_bug"
        if task_dir is None
        else (task_dir if task_dir.is_absolute() else project_root / task_dir)
    )
    task_dir = task_dir.resolve()
    checks: list[DockerSmokeCheck] = []
    run_report_path: str | None = None
    run_trace_path: str | None = None
    run_id: str | None = None
    test_exit_code: int | None = None

    docker_check = _docker_daemon_check(docker_binary)
    checks.append(docker_check)
    if docker_check.status != "passed":
        checks.append(
            DockerSmokeCheck(
                name="Smoke Image",
                status="skipped",
                evidence="Docker daemon was not available, so the image was not inspected.",
                next_action=f"Start Docker and build `{image}` before running the smoke.",
            )
        )
        checks.append(
            DockerSmokeCheck(
                name="Seeded Docker Test Run",
                status="skipped",
                evidence="Docker daemon was not available, so the seeded test was not run.",
                next_action="Rerun `docker-smoke` when Docker is available.",
            )
        )
    else:
        image_check = _docker_image_check(docker_binary, image)
        checks.append(image_check)
        if image_check.status != "passed":
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="skipped",
                    evidence="Required Docker image was not available locally.",
                    next_action=f"Build `{image}` and rerun `docker-smoke`.",
                )
            )
        elif not run_seeded:
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="skipped",
                    evidence="Seeded run was skipped by request.",
                    next_action="Rerun without `--skip-run` for executable smoke evidence.",
                )
            )
        else:
            result = _run_docker_seeded_smoke(
                task_dir=task_dir,
                artifacts_dir=artifacts_dir,
                test_command=test_command,
                runtime=runtime,
                context_provider=context_provider,
                sandbox_image=image,
            )
            run_report_path = str(result.report_path)
            run_trace_path = str(result.trace_path)
            run_id = result.run_id
            test_exit_code = result.test_result.exit_code if result.test_result else None
            passed = result.test_result is not None and result.test_result.exit_code == 0
            checks.append(
                DockerSmokeCheck(
                    name="Seeded Docker Test Run",
                    status="passed" if passed else "failed",
                    evidence=(
                        f"Run `{result.run_id}` test exit code: "
                        f"{test_exit_code if test_exit_code is not None else 'none'}."
                    ),
                    next_action=(
                        "No action needed."
                        if passed
                        else "Inspect the run report and Docker stderr for image/dependency gaps."
                    ),
                )
            )

    build_command = f"{docker_binary} build -f docker/seeded-smoke.Dockerfile -t {image} ."
    smoke_command = f"PYTHONPATH=src python3 -m patchsmith.cli docker-smoke --image {image} --json"
    environment_snapshot = _docker_environment_snapshot(docker_binary)
    return DockerSmokeReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        smoke_status=_docker_smoke_status(checks),
        docker_binary=docker_binary,
        image=image,
        task_dir=str(task_dir),
        test_command=test_command,
        runtime=runtime,
        context_provider=context_provider,
        run_report_path=run_report_path,
        run_trace_path=run_trace_path,
        run_id=run_id,
        test_exit_code=test_exit_code,
        checks=checks,
        environment=environment_snapshot,
        remediation_commands=_docker_remediation_commands(
            docker_binary=docker_binary,
            build_command=build_command,
            smoke_command=smoke_command,
            environment=environment_snapshot,
        ),
        build_command=build_command,
        smoke_command=smoke_command,
    )


def write_docker_smoke_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    image: str = "patchsmith-seeded-smoke:py312",
    task_dir: Path | None = None,
    test_command: str = "python3 -m pytest",
    runtime: str = "heuristic",
    context_provider: str = "native_hybrid",
    docker_binary: str = "docker",
    run_seeded: bool = True,
) -> DockerSmokeReport:
    report = build_docker_smoke_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        image=image,
        task_dir=task_dir,
        test_command=test_command,
        runtime=runtime,
        context_provider=context_provider,
        docker_binary=docker_binary,
        run_seeded=run_seeded,
    )
    write_markdown(output_path, render_docker_smoke_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_docker_smoke_report(report: DockerSmokeReport) -> str:
    lines = [
        "# PatchSmith Docker Smoke Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Smoke status: `{report.smoke_status}`",
        f"- Docker binary: `{report.docker_binary}`",
        f"- Image: `{report.image}`",
        f"- Task directory: `{report.task_dir}`",
        f"- Test command: `{report.test_command}`",
        f"- Runtime: `{report.runtime}`",
        f"- Context provider: `{report.context_provider}`",
        f"- Run ID: `{report.run_id or 'n/a'}`",
        f"- Test exit code: `{report.test_exit_code if report.test_exit_code is not None else 'n/a'}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Environment",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
    )
    for key, value in report.environment.items():
        lines.append(f"| {key} | {_markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "Diagnostic and remediation commands:",
            "",
            "```bash",
            *report.remediation_commands,
            "```",
            "",
            "Build the seeded smoke image:",
            "",
            "```bash",
            report.build_command,
            "```",
            "",
            "Run the smoke:",
            "",
            "```bash",
            report.smoke_command,
            "```",
        ]
    )
    if report.run_report_path or report.run_trace_path:
        lines.extend(["", "## Run Artifacts", ""])
        if report.run_report_path:
            lines.append(f"- Report: `{report.run_report_path}`")
        if report.run_trace_path:
            lines.append(f"- Trace: `{report.run_trace_path}`")
    lines.extend(["", "## Decision", "", _docker_smoke_decision(report)])
    return "\n".join(lines) + "\n"


def _docker_sandbox_success_count(artifacts_dir: Path) -> int:
    run_ids: set[str] = set()
    for trace_path in sorted(artifacts_dir.glob("**/traces.jsonl")):
        try:
            lines = trace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if (
                event.get("event_type") == "sandbox_command"
                and payload.get("sandbox_mode") == "docker"
                and payload.get("exit_code") == 0
            ):
                run_ids.add(str(event.get("run_id") or trace_path.parent.name))
    return len(run_ids) + _docker_smoke_success_count(artifacts_dir)


def _docker_smoke_success_count(artifacts_dir: Path) -> int:
    count = 0
    for report_path in sorted(artifacts_dir.glob("**/docker_smoke*.json")):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("smoke_status") == "passed":
            count += 1
    return count


def _latest_docker_smoke_status(artifacts_dir: Path) -> str | None:
    report_paths = sorted(
        artifacts_dir.glob("**/docker_smoke*.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for report_path in report_paths:
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("smoke_status"), str):
            return payload["smoke_status"]
    return None


def _docker_daemon_check(docker_binary: str) -> DockerSmokeCheck:
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


def _docker_image_check(docker_binary: str, image: str) -> DockerSmokeCheck:
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


def _docker_environment_snapshot(docker_binary: str) -> dict[str, str]:
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


def _docker_remediation_commands(
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


def _run_docker_seeded_smoke(
    *,
    task_dir: Path,
    artifacts_dir: Path,
    test_command: str,
    runtime: str,
    context_provider: str,
    sandbox_image: str,
):
    from patchsmith.models import RunRequest
    from patchsmith.workflow import RepairRunner

    run_artifacts_dir = artifacts_dir / "experiments" / "docker_smoke_v1" / "run_artifacts"
    issue_path = task_dir / "issue.md"
    repo_path = task_dir / "repo"
    return RepairRunner(artifacts_dir=run_artifacts_dir).run(
        RunRequest(
            repo=str(repo_path),
            issue_text=issue_path.read_text(encoding="utf-8"),
            test_command=test_command,
            runtime=runtime,
            planner="heuristic",
            context_provider=context_provider,
            retrieval_strategy=context_provider,
            sandbox_mode="docker",
            sandbox_image=sandbox_image,
        )
    )


def _docker_smoke_status(checks: list[DockerSmokeCheck]) -> str:
    statuses = [check.status for check in checks]
    if "failed" in statuses:
        return "failed"
    if "missing" in statuses:
        return "not_available"
    if "skipped" in statuses:
        return "skipped"
    return "passed"


def _docker_smoke_decision(report: DockerSmokeReport) -> str:
    if report.smoke_status == "passed":
        return "Docker sandbox smoke passed. The MVP Docker-sandbox evidence can be cited."
    if report.smoke_status == "failed":
        return "Docker sandbox smoke ran but failed. Inspect the run artifacts before claiming Docker readiness."
    if report.smoke_status == "skipped":
        return "Docker preflight passed but the executable seeded run was skipped."
    return "Docker sandbox smoke is not available in this environment. Keep Docker readiness as a caveat."
