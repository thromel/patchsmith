"""Foundation delivery audit item builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from patchsmith.portfolio.delivery_audit_support import _delivery_item
from patchsmith.portfolio.models import DeliveryAuditItem
from patchsmith.portfolio.release_hygiene import _run_git


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


__all__ = [
    "_delivery_git_item",
    "_delivery_path_item",
    "_delivery_payload_status_item",
    "_delivery_sprint_plan_item",
]
