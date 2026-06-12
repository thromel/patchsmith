from __future__ import annotations

from patchsmith.models import CommandResult

FAILURE_MARKERS = (
    "assertionerror",
    "modulenotfounderror",
    "importerror",
    "nameerror",
    "typeerror",
    "valueerror",
    "no such file or directory",
)


def sandbox_feedback_summary(
    *,
    test_result: CommandResult | None,
    final_diff: str,
) -> str:
    sections: list[str] = []
    if test_result is not None:
        sections.append(f"Sandbox exit code: {test_result.exit_code}")
        signals = _failure_signals(f"{test_result.stdout}\n{test_result.stderr}")
        if signals:
            sections.extend(["Key failure lines:", *_bullet_lines(signals)])
    hunks = _diff_hunks(final_diff)
    if hunks:
        sections.extend(["Previous changed hunks:", *_bullet_lines(hunks)])
    return "\n".join(sections) if sections else "No compact sandbox feedback available."


def _failure_signals(text: str, *, limit: int = 8) -> list[str]:
    matches: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if (
            lowered.startswith(("failed ", "error ", "e   ", ">"))
            or "error:" in lowered
            or any(marker in lowered for marker in FAILURE_MARKERS)
        ):
            matches.append(stripped[:240])
            if len(matches) >= limit:
                break
    return _dedupe_preserve_order(matches)


def _diff_hunks(diff: str, *, limit: int = 12) -> list[str]:
    lines: list[str] = []
    for raw_line in diff.splitlines():
        if raw_line.startswith(("diff --git ", "@@ ")):
            lines.append(raw_line[:240])
        elif raw_line.startswith(("+", "-")) and not raw_line.startswith(("+++", "---")):
            stripped = raw_line.strip()
            if stripped:
                lines.append(stripped[:240])
        if len(lines) >= limit:
            break
    return _dedupe_preserve_order(lines)


def _bullet_lines(lines: list[str]) -> list[str]:
    return [f"- {line}" for line in lines]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


__all__ = ["sandbox_feedback_summary"]
