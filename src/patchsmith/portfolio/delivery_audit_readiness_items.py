"""Readiness delivery audit item builders."""

from __future__ import annotations

from typing import Any

from patchsmith.portfolio._helpers import _payload_int
from patchsmith.portfolio.delivery_audit_support import _delivery_item
from patchsmith.portfolio.live_calibration import _calibration_plan_run_counts
from patchsmith.portfolio.models import DeliveryAuditItem


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


__all__ = [
    "_delivery_calibration_plan_item",
    "_delivery_launch_blockers_item",
    "_delivery_setup_validation_item",
]
