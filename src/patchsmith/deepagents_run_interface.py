"""Run-interface assembly for the native DeepAgents planner."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from patchsmith.deepagents_files import (
    _agent_files,
    _repair_interface_manifest,
)
from patchsmith.deepagents_manifests import ManifestContents
from patchsmith.deepagents_prompts import PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH


@dataclass(frozen=True)
class DeepAgentsRunInterface:
    repair_interface_manifest: str
    agent_files: dict[str, dict[str, str]]
    repair_interface_manifest_path: str = PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH


def build_deepagents_run_interface(
    *,
    files: dict[str, dict[str, str]],
    virtual_to_repo: Mapping[str, str],
    subagent_mode: str,
    subagents_enabled: bool,
    subagent_routing_reasons: Iterable[str],
    resource_budget: Mapping[str, Any] | None,
    source_hint_manifest: str | None,
    retry_feedback_manifest: str | None,
    target_history_manifest: str | None,
    context_budget_manifest: str | None,
    repo_map_manifest: str | None,
    repo_instructions_manifest: str | None,
    acceptance_rubric_manifest: str | None,
    context_mode: str,
    context_window_lines: int,
    preferred_target_paths: Iterable[str],
    preferred_target_symbols: Mapping[str, Iterable[str]],
) -> DeepAgentsRunInterface:
    manifest_contents = ManifestContents.from_mapping(
        {
            "source_hint": source_hint_manifest,
            "repo_map": repo_map_manifest,
            "repo_instructions": repo_instructions_manifest,
            "acceptance_rubric": acceptance_rubric_manifest,
            "retry_feedback": retry_feedback_manifest,
            "target_history": target_history_manifest,
            "context_budget": context_budget_manifest,
        }
    )
    repair_interface_manifest = _repair_interface_manifest(
        virtual_to_repo=virtual_to_repo,
        files=files,
        subagent_mode=subagent_mode,
        subagents_enabled=subagents_enabled,
        subagent_routing_reasons=subagent_routing_reasons,
        resource_budget=resource_budget,
        manifest_contents=manifest_contents,
        context_mode=context_mode,
        context_window_lines=context_window_lines,
        preferred_target_paths=preferred_target_paths,
        preferred_target_symbols=preferred_target_symbols,
    )
    agent_files = _agent_files(
        files,
        manifest_contents=manifest_contents.with_content(
            "repair_interface",
            repair_interface_manifest,
        ),
        subagents_enabled=subagents_enabled,
    )
    return DeepAgentsRunInterface(
        repair_interface_manifest=repair_interface_manifest,
        agent_files=agent_files,
    )
