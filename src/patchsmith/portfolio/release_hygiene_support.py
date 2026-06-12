"""Shared release hygiene check helpers."""

from __future__ import annotations

from pathlib import Path

from patchsmith.portfolio.models import ReleaseHygieneCheck


def _path_check(
    *,
    name: str,
    root: Path,
    paths: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    missing = [path for path in paths if not (root / path).exists()]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    evidence = (
        f"Found {len(paths) - len(missing)}/{len(paths)} required paths."
        if missing
        else f"All {len(paths)} required paths found."
    )
    if missing:
        evidence += f" Missing: {', '.join(missing)}."
    return _release_check(
        name=name,
        status=status,
        evidence=evidence,
        next_action="No action needed." if not missing else missing_action,
    )


def _content_check(
    *,
    name: str,
    path: Path,
    needles: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing = [needle for needle in needles if needle not in text]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    return _release_check(
        name=name,
        status=status,
        evidence=(
            f"All {len(needles)} caveat markers found."
            if not missing
            else f"Missing markers: {', '.join(missing)}."
        ),
        next_action="No action needed." if not missing else missing_action,
    )


def _release_check(
    *,
    name: str,
    status: str,
    evidence: str,
    next_action: str,
) -> ReleaseHygieneCheck:
    return ReleaseHygieneCheck(
        name=name,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


__all__ = ["_content_check", "_path_check", "_release_check"]
