"""Portfolio delivery audit requirement checks."""

from __future__ import annotations

from pathlib import Path

from patchsmith.observability import ArtifactIndex
from patchsmith.portfolio._helpers import _load_json_artifact
from patchsmith.portfolio.delivery_audit_foundation_items import (
    _delivery_git_item,
    _delivery_path_item,
    _delivery_payload_status_item,
    _delivery_sprint_plan_item,
)
from patchsmith.portfolio.delivery_audit_public_issue_items import (
    _delivery_public_failure_signal_discovery_item,
    _delivery_public_repair_attempt_item,
    _delivery_public_repair_readiness_item,
    _delivery_public_reproduction_execution_item,
    _delivery_public_reproduction_plan_item,
    _delivery_public_reproduction_spec_validation_item,
)
from patchsmith.portfolio.delivery_audit_readiness_items import (
    _delivery_calibration_plan_item,
    _delivery_launch_blockers_item,
    _delivery_setup_validation_item,
)
from patchsmith.portfolio.delivery_audit_support import _delivery_item
from patchsmith.portfolio.models import DeliveryAuditItem


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
            pass_values={"complete", "ready"},
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
        _delivery_public_repair_readiness_item(
            public_repair_readiness_payload,
            public_repair_attempt_payload=public_repair_attempt_payload,
        ),
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
