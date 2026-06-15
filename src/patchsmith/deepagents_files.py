"""Virtual file helpers for the native DeepAgents planner."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
    PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
    PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
    deepagents_agents_md,
    deepagents_repair_skill_md,
)
from patchsmith.deepagents_rubric import acceptance_rubric_manifest
from patchsmith.models import RetrievedContext


def context_files(
    retrieved_context: list[RetrievedContext],
    *,
    repo_path: Path | None = None,
    max_file_chars: int = 40_000,
    context_mode: str = "full",
    context_window_lines: int = 80,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    files: dict[str, dict[str, str]] = {}
    virtual_to_repo: dict[str, str] = {}
    for context in retrieved_context:
        virtual_path = "/" + context.path.lstrip("/")
        virtual_to_repo[virtual_path] = context.path
        content, modified_at = context_file_content_and_timestamp(
            repo_path,
            context,
            max_file_chars=max_file_chars,
            context_mode=context_mode,
            context_window_lines=context_window_lines,
        )
        files[virtual_path] = {
            "content": content,
            "encoding": "utf-8",
            "created_at": modified_at,
            "modified_at": modified_at,
        }
    return files, virtual_to_repo


def select_contexts_for_deepagents(
    retrieved_context: list[RetrievedContext],
    *,
    max_context_files: int,
    preferred_paths: Iterable[str] = (),
) -> list[RetrievedContext]:
    if max_context_files <= 0 or len(retrieved_context) <= max_context_files:
        return list(retrieved_context)
    preferred_order = {
        path.strip().lstrip("/"): index
        for index, path in enumerate(preferred_paths)
        if path.strip()
    }
    ranked = sorted(
        enumerate(retrieved_context),
        key=lambda item: _deepagents_context_priority(
            item[0],
            item[1],
            max_context_files=max_context_files,
            preferred_order=preferred_order,
        ),
    )
    selected_indexes = sorted(index for index, _context in ranked[:max_context_files])
    return [retrieved_context[index] for index in selected_indexes]


def agent_files(
    files: dict[str, dict[str, str]],
    *,
    repair_interface_manifest: str | None = None,
    acceptance_rubric_manifest: str | None = None,
    context_budget_manifest: str | None = None,
    repo_map_manifest: str | None = None,
    repo_instructions_manifest: str | None = None,
    source_hint_manifest: str | None = None,
    retry_feedback_manifest: str | None = None,
    target_history_manifest: str | None = None,
    subagents_enabled: bool = True,
) -> dict[str, dict[str, str]]:
    agent_file_map = {
        **files,
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH: {
            "content": deepagents_agents_md(subagents_enabled=subagents_enabled),
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        },
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH: {
            "content": deepagents_repair_skill_md(subagents_enabled=subagents_enabled),
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        },
    }
    if repair_interface_manifest and repair_interface_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH] = {
            "content": repair_interface_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if acceptance_rubric_manifest and acceptance_rubric_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH] = {
            "content": acceptance_rubric_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if repo_map_manifest and repo_map_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH] = {
            "content": repo_map_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if repo_instructions_manifest and repo_instructions_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH] = {
            "content": repo_instructions_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if context_budget_manifest and context_budget_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH] = {
            "content": context_budget_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if source_hint_manifest and source_hint_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH] = {
            "content": source_hint_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if retry_feedback_manifest and retry_feedback_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH] = {
            "content": retry_feedback_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    if target_history_manifest and target_history_manifest.strip():
        agent_file_map[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH] = {
            "content": target_history_manifest,
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        }
    return agent_file_map


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
    required_reads = []
    if not budget_critical:
        required_reads.extend(
            [
                PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
                PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
            ]
        )
    if source_hint_manifest and not budget_critical:
        required_reads.append(PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH)
    if repo_map_manifest:
        required_reads.append(PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH)
    if repo_instructions_manifest and not budget_critical:
        required_reads.append(PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH)
    if acceptance_rubric_manifest:
        required_reads.append(PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH)
    if retry_feedback_manifest:
        required_reads.append(PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH)
    if target_history_manifest:
        required_reads.append(PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH)
    if context_budget_manifest:
        required_reads.append(PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH)

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


def context_budget_manifest(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    *,
    max_context_files: int,
    max_excerpt_chars: int = 1200,
) -> str | None:
    metadata = context_budget_metadata(
        retrieved_context,
        selected_context,
        max_context_files=max_context_files,
    )
    if metadata is None:
        return None
    omitted_context = _omitted_contexts(retrieved_context, selected_context)
    lines = [
        "# PatchSmith Context Budget Manifest",
        "",
        f"- Max mounted repository files: `{metadata['max_context_files']}`",
        f"- Retrieved context files: `{metadata['retrieved_file_count']}`",
        f"- Mounted repository files: `{metadata['mounted_file_count']}`",
        f"- Omitted retrieved files: `{metadata['omitted_file_count']}`",
        "",
        "PatchSmith mounted only the selected repository files in this DeepAgents "
        "filesystem to keep the run within the configured context budget. Omitted "
        "files below are retrieval evidence, not readable source files in this run.",
        "",
        "Use omitted-file summaries as routing evidence before final target selection. "
        "Do not return an omitted path unless it is also listed as a mounted provided "
        "file; choose a mounted control point that directly governs the omitted signal.",
        "",
        "## Mounted Repository Files",
        "",
    ]
    for context in selected_context:
        lines.append(f"- `{context.path}`")
    lines.extend(["", "## Omitted Retrieved Files", ""])
    for context in omitted_context:
        symbols = _context_symbols(context)
        terms = _display_terms(context.matched_terms)
        excerpt = clean_context_excerpt(context.excerpt).strip()
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[: max_excerpt_chars - 15] + "...[truncated]"
        lines.extend(
            [
                f"### `{context.path}`",
                f"- Rank: `{context.rank}`",
                f"- Score: `{context.score:.4f}`",
                f"- Method: `{context.method}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Matched terms: "
                + (", ".join(f"`{term}`" for term in terms) if terms else "none"),
            ]
        )
        if excerpt:
            lines.extend(["", "Excerpt:", "```text", excerpt, "```"])
        lines.append("")
    return "\n".join(lines).rstrip()


def context_budget_metadata(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    *,
    max_context_files: int,
) -> dict[str, object] | None:
    if max_context_files <= 0 or len(retrieved_context) <= len(selected_context):
        return None
    omitted_context = _omitted_contexts(retrieved_context, selected_context)
    if not omitted_context:
        return None
    return {
        "max_context_files": max_context_files,
        "retrieved_file_count": len(retrieved_context),
        "mounted_file_count": len(selected_context),
        "omitted_file_count": len(omitted_context),
        "mounted_paths": [context.path for context in selected_context],
        "omitted_paths": [context.path for context in omitted_context],
    }


REPO_INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules")


def repo_instructions_manifest(
    repo_path: Path | None,
    selected_context: list[RetrievedContext],
    *,
    max_instruction_files: int = 5,
    max_chars_per_file: int = 3500,
    max_total_chars: int = 12_000,
) -> str | None:
    if repo_path is None or not selected_context or max_instruction_files <= 0:
        return None
    root = _resolved_repo_root(repo_path)
    if root is None:
        return None
    sections: list[str] = []
    emitted = 0
    emitted_chars = 0
    seen_paths: set[Path] = set()
    for scope_dir in _repo_instruction_scope_dirs(selected_context):
        for filename in REPO_INSTRUCTION_FILENAMES:
            if emitted >= max_instruction_files or emitted_chars >= max_total_chars:
                break
            candidate = _repo_instruction_candidate(root, scope_dir, filename)
            if candidate is None or candidate in seen_paths:
                continue
            content = _read_repo_instruction_file(candidate)
            if content is None:
                continue
            remaining_chars = max_total_chars - emitted_chars
            clipped = content[: min(max_chars_per_file, remaining_chars)].rstrip()
            if len(content) > len(clipped):
                clipped += "\n...[truncated]"
            instruction_path = candidate.relative_to(root).as_posix()
            scoped_paths = _scoped_instruction_paths(scope_dir, selected_context)
            sections.extend(
                [
                    f"## `{instruction_path}`",
                    f"- Scope directory: `{scope_dir or '.'}`",
                    "- Applies to mounted paths: "
                    + ", ".join(f"`{path}`" for path in scoped_paths),
                    "",
                    "```markdown",
                    clipped,
                    "```",
                    "",
                ]
            )
            emitted += 1
            emitted_chars += len(clipped)
            seen_paths.add(candidate)
        if emitted >= max_instruction_files or emitted_chars >= max_total_chars:
            break
    if not sections:
        return None
    return "\n".join(
        [
            "# PatchSmith Scoped Repository Instructions",
            "",
            "PatchSmith found AGENTS.md-style repository instruction files that apply "
            "to the mounted repair context. Treat them as scoped constraints, not as "
            "permission for broad repository exploration.",
            "",
            "Use only concrete coding, style, safety, and validation requirements that "
            "match the mounted paths below. If an instruction is generic or unrelated "
            "to the selected patch target, keep the repair bounded to the issue evidence.",
            "",
            *sections,
        ]
    ).rstrip()


def _resolved_repo_root(repo_path: Path) -> Path | None:
    try:
        root = repo_path.resolve()
    except OSError:
        return None
    return root if root.is_dir() else None


def _repo_instruction_scope_dirs(contexts: list[RetrievedContext]) -> list[str]:
    scope_dirs = [""]
    for context in contexts:
        normalized = context.path.replace("\\", "/").strip().lstrip("/")
        if not normalized or normalized.startswith("../"):
            continue
        parts = [part for part in normalized.split("/")[:-1] if part and part != "."]
        for index in range(1, len(parts) + 1):
            scope = "/".join(parts[:index])
            if scope not in scope_dirs:
                scope_dirs.append(scope)
    return scope_dirs


def _repo_instruction_candidate(
    root: Path,
    scope_dir: str,
    filename: str,
) -> Path | None:
    try:
        candidate = (root / scope_dir / filename).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _read_repo_instruction_file(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return content or None


def _scoped_instruction_paths(
    scope_dir: str,
    contexts: list[RetrievedContext],
) -> list[str]:
    normalized_scope = scope_dir.strip().strip("/")
    scoped_paths = []
    for context in contexts:
        normalized_path = context.path.replace("\\", "/").strip().lstrip("/")
        if not normalized_path:
            continue
        if not normalized_scope or normalized_path.startswith(f"{normalized_scope}/"):
            scoped_paths.append(normalized_path)
    return scoped_paths or ["all mounted paths"]


def _omitted_contexts(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
) -> list[RetrievedContext]:
    selected_ids = {id(context) for context in selected_context}
    return [context for context in retrieved_context if id(context) not in selected_ids]


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


def repo_map_manifest(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    virtual_to_repo: dict[str, str],
    files: dict[str, dict[str, str]],
    *,
    max_definitions_per_file: int = 8,
    max_terms_per_file: int = 10,
) -> str | None:
    if not retrieved_context:
        return None
    selected_ids = {id(context) for context in selected_context}
    lines = [
        "# PatchSmith Retrieved Repo Map",
        "",
        "This compact map summarizes the retrieved context before deep file reads. "
        "Use it to route target selection, then inspect the mounted source file before "
        "returning a patch. Omitted files are retrieval evidence only and may not be "
        "valid final patch paths under a context cap.",
        "",
        "## Mounted Files",
        "",
    ]
    mounted_sections = _repo_map_sections(
        [context for context in retrieved_context if id(context) in selected_ids],
        selected=True,
        virtual_to_repo=virtual_to_repo,
        files=files,
        max_definitions_per_file=max_definitions_per_file,
        max_terms_per_file=max_terms_per_file,
    )
    omitted_sections = _repo_map_sections(
        [context for context in retrieved_context if id(context) not in selected_ids],
        selected=False,
        virtual_to_repo=virtual_to_repo,
        files=files,
        max_definitions_per_file=max_definitions_per_file,
        max_terms_per_file=max_terms_per_file,
    )
    lines.extend(mounted_sections or ["- none"])
    if omitted_sections:
        lines.extend(["", "## Omitted Retrieved Files", "", *omitted_sections])
    return "\n".join(lines).rstrip()


def _repo_map_sections(
    contexts: list[RetrievedContext],
    *,
    selected: bool,
    virtual_to_repo: dict[str, str],
    files: dict[str, dict[str, str]],
    max_definitions_per_file: int,
    max_terms_per_file: int,
) -> list[str]:
    sections: list[str] = []
    for context in contexts:
        virtual_path = "/" + context.path.lstrip("/")
        repo_path = virtual_to_repo.get(virtual_path, context.path)
        source = (
            files.get(virtual_path, {}).get("content", "")
            if selected
            else clean_context_excerpt(context.excerpt)
        )
        definitions = _definition_signatures(source)
        symbols = _context_symbols(context)
        terms = _display_terms(context.matched_terms, limit=max_terms_per_file)
        sections.extend(
            [
                f"### `{repo_path}`",
                f"- Virtual path: `{virtual_path}`",
                f"- Status: `{'mounted' if selected else 'omitted'}`",
                f"- Rank: `{context.rank}`",
                f"- Score: `{context.score:.4f}`",
                f"- Method: `{context.method}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Matched terms: "
                + (", ".join(f"`{term}`" for term in terms) if terms else "none"),
            ]
        )
        if definitions:
            sections.extend(["- Definition signatures:"])
            sections.extend(
                f"  - `{signature}`"
                for signature in definitions[: max(max_definitions_per_file, 0)]
            )
        sections.append("")
    return sections


def source_hint_manifest(
    retrieved_context: list[RetrievedContext],
    virtual_to_repo: dict[str, str],
    *,
    max_excerpt_chars: int = 4000,
) -> str | None:
    sections: list[str] = []
    for context in retrieved_context:
        symbols = _context_symbols(context)
        if "reviewed_source_hint" not in context.matched_terms and not symbols:
            continue
        virtual_path = "/" + context.path.lstrip("/")
        repo_path = virtual_to_repo.get(virtual_path, context.path)
        excerpt = clean_context_excerpt(context.excerpt).strip()
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[: max_excerpt_chars - 15] + "...[truncated]"
        sections.extend(
            [
                f"## `{repo_path}`",
                f"- Virtual path: `{virtual_path}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Priority: reviewed reproduction source hint",
            ]
        )
        if excerpt:
            sections.extend(
                [
                    "",
                    "Focused excerpt:",
                    "```text",
                    excerpt,
                    "```",
                ]
            )
        sections.append("")
    if not sections:
        return None
    return "\n".join(
        [
            "# PatchSmith Source Hint Manifest",
            "",
            "Read this manifest before broad source exploration. These hints came from "
            "reviewed reproduction evidence, and symbol-qualified hints identify code "
            "paths that should be inspected before selecting a different edit target.",
            "",
            *sections,
        ]
    ).rstrip()


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


def read_only_filesystem_permissions(
    paths: Iterable[str],
    *,
    permission_cls: Callable[..., Any],
) -> list[Any]:
    allowed_reads = sorted(
        {"/" + path.strip().lstrip("/") for path in paths if isinstance(path, str) and path.strip()}
    )
    return [
        permission_cls(operations=["read"], paths=allowed_reads, mode="allow"),
        permission_cls(operations=["read", "write"], paths=["/**"], mode="deny"),
    ]


def repo_path_from_agent_path(path: str, virtual_to_repo: dict[str, str]) -> str:
    normalized = "/" + path.strip().lstrip("/")
    return virtual_to_repo.get(normalized, normalized.lstrip("/"))


def context_file_content_and_timestamp(
    repo_path: Path | None,
    context: RetrievedContext,
    *,
    max_file_chars: int,
    context_mode: str = "full",
    context_window_lines: int = 80,
) -> tuple[str, str]:
    if repo_path is None:
        return clean_context_excerpt(context.excerpt), stable_timestamp()
    path = repo_path / context.path
    try:
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            return (
                focused_file_content(
                    content,
                    context.excerpt,
                    max_file_chars=max_file_chars,
                    context=context,
                    context_mode=context_mode,
                    context_window_lines=context_window_lines,
                ),
                path_modified_at(path),
            )
    except UnicodeDecodeError:
        pass
    return clean_context_excerpt(context.excerpt), stable_timestamp()


def focused_file_content(
    content: str,
    excerpt: str,
    *,
    max_file_chars: int,
    context: RetrievedContext | None = None,
    context_mode: str = "full",
    context_window_lines: int = 80,
) -> str:
    if context_mode == "span" and context is not None:
        span = _focused_source_span(
            content,
            context,
            max_file_chars=max_file_chars,
            context_window_lines=context_window_lines,
        )
        if span is not None:
            return span
    if max_file_chars <= 0 or len(content) <= max_file_chars:
        return content
    cleaned_excerpt = clean_context_excerpt(excerpt)
    if cleaned_excerpt.strip():
        return cleaned_excerpt[:max_file_chars]
    return content[:max_file_chars]


def _focused_source_span(
    content: str,
    context: RetrievedContext,
    *,
    max_file_chars: int,
    context_window_lines: int,
) -> str | None:
    lines = content.splitlines(keepends=True)
    if not lines:
        return None
    anchors = _source_span_anchor_lines(content, lines, context)
    if not anchors:
        return None
    anchor = anchors[0]
    window = max(8, context_window_lines)
    before = window // 2
    after = window - before
    start = max(0, anchor - before)
    end = min(len(lines), anchor + after)
    text = "".join(lines[start:end])
    if max_file_chars > 0 and len(text) > max_file_chars:
        text = _trim_span_to_char_budget(
            lines,
            anchor=anchor,
            max_file_chars=max_file_chars,
        )
    return text if text.strip() else None


def _source_span_anchor_lines(
    content: str,
    lines: list[str],
    context: RetrievedContext,
) -> list[int]:
    terms = _source_span_anchor_terms(context)
    scored: list[tuple[int, int]] = []
    if terms:
        lowered_terms = [term.lower() for term in terms]
        for index, line in enumerate(lines):
            lowered = line.lower()
            score = sum(1 for term in lowered_terms if term and term in lowered)
            if score:
                scored.append((-score, index))
    excerpt_anchor = _excerpt_anchor_line(content, lines, context.excerpt)
    if excerpt_anchor is not None:
        scored.append((-100, excerpt_anchor))
    return [index for _score, index in sorted(dict.fromkeys(scored))]


def _source_span_anchor_terms(context: RetrievedContext) -> list[str]:
    terms: list[str] = []
    for term in context.matched_terms:
        for candidate in _term_candidates(term):
            if candidate and candidate not in terms:
                terms.append(candidate)
    return terms


def _term_candidates(term: str) -> list[str]:
    raw = term.strip()
    if not raw:
        return []
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1].strip()
    raw = raw.strip("`'\"")
    candidates = [raw] if len(raw) >= 4 else []
    candidates.extend(
        part
        for part in re.split(r"[^A-Za-z0-9_]+", raw)
        if len(part) >= 4
    )
    return [candidate for candidate in dict.fromkeys(candidates) if candidate]


def _excerpt_anchor_line(
    content: str,
    lines: list[str],
    excerpt: str,
) -> int | None:
    cleaned = clean_context_excerpt(excerpt)
    for excerpt_line in cleaned.splitlines():
        needle = excerpt_line.strip()
        if len(needle) < 12:
            continue
        offset = content.find(needle)
        if offset < 0:
            continue
        running = 0
        for index, line in enumerate(lines):
            running += len(line)
            if running > offset:
                return index
    return None


def _trim_span_to_char_budget(
    lines: list[str],
    *,
    anchor: int,
    max_file_chars: int,
) -> str:
    start = anchor
    end = anchor + 1
    text = "".join(lines[start:end])
    while len(text) < max_file_chars and (start > 0 or end < len(lines)):
        expanded = False
        if start > 0:
            candidate = lines[start - 1] + text
            if len(candidate) <= max_file_chars:
                start -= 1
                text = candidate
                expanded = True
        if end < len(lines):
            candidate = text + lines[end]
            if len(candidate) <= max_file_chars:
                end += 1
                text = candidate
                expanded = True
        if not expanded:
            break
    return text


def clean_context_excerpt(excerpt: str) -> str:
    lines = []
    for line in excerpt.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line))
    return "\n".join(lines)


def path_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def stable_timestamp() -> str:
    return "1970-01-01T00:00:00+00:00"


def _context_symbols(context: RetrievedContext) -> list[str]:
    symbols = []
    for term in context.matched_terms:
        if term.startswith("symbol:"):
            symbol = term.removeprefix("symbol:").strip()
            if symbol:
                symbols.append(symbol)
    return sorted(dict.fromkeys(symbols))


def _display_terms(terms: Iterable[str], *, limit: int = 12) -> list[str]:
    displayed: list[str] = []
    for term in terms:
        stripped = term.strip()
        if stripped and stripped not in displayed:
            displayed.append(stripped)
        if len(displayed) >= limit:
            break
    return displayed


def _definition_signatures(source: str) -> list[str]:
    signatures: list[str] = []
    for line in clean_context_excerpt(source).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        if _looks_like_definition_signature(stripped):
            signatures.append(_truncate_signature(stripped))
    return list(dict.fromkeys(signatures))


def _looks_like_definition_signature(line: str) -> bool:
    return bool(
        re.match(
            r"^(?:async\s+def|def|class)\s+[A-Za-z_][A-Za-z0-9_]*",
            line,
        )
        or re.match(
            r"^(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][A-Za-z0-9_$]*",
            line,
        )
        or re.match(
            r"^(?:export\s+)?(?:class|interface|type)\s+[A-Za-z_$][A-Za-z0-9_$]*",
            line,
        )
        or re.match(
            r"^(?:pub\s+)?(?:async\s+)?fn\s+[A-Za-z_][A-Za-z0-9_]*",
            line,
        )
    )


def _truncate_signature(signature: str, *, limit: int = 160) -> str:
    compact = " ".join(signature.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 15] + "...[truncated]"


def _deepagents_context_priority(
    index: int,
    context: RetrievedContext,
    *,
    max_context_files: int,
    preferred_order: Mapping[str, int],
) -> tuple[int, int, int, int, int, float, int]:
    terms = set(context.matched_terms)
    reviewed_hint = "reviewed_source_hint" in terms or "active_path" in terms
    symbol_hint = any(term.startswith("symbol:") for term in terms)
    validation_fixture = _is_validation_fixture_context(context)
    preferred_rank = preferred_order.get(context.path.strip().lstrip("/"))
    rank = context.rank if context.rank > 0 else index + 1
    return (
        0 if validation_fixture and max_context_files > 1 else 1,
        preferred_rank if preferred_rank is not None else len(preferred_order) + 1,
        0 if reviewed_hint else 1,
        0 if symbol_hint else 1,
        rank,
        -context.score,
        index,
    )


def _is_validation_fixture_context(context: RetrievedContext) -> bool:
    normalized_path = context.path.replace("\\", "/").lower()
    terms = {term.lower() for term in context.matched_terms}
    if "validation_fixture" in terms or "reproduction_fixture" in terms:
        return True
    if normalized_path.startswith(("tests/", "testing/")):
        return True
    path_name = normalized_path.rsplit("/", maxsplit=1)[-1]
    return path_name.startswith("test_") or "_repro" in path_name


_agent_files = agent_files
_acceptance_rubric_manifest = acceptance_rubric_manifest
_clean_context_excerpt = clean_context_excerpt
_context_budget_manifest = context_budget_manifest
_context_budget_metadata = context_budget_metadata
_context_files = context_files
_read_only_filesystem_permissions = read_only_filesystem_permissions
_repair_interface_manifest = repair_interface_manifest
_repo_path_from_agent_path = repo_path_from_agent_path
_repo_instructions_manifest = repo_instructions_manifest
_repo_map_manifest = repo_map_manifest
_select_contexts_for_deepagents = select_contexts_for_deepagents
_source_hint_manifest = source_hint_manifest
_target_history_manifest = target_history_manifest
