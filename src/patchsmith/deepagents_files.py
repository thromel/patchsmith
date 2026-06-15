"""Virtual file helpers for the native DeepAgents planner."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from patchsmith import deepagents_context_files as _context_file_exports
from patchsmith.deepagents_context_budget import (
    context_budget_manifest,
    context_budget_metadata,
)
from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
)
from patchsmith.deepagents_manifests import (
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

context_file_content_and_timestamp = (
    _context_file_exports.context_file_content_and_timestamp
)
context_files = _context_file_exports.context_files
focused_file_content = _context_file_exports.focused_file_content
path_modified_at = _context_file_exports.path_modified_at
stable_timestamp = _context_file_exports.stable_timestamp


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
