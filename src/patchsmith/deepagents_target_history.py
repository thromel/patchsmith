"""Target-history manifest rendering for DeepAgents retries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def target_history_manifest(
    deprioritized_paths: list[str],
    *,
    preferred_target_paths: list[str] | None = None,
    preferred_target_reasons: Mapping[str, Iterable[str]] | None = None,
) -> str | None:
    paths = [path.strip() for path in deprioritized_paths if path.strip()]
    preferred_paths = [
        path.strip()
        for path in (preferred_target_paths or [])
        if path.strip() and path.strip() not in paths
    ]
    revived_paths = [
        path.strip()
        for path in (preferred_target_paths or [])
        if path.strip() and path.strip() in paths
    ]
    if not paths and not preferred_paths and not revived_paths:
        return None
    lines = [
        "# PatchSmith Target History Manifest",
        "",
        "These target paths were selected in earlier attempts or marked as ineffective "
        "after repeated failures. Treat them as negative evidence for this retry.",
        "",
        "PatchSmith rejects a plan for one of these paths unless `target_rationale` "
        "names the exact distinct branch, cache read, dispatch site, or call path "
        "inside that file that was not exercised by the failed attempts, and cites "
        "an exact identifier from the proposed `old` span. Prefer an untried control "
        "point.",
        "",
    ]
    if preferred_paths:
        lines.extend(
            [
                "## Preferred Untried Source Targets",
                "",
                "PatchSmith retrieved these source paths for this retry and they are not "
                "in the target-history list. Inspect them before returning to a historical "
                "target.",
                "",
                "Required next-path rule: choose one of these preferred paths as the next "
                "`path` unless a historical target has explicit old-span evidence for a "
                "different branch, cache read, dispatch site, or call path.",
                "",
            ]
        )
        for path in preferred_paths:
            reasons = _prioritized_target_reasons(
                (preferred_target_reasons or {}).get(path, []),
            )
            if reasons:
                lines.append(f"- `{path}` - {', '.join(reasons[:4])}")
            else:
                lines.append(f"- `{path}`")
        lines.append("")
    if revived_paths:
        lines.extend(
            [
                "## Revived Historical Control Points",
                "",
                "Retry-time localization points back to these historical paths as likely "
                "control points. They are still historical: PatchSmith will reject them "
                "unless the proposed `old` span is not a reused failed span and "
                "`target_rationale` cites a distinct identifier from that span.",
                "",
            ]
        )
        for path in revived_paths:
            reasons = _prioritized_target_reasons(
                (preferred_target_reasons or {}).get(path, []),
            )
            if reasons:
                lines.append(f"- `{path}` - {', '.join(reasons[:4])}")
            else:
                lines.append(f"- `{path}`")
        lines.append("")
    if paths:
        lines.extend(
            [
                "## Historical Target Paths",
                "",
            ]
        )
        lines.extend(f"- `{path}`" for path in paths)
    return "\n".join(lines)


def _prioritized_target_reasons(reasons: Iterable[str]) -> list[str]:
    cleaned = [reason.strip() for reason in reasons if reason.strip()]
    priority_prefixes = (
        "reviewed_source_hint",
        "stale_path_control_point_cues",
        "python_import_cache_cues",
        "exact_identifiers",
        "matched_terms",
        "path_terms",
    )
    return sorted(
        dict.fromkeys(cleaned),
        key=lambda reason: (
            next(
                (
                    index
                    for index, prefix in enumerate(priority_prefixes)
                    if reason.startswith(prefix)
                ),
                len(priority_prefixes),
            ),
            reason,
        ),
    )
