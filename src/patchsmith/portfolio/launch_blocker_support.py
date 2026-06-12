"""Shared helpers for launch blocker item construction."""

from __future__ import annotations

from typing import Any

from patchsmith.portfolio.models import LaunchBlockerItem


def first_actionable_check(checks: list[Any]) -> dict[str, Any] | None:
    for check in checks:
        if isinstance(check, dict) and check.get("status") not in {"passed", "ready"}:
            return check
    return None


def launch_item(
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


def launch_blocker_sort_key(item: LaunchBlockerItem) -> tuple[int, int, str]:
    status_rank = {"blocked": 0, "warning": 1, "ready": 2}.get(item.status, 3)
    severity_rank = {"P0": 0, "P1": 1, "P2": 2}.get(item.severity, 3)
    return status_rank, severity_rank, item.blocker_id


__all__ = [
    "first_actionable_check",
    "launch_blocker_sort_key",
    "launch_item",
]
