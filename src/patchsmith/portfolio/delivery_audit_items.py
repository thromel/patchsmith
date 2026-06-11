"""Portfolio delivery audit requirement checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.observability import ArtifactIndex
from patchsmith.portfolio._helpers import _load_json_artifact, _payload_int
from patchsmith.portfolio.delivery_audit_public_issue_items import (
    _delivery_public_failure_signal_discovery_item,
    _delivery_public_repair_attempt_item,
    _delivery_public_repair_readiness_item,
    _delivery_public_reproduction_execution_item,
    _delivery_public_reproduction_plan_item,
    _delivery_public_reproduction_spec_validation_item,
)
from patchsmith.portfolio.delivery_audit_support import _delivery_item
from patchsmith.portfolio.live_calibration import _calibration_plan_run_counts
from patchsmith.portfolio.models import DeliveryAuditItem
from patchsmith.portfolio.release_hygiene import _run_git


def _delivery_audit_items(
    *,
    project_root: Path,
    artifacts_dir: Path,
    index: ArtifactIndex,
) -> list[DeliveryAuditItem]:
    mvp_payload = _load_json_artifact(artifacts_dir / "experiments" / "mvp_progress.json")
    release_payload = _load_json_artifact(artifacts_dir / "experiments" / "release_hygiene.json")
    environment_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "environment_readiness.json"
    )
    docker_payload = _load_json_artifact(artifacts_dir / "experiments" / "docker_smoke.json")
    launch_payload = _load_json_artifact(artifacts_dir / "experiments" / "launch_blockers.json")
    calibration_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "calibration_readiness.json"
    )
    calibration_plan_payload = _load_json_artifact(
        artifacts_dir / "experiments" / "live_calibration_plan.json"
    )
    setup_validation_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "focused_test_setup_validation_summary.json"
    )
    reproduction_plan_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_reproduction_plan_summary.json"
    )
    reproduction_spec_validation_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_reproduction_spec_validation_summary.json"
    )
    failure_signal_discovery_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_failure_signal_discovery_summary.json"
    )
    reproduction_execution_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_reproduction_execution_summary.json"
    )
    public_repair_readiness_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_repair_readiness_summary.json"
    )
    public_repair_attempt_payload = _load_json_artifact(
        artifacts_dir
        / "experiments"
        / "public_issue_corpus_v1"
        / "public_issue_repair_attempt_summary.json"
    )
    quality_payload = _load_json_artifact(artifacts_dir / "experiments" / "quality_gate.json")

    return [
        _delivery_path_item(
            project_root=project_root,
            requirement="Requirements and roadmaps are saved.",
            source="README.md, docs/01_product_requirements.md, docs/09_roadmap.md, docs/12_release_and_portfolio_plan.md",
            paths=[
                "README.md",
                "docs/01_product_requirements.md",
                "docs/09_roadmap.md",
                "docs/12_release_and_portfolio_plan.md",
            ],
            next_action="Restore missing source planning docs before claiming delivery continuity.",
        ),
        _delivery_sprint_plan_item(project_root),
        _delivery_path_item(
            project_root=project_root,
            requirement="Industry process docs are saved.",
            source="docs/10_testing_strategy.md, docs/14_risk_register.md, docs/18_delivery_process.md, docs/06_safety_and_sandboxing.md",
            paths=[
                "docs/10_testing_strategy.md",
                "docs/14_risk_register.md",
                "docs/18_delivery_process.md",
                "docs/06_safety_and_sandboxing.md",
            ],
            next_action="Restore missing testing, risk, safety, or delivery-process docs.",
        ),
        _delivery_git_item(project_root),
        _delivery_path_item(
            project_root=project_root,
            requirement="Automated verification surfaces exist.",
            source="tests/, pyproject.toml, .github/workflows",
            paths=["tests", "pyproject.toml", ".github/workflows"],
            next_action="Keep pytest, packaging, and CI workflow surfaces available.",
        ),
        _delivery_item(
            requirement="Saved evaluation artifacts exist.",
            status="passed"
            if index.experiment_count and index.run_count and index.metrics
            else "missing",
            evidence=(
                f"{index.experiment_count} experiments, {index.run_count} runs, "
                f"{len(index.metrics)} normalized metric rows."
            ),
            source="artifacts/experiments/index.json",
            next_action=(
                "Regenerate `index-artifacts` before review."
                if not (index.experiment_count and index.run_count and index.metrics)
                else "Keep artifact index current after new evals."
            ),
        ),
        _delivery_payload_status_item(
            requirement="Executable quality gate has passed.",
            payload=quality_payload,
            status_key="quality_status",
            pass_values={"passed"},
            warning_values={"passed_with_skips"},
            blocked_values={"failed"},
            evidence_keys=["passed_count", "failed_count", "skipped_count"],
            source="artifacts/experiments/quality_gate.json",
            missing_action="Run `quality-gate` and preserve the generated logs.",
        ),
        _delivery_payload_status_item(
            requirement="MVP checklist progress is evidence-backed.",
            payload=mvp_payload,
            status_key="status",
            pass_values={"ready"},
            warning_values={"ready_with_caveats"},
            blocked_values={"blocked"},
            evidence_keys=["completion_percent", "blocked_count", "warning_count"],
            source="artifacts/experiments/mvp_progress.json",
            missing_action="Regenerate `mvp-progress`.",
        ),
        _delivery_payload_status_item(
            requirement="Release hygiene gate is current.",
            payload=release_payload,
            status_key="release_status",
            pass_values={"ready"},
            warning_values={"ready_with_warnings"},
            blocked_values={"blocked"},
            evidence_keys=["blocked_count", "warning_count"],
            source="artifacts/experiments/release_hygiene.json",
            missing_action="Regenerate `release-hygiene` from a clean worktree.",
        ),
        _delivery_payload_status_item(
            requirement="Environment readiness prerequisites are captured.",
            payload=environment_payload,
            status_key="readiness_status",
            pass_values={"ready"},
            warning_values={"ready_with_warnings"},
            blocked_values={"blocked"},
            evidence_keys=["passed_count", "warning_count", "blocked_count"],
            source="artifacts/experiments/environment_readiness.json",
            missing_action=(
                "Regenerate `environment-readiness` and resolve blocked external prerequisites."
            ),
        ),
        _delivery_launch_blockers_item(launch_payload),
        _delivery_payload_status_item(
            requirement="Docker sandbox smoke has executable evidence.",
            payload=docker_payload,
            status_key="smoke_status",
            pass_values={"passed"},
            warning_values={"skipped"},
            blocked_values={"failed", "not_available"},
            evidence_keys=["smoke_status"],
            source="artifacts/experiments/docker_smoke.json",
            missing_action="Start Docker, build the smoke image, and rerun `docker-smoke`.",
        ),
        _delivery_setup_validation_item(setup_validation_payload),
        _delivery_public_reproduction_plan_item(reproduction_plan_payload),
        _delivery_public_failure_signal_discovery_item(failure_signal_discovery_payload),
        _delivery_public_reproduction_spec_validation_item(reproduction_spec_validation_payload),
        _delivery_public_reproduction_execution_item(reproduction_execution_payload),
        _delivery_public_repair_readiness_item(public_repair_readiness_payload),
        _delivery_public_repair_attempt_item(public_repair_attempt_payload),
        _delivery_payload_status_item(
            requirement="Live LLM calibration has provider evidence.",
            payload=calibration_payload,
            status_key="calibration_status",
            pass_values={"calibrated"},
            warning_values={"ready_to_run", "needs_review"},
            blocked_values={"not_configured"},
            evidence_keys=[
                "saved_live_provider_count",
                "deepagents_package_run_count",
                "openai_agents_package_run_count",
            ],
            source="artifacts/experiments/calibration_readiness.json",
            missing_action="Configure credentials and run the required live-provider smoke.",
        ),
        _delivery_calibration_plan_item(calibration_plan_payload),
    ]


def _delivery_path_item(
    *,
    project_root: Path,
    requirement: str,
    source: str,
    paths: list[str],
    next_action: str,
) -> DeliveryAuditItem:
    missing = [path for path in paths if not (project_root / path).exists()]
    return _delivery_item(
        requirement=requirement,
        status="passed" if not missing else "missing",
        evidence=(
            f"All {len(paths)} required paths exist."
            if not missing
            else f"Missing: {', '.join(missing)}."
        ),
        source=source,
        next_action="No action needed." if not missing else next_action,
    )


def _delivery_sprint_plan_item(project_root: Path) -> DeliveryAuditItem:
    path = project_root / "docs" / "17_sprint_plans.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    sprint_count = text.count("### Sprint ")
    task_marker_count = text.count("| S")
    passed = sprint_count >= 10 and task_marker_count >= 10
    return _delivery_item(
        requirement="Roadmap is decomposed into sprint plans.",
        status="passed" if passed else "missing",
        evidence=f"{sprint_count} sprint sections and {task_marker_count} sprint-task rows found.",
        source="docs/17_sprint_plans.md",
        next_action=(
            "No action needed."
            if passed
            else "Restore sprint sections and task breakdown rows in docs/17_sprint_plans.md."
        ),
    )


def _delivery_git_item(project_root: Path) -> DeliveryAuditItem:
    if not (project_root / ".git").exists():
        return _delivery_item(
            requirement="Development is versioned in Git.",
            status="missing",
            evidence="No .git directory found.",
            source="git",
            next_action="Initialize or restore Git metadata.",
        )
    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if head.returncode != 0:
        return _delivery_item(
            requirement="Development is versioned in Git.",
            status="missing",
            evidence="Git repository has no readable HEAD.",
            source="git",
            next_action="Create a verified baseline commit.",
        )
    dirty = bool(status.stdout.strip()) if status.returncode == 0 else True
    return _delivery_item(
        requirement="Development is versioned in Git.",
        status="warning" if dirty else "passed",
        evidence=(
            f"Current commit {head.stdout.strip()}; worktree {'dirty' if dirty else 'clean'}."
        ),
        source="git status",
        next_action=(
            "Commit or intentionally discard pending changes before release audit."
            if dirty
            else "No action needed."
        ),
    )


def _delivery_payload_status_item(
    *,
    requirement: str,
    payload: dict[str, Any] | None,
    status_key: str,
    pass_values: set[str],
    warning_values: set[str],
    blocked_values: set[str],
    evidence_keys: list[str],
    source: str,
    missing_action: str,
) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement=requirement,
            status="missing",
            evidence="Saved JSON artifact is missing or invalid.",
            source=source,
            next_action=missing_action,
        )
    raw_status = str(payload.get(status_key) or "unknown")
    if raw_status in pass_values:
        status = "passed"
    elif raw_status in warning_values:
        status = "warning"
    elif raw_status in blocked_values:
        status = "blocked"
    else:
        status = "warning"
    details = [f"{status_key}={raw_status}"]
    for key in evidence_keys:
        if key in payload and key != status_key:
            details.append(f"{key}={payload[key]}")
    return _delivery_item(
        requirement=requirement,
        status=status,
        evidence=", ".join(details),
        source=source,
        next_action="No action needed." if status == "passed" else missing_action,
    )


def _delivery_launch_blockers_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Launch blockers are tracked.",
            status="missing",
            evidence="Launch blocker artifact is missing.",
            source="artifacts/experiments/launch_blockers.json",
            next_action="Regenerate `launch-blockers`.",
        )
    launch_status = str(payload.get("launch_status") or "unknown")
    return _delivery_item(
        requirement="Launch blockers are tracked.",
        status="passed",
        evidence=(
            f"launch_status={launch_status}, "
            f"blocked_count={_payload_int(payload, 'blocked_count')}, "
            f"warning_count={_payload_int(payload, 'warning_count')}"
        ),
        source="artifacts/experiments/launch_blockers.json",
        next_action="Work the listed blocker next actions before public launch claims.",
    )


def _delivery_calibration_plan_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Live calibration execution plan is saved.",
            status="missing",
            evidence="Live calibration plan artifact is missing.",
            source="artifacts/experiments/live_calibration_plan.json",
            next_action="Regenerate `live-calibration-plan`.",
        )
    plan_status = str(payload.get("plan_status") or "unknown")
    run_count, ready_runs, blocked_runs = _calibration_plan_run_counts(payload)
    return _delivery_item(
        requirement="Live calibration execution plan is saved.",
        status="passed",
        evidence=(
            f"plan_status={plan_status}, "
            f"run_count={run_count}, "
            f"ready_runs={ready_runs}, "
            f"blocked_runs={blocked_runs}"
        ),
        source="artifacts/experiments/live_calibration_plan.json",
        next_action="Run the required live smoke only after credentials and budget are available.",
    )


def _delivery_setup_validation_item(payload: dict[str, Any] | None) -> DeliveryAuditItem:
    if payload is None:
        return _delivery_item(
            requirement="Public issue setup validation has a safe gate.",
            status="missing",
            evidence="Setup-validation summary artifact is missing.",
            source="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
            next_action="Regenerate `validate-focused-test-setups`.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    passed = _payload_int(payload, "passed_tasks")
    status = "passed" if passed else "warning" if attempted else "blocked"
    return _delivery_item(
        requirement="Public issue setup validation has a safe gate.",
        status=status,
        evidence=(f"blocked_tasks={blocked}, attempted_tasks={attempted}, passed_tasks={passed}"),
        source="artifacts/experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        next_action=(
            "No action needed."
            if status == "passed"
            else "Resolve Docker/setup blockers before claiming public issue reproduction."
        ),
    )
