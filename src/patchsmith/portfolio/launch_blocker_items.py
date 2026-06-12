"""Launch blocker item construction and evidence helpers."""

from __future__ import annotations

from pathlib import Path

from patchsmith.portfolio._helpers import (
    _dedupe_strings,
    _load_json_artifact,
    _payload_int,
    _payload_string,
    _payload_string_list,
)
from patchsmith.portfolio.launch_blocker_public_items import (
    focused_setup_readiness_launch_item,
    public_repair_readiness_launch_item,
)
from patchsmith.portfolio.launch_blocker_support import (
    first_actionable_check,
    launch_blocker_sort_key,
    launch_item,
)
from patchsmith.portfolio.models import LaunchBlockerItem


def launch_blocker_items(artifacts_dir: Path) -> list[LaunchBlockerItem]:
    items = [
        _docker_smoke_launch_item(artifacts_dir),
        focused_setup_readiness_launch_item(artifacts_dir),
        public_repair_readiness_launch_item(artifacts_dir),
        _live_calibration_launch_item(artifacts_dir),
        _release_hygiene_launch_item(artifacts_dir),
    ]
    return sorted(items, key=launch_blocker_sort_key)


def _docker_smoke_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/docker_smoke.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return launch_item(
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
    actionable_check = first_actionable_check(checks if isinstance(checks, list) else [])
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
    return launch_item(
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


def _live_calibration_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/calibration_readiness.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return launch_item(
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
    return launch_item(
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
        return launch_item(
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
    return launch_item(
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


__all__ = [
    "_has_executed_public_repair_attempt_evidence",
    "_has_executed_public_reproduction_evidence",
    "launch_blocker_items",
]
