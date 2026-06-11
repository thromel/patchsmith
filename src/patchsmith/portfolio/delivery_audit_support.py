"""Shared helpers for portfolio delivery audit modules."""

from __future__ import annotations

from patchsmith.portfolio.models import DeliveryAuditItem


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
