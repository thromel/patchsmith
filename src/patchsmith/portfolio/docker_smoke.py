"""Portfolio docker smoke (split from portfolio.py)."""

from __future__ import annotations

import json
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import _utc_now
from patchsmith.portfolio.docker_smoke_checks import (
    docker_daemon_check,
    docker_environment_snapshot,
    docker_image_check,
    docker_remediation_commands,
    docker_smoke_status,
)
from patchsmith.portfolio.docker_smoke_reports import render_docker_smoke_report
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

    docker_check = docker_daemon_check(docker_binary)
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
        image_check = docker_image_check(docker_binary, image)
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
    environment_snapshot = docker_environment_snapshot(docker_binary)
    return DockerSmokeReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        smoke_status=docker_smoke_status(checks),
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
        remediation_commands=docker_remediation_commands(
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
