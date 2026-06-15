"""Acceptance-rubric manifest generation for native DeepAgents runs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from patchsmith.models import RetrievedContext


def acceptance_rubric_manifest(
    *,
    issue_text: str,
    selected_context: list[RetrievedContext],
    preferred_target_paths: Iterable[str] | None = None,
    preferred_target_symbols: Mapping[str, Iterable[str]] | None = None,
    max_issue_chars: int = 1400,
) -> str:
    """Build a compact verifier checklist for the DeepAgents repair planner."""

    preferred_paths = _ordered_unique_paths(preferred_target_paths or [])
    validation_paths = [
        context.path for context in selected_context if _is_validation_fixture_context(context)
    ]
    mounted_paths = _ordered_unique_paths(context.path for context in selected_context)
    issue_excerpt = _clean_context_excerpt(issue_text).strip()
    if len(issue_excerpt) > max_issue_chars:
        issue_excerpt = issue_excerpt[: max_issue_chars - 15] + "...[truncated]"
    lines = [
        "# PatchSmith Acceptance Rubric",
        "",
        "Use this codebase-grounded checklist before returning the final bounded "
        "`PatchPlan`. If a candidate patch fails one of these checks, select a smaller "
        "or better-localized control point before final output.",
        "",
        "## Issue Evidence",
        "",
    ]
    if issue_excerpt:
        lines.extend(["```text", issue_excerpt, "```"])
    else:
        lines.append("- No issue text was provided.")
    lines.extend(
        [
            "",
            "## Target Checks",
            "",
            "- `path` must be one of the mounted repository files.",
            "- The selected target must directly control the observed failure mechanism.",
            "- `target_rationale` must name why this file and old span control the failure.",
        ]
    )
    if mounted_paths:
        lines.extend(["", "Mounted repository files:"])
        lines.extend(f"- `{path}`" for path in mounted_paths)
    if preferred_paths:
        lines.extend(
            [
                "",
                "Preferred target order:",
                "",
            ]
        )
        for path in preferred_paths:
            lines.append(f"- `{path}`")
        symbol_lines = _preferred_target_symbol_lines(
            preferred_target_symbols,
            preferred_paths=preferred_paths,
        )
        if symbol_lines:
            lines.extend(["", "Preferred symbol focus:", "", *symbol_lines])
    lines.extend(
        [
            "",
            "## Span Checks",
            "",
            "- `old` must be copied verbatim from the selected mounted file after rereading it.",
            "- `new` must make a concrete behavior change, not a comment-only or whitespace-only edit.",
            "- Python replacements must be syntactically complete and must not leave an unterminated compound block.",
            "- Do not introduce helper names, variables, or imports that are not bound in the replacement scope.",
            "",
            "## Validation Checks",
            "",
            "- The patch must be aimed at the reproduced failure, not at incidental wording.",
            "- Prefer source fixes over test, fixture, docs, examples, or report-only edits.",
            "- `failure_mechanism` must describe the runtime behavior expected to change.",
        ]
    )
    if validation_paths:
        lines.extend(["", "Mounted validation or reproduction files:"])
        lines.extend(f"- `{path}`" for path in validation_paths)
    lines.extend(
        [
            "",
            "## Unsafe Patch Exclusions",
            "",
            "- No broad `except Exception`, bare `except:`, silent `pass`, or catch-and-return fallback unless the issue specifically requires that defensive boundary.",
            "- No runtime `__code__` mutation, manual `types.CodeType` rebuild, or metadata rewrite such as `co_filename` unless that is the only source-level control point.",
            "- No naked `importlib.invalidate_caches()` or direct `compile(source.read_text(...), ...)` workaround for stale-cache failures.",
            "- No import-only patch for a behavioral failure unless the sandbox failure is ImportError, ModuleNotFoundError, or NameError.",
        ]
    )
    return "\n".join(lines).rstrip()


def _clean_context_excerpt(excerpt: str) -> str:
    lines = []
    for line in excerpt.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line))
    return "\n".join(lines)


def _ordered_unique_paths(paths: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for path in paths:
        stripped = path.strip().lstrip("/")
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def _preferred_target_symbol_lines(
    preferred_target_symbols: Mapping[str, Iterable[str]] | None,
    *,
    preferred_paths: Iterable[str],
) -> list[str]:
    if not preferred_target_symbols:
        return []
    preferred = [path.strip().lstrip("/") for path in preferred_paths if path.strip()]
    lines: list[str] = []
    for path in preferred:
        symbols = _ordered_unique_symbols(preferred_target_symbols.get(path, []))
        if symbols:
            lines.append(f"- `{path}`: " + ", ".join(f"`{symbol}`" for symbol in symbols))
    return lines


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def _is_validation_fixture_context(context: RetrievedContext) -> bool:
    normalized_path = context.path.replace("\\", "/").lower()
    terms = {term.lower() for term in context.matched_terms}
    if "validation_fixture" in terms or "reproduction_fixture" in terms:
        return True
    if normalized_path.startswith(("tests/", "testing/")):
        return True
    path_name = normalized_path.rsplit("/", maxsplit=1)[-1]
    return path_name.startswith("test_") or "_repro" in path_name


__all__ = ["acceptance_rubric_manifest"]
