"""Public issue launch blocker item construction."""

from __future__ import annotations

from pathlib import Path

from patchsmith.portfolio._helpers import (
    _load_json_artifact,
    _payload_int,
    _payload_string,
)
from patchsmith.portfolio.launch_blocker_support import launch_item
from patchsmith.portfolio.models import LaunchBlockerItem


def focused_setup_readiness_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return launch_item(
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
    return launch_item(
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


def public_repair_readiness_launch_item(artifacts_dir: Path) -> LaunchBlockerItem:
    source = "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json"
    payload = _load_json_artifact(artifacts_dir / source)
    if payload is None:
        return launch_item(
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
    return launch_item(
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


__all__ = [
    "focused_setup_readiness_launch_item",
    "public_repair_readiness_launch_item",
]
