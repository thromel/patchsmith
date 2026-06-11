"""Portfolio delivery audit (split from portfolio.py)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from patchsmith.observability import (
    ArtifactIndex,
    build_artifact_index,
)
from patchsmith.portfolio._helpers import (
    _load_json_artifact,
    _markdown_cell,
    _payload_int,
    _utc_now,
)
from patchsmith.portfolio.live_calibration import _calibration_plan_run_counts
from patchsmith.portfolio.models import DeliveryAuditItem, DeliveryAuditReport
from patchsmith.portfolio.release_hygiene import _run_git


def build_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
) -> DeliveryAuditReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    items = _delivery_audit_items(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        index=index,
    )
    status_counts = Counter(item.status for item in items)
    return DeliveryAuditReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        delivery_status=_delivery_status(items),
        completion_percent=_delivery_completion_percent(items),
        item_count=len(items),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        missing_count=status_counts.get("missing", 0),
        items=items,
    )


def write_delivery_audit_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
) -> DeliveryAuditReport:
    report = build_delivery_audit_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_delivery_audit_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_delivery_audit_report(report: DeliveryAuditReport) -> str:
    lines = [
        "# PatchSmith Delivery Audit",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Delivery status: `{report.delivery_status}`",
        f"- Evidence-weighted completion: `{report.completion_percent:.1f}%`",
        f"- Items: `{report.item_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        f"- Missing: `{report.missing_count}`",
        "",
        "## Requirement Evidence",
        "",
        "| Requirement | Status | Evidence | Source | Next Action |",
        "|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            f"{item.requirement} | "
            f"{item.status} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.source)} | "
            f"{_markdown_cell(item.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Scoring",
            "",
            "- Passed items count as 1.0.",
            "- Warning items count as 0.5 because evidence exists but is incomplete.",
            "- Blocked and missing items count as 0.0.",
            "- This audit is a delivery status artifact; it does not replace rerunning tests or live calibration.",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _delivery_public_reproduction_plan_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction criteria are planned.",
            status="missing",
            evidence="Public reproduction-plan summary artifact is missing.",
            source=source,
            next_action="Run `plan-public-issue-reproductions` from materialized tasks.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    warning = _payload_int(payload, "warning_tasks")
    planned = _payload_int(payload, "planned_tasks")
    manual_specs = _payload_int(payload, "manual_spec_required_tasks")
    commands = _payload_int(payload, "command_count")
    if blocked:
        status = "blocked"
        next_action = "Resolve blocked reproduction-plan prerequisites."
    elif warning or manual_specs:
        status = "warning"
        next_action = "Encode expected failing signals before claiming issue reproduction."
    else:
        status = "passed"
        next_action = "Execute reproduction commands and save failing evidence."
    return _delivery_item(
        requirement="Public issue reproduction criteria are planned.",
        status=status,
        evidence=(
            f"planned_tasks={planned}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"manual_spec_required_tasks={manual_specs}, command_count={commands}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_failure_signal_discovery_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_failure_signal_discovery_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue failure-signal discovery is available.",
            status="missing",
            evidence="Public failure-signal discovery summary artifact is missing.",
            source=source,
            next_action=(
                "Run `discover-public-issue-failure-signals` after reproduction planning."
            ),
        )
    dry_run = _payload_int(payload, "dry_run_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    observed = _payload_int(payload, "observed_failure_tasks")
    passed = _payload_int(payload, "passed_tasks")
    timed_out = _payload_int(payload, "timed_out_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    candidate_signals = _payload_int(payload, "candidate_signal_tasks")
    if timed_out or blocked:
        status = "blocked"
        next_action = "Resolve discovery blockers or inspect timed-out command logs."
    elif candidate_signals:
        status = "passed"
        next_action = "Review candidate signals and copy exact issue-specific lines into specs."
    else:
        status = "warning"
        next_action = (
            "Execute discovery or author a more specific reproduction command to obtain "
            "failure-signal candidates."
        )
    return _delivery_item(
        requirement="Public issue failure-signal discovery is available.",
        status=status,
        evidence=(
            f"dry_run_tasks={dry_run}, attempted_tasks={attempted}, "
            f"observed_failure_tasks={observed}, passed_tasks={passed}, "
            f"blocked_tasks={blocked}, candidate_signal_tasks={candidate_signals}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_reproduction_spec_validation_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_reproduction_spec_validation_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction specs are validated.",
            status="missing",
            evidence="Public reproduction-spec validation summary artifact is missing.",
            source=source,
            next_action=(
                "Run `validate-public-issue-reproduction-specs` after reproduction planning."
            ),
        )
    ready = _payload_int(payload, "ready_tasks")
    warning = _payload_int(payload, "warning_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    missing_specs = _payload_int(payload, "missing_spec_tasks")
    empty_signals = _payload_int(payload, "empty_signal_tasks")
    policy_blocked = _payload_int(payload, "policy_blocked_tasks")
    extra_specs = _payload_int(payload, "extra_spec_tasks")
    if blocked or missing_specs or empty_signals or policy_blocked or extra_specs:
        status = "blocked"
        next_action = (
            "Fill reviewed expected failure signals and resolve spec validation blockers "
            "before reproduction execution."
        )
    elif warning:
        status = "warning"
        next_action = "Review warnings before executing reproduction commands."
    else:
        status = "passed"
        next_action = "Use validated specs to regenerate the reproduction plan."
    return _delivery_item(
        requirement="Public issue reproduction specs are validated.",
        status=status,
        evidence=(
            f"ready_tasks={ready}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"missing_spec_tasks={missing_specs}, empty_signal_tasks={empty_signals}, "
            f"policy_blocked_tasks={policy_blocked}, extra_spec_tasks={extra_specs}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_reproduction_execution_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/"
        "public_issue_reproduction_execution_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue reproduction execution is safely gated.",
            status="missing",
            evidence="Public reproduction-execution summary artifact is missing.",
            source=source,
            next_action="Run `execute-public-issue-reproductions` after reproduction planning.",
        )
    reproduced = _payload_int(payload, "reproduced_tasks")
    dry_run = _payload_int(payload, "dry_run_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    manual_specs = _payload_int(payload, "manual_spec_required_tasks")
    failed = _payload_int(payload, "failed_tasks")
    timed_out = _payload_int(payload, "timed_out_tasks")
    not_reproduced = _payload_int(payload, "not_reproduced_tasks")
    if failed or timed_out:
        status = "blocked"
        next_action = "Inspect reproduction logs before using public issue repair evidence."
    elif reproduced:
        status = "passed"
        next_action = "Use saved failing logs as pre-repair reproduction evidence."
    elif dry_run or (blocked and blocked == manual_specs):
        status = "warning"
        next_action = "Execute only after expected failing signals are encoded and reviewed."
    elif blocked:
        status = "blocked"
        next_action = "Resolve reproduction execution blockers."
    elif attempted and not_reproduced:
        status = "warning"
        next_action = (
            "Confirm whether selected public issues are already fixed or adjust reproductions."
        )
    else:
        status = "warning"
        next_action = "Run reproduction execution after reviewing planned commands."
    return _delivery_item(
        requirement="Public issue reproduction execution is safely gated.",
        status=status,
        evidence=(
            f"reproduced_tasks={reproduced}, dry_run_tasks={dry_run}, "
            f"attempted_tasks={attempted}, blocked_tasks={blocked}, "
            f"manual_spec_required_tasks={manual_specs}, failed_tasks={failed}, "
            f"timed_out_tasks={timed_out}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_repair_readiness_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = (
        "artifacts/experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json"
    )
    if payload is None:
        return _delivery_item(
            requirement="Public issue repair attempts are readiness-gated.",
            status="missing",
            evidence="Public repair-readiness summary artifact is missing.",
            source=source,
            next_action="Run `check-public-issue-repair-readiness` after setup validation.",
        )
    blocked = _payload_int(payload, "blocked_tasks")
    warning = _payload_int(payload, "warning_tasks")
    ready = _payload_int(payload, "ready_tasks")
    repair_commands = _payload_int(payload, "repair_command_tasks")
    missing_reproduction = _payload_int(payload, "missing_reproduction_tasks")
    if blocked:
        status = "blocked"
        next_action = "Resolve blocked public repair-readiness prerequisites."
    elif warning:
        status = "warning"
        next_action = (
            "Review warning-class setup and sandbox caveats before claiming public repair quality."
            if missing_reproduction == 0
            else "Capture failing reproduction evidence before claiming public repair quality."
        )
    else:
        status = "passed"
        next_action = "Run bounded public issue repair attempts and save run artifacts."
    return _delivery_item(
        requirement="Public issue repair attempts are readiness-gated.",
        status=status,
        evidence=(
            f"ready_tasks={ready}, warning_tasks={warning}, blocked_tasks={blocked}, "
            f"repair_command_tasks={repair_commands}, "
            f"missing_reproduction_tasks={missing_reproduction}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_public_repair_attempt_item(
    payload: dict[str, Any] | None,
) -> DeliveryAuditItem:
    source = "artifacts/experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json"
    if payload is None:
        return _delivery_item(
            requirement="Public issue repair attempts are safely gated.",
            status="missing",
            evidence="Public repair-attempt summary artifact is missing.",
            source=source,
            next_action="Run `execute-public-issue-repairs` after repair readiness.",
        )
    validated = _payload_int(payload, "validated_tasks")
    attempted = _payload_int(payload, "attempted_tasks")
    blocked = _payload_int(payload, "blocked_tasks")
    failed = _payload_int(payload, "failed_tasks")
    dry_run = _payload_int(payload, "dry_run_tasks")
    reproduced_inputs = _payload_int(payload, "reproduced_input_tasks")
    if failed:
        status = "blocked"
        next_action = "Inspect failed public repair run artifacts."
    elif validated:
        status = "passed"
        next_action = "Review final diffs and broaden validation before claims."
    elif blocked and not reproduced_inputs:
        status = "warning"
        next_action = "Capture reproduced failing evidence before executing repairs."
    elif dry_run:
        status = "warning"
        next_action = "Use --execute only after reviewing dry-run evidence."
    elif blocked:
        status = "blocked"
        next_action = "Resolve repair-attempt blockers before execution."
    elif attempted:
        status = "warning"
        next_action = "Review attempted repair artifacts."
    else:
        status = "warning"
        next_action = "Run repair-attempt dry-run after readiness is available."
    return _delivery_item(
        requirement="Public issue repair attempts are safely gated.",
        status=status,
        evidence=(
            f"validated_tasks={validated}, attempted_tasks={attempted}, "
            f"blocked_tasks={blocked}, failed_tasks={failed}, "
            f"dry_run_tasks={dry_run}, reproduced_input_tasks={reproduced_inputs}"
        ),
        source=source,
        next_action=next_action,
    )


def _delivery_item(
    *,
    requirement: str,
    status: str,
    evidence: str,
    source: str,
    next_action: str,
) -> DeliveryAuditItem:
    return DeliveryAuditItem(
        requirement=requirement,
        status=status,
        evidence=evidence,
        source=source,
        next_action=next_action,
    )


def _delivery_status(items: list[DeliveryAuditItem]) -> str:
    statuses = {item.status for item in items}
    if "blocked" in statuses:
        return "in_progress_with_blockers"
    if "missing" in statuses:
        return "in_progress_missing_evidence"
    if "warning" in statuses:
        return "in_progress_with_caveats"
    return "ready_for_completion_review"


def _delivery_completion_percent(items: list[DeliveryAuditItem]) -> float:
    if not items:
        return 0.0
    score = 0.0
    for item in items:
        if item.status == "passed":
            score += 1.0
        elif item.status == "warning":
            score += 0.5
    return round(score / len(items) * 100.0, 1)
