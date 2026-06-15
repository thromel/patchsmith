"""Structured contract metadata for native DeepAgents planning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from patchsmith.deepagents_config import (
    deepagents_encrypted_reasoning_enabled,
    deepagents_encrypted_reasoning_mode,
)
from patchsmith.deepagents_manifests import ManifestContents
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
)
from patchsmith.deepagents_schema import patch_plan_response_schema

PATCH_QUALITY_POLICY = {
    "prefer_minimal_control_point_patch": True,
    "avoid_broad_exception_swallowing": True,
    "avoid_bare_except_swallowing": True,
    "avoid_silent_fallbacks": True,
    "prefer_explicit_guards_over_catch_and_fallback": True,
    "avoid_runtime_code_object_mutation": True,
    "avoid_manual_code_type_rebuild": True,
    "avoid_code_object_metadata_rewrite": True,
    "avoid_module_file_metadata_rewrite": True,
    "avoid_naked_import_cache_invalidation": True,
    "avoid_unbound_helper_names": True,
    "avoid_test_fixture_doc_targets": True,
    "large_span_expansions_require_rationale": True,
    "require_complete_python_replacement_spans": True,
    "reject_no_op_replacements": True,
    "high_risk_patterns_require_rationale": True,
    "enforced_as_quality_warning": True,
}


def deepagents_planning_contract(
    *,
    config: Any,
    virtual_file_paths: Iterable[str],
    subagents: list[dict[str, str]],
    custom_agent_factory: bool,
    context_budget_manifest: bool = False,
    context_budget_metadata: Mapping[str, Any] | None = None,
    repo_map_manifest: bool = False,
    repo_instructions_manifest: bool = False,
    acceptance_rubric_manifest: bool = False,
    source_hint_manifest: bool = False,
    retry_feedback_manifest: bool = False,
    target_history_manifest: bool = False,
    repair_interface_manifest: bool = False,
    manifest_contents: ManifestContents | None = None,
    resource_budget: Mapping[str, Any] | None = None,
    patchable_target_paths: Iterable[str] | None = None,
    preferred_target_symbols: Mapping[str, Iterable[str]] | None = None,
    historical_target_paths: Iterable[str] | None = None,
    subagent_routing_reasons: Iterable[str] | None = None,
) -> dict[str, Any]:
    file_paths = sorted({path for path in virtual_file_paths if path})
    patchable_paths = _ordered_unique_paths(patchable_target_paths or [])
    historical_paths = sorted(
        {
            path.strip().lstrip("/")
            for path in (historical_target_paths or [])
            if path.strip()
        }
    )
    memory_paths = [PATCHSMITH_DEEPAGENTS_MEMORY_PATH]
    skill_sources = [PATCHSMITH_DEEPAGENTS_SKILL_DIR]
    skill_paths = [PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]
    manifest_presence = manifest_contents or ManifestContents.from_enabled_flags(
        repair_interface=repair_interface_manifest,
        source_hint=source_hint_manifest,
        repo_map=repo_map_manifest,
        repo_instructions=repo_instructions_manifest,
        acceptance_rubric=acceptance_rubric_manifest,
        retry_feedback=retry_feedback_manifest,
        target_history=target_history_manifest,
        context_budget=context_budget_manifest,
    )
    repair_interface_manifest = manifest_presence.is_enabled("repair_interface")
    context_budget_manifest = manifest_presence.is_enabled("context_budget")
    repo_map_manifest = manifest_presence.is_enabled("repo_map")
    repo_instructions_manifest = manifest_presence.is_enabled("repo_instructions")
    acceptance_rubric_manifest = manifest_presence.is_enabled("acceptance_rubric")
    source_hint_manifest = manifest_presence.is_enabled("source_hint")
    retry_feedback_manifest = manifest_presence.is_enabled("retry_feedback")
    target_history_manifest = manifest_presence.is_enabled("target_history")
    repair_interface_path = manifest_presence.path_if_enabled("repair_interface")
    context_budget_path = manifest_presence.path_if_enabled("context_budget")
    repo_map_path = manifest_presence.path_if_enabled("repo_map")
    repo_instructions_path = manifest_presence.path_if_enabled("repo_instructions")
    acceptance_rubric_path = manifest_presence.path_if_enabled("acceptance_rubric")
    source_hint_path = manifest_presence.path_if_enabled("source_hint")
    retry_feedback_path = manifest_presence.path_if_enabled("retry_feedback")
    target_history_path = manifest_presence.path_if_enabled("target_history")
    allowed_reads = sorted(
        {
            *file_paths,
            *manifest_presence.enabled_paths(include_core=True),
        }
    )
    subagent_names = {
        subagent.get("name", "").strip()
        for subagent in subagents
        if subagent.get("name", "").strip()
    }
    failure_localizer_enabled = "failure-localizer" in subagent_names
    patch_reviewer_enabled = "patch-reviewer" in subagent_names
    subagent_mode = str(getattr(config, "subagent_mode", "") or "full")
    routing_reasons = [reason for reason in subagent_routing_reasons or [] if reason]
    budget_critical = _is_budget_critical(resource_budget)
    return {
        "framework": "deepagents",
        "mode": "custom_agent_factory" if custom_agent_factory else "native_create_deep_agent",
        "model": str(getattr(config, "model", "")),
        "max_output_tokens": int(getattr(config, "max_output_tokens", 0) or 0),
        "max_file_chars": int(getattr(config, "max_file_chars", 0) or 0),
        "max_context_files": int(getattr(config, "max_context_files", 0) or 0),
        "context_mode": str(getattr(config, "context_mode", "") or "full"),
        "context_selection_mode": str(
            getattr(config, "context_selection_mode", "") or "retrieved"
        ),
        "context_window_lines": int(
            getattr(config, "context_window_lines", 0) or 0
        ),
        "subagent_mode": subagent_mode,
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "use_responses_api": bool(getattr(config, "use_responses_api", False)),
        "store": bool(getattr(config, "store", False)),
        "encrypted_reasoning": {
            "mode": deepagents_encrypted_reasoning_mode(config),
            "enabled": deepagents_encrypted_reasoning_enabled(config),
            "include": (
                ["reasoning.encrypted_content"]
                if deepagents_encrypted_reasoning_enabled(config)
                else []
            ),
        },
        "state_backend": "deepagents.backends.StateBackend",
        "memory_paths": memory_paths,
        "skill_sources": skill_sources,
        "skill_paths": skill_paths,
        "repair_interface_manifest_path": repair_interface_path,
        "context_budget_manifest_path": context_budget_path,
        "context_budget": (
            _context_budget_contract_metadata(context_budget_metadata)
            if context_budget_manifest
            else None
        ),
        "resource_budget": _resource_budget_contract_metadata(resource_budget),
        "repo_map_manifest_path": repo_map_path,
        "repo_instructions_manifest_path": repo_instructions_path,
        "repository_instructions": {
            "type": "scoped_repo_instructions",
            "manifest_path": repo_instructions_path,
            "required": repo_instructions_manifest and not budget_critical,
        },
        "acceptance_rubric_manifest_path": acceptance_rubric_path,
        "contextual_verifier": {
            "type": "acceptance_rubric",
            "manifest_path": acceptance_rubric_path,
            "required": acceptance_rubric_manifest,
        },
        "source_hint_manifest_path": source_hint_path,
        "retry_feedback_manifest_path": retry_feedback_path,
        "target_history_manifest_path": target_history_path,
        "virtual_file_count": len(file_paths),
        "virtual_file_paths": file_paths,
        "filesystem_policy": {
            "allowed_read_paths": allowed_reads,
            "denied_paths": ["/**"],
            "denied_operations": ["read", "write"],
        },
        "patch_selection_policy": {
            "patchable_paths": patchable_paths,
            "preferred_symbols": _preferred_symbol_contract_metadata(
                preferred_target_symbols,
                patchable_paths=patchable_paths,
            ),
            "historical_paths": historical_paths,
            "historical_paths_require_old_span_evidence": bool(historical_paths),
            "enforced": bool(patchable_paths),
        },
        "patch_quality_policy": dict(PATCH_QUALITY_POLICY),
        "subagent_routing": {
            "configured_mode": subagent_mode,
            "enabled": bool(subagents),
            "reasons": routing_reasons,
        },
        "budget_critical_mode": budget_critical,
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
            "todos_required": not budget_critical,
            "filesystem_reads_required": True,
            "repair_interface_manifest_read_first": repair_interface_manifest,
            "resource_budget_read_first": bool(resource_budget),
            "validation_fixtures_read_first": True,
            "context_budget_manifest_read_first": context_budget_manifest,
            "repo_map_manifest_read_first": repo_map_manifest,
            "repo_instructions_manifest_read_first": (
                repo_instructions_manifest and not budget_critical
            ),
            "acceptance_rubric_manifest_read_first": acceptance_rubric_manifest,
            "source_hint_manifest_read_first": (
                source_hint_manifest and not budget_critical
            ),
            "retry_feedback_manifest_read_first": retry_feedback_manifest,
            "target_history_manifest_read_first": target_history_manifest,
            "failure_localizer_subagent_for_validation_fixtures": (
                failure_localizer_enabled
            ),
            "patch_review_subagent_for_ambiguous_repairs": patch_reviewer_enabled,
            "inline_failure_localization_required": not failure_localizer_enabled,
            "inline_patch_review_required": not patch_reviewer_enabled,
            "one_bounded_replacement": True,
            "retrieval_bound_paths": True,
            "failure_localization_fields_required": True,
            "patch_quality_policy_read_first": not budget_critical,
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


def _ordered_unique_paths(paths: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for path in paths:
        stripped = path.strip().lstrip("/")
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def _preferred_symbol_contract_metadata(
    preferred_target_symbols: Mapping[str, Iterable[str]] | None,
    *,
    patchable_paths: Iterable[str],
) -> dict[str, list[str]]:
    if not preferred_target_symbols:
        return {}
    patchable = {
        path.strip().lstrip("/")
        for path in patchable_paths
        if path.strip()
    }
    normalized: dict[str, list[str]] = {}
    for path, symbols in preferred_target_symbols.items():
        clean_path = path.strip().lstrip("/")
        if not clean_path or clean_path not in patchable:
            continue
        clean_symbols = _ordered_unique_symbols(symbols)
        if clean_symbols:
            normalized[clean_path] = clean_symbols
    return normalized


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def _context_budget_contract_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not metadata:
        return {}
    return {
        "max_context_files": _optional_nonnegative_int(metadata.get("max_context_files")),
        "retrieved_file_count": _optional_nonnegative_int(metadata.get("retrieved_file_count")),
        "mounted_file_count": _optional_nonnegative_int(metadata.get("mounted_file_count")),
        "omitted_file_count": _optional_nonnegative_int(metadata.get("omitted_file_count")),
        "mounted_paths": _ordered_unique_paths(_string_list(metadata.get("mounted_paths"))),
        "omitted_paths": _ordered_unique_paths(_string_list(metadata.get("omitted_paths"))),
    }


def _resource_budget_contract_metadata(
    resource_budget: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not resource_budget:
        return None
    budget = {
        "max_model_responses": _optional_nonnegative_int(
            resource_budget.get("max_model_responses")
        ),
        "max_model_tokens": _optional_nonnegative_int(
            resource_budget.get("max_model_tokens")
        ),
        "used_model_responses": _optional_nonnegative_int(
            resource_budget.get("used_model_responses")
        ),
        "used_model_tokens": _optional_nonnegative_int(
            resource_budget.get("used_model_tokens")
        ),
        "remaining_model_responses": _optional_nonnegative_int(
            resource_budget.get("remaining_model_responses")
        ),
        "remaining_model_tokens": _optional_nonnegative_int(
            resource_budget.get("remaining_model_tokens")
        ),
    }
    return {key: value for key, value in budget.items() if value is not None} or None


def _is_budget_critical(resource_budget: Mapping[str, Any] | None) -> bool:
    if not resource_budget:
        return False
    remaining = _optional_nonnegative_int(
        resource_budget.get("remaining_model_responses")
    )
    if remaining is not None:
        return remaining <= 6
    max_responses = _optional_nonnegative_int(resource_budget.get("max_model_responses"))
    return max_responses is not None and max_responses <= 6


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
