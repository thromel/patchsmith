"""Structured contract metadata for native DeepAgents planning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
)
from patchsmith.deepagents_schema import patch_plan_response_schema


def deepagents_planning_contract(
    *,
    config: Any,
    virtual_file_paths: Iterable[str],
    subagents: list[dict[str, str]],
    custom_agent_factory: bool,
) -> dict[str, Any]:
    file_paths = sorted({path for path in virtual_file_paths if path})
    memory_paths = [PATCHSMITH_DEEPAGENTS_MEMORY_PATH]
    skill_sources = [PATCHSMITH_DEEPAGENTS_SKILL_DIR]
    skill_paths = [PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]
    allowed_reads = sorted({*file_paths, *memory_paths, *skill_paths})
    return {
        "framework": "deepagents",
        "mode": "custom_agent_factory" if custom_agent_factory else "native_create_deep_agent",
        "model": str(getattr(config, "model", "")),
        "max_output_tokens": int(getattr(config, "max_output_tokens", 0) or 0),
        "max_file_chars": int(getattr(config, "max_file_chars", 0) or 0),
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "use_responses_api": bool(getattr(config, "use_responses_api", False)),
        "store": bool(getattr(config, "store", False)),
        "state_backend": "deepagents.backends.StateBackend",
        "memory_paths": memory_paths,
        "skill_sources": skill_sources,
        "skill_paths": skill_paths,
        "virtual_file_count": len(file_paths),
        "virtual_file_paths": file_paths,
        "filesystem_policy": {
            "allowed_read_paths": allowed_reads,
            "denied_paths": ["/**"],
            "denied_operations": ["read", "write"],
        },
        "subagents": [
            {
                "name": subagent.get("name", ""),
                "description": subagent.get("description", ""),
            }
            for subagent in subagents
        ],
        "response_format": "PatchPlan",
        "response_schema": patch_plan_response_schema(),
        "planning_policy": {
            "todos_required": True,
            "filesystem_reads_required": True,
            "patch_review_subagent_for_ambiguous_repairs": True,
            "one_bounded_replacement": True,
            "retrieval_bound_paths": True,
        },
    }


def combine_plan_metadata(
    *,
    model_call: Mapping[str, Any] | None,
    deepagents_contract: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {}
    if model_call:
        metadata["model_call"] = dict(model_call)
    if deepagents_contract:
        metadata["deepagents_contract"] = dict(deepagents_contract)
    return metadata or None
