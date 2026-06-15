"""Repair-interface manifest assembly for DeepAgents runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from patchsmith.deepagents_manifests import (
    manifest_enabled_keys,
    required_read_paths,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
)


def repair_interface_manifest(
    *,
    virtual_to_repo: Mapping[str, str],
    files: Mapping[str, Mapping[str, str]] | None = None,
    subagent_mode: str,
    subagents_enabled: bool,
    subagent_routing_reasons: Iterable[str],
    resource_budget: Mapping[str, Any] | None = None,
    source_hint_manifest: bool = False,
    retry_feedback_manifest: bool = False,
    target_history_manifest: bool = False,
    context_budget_manifest: bool = False,
    repo_map_manifest: bool = False,
    repo_instructions_manifest: bool = False,
    acceptance_rubric_manifest: bool = False,
    context_mode: str = "full",
    context_window_lines: int = 0,
    preferred_target_paths: Iterable[str] | None = None,
    preferred_target_symbols: Mapping[str, Iterable[str]] | None = None,
) -> str:
    """Build the compact agent-computer interface mounted for one repair run."""

    budget_response_limit = _resource_budget_response_limit(resource_budget)
    budget_critical = budget_response_limit is not None and budget_response_limit <= 6
    preferred_paths = _ordered_unique_paths(preferred_target_paths or [])
    required_reads = required_read_paths(
        manifest_enabled_keys(
            source_hint_manifest=source_hint_manifest,
            repo_map_manifest=repo_map_manifest,
            repo_instructions_manifest=repo_instructions_manifest,
            acceptance_rubric_manifest=acceptance_rubric_manifest,
            retry_feedback_manifest=retry_feedback_manifest,
            target_history_manifest=target_history_manifest,
            context_budget_manifest=context_budget_manifest,
        ),
        budget_critical=budget_critical,
    )

    lines = [
        "# PatchSmith Repair Interface",
        "",
        "Read this file first. It is the compact agent-computer interface for "
        "this run; use the referenced manifests and mounted source files before "
        "returning a bounded patch plan.",
        "",
        "## Runtime Routing",
        "",
        f"- Subagent mode: `{subagent_mode}`",
        f"- Subagents enabled: `{str(subagents_enabled).lower()}`",
        "- Routing reasons: "
        + (
            ", ".join(f"`{reason}`" for reason in subagent_routing_reasons if reason)
            or "none"
        ),
        f"- Context mode: `{context_mode}`",
        f"- Context window lines: `{context_window_lines}`",
        "",
        "## Required Reads",
        "",
    ]
    lines.extend(f"- `{path}`" for path in required_reads)
    if budget_critical:
        lines.extend(
            [
                "",
                "## Budget-Critical Mode",
                "",
                f"- Response ceiling: `{budget_response_limit}`",
                "- Do not spend responses rereading generic memory or skill files; "
                "this repair interface is the authoritative compact contract for this run.",
                "- Read the validation fixture and the first preferred source path/symbol, "
                "then return one structured `PatchPlan` as soon as the controlling branch "
                "is identifiable.",
                "- Read optional manifests only if the preferred source contradicts the "
                "repair interface.",
            ]
        )
        fast_patch_lines = _fast_patch_packet_lines(
            files or {},
            virtual_to_repo=virtual_to_repo,
            preferred_paths=preferred_paths,
            preferred_target_symbols=preferred_target_symbols,
        )
        if fast_patch_lines:
            lines.extend(["", "## Fast Patch Packet", ""])
            lines.extend(fast_patch_lines)
    budget_lines = _resource_budget_lines(resource_budget)
    if budget_lines:
        lines.extend(["", "## Resource Budget", ""])
        lines.extend(budget_lines)
        lines.extend(
            [
                "",
                "Treat these as benchmark claim limits. Keep source reads targeted, "
                "avoid unnecessary subagent calls, and return one bounded patch plan "
                "as soon as the controlling mechanism is identified.",
            ]
        )
    lines.extend(["", "## Mounted Repository Files", ""])
    for virtual_path, repo_path in sorted(virtual_to_repo.items(), key=lambda item: item[1]):
        lines.append(f"- `{repo_path}` via `{virtual_path}`")

    if preferred_paths:
        if target_history_manifest:
            preferred_guidance = (
                "Choose one of these mounted paths unless a historical target has "
                "fresh old-span evidence for a distinct control point."
            )
        else:
            preferred_guidance = (
                "Choose the first viable mounted path from this ranked list unless "
                "rereading the mounted files reveals a stronger direct control point."
            )
        lines.extend(
            [
                "",
                "## Preferred Next Patch Paths",
                "",
                preferred_guidance,
                "",
            ]
        )
        lines.extend(f"- `{path}`" for path in preferred_paths)
        symbol_lines = _preferred_target_symbol_lines(
            preferred_target_symbols,
            preferred_paths=preferred_paths,
        )
        if symbol_lines:
            lines.extend(
                [
                    "",
                    "Preferred symbol focus within ranked paths:",
                    "",
                    *symbol_lines,
                    "",
                    "Patch inside the listed symbol unless rereading the validation "
                    "fixture proves that an adjacent caller is the direct control point.",
                ]
            )

    if acceptance_rubric_manifest:
        lines.extend(
            [
                "",
                "## Contextual Verifier",
                "",
                f"- Acceptance rubric: `{PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH}`",
                "- Read the rubric before final output and check the selected patch "
                "against its target, span, validation, and unsafe-patch criteria.",
            ]
        )

    if repo_instructions_manifest:
        lines.extend(
            [
                "",
                "## Scoped Repository Instructions",
                "",
                f"- Repository instructions: `{PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH}`",
                "- Read these scoped AGENTS.md-style constraints before source edits "
                "when not in Budget-Critical Mode.",
                "- Apply concrete coding, test, and style requirements only when they "
                "match a mounted path; do not broaden exploration because of generic "
                "repository guidance.",
            ]
        )

    lines.extend(
        [
            "",
            "## Output Contract",
            "",
            "- Return exactly one structured `PatchPlan`.",
            "- `path` must be one of the mounted repository paths above.",
            "- `old` must be copied verbatim after rereading the selected file.",
            "- Include `failure_mechanism` and `target_rationale`.",
            "- Do not write files, run commands, or patch omitted context.",
        ]
    )
    return "\n".join(lines).rstrip()


def _resource_budget_lines(resource_budget: Mapping[str, Any] | None) -> list[str]:
    if not resource_budget:
        return []
    lines: list[str] = []
    max_model_responses = _optional_nonnegative_int(
        resource_budget.get("max_model_responses")
    )
    max_model_tokens = _optional_nonnegative_int(resource_budget.get("max_model_tokens"))
    used_model_responses = _optional_nonnegative_int(
        resource_budget.get("used_model_responses")
    )
    used_model_tokens = _optional_nonnegative_int(resource_budget.get("used_model_tokens"))
    remaining_model_responses = _optional_nonnegative_int(
        resource_budget.get("remaining_model_responses")
    )
    remaining_model_tokens = _optional_nonnegative_int(
        resource_budget.get("remaining_model_tokens")
    )
    if max_model_responses is not None:
        lines.append(f"- Max model responses: `{max_model_responses}`")
    if max_model_tokens is not None:
        lines.append(f"- Max total model tokens: `{max_model_tokens}`")
    if used_model_responses is not None:
        lines.append(f"- Used model responses before this attempt: `{used_model_responses}`")
    if used_model_tokens is not None:
        lines.append(f"- Used model tokens before this attempt: `{used_model_tokens}`")
    if remaining_model_responses is not None:
        lines.append(
            f"- Remaining model responses for this attempt: `{remaining_model_responses}`"
        )
    if remaining_model_tokens is not None:
        lines.append(
            f"- Remaining model tokens for this attempt: `{remaining_model_tokens}`"
        )
    if remaining_model_responses is not None or remaining_model_tokens is not None:
        lines.append(
            "- If remaining budget is tight, localize and review inline before using "
            "subagents."
        )
    return lines


def _resource_budget_response_limit(
    resource_budget: Mapping[str, Any] | None,
) -> int | None:
    if not resource_budget:
        return None
    remaining = _optional_nonnegative_int(
        resource_budget.get("remaining_model_responses")
    )
    if remaining is not None:
        return remaining
    return _optional_nonnegative_int(resource_budget.get("max_model_responses"))


def _fast_patch_packet_lines(
    files: Mapping[str, Mapping[str, str]],
    *,
    virtual_to_repo: Mapping[str, str],
    preferred_paths: Iterable[str],
    preferred_target_symbols: Mapping[str, Iterable[str]] | None,
    max_chars: int = 3500,
) -> list[str]:
    paths = _ordered_unique_paths(preferred_paths)
    if not paths:
        return []
    repo_to_virtual = {
        repo_path.strip().lstrip("/"): virtual_path
        for virtual_path, repo_path in virtual_to_repo.items()
        if repo_path.strip()
    }
    lines = [
        "Use this packet as the authoritative compact source context for this "
        "budget-critical run. If the controlling mechanism is clear here, return the "
        "structured `PatchPlan` without extra source exploration.",
        "",
    ]
    emitted = False
    for path in paths[:1]:
        virtual_path = repo_to_virtual.get(path)
        if virtual_path is None:
            continue
        file_record = files.get(virtual_path)
        if not isinstance(file_record, Mapping):
            continue
        content = file_record.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        snippet = content if len(content) <= max_chars else content[:max_chars].rstrip()
        lines.extend(
            [
                f"### `{path}` via `{virtual_path}`",
                "",
                "Preferred symbols: "
                + _preferred_symbol_text(preferred_target_symbols, path=path),
                "",
                "```python",
                snippet.rstrip(),
                "```",
                "",
                "Copy `old` exactly from this packet or from the mounted file if you "
                "reread it. The returned `new` span must be a concrete behavior change.",
            ]
        )
        emitted = True
        break
    return lines if emitted else []


def _preferred_symbol_text(
    preferred_target_symbols: Mapping[str, Iterable[str]] | None,
    *,
    path: str,
) -> str:
    if not preferred_target_symbols:
        return "none"
    symbols = _ordered_unique_symbols(
        preferred_target_symbols.get(path, [])
    )
    return ", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


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
            lines.append(
                f"- `{path}`: "
                + ", ".join(f"`{symbol}`" for symbol in symbols)
            )
    return lines


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered
