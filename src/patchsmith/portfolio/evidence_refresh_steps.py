"""Evidence-refresh step construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.artifacts import write_json
from patchsmith.evaluation import (
    ComplexBenchmarkSuiteThresholds,
    summarize_complex_benchmark_suite,
    validate_complex_benchmark_suite_inputs,
)
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
    include_complex_suite: bool
    complex_suite_attempt_dirs: tuple[Path, ...]
    complex_suite_output_dir: Path | None
    complex_suite_benchmark: str
    complex_suite_thresholds: ComplexBenchmarkSuiteThresholds

    @property
    def experiments_dir(self) -> Path:
        return self.artifacts_dir / "experiments"

    def experiment_path(self, relative_path: str) -> Path:
        return self.experiments_dir / relative_path

    def output_paths(self, *relative_paths: str) -> list[str]:
        return [str(self.experiment_path(path)) for path in relative_paths]

    def complex_suite_output_path(self) -> Path:
        return self.complex_suite_output_dir or self.experiment_path("complex_benchmark_suite")

    def complex_suite_output_paths(self, *filenames: str) -> list[str]:
        output_dir = self.complex_suite_output_path()
        return [str(output_dir / filename) for filename in filenames]


@dataclass(frozen=True)
class ComplexSuiteEvidenceRefreshResult:
    complex_suite_status: str
    attempt_dir_count: int
    task_count: int
    unique_task_count: int
    validated_tasks: int
    live_provider_tasks: int
    validation_rate: float
    avg_progress_score: float
    selected_avg_progress_score: float
    partial_progress_tasks: int
    failure_class_counts: dict[str, int]
    selected_failure_class_counts: dict[str, int]
    harness_layer_counts: dict[str, int]
    selected_harness_layer_counts: dict[str, int]
    retry_failure_class_counts: dict[str, int]
    process_quality_label_counts: dict[str, int]
    process_quality_flag_counts: dict[str, int]
    selected_cost_per_validated_task_usd: float | None
    selected_tokens_per_validated_task: float | None
    selected_virtual_files_per_validated_task: float | None
    selected_tokens_per_virtual_file: float | None
    selected_responses_per_virtual_file: float | None
    selected_context_target_recall: float | None
    selected_context_target_precision: float | None
    repo_instructions_manifest_rate: float
    repo_instructions_read_first_rate: float
    acceptance_rubric_manifest_rate: float
    acceptance_rubric_read_first_rate: float
    acceptance_rubric_alignment_rate: float
    avg_agent_trajectory_score: float
    contextual_verifier_rate: float
    target_alignment_rate: float
    output_dir: str


def build_evidence_refresh_steps(config: EvidenceRefreshConfig) -> list[EvidenceRefreshStep]:
    return [
        *_core_evidence_refresh_steps(config),
        *public_issue_evidence_refresh_steps(
            project_root=config.project_root,
            experiments_dir=config.experiments_dir,
        ),
        _complex_suite_step(config),
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


def _complex_suite_step(config: EvidenceRefreshConfig) -> EvidenceRefreshStep:
    artifact_paths = config.complex_suite_output_paths(
        "complex_benchmark_results.json",
        "complex_benchmark_summary.json",
        "complex_benchmark_selected_results.json",
        "complex_benchmark_report.md",
        "complex_benchmark_attempt_summaries.json",
        "complex_benchmark_suite_report.md",
        "complex_benchmark_suite_gate.json",
    )
    if not config.include_complex_suite:
        return EvidenceRefreshStep(
            name="Complex benchmark suite",
            status="skipped",
            duration_ms=0,
            artifact_paths=artifact_paths,
            summary=(
                "Skipped by request. Pass `--include-complex-suite` with one or more "
                "`--complex-suite-attempt-dir` values to aggregate saved live-agent evidence."
            ),
        )
    if not config.complex_suite_attempt_dirs:
        return EvidenceRefreshStep(
            name="Complex benchmark suite",
            status="failed",
            duration_ms=0,
            artifact_paths=artifact_paths,
            summary=(
                "Complex benchmark suite was requested but no saved attempt "
                "directories were provided."
            ),
            error="missing --complex-suite-attempt-dir",
        )
    return _run_evidence_refresh_step(
        name="Complex benchmark suite",
        artifact_paths=artifact_paths,
        action=lambda: _write_complex_suite_refresh(config),
    )


def _write_complex_suite_refresh(
    config: EvidenceRefreshConfig,
) -> ComplexSuiteEvidenceRefreshResult:
    output_dir = config.complex_suite_output_path()
    preflight = validate_complex_benchmark_suite_inputs(
        attempt_dirs=list(config.complex_suite_attempt_dirs),
        output_dir=output_dir,
        benchmark=config.complex_suite_benchmark,
        gate_threshold_count=config.complex_suite_thresholds.count,
    )
    if preflight.status != "passed":
        raise RuntimeError(
            "complex benchmark suite preflight failed: " + "; ".join(preflight.errors)
        )
    _results, summary, _attempt_summaries, _followup_candidates = summarize_complex_benchmark_suite(
        attempt_dirs=list(config.complex_suite_attempt_dirs),
        output_dir=output_dir,
        benchmark=config.complex_suite_benchmark,
    )
    gate = config.complex_suite_thresholds.gate(summary)
    write_json(
        output_dir / "complex_benchmark_suite_gate.json",
        gate.to_dict(),
        trailing_newline=True,
    )
    if gate.status != "passed":
        raise RuntimeError("complex benchmark suite gate failed: " + "; ".join(gate.failures))
    return ComplexSuiteEvidenceRefreshResult(
        complex_suite_status=gate.status,
        attempt_dir_count=len(config.complex_suite_attempt_dirs),
        task_count=summary.task_count,
        unique_task_count=summary.unique_task_count,
        validated_tasks=summary.validated_tasks,
        live_provider_tasks=summary.live_provider_tasks,
        validation_rate=summary.validation_rate,
        avg_progress_score=summary.avg_progress_score,
        selected_avg_progress_score=summary.selected_avg_progress_score,
        partial_progress_tasks=summary.partial_progress_tasks,
        failure_class_counts=summary.failure_class_counts,
        selected_failure_class_counts=summary.selected_failure_class_counts,
        harness_layer_counts=summary.harness_layer_counts,
        selected_harness_layer_counts=summary.selected_harness_layer_counts,
        retry_failure_class_counts=summary.retry_failure_class_counts,
        process_quality_label_counts=summary.process_quality_label_counts,
        process_quality_flag_counts=summary.process_quality_flag_counts,
        selected_cost_per_validated_task_usd=(summary.selected_cost_per_validated_task_usd),
        selected_tokens_per_validated_task=summary.selected_tokens_per_validated_task,
        selected_virtual_files_per_validated_task=(
            summary.selected_virtual_files_per_validated_task
        ),
        selected_tokens_per_virtual_file=summary.selected_tokens_per_virtual_file,
        selected_responses_per_virtual_file=summary.selected_responses_per_virtual_file,
        selected_context_target_recall=summary.selected_context_target_recall,
        selected_context_target_precision=summary.selected_context_target_precision,
        repo_instructions_manifest_rate=(
            summary.repo_instructions_manifest_tasks / summary.task_count
            if summary.task_count
            else 0.0
        ),
        repo_instructions_read_first_rate=summary.repo_instructions_read_first_rate,
        acceptance_rubric_manifest_rate=(
            summary.acceptance_rubric_manifest_tasks / summary.task_count
            if summary.task_count
            else 0.0
        ),
        acceptance_rubric_read_first_rate=summary.acceptance_rubric_read_first_rate,
        acceptance_rubric_alignment_rate=summary.acceptance_rubric_alignment_rate,
        avg_agent_trajectory_score=summary.avg_agent_trajectory_score,
        contextual_verifier_rate=summary.contextual_verifier_rate,
        target_alignment_rate=summary.target_alignment_rate,
        output_dir=str(output_dir),
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
