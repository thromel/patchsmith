"""Evidence-refresh step construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.observability import (
    write_artifact_index,
    write_failure_report,
)
from patchsmith.portfolio.delivery_audit import write_delivery_audit_report
from patchsmith.portfolio.demo_assets import write_demo_media_assets, write_demo_script_report
from patchsmith.portfolio.demo_readiness import write_demo_readiness_report
from patchsmith.portfolio.docker_smoke import write_docker_smoke_report
from patchsmith.portfolio.environment_readiness import write_environment_readiness_report
from patchsmith.portfolio.evidence_refresh_public_issues import (
    public_issue_evidence_refresh_steps,
)
from patchsmith.portfolio.evidence_refresh_support import _run_evidence_refresh_step
from patchsmith.portfolio.final_evaluation import write_final_evaluation_report
from patchsmith.portfolio.launch_blockers import write_launch_blocker_report
from patchsmith.portfolio.live_calibration import (
    write_live_calibration_plan_report,
    write_live_calibration_report,
)
from patchsmith.portfolio.models import EvidenceRefreshStep
from patchsmith.portfolio.mvp_progress import write_mvp_progress_report
from patchsmith.portfolio.project_status import write_project_status_report
from patchsmith.portfolio.quality_gate import write_quality_gate_report
from patchsmith.portfolio.release_hygiene import write_release_hygiene_report


@dataclass(frozen=True)
class EvidenceRefreshConfig:
    project_root: Path
    artifacts_dir: Path
    max_failure_runs: int | None
    include_quality_gate: bool
    quality_timeout_seconds: int
    include_docker_smoke: bool
    docker_smoke_skip_run: bool
    docker_smoke_image: str
    docker_binary: str

    @property
    def experiments_dir(self) -> Path:
        return self.artifacts_dir / "experiments"

    def experiment_path(self, relative_path: str) -> Path:
        return self.experiments_dir / relative_path

    def output_paths(self, *relative_paths: str) -> list[str]:
        return [str(self.experiment_path(path)) for path in relative_paths]


def build_evidence_refresh_steps(config: EvidenceRefreshConfig) -> list[EvidenceRefreshStep]:
    return [
        *_core_evidence_refresh_steps(config),
        *public_issue_evidence_refresh_steps(
            project_root=config.project_root,
            experiments_dir=config.experiments_dir,
        ),
        *_review_evidence_refresh_steps(config),
    ]


def _core_evidence_refresh_steps(config: EvidenceRefreshConfig) -> list[EvidenceRefreshStep]:
    steps = [
        _run_evidence_refresh_step(
            name="Artifact index",
            artifact_paths=config.output_paths("index.md", "index.json", "index.html"),
            action=lambda: write_artifact_index(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("index.md"),
                json_output_path=config.experiment_path("index.json"),
                html_output_path=config.experiment_path("index.html"),
                run_detail_output_dir=config.experiment_path("run-details"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Failure report",
            artifact_paths=config.output_paths("failure_report.md", "failure_report.json"),
            action=lambda: write_failure_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("failure_report.md"),
                json_output_path=config.experiment_path("failure_report.json"),
                max_runs=config.max_failure_runs,
            ),
        ),
        _run_evidence_refresh_step(
            name="Demo readiness",
            artifact_paths=config.output_paths("demo_readiness.md", "demo_readiness.json"),
            action=lambda: write_demo_readiness_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("demo_readiness.md"),
                json_output_path=config.experiment_path("demo_readiness.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
        _run_evidence_refresh_step(
            name="Live calibration readiness",
            artifact_paths=config.output_paths(
                "calibration_readiness.md",
                "calibration_readiness.json",
            ),
            action=lambda: write_live_calibration_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("calibration_readiness.md"),
                json_output_path=config.experiment_path("calibration_readiness.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Live calibration plan",
            artifact_paths=config.output_paths(
                "live_calibration_plan.md",
                "live_calibration_plan.json",
            ),
            action=lambda: write_live_calibration_plan_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("live_calibration_plan.md"),
                json_output_path=config.experiment_path("live_calibration_plan.json"),
            ),
        ),
        _docker_smoke_step(config),
        _run_evidence_refresh_step(
            name="Environment readiness",
            artifact_paths=config.output_paths(
                "environment_readiness.md",
                "environment_readiness.json",
            ),
            action=lambda: write_environment_readiness_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("environment_readiness.md"),
                json_output_path=config.experiment_path("environment_readiness.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Demo script",
            artifact_paths=config.output_paths("demo_script.md", "demo_script.json"),
            action=lambda: write_demo_script_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("demo_script.md"),
                json_output_path=config.experiment_path("demo_script.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
        _run_evidence_refresh_step(
            name="Demo media",
            artifact_paths=config.output_paths(
                "demo_media.md",
                "demo_media.svg",
                "demo_media.png",
                "demo_media.json",
            ),
            action=lambda: write_demo_media_assets(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("demo_media.md"),
                svg_output_path=config.experiment_path("demo_media.svg"),
                png_output_path=config.experiment_path("demo_media.png"),
                json_output_path=config.experiment_path("demo_media.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
        _run_evidence_refresh_step(
            name="Final evaluation",
            artifact_paths=config.output_paths("final_evaluation.md", "final_evaluation.json"),
            action=lambda: write_final_evaluation_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("final_evaluation.md"),
                json_output_path=config.experiment_path("final_evaluation.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
    ]
    return steps


def _review_evidence_refresh_steps(config: EvidenceRefreshConfig) -> list[EvidenceRefreshStep]:
    return [
        _run_evidence_refresh_step(
            name="Launch blockers",
            artifact_paths=config.output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("launch_blockers.md"),
                json_output_path=config.experiment_path("launch_blockers.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="MVP progress",
            artifact_paths=config.output_paths("mvp_progress.md", "mvp_progress.json"),
            action=lambda: write_mvp_progress_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("mvp_progress.md"),
                json_output_path=config.experiment_path("mvp_progress.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
        _quality_gate_step(config),
        _run_evidence_refresh_step(
            name="Delivery audit pre-release",
            artifact_paths=config.output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("delivery_audit.md"),
                json_output_path=config.experiment_path("delivery_audit.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Project status pre-release",
            artifact_paths=config.output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("project_status.md"),
                json_output_path=config.experiment_path("project_status.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Release hygiene",
            artifact_paths=config.output_paths("release_hygiene.md", "release_hygiene.json"),
            action=lambda: write_release_hygiene_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("release_hygiene.md"),
                json_output_path=config.experiment_path("release_hygiene.json"),
                max_failure_runs=config.max_failure_runs,
            ),
        ),
        _run_evidence_refresh_step(
            name="Launch blockers final",
            artifact_paths=config.output_paths("launch_blockers.md", "launch_blockers.json"),
            action=lambda: write_launch_blocker_report(
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("launch_blockers.md"),
                json_output_path=config.experiment_path("launch_blockers.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Delivery audit final",
            artifact_paths=config.output_paths("delivery_audit.md", "delivery_audit.json"),
            action=lambda: write_delivery_audit_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("delivery_audit.md"),
                json_output_path=config.experiment_path("delivery_audit.json"),
            ),
        ),
        _run_evidence_refresh_step(
            name="Project status final",
            artifact_paths=config.output_paths("project_status.md", "project_status.json"),
            action=lambda: write_project_status_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("project_status.md"),
                json_output_path=config.experiment_path("project_status.json"),
            ),
        ),
    ]


def _docker_smoke_step(config: EvidenceRefreshConfig) -> EvidenceRefreshStep:
    if config.include_docker_smoke:
        return _run_evidence_refresh_step(
            name="Docker smoke",
            artifact_paths=config.output_paths("docker_smoke.md", "docker_smoke.json"),
            action=lambda: write_docker_smoke_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("docker_smoke.md"),
                json_output_path=config.experiment_path("docker_smoke.json"),
                image=config.docker_smoke_image,
                docker_binary=config.docker_binary,
                run_seeded=not config.docker_smoke_skip_run,
            ),
        )
    return EvidenceRefreshStep(
        name="Docker smoke",
        status="skipped",
        duration_ms=0,
        artifact_paths=config.output_paths("docker_smoke.md", "docker_smoke.json"),
        summary=(
            "Skipped by request. Run `docker-smoke` or pass "
            "`--include-docker-smoke` to refresh Docker sandbox evidence."
        ),
    )


def _quality_gate_step(config: EvidenceRefreshConfig) -> EvidenceRefreshStep:
    if config.include_quality_gate:
        return _run_evidence_refresh_step(
            name="Quality gate",
            artifact_paths=config.output_paths("quality_gate.md", "quality_gate.json"),
            action=lambda: write_quality_gate_report(
                project_root=config.project_root,
                artifacts_dir=config.artifacts_dir,
                output_path=config.experiment_path("quality_gate.md"),
                json_output_path=config.experiment_path("quality_gate.json"),
                logs_dir=config.experiment_path("quality_gate_logs"),
                timeout_seconds=config.quality_timeout_seconds,
            ),
        )
    return EvidenceRefreshStep(
        name="Quality gate",
        status="skipped",
        duration_ms=0,
        artifact_paths=config.output_paths("quality_gate.md", "quality_gate.json"),
        summary=(
            "Skipped by request. Run `quality-gate` or pass "
            "`--include-quality-gate` to execute tests and package build."
        ),
    )


__all__ = [
    "EvidenceRefreshConfig",
    "build_evidence_refresh_steps",
]
