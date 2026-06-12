from __future__ import annotations

from typing import Any

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


def patch_plan_feedback_summary(runtime_trace: list[dict[str, Any]]) -> str:
    diagnostics = _latest_patch_plan_diagnostics(runtime_trace)
    if not diagnostics:
        return ""

    lines = [
        "Previous patch plan diagnostics:",
        f"- Path: {_clean_feedback_value(diagnostics.get('path', ''))}",
    ]
    if "target_read_error" in diagnostics:
        lines.append(
            f"- Target read error: {_clean_feedback_value(diagnostics.get('target_read_error', ''))}"
        )
    if "target_char_count" in diagnostics:
        lines.append(f"- Target chars: {diagnostics.get('target_char_count')}")
    if "old_found" in diagnostics:
        lines.append(f"- Old span found in clean target: {bool(diagnostics.get('old_found'))}")
    if "old_occurrences" in diagnostics:
        lines.append(f"- Old span occurrences: {diagnostics.get('old_occurrences')}")
    old = diagnostics.get("old")
    if isinstance(old, dict):
        lines.extend(_span_summary_lines("Old span", old))
    new = diagnostics.get("new")
    if isinstance(new, dict):
        lines.extend(_span_summary_lines("New span", new))
    return "\n".join(lines)


def _latest_patch_plan_diagnostics(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        diagnostics = event.get("patch_plan")
        if isinstance(diagnostics, dict):
            return diagnostics
    return None


def _span_summary_lines(label: str, span: dict[str, Any]) -> list[str]:
    return [
        (
            f"- {label}: lines={span.get('line_count')}, chars={span.get('char_count')}, "
            f"sha256_12={_clean_feedback_value(span.get('sha256_12', ''))}"
        ),
        f"- {label} first line: {_clean_feedback_value(span.get('first_line_preview', ''))}",
        f"- {label} last line: {_clean_feedback_value(span.get('last_line_preview', ''))}",
    ]


def _clean_feedback_value(value: object, *, limit: int = 240) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 15] + "...[truncated]"


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


__all__ = ["patch_plan_feedback_summary", "sandbox_feedback_summary"]
