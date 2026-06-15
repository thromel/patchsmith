"""Portfolio evidence refresh (split from portfolio.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.evaluation import (
    load_complex_benchmark_suite_spec,
    resolve_complex_benchmark_suite_config,
)
from patchsmith.portfolio._helpers import _utc_now
from patchsmith.portfolio.evidence_refresh_steps import (
    EvidenceRefreshConfig,
    build_evidence_refresh_steps,
)
from patchsmith.portfolio.evidence_refresh_support import (
    _evidence_refresh_status,
    render_evidence_refresh_report,
)
from patchsmith.portfolio.models import EvidenceRefreshReport
from patchsmith.portfolio.quality_gate import (
    DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS,
)


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
    include_complex_suite: bool = False,
    complex_suite_spec_path: Path | None = None,
    complex_suite_attempt_dirs: tuple[Path, ...] | None = None,
    complex_suite_output_dir: Path | None = None,
    complex_suite_benchmark: str = "public_issue_repair_attempts",
    complex_suite_min_validation_rate: float | None = None,
    complex_suite_min_live_provider_tasks: int | None = None,
    complex_suite_min_unique_tasks: int | None = None,
    complex_suite_max_selected_cost_per_validated_task_usd: float | None = None,
    complex_suite_max_selected_tokens_per_validated_task: float | None = None,
    complex_suite_max_selected_virtual_files_per_validated_task: float | None = None,
    complex_suite_max_selected_tokens_per_virtual_file: float | None = None,
    complex_suite_max_selected_responses_per_virtual_file: float | None = None,
    complex_suite_min_selected_progress_score: float | None = None,
    complex_suite_min_selected_context_target_recall: float | None = None,
    complex_suite_min_selected_context_target_precision: float | None = None,
    complex_suite_min_repo_instructions_manifest_rate: float | None = None,
    complex_suite_min_repo_instructions_read_first_rate: float | None = None,
    complex_suite_min_acceptance_rubric_manifest_rate: float | None = None,
    complex_suite_min_acceptance_rubric_read_first_rate: float | None = None,
    complex_suite_min_acceptance_rubric_alignment_rate: float | None = None,
    complex_suite_min_agent_trajectory_score: float | None = None,
    complex_suite_min_contextual_verifier_rate: float | None = None,
    complex_suite_min_process_quality_score: float | None = None,
    complex_suite_max_process_risky_validated_tasks: int | None = None,
    complex_suite_min_target_alignment_rate: float | None = None,
) -> EvidenceRefreshReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    complex_suite_spec = (
        load_complex_benchmark_suite_spec(complex_suite_spec_path)
        if complex_suite_spec_path is not None
        else None
    )
    complex_suite_config = resolve_complex_benchmark_suite_config(
        suite_spec=complex_suite_spec,
        attempt_dirs=complex_suite_attempt_dirs,
        output_dir=complex_suite_output_dir,
        benchmark=(
            None
            if complex_suite_spec is not None
            and complex_suite_benchmark == "public_issue_repair_attempts"
            else complex_suite_benchmark
        ),
        min_validation_rate=complex_suite_min_validation_rate,
        min_live_provider_tasks=complex_suite_min_live_provider_tasks,
        min_unique_tasks=complex_suite_min_unique_tasks,
        max_selected_cost_per_validated_task_usd=(
            complex_suite_max_selected_cost_per_validated_task_usd
        ),
        max_selected_tokens_per_validated_task=(
            complex_suite_max_selected_tokens_per_validated_task
        ),
        max_selected_virtual_files_per_validated_task=(
            complex_suite_max_selected_virtual_files_per_validated_task
        ),
        max_selected_tokens_per_virtual_file=(
            complex_suite_max_selected_tokens_per_virtual_file
        ),
        max_selected_responses_per_virtual_file=(
            complex_suite_max_selected_responses_per_virtual_file
        ),
        min_selected_progress_score=complex_suite_min_selected_progress_score,
        min_selected_context_target_recall=(
            complex_suite_min_selected_context_target_recall
        ),
        min_selected_context_target_precision=(
            complex_suite_min_selected_context_target_precision
        ),
        min_repo_instructions_manifest_rate=(
            complex_suite_min_repo_instructions_manifest_rate
        ),
        min_repo_instructions_read_first_rate=(
            complex_suite_min_repo_instructions_read_first_rate
        ),
        min_acceptance_rubric_manifest_rate=(
            complex_suite_min_acceptance_rubric_manifest_rate
        ),
        min_acceptance_rubric_read_first_rate=(
            complex_suite_min_acceptance_rubric_read_first_rate
        ),
        min_acceptance_rubric_alignment_rate=(
            complex_suite_min_acceptance_rubric_alignment_rate
        ),
        min_agent_trajectory_score=complex_suite_min_agent_trajectory_score,
        min_contextual_verifier_rate=complex_suite_min_contextual_verifier_rate,
        min_process_quality_score=complex_suite_min_process_quality_score,
        max_process_risky_validated_tasks=(
            complex_suite_max_process_risky_validated_tasks
        ),
        min_target_alignment_rate=complex_suite_min_target_alignment_rate,
        default_output_dir=artifacts_dir / "experiments" / "complex_benchmark_suite",
    )
    steps = build_evidence_refresh_steps(
        EvidenceRefreshConfig(
            project_root=project_root,
            artifacts_dir=artifacts_dir,
            max_failure_runs=max_failure_runs,
            include_quality_gate=include_quality_gate,
            quality_timeout_seconds=quality_timeout_seconds,
            include_docker_smoke=include_docker_smoke,
            docker_smoke_skip_run=docker_smoke_skip_run,
            docker_smoke_image=docker_smoke_image,
            docker_binary=docker_binary,
            include_complex_suite=include_complex_suite or complex_suite_spec is not None,
            complex_suite_attempt_dirs=complex_suite_config.attempt_dirs,
            complex_suite_output_dir=complex_suite_config.output_dir,
            complex_suite_benchmark=complex_suite_config.benchmark,
            complex_suite_thresholds=complex_suite_config.thresholds,
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
        complex_suite_refreshed=include_complex_suite or complex_suite_spec is not None,
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
    include_complex_suite: bool = False,
    complex_suite_spec_path: Path | None = None,
    complex_suite_attempt_dirs: tuple[Path, ...] | None = None,
    complex_suite_output_dir: Path | None = None,
    complex_suite_benchmark: str = "public_issue_repair_attempts",
    complex_suite_min_validation_rate: float | None = None,
    complex_suite_min_live_provider_tasks: int | None = None,
    complex_suite_min_unique_tasks: int | None = None,
    complex_suite_max_selected_cost_per_validated_task_usd: float | None = None,
    complex_suite_max_selected_tokens_per_validated_task: float | None = None,
    complex_suite_max_selected_virtual_files_per_validated_task: float | None = None,
    complex_suite_max_selected_tokens_per_virtual_file: float | None = None,
    complex_suite_max_selected_responses_per_virtual_file: float | None = None,
    complex_suite_min_selected_progress_score: float | None = None,
    complex_suite_min_selected_context_target_recall: float | None = None,
    complex_suite_min_selected_context_target_precision: float | None = None,
    complex_suite_min_repo_instructions_manifest_rate: float | None = None,
    complex_suite_min_repo_instructions_read_first_rate: float | None = None,
    complex_suite_min_acceptance_rubric_manifest_rate: float | None = None,
    complex_suite_min_acceptance_rubric_read_first_rate: float | None = None,
    complex_suite_min_acceptance_rubric_alignment_rate: float | None = None,
    complex_suite_min_agent_trajectory_score: float | None = None,
    complex_suite_min_contextual_verifier_rate: float | None = None,
    complex_suite_min_process_quality_score: float | None = None,
    complex_suite_max_process_risky_validated_tasks: int | None = None,
    complex_suite_min_target_alignment_rate: float | None = None,
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
        include_complex_suite=include_complex_suite,
        complex_suite_spec_path=complex_suite_spec_path,
        complex_suite_attempt_dirs=complex_suite_attempt_dirs,
        complex_suite_output_dir=complex_suite_output_dir,
        complex_suite_benchmark=complex_suite_benchmark,
        complex_suite_min_validation_rate=complex_suite_min_validation_rate,
        complex_suite_min_live_provider_tasks=complex_suite_min_live_provider_tasks,
        complex_suite_min_unique_tasks=complex_suite_min_unique_tasks,
        complex_suite_max_selected_cost_per_validated_task_usd=(
            complex_suite_max_selected_cost_per_validated_task_usd
        ),
        complex_suite_max_selected_tokens_per_validated_task=(
            complex_suite_max_selected_tokens_per_validated_task
        ),
        complex_suite_max_selected_virtual_files_per_validated_task=(
            complex_suite_max_selected_virtual_files_per_validated_task
        ),
        complex_suite_max_selected_tokens_per_virtual_file=(
            complex_suite_max_selected_tokens_per_virtual_file
        ),
        complex_suite_max_selected_responses_per_virtual_file=(
            complex_suite_max_selected_responses_per_virtual_file
        ),
        complex_suite_min_selected_progress_score=(
            complex_suite_min_selected_progress_score
        ),
        complex_suite_min_selected_context_target_recall=(
            complex_suite_min_selected_context_target_recall
        ),
        complex_suite_min_selected_context_target_precision=(
            complex_suite_min_selected_context_target_precision
        ),
        complex_suite_min_repo_instructions_manifest_rate=(
            complex_suite_min_repo_instructions_manifest_rate
        ),
        complex_suite_min_repo_instructions_read_first_rate=(
            complex_suite_min_repo_instructions_read_first_rate
        ),
        complex_suite_min_acceptance_rubric_manifest_rate=(
            complex_suite_min_acceptance_rubric_manifest_rate
        ),
        complex_suite_min_acceptance_rubric_read_first_rate=(
            complex_suite_min_acceptance_rubric_read_first_rate
        ),
        complex_suite_min_acceptance_rubric_alignment_rate=(
            complex_suite_min_acceptance_rubric_alignment_rate
        ),
        complex_suite_min_agent_trajectory_score=complex_suite_min_agent_trajectory_score,
        complex_suite_min_contextual_verifier_rate=(
            complex_suite_min_contextual_verifier_rate
        ),
        complex_suite_min_process_quality_score=(
            complex_suite_min_process_quality_score
        ),
        complex_suite_max_process_risky_validated_tasks=(
            complex_suite_max_process_risky_validated_tasks
        ),
        complex_suite_min_target_alignment_rate=complex_suite_min_target_alignment_rate,
    )
    write_markdown(output_path, render_evidence_refresh_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report
