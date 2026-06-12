"""Portfolio evidence refresh (split from portfolio.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.observability import (
    write_artifact_index,
    write_failure_report,
)
from patchsmith.portfolio._helpers import _utc_now
from patchsmith.portfolio.delivery_audit import write_delivery_audit_report
from patchsmith.portfolio.demo_assets import write_demo_media_assets, write_demo_script_report
from patchsmith.portfolio.demo_readiness import write_demo_readiness_report
from patchsmith.portfolio.docker_smoke import write_docker_smoke_report
from patchsmith.portfolio.environment_readiness import write_environment_readiness_report
from patchsmith.portfolio.evidence_refresh_public_issues import (
    public_issue_evidence_refresh_steps,
)
from patchsmith.portfolio.evidence_refresh_support import (
    _evidence_refresh_status,
    _run_evidence_refresh_step,
    render_evidence_refresh_report,
)
from patchsmith.portfolio.final_evaluation import write_final_evaluation_report
from patchsmith.portfolio.launch_blockers import write_launch_blocker_report
from patchsmith.portfolio.live_calibration import (
    write_live_calibration_plan_report,
    write_live_calibration_report,
)
from patchsmith.portfolio.models import EvidenceRefreshReport, EvidenceRefreshStep
from patchsmith.portfolio.mvp_progress import write_mvp_progress_report
from patchsmith.portfolio.project_status import write_project_status_report
from patchsmith.portfolio.quality_gate import (
    DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
    write_quality_gate_report,
)
from patchsmith.portfolio.release_hygiene import write_release_hygiene_report


def build_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
    include_docker_smoke: bool = False,
    docker_smoke_skip_run: bool = False,
    docker_smoke_image: str = "patchsmith-seeded-smoke:py312",
    docker_binary: str = "docker",
) -> EvidenceRefreshReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    experiments_dir = artifacts_dir / "experiments"
    steps: list[EvidenceRefreshStep] = []

    def experiment_path(relative_path: str) -> Path:
        return experiments_dir / relative_path

    def output_paths(*relative_paths: str) -> list[str]:
        return [str(experiment_path(path)) for path in relative_paths]

    steps.append(
        _run_evidence_refresh_step(
            name="Artifact index",
            artifact_paths=output_paths("index.md", "index.json", "index.html"),
            action=lambda: write_artifact_index(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("index.md"),
                json_output_path=experiment_path("index.json"),
                html_output_path=experiment_path("index.html"),
                run_detail_output_dir=experiment_path("run-details"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Failure report",
            artifact_paths=output_paths("failure_report.md", "failure_report.json"),
            action=lambda: write_failure_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("failure_report.md"),
                json_output_path=experiment_path("failure_report.json"),
                max_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo readiness",
            artifact_paths=output_paths("demo_readiness.md", "demo_readiness.json"),
            action=lambda: write_demo_readiness_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_readiness.md"),
                json_output_path=experiment_path("demo_readiness.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Live calibration readiness",
            artifact_paths=output_paths(
                "calibration_readiness.md",
                "calibration_readiness.json",
            ),
            action=lambda: write_live_calibration_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("calibration_readiness.md"),
                json_output_path=experiment_path("calibration_readiness.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Live calibration plan",
            artifact_paths=output_paths(
                "live_calibration_plan.md",
                "live_calibration_plan.json",
            ),
            action=lambda: write_live_calibration_plan_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("live_calibration_plan.md"),
                json_output_path=experiment_path("live_calibration_plan.json"),
            ),
        )
    )
    if include_docker_smoke:
        steps.append(
            _run_evidence_refresh_step(
                name="Docker smoke",
                artifact_paths=output_paths("docker_smoke.md", "docker_smoke.json"),
                action=lambda: write_docker_smoke_report(
                    project_root=project_root,
                    artifacts_dir=artifacts_dir,
                    output_path=experiment_path("docker_smoke.md"),
                    json_output_path=experiment_path("docker_smoke.json"),
                    image=docker_smoke_image,
                    docker_binary=docker_binary,
                    run_seeded=not docker_smoke_skip_run,
                ),
            )
        )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Docker smoke",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths("docker_smoke.md", "docker_smoke.json"),
                summary=(
                    "Skipped by request. Run `docker-smoke` or pass "
                    "`--include-docker-smoke` to refresh Docker sandbox evidence."
                ),
            )
        )
    steps.append(
        _run_evidence_refresh_step(
            name="Environment readiness",
            artifact_paths=output_paths(
                "environment_readiness.md",
                "environment_readiness.json",
            ),
            action=lambda: write_environment_readiness_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("environment_readiness.md"),
                json_output_path=experiment_path("environment_readiness.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo script",
            artifact_paths=output_paths("demo_script.md", "demo_script.json"),
            action=lambda: write_demo_script_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_script.md"),
                json_output_path=experiment_path("demo_script.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Demo media",
            artifact_paths=output_paths(
                "demo_media.md",
                "demo_media.svg",
                "demo_media.png",
                "demo_media.json",
            ),
            action=lambda: write_demo_media_assets(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("demo_media.md"),
                svg_output_path=experiment_path("demo_media.svg"),
                png_output_path=experiment_path("demo_media.png"),
                json_output_path=experiment_path("demo_media.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Final evaluation",
            artifact_paths=output_paths("final_evaluation.md", "final_evaluation.json"),
            action=lambda: write_final_evaluation_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("final_evaluation.md"),
                json_output_path=experiment_path("final_evaluation.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.extend(
        public_issue_evidence_refresh_steps(
            project_root=project_root,
            experiments_dir=experiments_dir,
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Launch blockers",
            artifact_paths=output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("launch_blockers.md"),
                json_output_path=experiment_path("launch_blockers.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="MVP progress",
            artifact_paths=output_paths("mvp_progress.md", "mvp_progress.json"),
            action=lambda: write_mvp_progress_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("mvp_progress.md"),
                json_output_path=experiment_path("mvp_progress.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    if include_quality_gate:
        steps.append(
            _run_evidence_refresh_step(
                name="Quality gate",
                artifact_paths=output_paths("quality_gate.md", "quality_gate.json"),
                action=lambda: write_quality_gate_report(
                    project_root=project_root,
                    artifacts_dir=artifacts_dir,
                    output_path=experiment_path("quality_gate.md"),
                    json_output_path=experiment_path("quality_gate.json"),
                    logs_dir=experiment_path("quality_gate_logs"),
                    timeout_seconds=quality_timeout_seconds,
                ),
            )
        )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Quality gate",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths("quality_gate.md", "quality_gate.json"),
                summary=(
                    "Skipped by request. Run `quality-gate` or pass "
                    "`--include-quality-gate` to execute tests and package build."
                ),
            )
        )
    steps.append(
        _run_evidence_refresh_step(
            name="Delivery audit pre-release",
            artifact_paths=output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("delivery_audit.md"),
                json_output_path=experiment_path("delivery_audit.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Project status pre-release",
            artifact_paths=output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("project_status.md"),
                json_output_path=experiment_path("project_status.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Release hygiene",
            artifact_paths=output_paths("release_hygiene.md", "release_hygiene.json"),
            action=lambda: write_release_hygiene_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("release_hygiene.md"),
                json_output_path=experiment_path("release_hygiene.json"),
                max_failure_runs=max_failure_runs,
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Launch blockers final",
            artifact_paths=output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("launch_blockers.md"),
                json_output_path=experiment_path("launch_blockers.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Delivery audit final",
            artifact_paths=output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("delivery_audit.md"),
                json_output_path=experiment_path("delivery_audit.json"),
            ),
        )
    )
    steps.append(
        _run_evidence_refresh_step(
            name="Project status final",
            artifact_paths=output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=project_root,
                artifacts_dir=artifacts_dir,
                output_path=experiment_path("project_status.md"),
                json_output_path=experiment_path("project_status.json"),
            ),
        )
    )
    status_counts = Counter(step.status for step in steps)
    return EvidenceRefreshReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        refresh_status=_evidence_refresh_status(steps),
        step_count=len(steps),
        passed_count=status_counts.get("passed", 0),
        failed_count=status_counts.get("failed", 0),
        skipped_count=status_counts.get("skipped", 0),
        quality_gate_refreshed=include_quality_gate,
        docker_smoke_refreshed=include_docker_smoke,
        steps=steps,
    )


def write_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
    include_docker_smoke: bool = False,
    docker_smoke_skip_run: bool = False,
    docker_smoke_image: str = "patchsmith-seeded-smoke:py312",
    docker_binary: str = "docker",
) -> EvidenceRefreshReport:
    report = build_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
        include_quality_gate=include_quality_gate,
        quality_timeout_seconds=quality_timeout_seconds,
        include_docker_smoke=include_docker_smoke,
        docker_smoke_skip_run=docker_smoke_skip_run,
        docker_smoke_image=docker_smoke_image,
        docker_binary=docker_binary,
    )
    write_markdown(output_path, render_evidence_refresh_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report
