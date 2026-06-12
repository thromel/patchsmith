"""Public issue evidence-refresh steps."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from patchsmith.evaluation import (
    check_public_issue_repair_readiness,
    discover_public_issue_failure_signals,
    execute_public_issue_repairs,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
    validate_public_issue_reproduction_specs,
)
from patchsmith.portfolio.evidence_refresh_support import _run_evidence_refresh_step
from patchsmith.portfolio.launch_blockers import (
    _has_executed_public_repair_attempt_evidence,
    _has_executed_public_reproduction_evidence,
)
from patchsmith.portfolio.models import EvidenceRefreshStep

ExperimentPath = Callable[[str], Path]
OutputPaths = Callable[..., list[str]]


def public_issue_evidence_refresh_steps(
    *,
    project_root: Path,
    experiments_dir: Path,
) -> list[EvidenceRefreshStep]:
    steps: list[EvidenceRefreshStep] = []

    def experiment_path(relative_path: str) -> Path:
        return experiments_dir / relative_path

    def output_paths(*relative_paths: str) -> list[str]:
        return [str(experiment_path(path)) for path in relative_paths]

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
        steps.extend(
            _public_issue_reproduction_steps(
                experiment_path=experiment_path,
                output_paths=output_paths,
                public_tasks_dir=public_tasks_dir,
                public_focused_plan_path=public_focused_plan_path,
                public_reproduction_plan_path=public_reproduction_plan_path,
                public_reproduction_specs_path=public_reproduction_specs_path,
                public_reviewed_reproduction_specs_path=public_reviewed_reproduction_specs_path,
            )
        )
    else:
        steps.extend(_missing_public_issue_reproduction_steps(output_paths=output_paths))

    steps.extend(
        _public_issue_repair_steps(
            experiment_path=experiment_path,
            output_paths=output_paths,
        )
    )
    return steps


def _public_issue_reproduction_steps(
    *,
    experiment_path: ExperimentPath,
    output_paths: OutputPaths,
    public_tasks_dir: Path,
    public_focused_plan_path: Path,
    public_reproduction_plan_path: Path,
    public_reproduction_specs_path: Path,
    public_reviewed_reproduction_specs_path: Path,
) -> list[EvidenceRefreshStep]:
    steps: list[EvidenceRefreshStep] = []
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
                    "public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
                    "public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
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
                    "public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
                    "public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
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
                    "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
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
                    "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
                ),
                action=lambda: execute_public_issue_reproductions(
                    plan_path=public_reproduction_plan_path,
                    output_dir=experiment_path("public_issue_corpus_v1"),
                )[1],
            )
        )
    return steps


def _missing_public_issue_reproduction_steps(
    *, output_paths: OutputPaths
) -> list[EvidenceRefreshStep]:
    return [
        EvidenceRefreshStep(
            name="Public issue reproduction plan",
            status="skipped",
            duration_ms=0,
            artifact_paths=output_paths(
                "public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
                "public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
            ),
            summary="Skipped because materialized public issue tasks are missing.",
        ),
        EvidenceRefreshStep(
            name="Public issue reproduction execution",
            status="skipped",
            duration_ms=0,
            artifact_paths=output_paths(
                "public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
                "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
            ),
            summary="Skipped because materialized public issue tasks are missing.",
        ),
        EvidenceRefreshStep(
            name="Public issue failure-signal discovery",
            status="skipped",
            duration_ms=0,
            artifact_paths=output_paths(
                "public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
                "public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
            ),
            summary="Skipped because materialized public issue tasks are missing.",
        ),
        EvidenceRefreshStep(
            name="Public issue reproduction spec validation",
            status="skipped",
            duration_ms=0,
            artifact_paths=output_paths(
                "public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
                "public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
            ),
            summary="Skipped because materialized public issue tasks are missing.",
        ),
    ]


def _public_issue_repair_steps(
    *,
    experiment_path: ExperimentPath,
    output_paths: OutputPaths,
) -> list[EvidenceRefreshStep]:
    public_repair_inputs = [
        experiment_path("public_issue_corpus_v1/focused_test_run_results.json"),
        experiment_path("public_issue_corpus_v1/focused_test_diagnosis_results.json"),
        experiment_path("public_issue_corpus_v1/focused_test_setup_validation_results.json"),
    ]
    public_reproduction_execution_path = experiment_path(
        "public_issue_corpus_v1/public_issue_reproduction_execution_results.json"
    )
    if all(path.exists() for path in public_repair_inputs):
        return [
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
            ),
            _public_issue_repair_attempt_step(
                experiment_path=experiment_path,
                output_paths=output_paths,
            ),
        ]
    return [
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
        ),
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
        ),
    ]


def _public_issue_repair_attempt_step(
    *,
    experiment_path: ExperimentPath,
    output_paths: OutputPaths,
) -> EvidenceRefreshStep:
    if _has_executed_public_repair_attempt_evidence(
        experiment_path("public_issue_corpus_v1/public_issue_repair_attempt_summary.json")
    ):
        return EvidenceRefreshStep(
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
    return _run_evidence_refresh_step(
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


__all__ = ["public_issue_evidence_refresh_steps"]
