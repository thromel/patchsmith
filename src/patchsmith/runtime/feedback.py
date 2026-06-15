from __future__ import annotations

import re
from typing import Any

from patchsmith.models import CommandResult
from patchsmith.patch_effects import diff_changes_only_python_imports

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
        localization = failure_localization_summary(test_result)
        if localization:
            sections.append(localization)
        signals = _failure_signals(f"{test_result.stdout}\n{test_result.stderr}")
        if signals:
            sections.extend(["Key failure lines:", *_bullet_lines(signals)])
    hunks = _diff_hunks(final_diff)
    if hunks:
        sections.extend(["Previous changed hunks:", *_bullet_lines(hunks)])
        patch_effect_warnings: list[str] = []
        if diff_changes_only_python_imports(final_diff):
            patch_effect_warnings.append(
                "Previous diff changed only Python import statements. For a "
                "behavioral failure, an import-only patch is usually insufficient "
                "unless the sandbox failure is ImportError, ModuleNotFoundError, "
                "or NameError and the imported name directly fixes that failure."
            )
        basename_warning = _basename_only_path_guard_warning(
            test_result=test_result,
            final_diff=final_diff,
        )
        if basename_warning:
            patch_effect_warnings.append(basename_warning)
        if patch_effect_warnings:
            sections.extend(
                ["Patch effect warning:", *_bullet_lines(patch_effect_warnings)]
            )
    return "\n".join(sections) if sections else "No compact sandbox feedback available."


def assertion_progress_summary(
    *,
    test_result: CommandResult | None,
    final_diff: str,
) -> str:
    if test_result is None or not final_diff.strip():
        return ""
    added_text = _diff_added_text(final_diff).lower()
    if not added_text:
        return ""
    text = f"{test_result.stdout}\n{test_result.stderr}"
    for missing_literal, observed_value in _membership_assertion_values(text):
        normalized_observed = observed_value.lower()
        if (
            len(normalized_observed) >= 8
            and normalized_observed in added_text
            and missing_literal.lower() not in normalized_observed
        ):
            return (
                "Partial assertion progress: the previous patch changed the value now "
                "shown by the failing assertion, but the assertion still requires "
                f"`{_clean_feedback_value(missing_literal, limit=80)}`. Refine the "
                "same runtime-visible target span instead of abandoning it solely "
                "because the target appears in retry history."
            )
    return ""


def sandbox_failure_signature(test_result: CommandResult | None) -> str:
    if test_result is None:
        return ""
    text = f"{test_result.stdout}\n{test_result.stderr}"
    parts: list[str] = []
    exception = _first_exception(text)
    if exception:
        parts.append(exception)
    comparison = _assertion_comparison(text)
    if comparison is not None:
        actual, expected = comparison
        if _looks_path_like(actual) and _looks_path_like(expected):
            parts.append(f"path:{_path_tail(actual)}!={_path_tail(expected)}")
        else:
            parts.append(
                "assert:"
                f"{_clean_feedback_value(actual, limit=80)}!="
                f"{_clean_feedback_value(expected, limit=80)}"
            )
    location = _first_failure_location(text)
    if location:
        parts.append(f"at:{_clean_failure_location(location)}")
    return " | ".join(parts)


def failure_localization_summary(test_result: CommandResult | None) -> str:
    if test_result is None:
        return ""
    text = f"{test_result.stdout}\n{test_result.stderr}"
    cues: list[str] = []
    exception = _first_exception(text)
    if exception:
        cues.append(f"Exception class: {exception}")
    comparison = _assertion_comparison(text)
    if comparison is not None:
        actual, expected = comparison
        cues.append(f"Assertion actual: {_clean_feedback_value(actual)}")
        cues.append(f"Assertion expected: {_clean_feedback_value(expected)}")
        path_hint = _path_mismatch_hint(actual, expected)
        if path_hint:
            cues.append(path_hint)
    location = _first_failure_location(text)
    if location:
        cues.append(f"Failure location: {location}")
    if not cues:
        return ""
    return "\n".join(["Failure localization cues:", *_bullet_lines(cues)])


