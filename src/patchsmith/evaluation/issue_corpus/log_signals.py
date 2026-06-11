from __future__ import annotations


def matching_lines(text: str, patterns: list[str], *, limit: int) -> list[str]:
    matches: list[str] = []
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered_line = stripped.lower()
        if any(pattern in lowered_line for pattern in lowered_patterns):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return matches


def matched_expected_failure_signals(text: str, patterns: list[str]) -> list[str]:
    matched: list[str] = []
    lowered_text = text.lower()
    for pattern in patterns:
        if pattern.lower() in lowered_text:
            matched.append(pattern)
    return matched


def candidate_failure_signals_from_logs(text: str, *, limit: int = 8) -> list[str]:
    exception_markers = (
        "assertionerror",
        "modulenotfounderror",
        "importerror",
        "nameerror",
        "typeerror",
        "valueerror",
        "no such file or directory",
    )
    matches: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if (
            lowered.startswith(("failed ", "error ", "e   ", "traceback"))
            or "error:" in lowered
            or any(marker in lowered for marker in exception_markers)
        ):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return _dedupe_preserve_order(matches)


def last_nonempty_lines(text: str, *, limit: int) -> list[str]:
    lines = [line.strip()[:240] for line in text.splitlines() if line.strip()]
    return lines[-limit:]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
