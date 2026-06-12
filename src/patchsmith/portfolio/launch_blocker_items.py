"""Launch blocker item construction and evidence helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.portfolio._helpers import (
    _dedupe_strings,
    _load_json_artifact,
    _payload_int,
    _payload_string,
    _payload_string_list,
)
from patchsmith.portfolio.models import LaunchBlockerItem


def launch_blocker_items(artifacts_dir: Path) -> list[LaunchBlockerItem]:
    items = [
        _docker_smoke_launch_item(artifacts_dir),
        _focused_setup_readiness_launch_item(artifacts_dir),
        _public_repair_readiness_launch_item(artifacts_dir),
        _live_calibration_launch_item(artifacts_dir),
        _release_hygiene_launch_item(artifacts_dir),
    ]
    return sorted(items, key=_launch_blocker_sort_key)


def _docker_smoke_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/docker_smoke.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="docker_smoke",
            status="blocked",
            severity="P0",
            area="Sandbox",
            summary="Docker sandbox smoke evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `docker-smoke` after Docker Desktop or DOCKER_HOST is available.",
            source_artifact=source,
            remediation_commands=[
                "docker context ls",
                "docker version",
                "docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .",
                (
                    "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke "
                    "--project-root . --artifacts-dir artifacts "
                    "--image patchsmith-seeded-smoke:py312 "
                    "--output artifacts/experiments/docker_smoke.md "
                    "--json-output artifacts/experiments/docker_smoke.json --json"
                ),
            ],
        )

    smoke_status = _payload_string(payload, "smoke_status", "unknown")
    checks = payload.get("checks")
    actionable_check = _first_actionable_check(checks if isinstance(checks, list) else [])
    next_action = (
        actionable_check.get("next_action") if actionable_check else payload.get("smoke_command")
    )
    evidence = (
        actionable_check.get("evidence")
        if actionable_check
        else f"Docker smoke status is `{smoke_status}`."
    )
    commands = _dedupe_strings(
        [
            *_payload_string_list(payload, "remediation_commands"),
            _payload_string(payload, "build_command"),
            _payload_string(payload, "smoke_command"),
        ]
    )
    return _launch_item(
        blocker_id="docker_smoke",
        status="ready" if smoke_status == "passed" else "blocked",
        severity="P2" if smoke_status == "passed" else "P0",
        area="Sandbox",
        summary=(
            "Docker sandbox smoke passed."
            if smoke_status == "passed"
            else f"Docker sandbox smoke is `{smoke_status}`."
        ),
        evidence=str(evidence),
        next_action=(
            "No action needed."
            if smoke_status == "passed"
            else str(
                next_action or "Start Docker, build the smoke image, and rerun `docker-smoke`."
            )
        ),
        source_artifact=source,
        remediation_commands=[] if smoke_status == "passed" else commands,
    )


def _focused_setup_readiness_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="focused_setup_readiness",
            status="blocked",
            severity="P0",
            area="Public Issue Setup",
            summary="Focused public issue setup-readiness evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `check-focused-test-setup-readiness` after setup planning.",
            source_artifact=source,
        )

    task_count = _payload_int(payload, "task_count")
    blocked_tasks = _payload_int(payload, "blocked_tasks")
    warning_tasks = _payload_int(payload, "warning_tasks")
    ready_tasks = _payload_int(payload, "ready_tasks")
    docker_status = _payload_string(payload, "docker_smoke_status", "unknown")
    if blocked_tasks:
        status = "blocked"
        severity = "P0"
        summary = f"{blocked_tasks} focused public issue setup task(s) are blocked."
        next_action = "Resolve Docker smoke availability before executing setup commands."
    elif warning_tasks:
        status = "warning"
        severity = "P1"
        summary = f"{warning_tasks} focused public issue setup task(s) need review."
        next_action = "Review warnings before running dependency setup against public repos."
    else:
        status = "ready"
        severity = "P2"
        summary = "Focused public issue setup tasks are ready."
        next_action = "Proceed with focused setup execution under the approved sandbox policy."
    return _launch_item(
        blocker_id="focused_setup_readiness",
        status=status,
        severity=severity,
        area="Public Issue Setup",
        summary=summary,
        evidence=(
            f"{ready_tasks}/{task_count} ready, {warning_tasks} warning, "
            f"{blocked_tasks} blocked; Docker smoke `{docker_status}`."
        ),
        next_action=next_action,
        source_artifact=source,
        dependencies=["docker_smoke"],
        remediation_commands=[
            (
                "PYTHONPATH=src python3 -m patchsmith.cli check-focused-test-setup-readiness "
                "--setup-plan artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_plan_results.json "
                "--docker-smoke artifacts/experiments/docker_smoke.json "
                "--output artifacts/experiments/public_issue_corpus_v1 --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli execute-focused-test-setups "
                "--readiness artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_readiness_results.json "
                "--output artifacts/experiments/public_issue_corpus_v1 "
                "--allow-dependency-installs --sandbox-mode docker "
                "--sandbox-network bridge --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli validate-focused-test-setups "
                "--setup-execution artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_execution_results.json "
                "--output artifacts/experiments/public_issue_corpus_v1 "
                "--sandbox-mode docker --sandbox-network bridge --json"
            ),
        ],
    )


def _public_repair_readiness_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="public_repair_readiness",
            status="blocked",
            severity="P0",
            area="Public Issue Repair",
            summary="Public issue repair-readiness evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `check-public-issue-repair-readiness` after focused setup validation.",
            source_artifact=source,
            dependencies=["focused_setup_readiness"],
            remediation_commands=[
                (
                    "PYTHONPATH=src python3 -m patchsmith.cli "
                    "check-public-issue-repair-readiness "
                    "--output artifacts/experiments/public_issue_corpus_v1 --json"
                ),
            ],
        )

    task_count = _payload_int(payload, "task_count")
    ready_tasks = _payload_int(payload, "ready_tasks")
    warning_tasks = _payload_int(payload, "warning_tasks")
    blocked_tasks = _payload_int(payload, "blocked_tasks")
    repair_command_tasks = _payload_int(payload, "repair_command_tasks")
    missing_reproduction_tasks = _payload_int(payload, "missing_reproduction_tasks")
    if blocked_tasks:
        status = "blocked"
        severity = "P0"
        summary = f"{blocked_tasks} public issue repair attempt(s) are blocked."
        next_action = "Resolve missing focused-run, setup-validation, or repair-command evidence."
    elif warning_tasks:
        status = "warning"
        severity = "P1"
        summary = f"{warning_tasks} public issue repair attempt(s) need caveat review."
        next_action = (
            "Review warning-class setup and sandbox caveats before repair-quality claims."
            if missing_reproduction_tasks == 0
            else "Capture issue-specific failing reproduction evidence before repair-quality claims."
        )
    else:
        status = "ready"
        severity = "P2"
        summary = "Public issue repair attempts are readiness-gated."
        next_action = "Run bounded PatchSmith repair attempts and save normal run artifacts."
    return _launch_item(
        blocker_id="public_repair_readiness",
        status=status,
        severity=severity,
        area="Public Issue Repair",
        summary=summary,
        evidence=(
            f"{ready_tasks}/{task_count} ready, {warning_tasks} warning, "
            f"{blocked_tasks} blocked, {repair_command_tasks} with repair commands, "
            f"{missing_reproduction_tasks} missing reproduction evidence."
        ),
        next_action=next_action,
        source_artifact=source,
        dependencies=["focused_setup_readiness"],
        remediation_commands=[
            (
                "PYTHONPATH=src python3 -m patchsmith.cli "
                "check-public-issue-repair-readiness "
                "--focused-run artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_run_results.json "
                "--diagnosis artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_diagnosis_results.json "
                "--setup-validation artifacts/experiments/public_issue_corpus_v1/"
                "focused_test_setup_validation_results.json "
                "--tasks-dir artifacts/experiments/public_issue_corpus_v1/materialized_tasks "
                "--output artifacts/experiments/public_issue_corpus_v1 --json"
            ),
        ],
    )


def _live_calibration_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/calibration_readiness.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="live_calibration",
            status="warning",
            severity="P1",
            area="Model Evidence",
            summary="Live calibration readiness evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `live-calibration` before making provider or model-quality claims.",
            source_artifact=source,
        )

    live_runs = _payload_int(payload, "saved_live_provider_count")
    deepagents_runs = _payload_int(payload, "deepagents_package_run_count")
    compatibility_runs = _payload_int(payload, "deepagents_compatibility_run_count")
    calibration_status = _payload_string(payload, "calibration_status", "unknown")
    status = "ready" if live_runs else "warning"
    return _launch_item(
        blocker_id="live_calibration",
        status=status,
        severity="P2" if status == "ready" else "P1",
        area="Model Evidence",
        summary=(
            "Saved live-provider calibration evidence exists."
            if live_runs
            else "Live-provider calibration remains unconfigured."
        ),
        evidence=(
            f"Calibration `{calibration_status}` with {live_runs} live-provider run(s), "
            f"{deepagents_runs} DeepAgents package-backed run(s), and "
            f"{compatibility_runs} DeepAgents compatibility-mode run(s)."
        ),
        next_action=(
            "Report live quality, token use, and estimated cost together."
            if live_runs
            else "Configure credentials and budget, then run a live calibration smoke before claiming live LLM quality."
        ),
        source_artifact=source,
        remediation_commands=[]
        if live_runs
        else [
            "export OPENAI_API_KEY=...",
            "export PATCHSMITH_OPENAI_MODEL=<model>",
            (
                "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/calibration_readiness.md "
                "--json-output artifacts/experiments/calibration_readiness.json --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli live-calibration-plan "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/live_calibration_plan.md "
                "--json-output artifacts/experiments/live_calibration_plan.json --json"
            ),
        ],
    )


def _release_hygiene_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/release_hygiene.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return _launch_item(
            blocker_id="release_hygiene",
            status="warning",
            severity="P1",
            area="Release",
            summary="Release hygiene evidence is missing.",
            evidence=f"`{source}` was not found or could not be parsed.",
            next_action="Run `release-hygiene` after refreshing launch blockers.",
            source_artifact=source,
        )

    release_status = _payload_string(payload, "release_status", "unknown")
    blocked_count = _payload_int(payload, "blocked_count")
    warning_count = _payload_int(payload, "warning_count")
    passed_count = _payload_int(payload, "passed_count")
    if release_status == "ready":
        status = "ready"
        severity = "P2"
        summary = "Release hygiene is ready."
        next_action = "No action needed."
    elif release_status == "ready_with_warnings":
        status = "warning"
        severity = "P1"
        summary = "Release hygiene has warnings."
        next_action = "Review warning checks and keep caveats visible in release materials."
    else:
        status = "blocked"
        severity = "P0"
        summary = "Release hygiene is blocked."
        next_action = "Resolve blocked release hygiene checks before claiming launch readiness."
    return _launch_item(
        blocker_id="release_hygiene",
        status=status,
        severity=severity,
        area="Release",
        summary=summary,
        evidence=(
            f"Release status `{release_status}` with {passed_count} passed, "
            f"{warning_count} warning, {blocked_count} blocked check(s)."
        ),
        next_action=next_action,
        source_artifact=source,
        dependencies=["quality_gate", "launch_blockers"],
        remediation_commands=[
            (
                "PYTHONPATH=src python3 -m patchsmith.cli quality-gate "
                "--project-root . --artifacts-dir artifacts "
                "--output artifacts/experiments/quality_gate.md "
                "--json-output artifacts/experiments/quality_gate.json "
                "--logs-dir artifacts/experiments/quality_gate_logs --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli launch-blockers "
                "--artifacts-dir artifacts "
                "--output artifacts/experiments/launch_blockers.md "
                "--json-output artifacts/experiments/launch_blockers.json --json"
            ),
            (
                "PYTHONPATH=src python3 -m patchsmith.cli release-hygiene "
                "--project-root . --artifacts-dir artifacts "
                "--output artifacts/experiments/release_hygiene.md "
                "--json-output artifacts/experiments/release_hygiene.json --json"
            ),
        ],
    )


def _has_executed_public_reproduction_evidence(summary_path: Path) -> bool:
    payload = _load_json_artifact(summary_path)
    if not payload:
        return False
    return (
        payload.get("dry_run") is False
        and _payload_int(payload, "attempted_tasks") > 0
        and _payload_int(payload, "reproduced_tasks") > 0
    )


def _has_executed_public_repair_attempt_evidence(summary_path: Path) -> bool:
    payload = _load_json_artifact(summary_path)
    if not payload:
        return False
    return (
        payload.get("dry_run") is False
        and _payload_int(payload, "attempted_tasks") > 0
        and _payload_int(payload, "reproduced_input_tasks") > 0
        and _payload_int(payload, "blocked_tasks") == 0
    )


def _first_actionable_check(checks: list[Any]) -> dict[str, Any] | None:
    for check in checks:
        if isinstance(check, dict) and check.get("status") not in {"passed", "ready"}:
            return check
    return None


def _launch_item(
    *,
    blocker_id: str,
    status: str,
    severity: str,
    area: str,
    summary: str,
    evidence: str,
    next_action: str,
    source_artifact: str,
    dependencies: list[str] | None = None,
    remediation_commands: list[str] | None = None,
) -> LaunchBlockerItem:
    return LaunchBlockerItem(
        blocker_id=blocker_id,
        status=status,
        severity=severity,
        area=area,
        summary=summary,
        evidence=evidence,
        next_action=next_action,
        source_artifact=source_artifact,
        dependencies=dependencies or [],
        remediation_commands=remediation_commands or [],
    )


def _launch_blocker_sort_key(item: LaunchBlockerItem) -> tuple[int, int, str]:
    status_rank = {"blocked": 0, "warning": 1, "ready": 2}.get(item.status, 3)
    severity_rank = {"P0": 0, "P1": 1, "P2": 2}.get(item.severity, 3)
    return status_rank, severity_rank, item.blocker_id


__all__ = [
    "_has_executed_public_repair_attempt_evidence",
    "_has_executed_public_reproduction_evidence",
    "launch_blocker_items",
]