def patch_plan_feedback_summary(runtime_trace: list[dict[str, Any]]) -> str:
    diagnostics = _latest_patch_plan_diagnostics(runtime_trace)
    patch_quality = _latest_patch_quality_assessment(runtime_trace)
    no_op_patch_violation = _latest_no_op_patch_violation(runtime_trace)
    target_history_violation = _latest_target_history_violation(runtime_trace)
    target_selection_violation = _latest_target_selection_violation(runtime_trace)
    target_symbol_violation = _latest_target_symbol_violation(runtime_trace)
    safety_rejection = safety_gate_rejection_summary(runtime_trace)
    if (
        not diagnostics
        and patch_quality is None
        and no_op_patch_violation is None
        and target_history_violation is None
        and target_selection_violation is None
        and target_symbol_violation is None
        and not safety_rejection
    ):
        return ""

    lines = ["Previous patch plan diagnostics:"]
    if safety_rejection:
        lines.extend(safety_rejection.splitlines())
    if diagnostics:
        lines.append(f"- Path: {_clean_feedback_value(diagnostics.get('path', ''))}")
        if "target_read_error" in diagnostics:
            lines.append(
                f"- Target read error: {_clean_feedback_value(diagnostics.get('target_read_error', ''))}"
            )
        if "target_char_count" in diagnostics:
            lines.append(f"- Target chars: {diagnostics.get('target_char_count')}")
        if "old_found" in diagnostics:
            lines.append(
                f"- Old span found in clean target: {bool(diagnostics.get('old_found'))}"
            )
        if "old_occurrences" in diagnostics:
            lines.append(f"- Old span occurrences: {diagnostics.get('old_occurrences')}")
        old = diagnostics.get("old")
        if isinstance(old, dict):
            lines.extend(_span_summary_lines("Old span", old))
        new = diagnostics.get("new")
        if isinstance(new, dict):
            lines.extend(_span_summary_lines("New span", new))
        if _same_old_new_span_hash(old, new):
            lines.extend(_no_op_patch_plan_lines())
        nearest_excerpt = diagnostics.get("nearest_source_excerpt")
        if isinstance(nearest_excerpt, dict):
            lines.extend(_nearest_source_excerpt_lines(nearest_excerpt))
    if patch_quality is not None:
        lines.extend(_patch_quality_lines(patch_quality))
    if no_op_patch_violation is not None:
        lines.extend(_no_op_patch_violation_lines(no_op_patch_violation))
    if target_history_violation is not None:
        lines.extend(_target_history_violation_lines(target_history_violation))
    if target_selection_violation is not None:
        lines.extend(_target_selection_violation_lines(target_selection_violation))
    if target_symbol_violation is not None:
        lines.extend(_target_symbol_violation_lines(target_symbol_violation))
    return "\n".join(lines)


def safety_gate_rejection_summary(runtime_trace: list[dict[str, Any]]) -> str:
    rejection = _latest_safety_gate_rejection(runtime_trace)
    if rejection is None:
        return ""
    summary = _clean_feedback_value(rejection.get("summary", ""))
    if not summary:
        return ""
    lines = [
        f"- Patch safety gate rejection: {summary}",
    ]
    unbound_names = _unbound_names_from_safety_summary(summary)
    if unbound_names:
        lines.append(
            "- Unbound name correction: do not call helper names that are not already "
            "bound in the selected file or included in the returned replacement span. "
            "Either inline the check using names visible in the old span, or include "
            "the helper definition in the same bounded replacement with a rationale "
            "for the larger span."
        )
        lines.append(
            "- Rejected unbound names: "
            + ", ".join(f"`{name}`" for name in unbound_names)
        )
    if _looks_like_incomplete_python_span_rejection(summary):
        lines.append(
            "- Span boundary correction: choose a syntactically complete Python "
            "old/new span. Do not end `old` on an `if`, `try`, `with`, `def`, "
            "or `class` header without its body; include the complete block, or "
            "replace only that header with another header that keeps the body."
        )
    return "\n".join(lines)


def _latest_safety_gate_rejection(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        if event.get("node") != "edit" or event.get("status") != "failed":
            continue
        summary = event.get("summary")
        if isinstance(summary, str) and summary.strip():
            return event
    return None


def _unbound_names_from_safety_summary(summary: str) -> list[str]:
    if "unbound" not in summary.lower():
        return []
    return _dedupe_preserve_order(
        [
            name
            for name in re.findall(r"`([^`]+)`", summary)
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)
        ]
    )


def _looks_like_incomplete_python_span_rejection(summary: str) -> bool:
    lowered = summary.lower()
    return (
        "compound statement without its body" in lowered
        or "indentationerror" in lowered
        or "expected an indented block" in lowered
        or "unexpected indent" in lowered
    )


