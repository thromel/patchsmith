"""Portfolio project status (split from portfolio.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import (
    _format_utc,
    _load_json_artifact,
    _payload_float,
    _payload_int,
    _payload_string,
    _provider_summary,
)
from patchsmith.portfolio.models import (
    ProjectStatusReport,
    ProjectStatusSurface,
)
from patchsmith.portfolio.project_status_freshness import (
    project_evidence_freshness,
    project_evidence_freshness_status,
)
from patchsmith.portfolio.project_status_reports import render_project_status_report


def build_project_status_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
) -> ProjectStatusReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    generated_at_dt = datetime.now(UTC).replace(microsecond=0)
    generated_at = _format_utc(generated_at_dt)
    sources = {
        "mvp": "experiments/mvp_progress.json",
        "delivery": "experiments/delivery_audit.json",
        "quality": "experiments/quality_gate.json",
        "launch": "experiments/launch_blockers.json",
        "docker": "experiments/docker_smoke.json",
        "environment": "experiments/environment_readiness.json",
        "release": "experiments/release_hygiene.json",
        "calibration": "experiments/calibration_readiness.json",
        "public_reproduction": (
            "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json"
        ),
        "public_reproduction_spec_validation": (
            "experiments/public_issue_corpus_v1/"
            "public_issue_reproduction_spec_validation_summary.json"
        ),
        "public_failure_signal_discovery": (
            "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json"
        ),
        "public_reproduction_execution": (
            "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_summary.json"
        ),
        "public_repair": (
            "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json"
        ),
        "public_repair_attempt": (
            "experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json"
        ),
        "final": "experiments/final_evaluation.json",
        "index": "experiments/index.json",
    }
    payloads = {
        name: _load_json_artifact(artifacts_dir / source) for name, source in sources.items()
    }
    missing_sources = [source for name, source in sources.items() if payloads[name] is None]
    evidence_freshness = project_evidence_freshness(
        sources=sources,
        payloads=payloads,
        as_of=generated_at_dt,
    )
    stale_source_count = sum(1 for freshness in evidence_freshness if freshness.status == "stale")
    undated_source_count = sum(
        1 for freshness in evidence_freshness if freshness.status == "undated"
    )
    mvp = payloads["mvp"] or {}
    delivery = payloads["delivery"] or {}
    quality = payloads["quality"] or {}
    launch = payloads["launch"] or {}
    docker = payloads["docker"] or {}
    environment = payloads["environment"] or {}
    release = payloads["release"] or {}
    calibration = payloads["calibration"] or {}
    final = payloads["final"] or {}
    index = payloads["index"] or {}

    mvp_status = _payload_string(mvp, "status", "missing")
    mvp_completion = _payload_float(mvp, "completion_percent")
    delivery_status = _payload_string(delivery, "delivery_status", "missing")
    delivery_completion = _payload_float(delivery, "completion_percent")
    quality_status = _payload_string(quality, "quality_status", "missing")
    launch_status = _payload_string(launch, "launch_status", "missing")
    release_status = _payload_string(release, "release_status", "missing")
    docker_status = _payload_string(docker, "smoke_status", "missing")
    environment_status = _payload_string(environment, "readiness_status", "missing")
    calibration_status = _payload_string(calibration, "calibration_status", "missing")
    blocker_count = _payload_int(launch, "blocked_count")
    warning_count = _payload_int(launch, "warning_count")
    experiment_count = _payload_int(final, "experiment_count") or _payload_int(
        index, "experiment_count"
    )
    run_count = _payload_int(final, "run_count") or _payload_int(index, "run_count")
    metric_count = _payload_int(final, "metric_count") or _payload_int(index, "metric_count")
    model_providers = calibration.get("model_providers")
    model_provider_counts = model_providers if isinstance(model_providers, dict) else {}
    surfaces = [
        _project_status_surface(
            name="MVP Progress",
            status=mvp_status,
            evidence=(
                f"{mvp_completion:.1f}% complete; "
                f"{_payload_int(mvp, 'passed_count')} passed, "
                f"{_payload_int(mvp, 'warning_count')} warnings, "
                f"{_payload_int(mvp, 'blocked_count')} blocked."
            ),
            source=sources["mvp"],
        ),
        _project_status_surface(
            name="Delivery Audit",
            status=delivery_status,
            evidence=(
                f"{delivery_completion:.1f}% evidence-weighted; "
                f"{_payload_int(delivery, 'passed_count')} passed, "
                f"{_payload_int(delivery, 'warning_count')} warnings, "
                f"{_payload_int(delivery, 'blocked_count')} blockers."
            ),
            source=sources["delivery"],
        ),
        _project_status_surface(
            name="Quality Gate",
            status=quality_status,
            evidence=(
                f"{_payload_int(quality, 'passed_count')} passed, "
                f"{_payload_int(quality, 'failed_count')} failed, "
                f"{_payload_int(quality, 'skipped_count')} skipped."
            ),
            source=sources["quality"],
        ),
        _project_status_surface(
            name="Launch Blockers",
            status=launch_status,
            evidence=(
                f"{blocker_count} blockers, {warning_count} warnings, "
                f"{_payload_int(launch, 'ready_count')} ready items."
            ),
            source=sources["launch"],
        ),
        _project_status_surface(
            name="Docker Smoke",
            status=docker_status,
            evidence=(
                f"Image `{_payload_string(docker, 'image', 'unknown')}`; "
                f"run_id `{_payload_string(docker, 'run_id', 'none') or 'none'}`; "
                f"test_exit_code `{docker.get('test_exit_code')}`."
            ),
            source=sources["docker"],
        ),
        _project_status_surface(
            name="Live LLM Calibration",
            status=calibration_status,
            evidence=(
                f"{_payload_int(calibration, 'saved_live_provider_count')} live-provider runs; "
                f"providers {_provider_summary(model_provider_counts)}."
            ),
            source=sources["calibration"],
        ),
        _project_status_surface(
            name="Environment Readiness",
            status=environment_status,
            evidence=(
                f"{_payload_int(environment, 'passed_count')} passed, "
                f"{_payload_int(environment, 'warning_count')} warnings, "
                f"{_payload_int(environment, 'blocked_count')} blocked."
            ),
            source=sources["environment"],
        ),
        _project_status_surface(
            name="Adapter Evidence",
            status="recorded" if calibration else "missing",
            evidence=(
                f"{_payload_int(calibration, 'deepagents_package_run_count')} DeepAgents package-backed, "
                f"{_payload_int(calibration, 'deepagents_compatibility_run_count')} DeepAgents compatibility, "
                f"{_payload_int(calibration, 'openai_agents_package_run_count')} OpenAI Agents package-backed, "
                f"{_payload_int(calibration, 'openai_agents_compatibility_run_count')} OpenAI Agents compatibility."
            ),
            source=sources["calibration"],
        ),
        _project_status_surface(
            name="Release Hygiene",
            status=release_status,
            evidence=(
                f"{_payload_int(release, 'passed_count')} passed, "
                f"{_payload_int(release, 'warning_count')} warnings, "
                f"{_payload_int(release, 'blocked_count')} blocked."
            ),
            source=sources["release"],
        ),
        _project_status_surface(
            name="Saved Evidence Index",
            status="available" if experiment_count or run_count else "missing",
            evidence=(
                f"{experiment_count} experiments, {run_count} runs, {metric_count} metric rows."
            ),
            source=sources["final"] if final else sources["index"],
        ),
    ]
    return ProjectStatusReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=generated_at,
        overall_status=_project_overall_status(
            missing_sources=missing_sources,
            delivery_status=delivery_status,
            launch_status=launch_status,
            quality_status=quality_status,
            release_status=release_status,
            mvp_status=mvp_status,
            calibration_status=calibration_status,
            environment_status=environment_status,
        ),
        mvp_status=mvp_status,
        mvp_completion_percent=mvp_completion,
        delivery_status=delivery_status,
        delivery_completion_percent=delivery_completion,
        quality_status=quality_status,
        launch_status=launch_status,
        release_status=release_status,
        docker_smoke_status=docker_status,
        environment_readiness_status=environment_status,
        live_calibration_status=calibration_status,
        saved_live_provider_count=_payload_int(calibration, "saved_live_provider_count"),
        deepagents_package_run_count=_payload_int(calibration, "deepagents_package_run_count"),
        deepagents_compatibility_run_count=_payload_int(
            calibration, "deepagents_compatibility_run_count"
        ),
        openai_agents_package_run_count=_payload_int(
            calibration, "openai_agents_package_run_count"
        ),
        openai_agents_compatibility_run_count=_payload_int(
            calibration, "openai_agents_compatibility_run_count"
        ),
        experiment_count=experiment_count,
        run_count=run_count,
        metric_count=metric_count,
        blocker_count=blocker_count,
        warning_count=warning_count,
        evidence_freshness_status=project_evidence_freshness_status(evidence_freshness),
        stale_source_count=stale_source_count,
        undated_source_count=undated_source_count,
        missing_sources=missing_sources,
        surfaces=surfaces,
        evidence_freshness=evidence_freshness,
    )


def write_project_status_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> ProjectStatusReport:
    report = build_project_status_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
    )
    write_markdown(output_path, render_project_status_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def _project_status_surface(
    *,
    name: str,
    status: str,
    evidence: str,
    source: str,
) -> ProjectStatusSurface:
    return ProjectStatusSurface(
        name=name,
        status=status,
        evidence=evidence,
        source=source,
    )


def _project_overall_status(
    *,
    missing_sources: list[str],
    delivery_status: str,
    launch_status: str,
    quality_status: str,
    release_status: str,
    mvp_status: str,
    calibration_status: str,
    environment_status: str,
) -> str:
    if missing_sources:
        return "incomplete_evidence"
    if (
        delivery_status == "in_progress_with_blockers"
        or launch_status == "blocked"
        or quality_status == "failed"
        or release_status == "blocked"
        or environment_status == "blocked"
    ):
        return "in_progress_with_blockers"
    if (
        mvp_status == "ready_with_caveats"
        or release_status == "ready_with_warnings"
        or calibration_status == "not_configured"
    ):
        return "ready_with_caveats"
    return "ready"
