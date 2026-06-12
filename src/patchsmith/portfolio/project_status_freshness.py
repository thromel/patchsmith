"""Evidence freshness helpers for project status reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from patchsmith.portfolio._helpers import (
    _format_age_seconds,
    _format_utc,
    _parse_utc_datetime,
    _payload_string,
)
from patchsmith.portfolio.models import (
    PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS,
    ProjectEvidenceFreshness,
)


def project_evidence_freshness(
    *,
    sources: dict[str, str],
    payloads: dict[str, dict[str, Any] | None],
    as_of: datetime,
    threshold_seconds: int = PROJECT_STATUS_FRESHNESS_THRESHOLD_SECONDS,
) -> list[ProjectEvidenceFreshness]:
    return [
        _project_source_freshness(
            source=source,
            payload=payloads.get(name),
            as_of=as_of,
            threshold_seconds=threshold_seconds,
        )
        for name, source in sources.items()
    ]


def project_evidence_freshness_status(
    freshness: list[ProjectEvidenceFreshness],
) -> str:
    statuses = {item.status for item in freshness}
    if "missing" in statuses:
        return "missing"
    if "stale" in statuses:
        return "stale"
    if "undated" in statuses:
        return "undated"
    return "fresh"


def _project_source_freshness(
    *,
    source: str,
    payload: dict[str, Any] | None,
    as_of: datetime,
    threshold_seconds: int,
) -> ProjectEvidenceFreshness:
    if payload is None:
        return ProjectEvidenceFreshness(
            source=source,
            status="missing",
            generated_at=None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="Artifact is missing or could not be parsed as JSON.",
        )
    generated_at = _payload_string(payload, "generated_at")
    generated_at_dt = _parse_utc_datetime(generated_at)
    if generated_at_dt is None:
        return ProjectEvidenceFreshness(
            source=source,
            status="undated",
            generated_at=generated_at or None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="Artifact has no parseable generated_at timestamp.",
        )
    age_seconds = max(0, int((as_of - generated_at_dt).total_seconds()))
    threshold_label = _format_age_seconds(threshold_seconds)
    age_label = _format_age_seconds(age_seconds)
    if age_seconds > threshold_seconds:
        return ProjectEvidenceFreshness(
            source=source,
            status="stale",
            generated_at=_format_utc(generated_at_dt),
            age_seconds=age_seconds,
            threshold_seconds=threshold_seconds,
            detail=f"Generated {age_label} ago; exceeds {threshold_label} threshold.",
        )
    return ProjectEvidenceFreshness(
        source=source,
        status="fresh",
        generated_at=_format_utc(generated_at_dt),
        age_seconds=age_seconds,
        threshold_seconds=threshold_seconds,
        detail=f"Generated {age_label} ago; within {threshold_label} threshold.",
    )


__all__ = [
    "project_evidence_freshness",
    "project_evidence_freshness_status",
]