def _latest_patch_plan_diagnostics(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        diagnostics = event.get("patch_plan")
        if isinstance(diagnostics, dict):
            return diagnostics
    return None


def _latest_patch_quality_assessment(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        quality = event.get("quality")
        if isinstance(quality, dict):
            return quality
    return None


def _patch_quality_lines(quality: dict[str, Any]) -> list[str]:
    lines = [
        "- Patch quality risk: "
        f"{_clean_feedback_value(quality.get('severity', 'unknown'))}"
    ]
    findings = quality.get("findings")
    if isinstance(findings, list):
        for finding in findings[:5]:
            if not isinstance(finding, dict):
                continue
            code = _clean_feedback_value(finding.get("code", "unknown"))
            severity = _clean_feedback_value(finding.get("severity", "unknown"))
            message = _clean_feedback_value(finding.get("message", ""))
            lines.append(f"- Quality finding: {severity} {code} - {message}")
    return lines


def _latest_target_history_violation(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        violation = metadata.get("target_history_violation")
        if isinstance(violation, dict):
            return violation
    return None


def _latest_no_op_patch_violation(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        violation = metadata.get("no_op_patch_violation")
        if isinstance(violation, dict):
            return violation
    return None


def _latest_target_selection_violation(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        violation = metadata.get("target_selection_violation")
        if isinstance(violation, dict):
            return violation
    return None


def _latest_target_symbol_violation(
    runtime_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        violation = metadata.get("target_symbol_violation")
        if isinstance(violation, dict):
            return violation
    return None


def _no_op_patch_violation_lines(violation: dict[str, Any]) -> list[str]:
    return [
        "- No-op patch policy rejected replacement for path: "
        f"{_clean_feedback_value(violation.get('path', ''))}",
        "- Rejection reason: "
        f"{_clean_feedback_value(violation.get('reason', ''))}",
        "- Required patch policy: "
        f"{_clean_feedback_value(violation.get('required_patch_policy', ''))}",
        "- Retry correction: keep the selected control point if it is still right, "
        "but choose a real behavior-changing old/new span rather than returning "
        "the same source text.",
    ]


def _target_history_violation_lines(violation: dict[str, Any]) -> list[str]:
    lines = [
        "- Repeated target rejected by target-history guard: "
        f"{_clean_feedback_value(violation.get('path', ''))}",
        "- Rejection reason: "
        f"{_clean_feedback_value(violation.get('reason', ''))}",
        "- Required next-target evidence: "
        f"{_clean_feedback_value(violation.get('required_evidence', ''))}",
    ]
    deprioritized_paths = violation.get("deprioritized_paths")
    if isinstance(deprioritized_paths, list):
        compact_paths = ", ".join(
            _clean_feedback_value(path, limit=80) for path in deprioritized_paths
        )
        if compact_paths:
            lines.append(f"- Deprioritized target paths: {compact_paths}")
    preferred_target_paths = violation.get("preferred_target_paths")
    if isinstance(preferred_target_paths, list):
        compact_paths = ", ".join(
            _clean_feedback_value(path, limit=80) for path in preferred_target_paths
        )
        if compact_paths:
            lines.append(f"- Preferred untried source targets: {compact_paths}")
    return lines


def _target_selection_violation_lines(violation: dict[str, Any]) -> list[str]:
    lines = [
        "- Patchable target policy rejected path: "
        f"{_clean_feedback_value(violation.get('path', ''))}",
        "- Rejection reason: "
        f"{_clean_feedback_value(violation.get('reason', ''))}",
        "- Required path policy: "
        f"{_clean_feedback_value(violation.get('required_path_policy', ''))}",
    ]
    preferred_target_paths = violation.get("preferred_target_paths")
    if isinstance(preferred_target_paths, list):
        compact_paths = ", ".join(
            _clean_feedback_value(path, limit=80) for path in preferred_target_paths
        )
        if compact_paths:
            lines.append(f"- Patchable source targets: {compact_paths}")
    deprioritized_paths = violation.get("deprioritized_paths")
    if isinstance(deprioritized_paths, list):
        compact_paths = ", ".join(
            _clean_feedback_value(path, limit=80) for path in deprioritized_paths
        )
        if compact_paths:
            lines.append(f"- Historical target paths: {compact_paths}")
    return lines


def _target_symbol_violation_lines(violation: dict[str, Any]) -> list[str]:
    lines = [
        "- Preferred symbol policy rejected old span for path: "
        f"{_clean_feedback_value(violation.get('path', ''))}",
        "- Rejection reason: "
        f"{_clean_feedback_value(violation.get('reason', ''))}",
        "- Required symbol policy: "
        f"{_clean_feedback_value(violation.get('required_symbol_policy', ''))}",
    ]
    preferred_symbols = violation.get("preferred_symbols")
    if isinstance(preferred_symbols, list):
        compact_symbols = ", ".join(
            _clean_feedback_value(symbol, limit=80) for symbol in preferred_symbols
        )
        if compact_symbols:
            lines.append(f"- Preferred symbols for next old span: {compact_symbols}")
    return lines


def _same_old_new_span_hash(old: object, new: object) -> bool:
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    old_hash = old.get("sha256_12")
    new_hash = new.get("sha256_12")
    return isinstance(old_hash, str) and old_hash != "" and old_hash == new_hash


def _no_op_patch_plan_lines() -> list[str]:
    return [
        "- No-op replacement rejected: old and new span hashes are identical.",
        (
            "- Retry correction: do not abandon this source control point solely because "
            "the replacement was a no-op; choose a narrower exact old span in the same "
            "function when it is still the symbol-qualified or reviewed-source control "
            "point, and make a real behavior-changing edit."
        ),
    ]


def _span_summary_lines(label: str, span: dict[str, Any]) -> list[str]:
    return [
        (
            f"- {label}: lines={span.get('line_count')}, chars={span.get('char_count')}, "
            f"sha256_12={_clean_feedback_value(span.get('sha256_12', ''))}"
        ),
        f"- {label} first line: {_clean_feedback_value(span.get('first_line_preview', ''))}",
        f"- {label} last line: {_clean_feedback_value(span.get('last_line_preview', ''))}",
    ]


def _nearest_source_excerpt_lines(excerpt: dict[str, Any]) -> list[str]:
    text = str(excerpt.get("text", "")).strip()
    if not text:
        return []
    return [
        (
            "- Nearest exact source excerpt for old-span repair: "
            f"lines {excerpt.get('start_line')}-{excerpt.get('end_line')}, "
            f"similarity={excerpt.get('similarity')}"
        ),
        "- Copy this exact source text into the next `old` field if this is the intended target:",
        "```text",
        text,
        "```",
    ]


def _clean_feedback_value(value: object, *, limit: int = 240) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 15] + "...[truncated]"


def _clean_failure_location(location: str) -> str:
    normalized = location.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return _clean_feedback_value(location, limit=120)
    tail = "/".join(parts[-4:])
    return _clean_feedback_value(tail, limit=120)


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


def _membership_assertion_values(text: str) -> list[tuple[str, str]]:
    patterns = [
        re.compile(
            r"assert\s+\((['\"])(?P<missing>.+?)\1\s+in\s+(['\"])(?P<observed>.+?)\3\)"
        ),
        re.compile(
            r"assert\s+(['\"])(?P<missing>.+?)\1\s+in\s+(['\"])(?P<observed>.+?)\3"
        ),
    ]
    matches: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        for pattern in patterns:
            match = pattern.search(raw_line)
            if match:
                matches.append((match.group("missing"), match.group("observed")))
                break
    return matches


def _first_exception(text: str) -> str:
    for raw_line in text.splitlines():
        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):", raw_line)
        if match:
            return match.group(1)
    return ""


def _assertion_comparison(text: str) -> tuple[str, str] | None:
    patterns = [
        re.compile(
            r"AssertionError:\s+assert\s+(['\"])(?P<actual>.+?)\1\s+==\s+(['\"])(?P<expected>.+?)\3"
        ),
        re.compile(r"assert\s+(['\"])(?P<actual>.+?)\1\s+==\s+(['\"])(?P<expected>.+?)\3"),
    ]
    for raw_line in text.splitlines():
        for pattern in patterns:
            match = pattern.search(raw_line)
            if match:
                return match.group("actual"), match.group("expected")
    return None


def _path_mismatch_hint(actual: str, expected: str) -> str:
    actual_is_path = _looks_path_like(actual)
    expected_is_path = _looks_path_like(expected)
    if not actual_is_path and not expected_is_path:
        return ""
    if actual_is_path != expected_is_path:
        return (
            "Path-like assertion mismatch; one side is not path-like. Inspect code "
            "that passes filename/path arguments to compile, import, or code-object "
            f"creation. Actual is path-like: {str(actual_is_path).lower()}; "
            f"expected is path-like: {str(expected_is_path).lower()}."
        )
    actual_tail = _path_tail(actual)
    expected_tail = _path_tail(expected)
    hint = (
        "Path-like assertion mismatch; inspect filename/module/code-object caching "
        "that could preserve the old path after a move."
    )
    if actual_tail or expected_tail:
        hint += (
            f" Actual tail: {_clean_feedback_value(actual_tail)}; "
            f"expected tail: {_clean_feedback_value(expected_tail)}."
        )
    stale_hint = _stale_path_cache_hint(actual, expected)
    if stale_hint:
        hint += f" {stale_hint}"
    return hint


def _looks_path_like(value: str) -> bool:
    return (
        "/" in value
        or bool(re.search(r"\b[\w.-]+\.py\b", value))
        or bool(re.search(r"(?:[A-Za-z]:\\|\\\\[^nrt])", value))
    )


def _path_tail(value: str, *, segment_count: int = 3) -> str:
    parts = [part for part in value.replace("\\\\", "/").split("/") if part]
    return "/".join(parts[-segment_count:]) if parts else value


def _basename_only_path_guard_warning(
    *,
    test_result: CommandResult | None,
    final_diff: str,
) -> str:
    if test_result is None or not _diff_contains_path_name_guard(final_diff):
        return ""
    text = f"{test_result.stdout}\n{test_result.stderr}"
    comparison = _assertion_comparison(text)
    if comparison is None:
        return ""
    actual, expected = comparison
    if _stale_path_cache_hint(actual, expected) == "":
        return ""
    return (
        "Previous diff compared only a path basename (`.name`), but the failure keeps "
        "the same filename under a different parent directory. Compare the full cached "
        "filename/path against the current source path at the cache-read or compile "
        "control point instead of checking only the leaf filename."
    )


def _diff_contains_path_name_guard(diff: str) -> bool:
    return bool(
        re.search(r"\bPath\([^\n]+\)\.name\s*(?:==|!=)", diff)
        or re.search(r"(?:==|!=)\s*Path\([^\n]+\)\.name\b", diff)
        or re.search(r"\.name\s*(?:==|!=)\s*[A-Za-z_][A-Za-z0-9_\.]*\.name", diff)
    )


def _stale_path_cache_hint(actual: str, expected: str) -> str:
    actual_parts = _path_parts(actual)
    expected_parts = _path_parts(expected)
    if len(actual_parts) < 2 or len(expected_parts) < 2:
        return ""
    if actual_parts[-1] != expected_parts[-1]:
        return ""
    differing = _first_differing_tail_segment(actual_parts, expected_parts)
    if differing is None:
        return ""
    actual_segment, expected_segment = differing
    return (
        "Stale path cache hypothesis: the asserted paths name the same file "
        f"`{_clean_feedback_value(actual_parts[-1])}` but differ at parent segment "
        f"`{_clean_feedback_value(actual_segment)}` vs `{_clean_feedback_value(expected_segment)}`. "
        "Prefer fixing the cache/dispatch site that returns a module, function, or code "
        "object created before the move; post-import __file__ checks are usually too late. "
        "If the failure persists after a module-name or cache-write patch, inspect the "
        "cache read, bytecode validation, compile, or exec site that creates or reuses "
        "the code object. Retry source search terms: sys.modules, "
        "importlib.invalidate_caches, module_name_from_path, AssertionRewritingHook, "
        "_read_pyc, _write_pyc, cache_from_source, source_stat, exec(co, "
        "module.__dict__), pyc, __pycache__, co_filename."
    )


def _path_parts(value: str) -> list[str]:
    return [part for part in value.replace("\\\\", "/").split("/") if part]


def _first_differing_tail_segment(
    actual_parts: list[str],
    expected_parts: list[str],
) -> tuple[str, str] | None:
    for actual_segment, expected_segment in zip(
        reversed(actual_parts[:-1]),
        reversed(expected_parts[:-1]),
        strict=False,
    ):
        if actual_segment != expected_segment:
            return actual_segment, expected_segment
    return None


def _first_failure_location(text: str) -> str:
    location_pattern = re.compile(r"^(.+?\.py):(\d+):\s+([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))")
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        match = location_pattern.match(stripped)
        if match:
            return _clean_feedback_value(stripped)
    fallback_pattern = re.compile(r"^(.+?\.py):(\d+):\s*$")
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if fallback_pattern.match(stripped):
            return _clean_feedback_value(stripped)
    return ""


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


def _diff_added_text(diff: str) -> str:
    lines: list[str] = []
    for raw_line in diff.splitlines():
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            lines.append(raw_line[1:])
    return "\n".join(lines)


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


__all__ = [
    "assertion_progress_summary",
    "failure_localization_summary",
    "patch_plan_feedback_summary",
    "safety_gate_rejection_summary",
    "sandbox_failure_signature",
    "sandbox_feedback_summary",
]
