"""Virtual file helpers for the native DeepAgents planner."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.deepagents_context_budget import (
    context_budget_manifest,
    context_budget_metadata,
)
from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
)
from patchsmith.deepagents_manifests import (
    STABLE_TIMESTAMP,
    add_virtual_files,
    core_virtual_files,
    manifest_specs_from_contents,
)
from patchsmith.deepagents_prompts import deepagents_agents_md, deepagents_repair_skill_md
from patchsmith.deepagents_repair_interface import repair_interface_manifest
from patchsmith.deepagents_repo_instructions import repo_instructions_manifest
from patchsmith.deepagents_repo_map import repo_map_manifest
from patchsmith.deepagents_rubric import acceptance_rubric_manifest
from patchsmith.deepagents_source_hints import source_hint_manifest
from patchsmith.deepagents_target_history import target_history_manifest
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
    core_files = core_virtual_files(
        subagents_enabled=subagents_enabled,
        memory_content=lambda enabled: deepagents_agents_md(
            subagents_enabled=enabled,
        ),
        repair_skill_content=lambda enabled: deepagents_repair_skill_md(
            subagents_enabled=enabled,
        ),
    )
    manifest_files = [
        spec.to_virtual_file()
        for spec in manifest_specs_from_contents(
            {
                "repair_interface": repair_interface_manifest,
                "source_hint": source_hint_manifest,
                "repo_map": repo_map_manifest,
                "repo_instructions": repo_instructions_manifest,
                "acceptance_rubric": acceptance_rubric_manifest,
                "retry_feedback": retry_feedback_manifest,
                "target_history": target_history_manifest,
                "context_budget": context_budget_manifest,
            }
        )
    ]
    return add_virtual_files(files, [*core_files, *manifest_files])



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


def path_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def stable_timestamp() -> str:
    return STABLE_TIMESTAMP


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
