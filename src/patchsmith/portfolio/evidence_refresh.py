"""Portfolio evidence refresh (split from portfolio.py)."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.evaluation import (
    check_public_issue_repair_readiness,
    discover_public_issue_failure_signals,
    execute_public_issue_repairs,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
    validate_public_issue_reproduction_specs,
)
from patchsmith.observability import (
    write_artifact_index,
    write_failure_report,
)
from patchsmith.portfolio._helpers import _markdown_cell, _utc_now
from patchsmith.portfolio.delivery_audit import write_delivery_audit_report
from patchsmith.portfolio.demo_assets import write_demo_media_assets, write_demo_script_report
from patchsmith.portfolio.demo_readiness import write_demo_readiness_report
from patchsmith.portfolio.docker_smoke import write_docker_smoke_report
from patchsmith.portfolio.environment_readiness import write_environment_readiness_report
from patchsmith.portfolio.final_evaluation import write_final_evaluation_report
from patchsmith.portfolio.launch_blockers import (
    _has_executed_public_repair_attempt_evidence,
    _has_executed_public_reproduction_evidence,
    write_launch_blocker_report,
)
from patchsmith.portfolio.live_calibration import (
    write_live_calibration_plan_report,
    write_live_calibration_report,
)
from patchsmith.portfolio.models import EvidenceRefreshReport, EvidenceRefreshStep
from patchsmith.portfolio.mvp_progress import write_mvp_progress_report
from patchsmith.portfolio.project_status import write_project_status_report
from patchsmith.portfolio.quality_gate import write_quality_gate_report
from patchsmith.portfolio.release_hygiene import write_release_hygiene_report


def build_evidence_refresh_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
    include_quality_gate: bool = False,
    quality_timeout_seconds: int = 180,
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
    public_tasks_dir = experiment_path("public_issue_corpus_v1/materialized_tasks")
    public_focused_plan_path = experiment_path(
        "public_issue_corpus_v1/focused_test_plan_results.json"
    )
    public_reproduction_plan_path = experiment_path(
        "public_issue_corpus_v1/public_issue_reproduction_plan_results.json"
    )
    public_reproduction_template_path = experiment_path(
        "public_issue_corpus_v1/public_issue_reproduction_specs_template.json"
    )
    public_reviewed_reproduction_specs_path = (
        project_root
        / "evals"
        / "issue_corpora"
        / "public_issue_smoke_v1"
        / "reproduction_specs.reviewed.json"
    )
    public_reproduction_specs_path = (
        public_reviewed_reproduction_specs_path
        if public_reviewed_reproduction_specs_path.exists()
        else public_reproduction_template_path
    )
    if public_tasks_dir.exists() and public_tasks_dir.is_dir():
        steps.append(
            _run_evidence_refresh_step(
                name="Public issue reproduction plan",
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
                    "public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
                ),
                action=lambda: plan_public_issue_reproductions(
                    tasks_dir=public_tasks_dir,
                    focused_plan_path=(
                        public_focused_plan_path if public_focused_plan_path.exists() else None
                    ),
                    reproduction_specs_path=(
                        public_reviewed_reproduction_specs_path
                        if public_reviewed_reproduction_specs_path.exists()
                        else None
                    ),
                    output_dir=experiment_path("public_issue_corpus_v1"),
                )[1],
            )
        )
        steps.append(
            _run_evidence_refresh_step(
                name="Public issue failure-signal discovery",
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
                    "public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
                ),
                action=lambda: discover_public_issue_failure_signals(
                    plan_path=public_reproduction_plan_path,
                    output_dir=experiment_path("public_issue_corpus_v1"),
                )[1],
            )
        )
        if public_reproduction_specs_path.exists():
            steps.append(
                _run_evidence_refresh_step(
                    name="Public issue reproduction spec validation",
                    artifact_paths=output_paths(
                        (
                            "public_issue_corpus_v1/"
                            "public_issue_reproduction_spec_validation_report.md"
                        ),
                        (
                            "public_issue_corpus_v1/"
                            "public_issue_reproduction_spec_validation_summary.json"
                        ),
                    ),
                    action=lambda: validate_public_issue_reproduction_specs(
                        specs_path=public_reproduction_specs_path,
                        tasks_dir=public_tasks_dir,
                        focused_plan_path=(
                            public_focused_plan_path if public_focused_plan_path.exists() else None
                        ),
                        output_dir=experiment_path("public_issue_corpus_v1"),
                    )[1],
                )
            )
        else:
            steps.append(
                EvidenceRefreshStep(
                    name="Public issue reproduction spec validation",
                    status="skipped",
                    duration_ms=0,
                    artifact_paths=output_paths(
                        (
                            "public_issue_corpus_v1/"
                            "public_issue_reproduction_spec_validation_report.md"
                        ),
                        (
                            "public_issue_corpus_v1/"
                            "public_issue_reproduction_spec_validation_summary.json"
                        ),
                    ),
                    summary="Skipped because the reproduction specs template is missing.",
                )
            )
        public_reproduction_execution_summary_path = experiment_path(
            "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json"
        )
        if _has_executed_public_reproduction_evidence(public_reproduction_execution_summary_path):
            steps.append(
                EvidenceRefreshStep(
                    name="Public issue reproduction execution",
                    status="passed",
                    duration_ms=0,
                    artifact_paths=output_paths(
                        "public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
                        ("public_issue_corpus_v1/public_issue_reproduction_execution_summary.json"),
                    ),
                    summary=(
                        "Preserved existing executed reproduction evidence; rerun "
                        "`execute-public-issue-reproductions --execute` explicitly to refresh it."
                    ),
                )
            )
        else:
            steps.append(
                _run_evidence_refresh_step(
                    name="Public issue reproduction execution",
                    artifact_paths=output_paths(
                        "public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
                        ("public_issue_corpus_v1/public_issue_reproduction_execution_summary.json"),
                    ),
                    action=lambda: execute_public_issue_reproductions(
                        plan_path=public_reproduction_plan_path,
                        output_dir=experiment_path("public_issue_corpus_v1"),
                    )[1],
                )
            )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Public issue reproduction plan",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
                    "public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
                ),
                summary="Skipped because materialized public issue tasks are missing.",
            )
        )
        steps.append(
            EvidenceRefreshStep(
                name="Public issue reproduction execution",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
                    "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
                ),
                summary="Skipped because materialized public issue tasks are missing.",
            )
        )
        steps.append(
            EvidenceRefreshStep(
                name="Public issue failure-signal discovery",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
                    "public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
                ),
                summary="Skipped because materialized public issue tasks are missing.",
            )
        )
        steps.append(
            EvidenceRefreshStep(
                name="Public issue reproduction spec validation",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    ("public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md"),
                    (
                        "public_issue_corpus_v1/"
                        "public_issue_reproduction_spec_validation_summary.json"
                    ),
                ),
                summary="Skipped because materialized public issue tasks are missing.",
            )
        )
    public_repair_inputs = [
        experiment_path("public_issue_corpus_v1/focused_test_run_results.json"),
        experiment_path("public_issue_corpus_v1/focused_test_diagnosis_results.json"),
        experiment_path("public_issue_corpus_v1/focused_test_setup_validation_results.json"),
    ]
    public_reproduction_execution_path = experiment_path(
        "public_issue_corpus_v1/public_issue_reproduction_execution_results.json"
    )
    if all(path.exists() for path in public_repair_inputs):
        steps.append(
            _run_evidence_refresh_step(
                name="Public issue repair readiness",
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_repair_readiness_report.md",
                    "public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
                ),
                action=lambda: check_public_issue_repair_readiness(
                    focused_run_path=public_repair_inputs[0],
                    diagnosis_path=public_repair_inputs[1],
                    setup_validation_path=public_repair_inputs[2],
                    reproduction_execution_path=(
                        public_reproduction_execution_path
                        if public_reproduction_execution_path.exists()
                        else None
                    ),
                    tasks_dir=experiment_path("public_issue_corpus_v1/materialized_tasks"),
                    output_dir=experiment_path("public_issue_corpus_v1"),
                )[1],
            )
        )
        steps.append(
            EvidenceRefreshStep(
                name="Public issue repair attempts",
                status="passed",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_repair_attempt_report.md",
                    "public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
                ),
                summary=(
                    "Preserved existing executed repair-attempt evidence; rerun "
                    "`execute-public-issue-repairs --execute` explicitly to refresh it."
                ),
            )
            if _has_executed_public_repair_attempt_evidence(
                experiment_path("public_issue_corpus_v1/public_issue_repair_attempt_summary.json")
            )
            else _run_evidence_refresh_step(
                name="Public issue repair attempts",
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_repair_attempt_report.md",
                    "public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
                ),
                action=lambda: execute_public_issue_repairs(
                    readiness_path=experiment_path(
                        "public_issue_corpus_v1/public_issue_repair_readiness_results.json"
                    ),
                    tasks_dir=experiment_path("public_issue_corpus_v1/materialized_tasks"),
                    output_dir=experiment_path("public_issue_corpus_v1"),
                    allow_warnings=True,
                )[1],
            )
        )
    else:
        steps.append(
            EvidenceRefreshStep(
                name="Public issue repair readiness",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_repair_readiness_report.md",
                    "public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
                ),
                summary=(
                    "Skipped because focused public issue run, diagnosis, or setup-validation "
                    "inputs are missing."
                ),
            )
        )
        steps.append(
            EvidenceRefreshStep(
                name="Public issue repair attempts",
                status="skipped",
                duration_ms=0,
                artifact_paths=output_paths(
                    "public_issue_corpus_v1/public_issue_repair_attempt_report.md",
                    "public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
                ),
                summary=(
                    "Skipped because focused public issue run, diagnosis, or setup-validation "
                    "inputs are missing."
                ),
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
    quality_timeout_seconds: int = 180,
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


def render_evidence_refresh_report(report: EvidenceRefreshReport) -> str:
    lines = [
        "# PatchSmith Evidence Refresh Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Refresh status: `{report.refresh_status}`",
        f"- Steps: `{report.step_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Failed: `{report.failed_count}`",
        f"- Skipped: `{report.skipped_count}`",
        f"- Quality gate refreshed: `{str(report.quality_gate_refreshed).lower()}`",
        f"- Docker smoke refreshed: `{str(report.docker_smoke_refreshed).lower()}`",
        "",
        "## Steps",
        "",
        "| Step | Status | Duration | Artifacts | Summary | Error |",
        "|---|---|---:|---|---|---|",
    ]
    for step in report.steps:
        artifacts = "<br>".join(f"`{path}`" for path in step.artifact_paths)
        lines.append(
            "| "
            f"{step.name} | "
            f"{step.status} | "
            f"{step.duration_ms}ms | "
            f"{artifacts} | "
            f"{_markdown_cell(step.summary)} | "
            f"{_markdown_cell(step.error or '')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- This command refreshes saved review/status artifacts.",
            "- It executes Docker smoke only when `--include-docker-smoke` is set.",
            "- It does not call live model providers.",
            "- By default it skips the full quality gate; use `--include-quality-gate` to run tests and package build.",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_evidence_refresh_step(
    *,
    name: str,
    artifact_paths: list[str],
    action: Any,
) -> EvidenceRefreshStep:
    started = time.perf_counter()
    try:
        result = action()
    except Exception as error:  # pragma: no cover - exercised through callers.
        return EvidenceRefreshStep(
            name=name,
            status="failed",
            duration_ms=int((time.perf_counter() - started) * 1000),
            artifact_paths=artifact_paths,
            summary=f"{type(error).__name__}: {error}",
            error=str(error),
        )
    return EvidenceRefreshStep(
        name=name,
        status="passed",
        duration_ms=int((time.perf_counter() - started) * 1000),
        artifact_paths=artifact_paths,
        summary=_evidence_refresh_summary(result),
    )


def _evidence_refresh_summary(result: Any) -> str:
    if hasattr(result, "overall_status"):
        return (
            f"overall_status={result.overall_status}, "
            f"mvp={getattr(result, 'mvp_completion_percent', 0.0):.1f}%, "
            f"delivery={getattr(result, 'delivery_completion_percent', 0.0):.1f}%"
        )
    if hasattr(result, "refresh_status"):
        return f"refresh_status={result.refresh_status}"
    if hasattr(result, "smoke_status"):
        return (
            f"smoke_status={result.smoke_status}, "
            f"run_id={getattr(result, 'run_id', None) or 'none'}"
        )
    if hasattr(result, "quality_status"):
        return (
            f"quality_status={result.quality_status}, "
            f"passed={result.passed_count}, failed={result.failed_count}"
        )
    if hasattr(result, "delivery_status"):
        return (
            f"delivery_status={result.delivery_status}, completion={result.completion_percent:.1f}%"
        )
    if hasattr(result, "completion_percent") and hasattr(result, "status"):
        return f"status={result.status}, completion={result.completion_percent:.1f}%"
    if hasattr(result, "release_status"):
        return (
            f"release_status={result.release_status}, "
            f"warnings={result.warning_count}, blockers={result.blocked_count}"
        )
    if hasattr(result, "launch_status"):
        return (
            f"launch_status={result.launch_status}, "
            f"blockers={result.blocked_count}, warnings={result.warning_count}"
        )
    if hasattr(result, "readiness_status") and hasattr(result, "blocked_count"):
        return (
            f"readiness_status={result.readiness_status}, "
            f"blocked={result.blocked_count}, warnings={result.warning_count}"
        )
    if hasattr(result, "readiness_status"):
        return (
            f"readiness_status={result.readiness_status}, "
            f"experiments={getattr(result, 'experiment_count', 0)}, "
            f"runs={getattr(result, 'run_count', 0)}"
        )
    if hasattr(result, "calibration_status"):
        return (
            f"calibration_status={result.calibration_status}, "
            f"live_runs={getattr(result, 'saved_live_provider_count', 0)}"
        )
    if hasattr(result, "plan_status"):
        return f"plan_status={result.plan_status}, ready_runs={getattr(result, 'ready_runs', 0)}"
    if hasattr(result, "repair_command_tasks"):
        return (
            f"ready={result.ready_tasks}, warning={result.warning_tasks}, "
            f"blocked={result.blocked_tasks}, commands={result.repair_command_tasks}"
        )
    if hasattr(result, "reproduced_tasks"):
        return (
            f"reproduced={result.reproduced_tasks}, "
            f"dry_run={result.dry_run_tasks}, blocked={result.blocked_tasks}, "
            f"manual_specs={result.manual_spec_required_tasks}"
        )
    if hasattr(result, "validated_tasks"):
        return (
            f"validated={result.validated_tasks}, "
            f"attempted={result.attempted_tasks}, blocked={result.blocked_tasks}"
        )
    if hasattr(result, "manual_spec_required_tasks"):
        return (
            f"planned={result.planned_tasks}, warning={result.warning_tasks}, "
            f"blocked={result.blocked_tasks}, manual_specs={result.manual_spec_required_tasks}"
        )
    if hasattr(result, "experiment_count"):
        return (
            f"experiments={result.experiment_count}, "
            f"runs={getattr(result, 'run_count', 0)}, "
            f"metrics={len(getattr(result, 'metrics', []))}"
        )
    if hasattr(result, "runs_requiring_attention"):
        return (
            f"runs_scanned={result.runs_scanned}, "
            f"requiring_attention={result.runs_requiring_attention}"
        )
    if hasattr(result, "target_duration_seconds"):
        return f"target_duration_seconds={result.target_duration_seconds}"
    if hasattr(result, "png_path"):
        return f"png_path={result.png_path}"
    return type(result).__name__


def _evidence_refresh_status(steps: list[EvidenceRefreshStep]) -> str:
    statuses = {step.status for step in steps}
    if "failed" in statuses:
        return "failed"
    if "skipped" in statuses:
        return "passed_with_skips"
    return "passed"
