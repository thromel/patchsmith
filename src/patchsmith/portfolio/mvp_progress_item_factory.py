"""Shared MVP progress item factory helpers."""

from __future__ import annotations

from patchsmith.portfolio.models import MvpProgressItem


def mvp_item(
    category: str,
    item: str,
    status: str,
    evidence: str,
    next_action: str,
) -> MvpProgressItem:
    return MvpProgressItem(
        category=category,
        item=item,
        status=status,
        evidence=evidence,
        next_action="No action needed." if status == "passed" else next_action,
        score=mvp_status_score(status),
    )


def mvp_status_score(status: str) -> float:
    if status == "passed":
        return 1.0
    if status == "warning":
        return 0.5
    return 0.0


__all__ = ["mvp_item", "mvp_status_score"]
