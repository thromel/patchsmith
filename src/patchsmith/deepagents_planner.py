from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any

from patchsmith.deepagents_agent import build_deepagents_agent
from patchsmith.deepagents_config import (
    DEEPAGENTS_PROVIDER,
    DEFAULT_DEEPAGENTS_CONTEXT_MODE,
    DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE,
    DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES,
    DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES,
    DEFAULT_DEEPAGENTS_MAX_FILE_CHARS,
    DEFAULT_DEEPAGENTS_MODEL,
    DeepAgentsPlannerConfig,
    deepagents_config_from_env,
)
from patchsmith.deepagents_context_selection import select_deepagents_context
from patchsmith.deepagents_contract import (
    combine_plan_metadata,
    deepagents_planning_contract,
)
from patchsmith.deepagents_files import (
    _context_budget_manifest,
    _context_budget_metadata,
    _context_files,
    _read_only_filesystem_permissions,
    _repo_instructions_manifest,
    _repo_map_manifest,
    _source_hint_manifest,
    _target_history_manifest,
)
from patchsmith.deepagents_invoke import invoke_deepagents_plan
from patchsmith.deepagents_plan_validation import (
    validate_deepagents_plan_result,
)
from patchsmith.deepagents_routing import (
    is_budget_critical as _is_budget_critical,
)
from patchsmith.deepagents_routing import (
    resource_budget_response_limit as _resource_budget_response_limit,
)
from patchsmith.deepagents_routing import (
    resource_budget_token_limit as _resource_budget_token_limit,
)
from patchsmith.deepagents_routing import (
    subagent_routing_for_task as _subagent_routing_for_task,
)
from patchsmith.deepagents_rubric import (
    acceptance_rubric_manifest as build_acceptance_rubric_manifest,
)
from patchsmith.deepagents_run_interface import build_deepagents_run_interface
from patchsmith.model_config import openai_model_pricing
from patchsmith.models import RetrievedContext
from patchsmith.planning import (
    ModelCallMetadata,
    RepairPlan,
)
from patchsmith.target_localization import (
    TargetLocalizationCandidate,
)

__all__ = [
    "DEEPAGENTS_PROVIDER",
    "DEFAULT_DEEPAGENTS_CONTEXT_MODE",
    "DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE",
    "DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES",
    "DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES",
    "DEFAULT_DEEPAGENTS_MAX_FILE_CHARS",
    "DEFAULT_DEEPAGENTS_MODEL",
    "DeepAgentsPlannerConfig",
    "DeepAgentsRepairPlanner",
    "_read_only_filesystem_permissions",
]


class DeepAgentsRepairPlanner:
    """Native DeepAgents planner that still returns a bounded PatchSmith edit.

    DeepAgents gets the planning/scaffold responsibility: todo management,
    state-backed file reads, and a patch-review subagent. PatchSmith keeps the
    final safety boundary by accepting only one retrieval-bound text replacement.
    """

    def __init__(
        self,
        config: DeepAgentsPlannerConfig | None = None,
        *,
        agent_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or DeepAgentsPlannerConfig()
        self.agent_factory = agent_factory
        self.last_model_metadata: ModelCallMetadata | None = None
        self.last_plan_metadata: dict[str, Any] | None = None
        self._repo_path: Path | None = None

    def prepare_task(self, task: Any) -> None:
        repo_path = getattr(task, "repo_path", None)
        self._repo_path = Path(repo_path) if repo_path else None

    def plan_for_task(self, *, task: Any) -> RepairPlan | None:
        repo_path = getattr(task, "repo_path", None)
        runtime_config = getattr(task, "runtime_config", {})
        target_history_paths = _merge_string_lists(
            _runtime_config_string_list(runtime_config, "target_history_paths"),
            _runtime_config_string_list(runtime_config, "deprioritized_context_paths"),
        )
        target_history_old_span_hashes = _runtime_config_string_list_map(
            runtime_config,
            "target_history_old_span_hashes",
        )
        max_context_files = _runtime_config_nonnegative_int(
            runtime_config,
            "max_context_files",
        )
        resource_budget = _runtime_config_resource_budget(runtime_config)
        subagent_mode_override = _runtime_config_subagent_mode(runtime_config)
        model_override = _runtime_config_string(runtime_config, "model")
        context_selection_pinned_paths = _runtime_config_string_list(
            runtime_config,
            "context_selection_pinned_paths",
        )
        return self._plan_with_repo_path(
            issue_text=str(getattr(task, "issue_text", "")),
            retrieved_context=list(getattr(task, "retrieved_context", [])),
            repo_path=Path(repo_path) if repo_path else None,
            retry_feedback_manifest=_runtime_config_string(
                runtime_config,
                "retry_feedback_brief",
            ),
            deprioritized_paths=target_history_paths,
            target_old_span_hashes=target_history_old_span_hashes,
            max_context_files=max_context_files,
            resource_budget=resource_budget,
            subagent_mode_override=subagent_mode_override,
            model_override=model_override,
            context_selection_pinned_paths=context_selection_pinned_paths,
        )

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        agent_factory: Callable[..., Any] | None = None,
    ) -> DeepAgentsRepairPlanner:
        return cls(
            deepagents_config_from_env(environ),
            agent_factory=agent_factory,
        )

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        return self._plan_with_repo_path(
            issue_text=issue_text,
            retrieved_context=retrieved_context,
            repo_path=self._repo_path,
            retry_feedback_manifest=None,
            deprioritized_paths=[],
            target_old_span_hashes={},
            max_context_files=None,
            resource_budget=None,
            subagent_mode_override=None,
            model_override=None,
        )

    def _plan_with_repo_path(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
        repo_path: Path | None,
        retry_feedback_manifest: str | None,
        deprioritized_paths: list[str],
        target_old_span_hashes: dict[str, list[str]],
        max_context_files: int | None,
        resource_budget: dict[str, int] | None,
        subagent_mode_override: str | None,
        model_override: str | None,
        context_selection_pinned_paths: list[str] | None = None,
    ) -> RepairPlan | None:
        self.last_model_metadata = None
        self.last_plan_metadata = None
        if not retrieved_context:
            return None
        effective_config = self.config
        if model_override is not None:
            pricing = openai_model_pricing(model_override)
            effective_config = dataclass_replace(
                effective_config,
                model=model_override,
                input_cost_per_1m=pricing.input_cost_per_1m if pricing else None,
                output_cost_per_1m=pricing.output_cost_per_1m if pricing else None,
            )
        if max_context_files is not None:
            effective_config = dataclass_replace(
                effective_config,
                max_context_files=max_context_files,
            )
        if subagent_mode_override is not None:
            effective_config = dataclass_replace(
                effective_config,
                subagent_mode=subagent_mode_override,
            )
        elif resource_budget is not None and effective_config.subagent_mode == "full":
            effective_config = dataclass_replace(effective_config, subagent_mode="auto")
        if resource_budget is not None:
            effective_config = dataclass_replace(
                effective_config,
                max_model_responses=_resource_budget_response_limit(resource_budget),
                max_model_tokens=_resource_budget_token_limit(resource_budget),
            )
        budget_critical = _is_budget_critical(resource_budget)

        context_selection = select_deepagents_context(
            issue_text=issue_text,
            retrieved_context=retrieved_context,
            config=effective_config,
            retry_feedback_manifest=retry_feedback_manifest,
            deprioritized_paths=deprioritized_paths,
            context_selection_pinned_paths=context_selection_pinned_paths,
            resource_budget=resource_budget,
        )
        effective_config = context_selection.config
        selected_context = context_selection.selected_context
        selected_max_context_files = context_selection.selected_max_context_files
        files, virtual_to_repo = _context_files(
            selected_context,
            repo_path=repo_path,
            max_file_chars=effective_config.max_file_chars,
            context_mode=effective_config.context_mode,
            context_window_lines=effective_config.context_window_lines,
        )
        context_budget_manifest = _context_budget_manifest(
            retrieved_context,
            selected_context,
            max_context_files=selected_max_context_files,
        )
        context_budget_metadata = _context_budget_metadata(
            retrieved_context,
            selected_context,
            max_context_files=selected_max_context_files,
        )
        repo_map_manifest = (
            _repo_map_manifest(
                retrieved_context,
                selected_context,
                virtual_to_repo,
                files,
            )
            if self.config.enable_repo_map
            else None
        )
        repo_instructions_manifest = _repo_instructions_manifest(
            repo_path,
            selected_context,
        )
        source_hint_manifest = _source_hint_manifest(selected_context, virtual_to_repo)
        target_candidates = context_selection.target_candidates
        preferred_target_paths = context_selection.preferred_target_paths
        preferred_target_reasons = context_selection.preferred_target_reasons
        preferred_target_symbols = context_selection.preferred_target_symbols
        acceptance_rubric_manifest = build_acceptance_rubric_manifest(
            issue_text=issue_text,
            selected_context=selected_context,
            preferred_target_paths=preferred_target_paths,
            preferred_target_symbols=preferred_target_symbols,
        )
        target_history_manifest = (
            _target_history_manifest(
                deprioritized_paths,
                preferred_target_paths=preferred_target_paths,
                preferred_target_reasons=preferred_target_reasons,
            )
            if deprioritized_paths
            else None
        )
        subagent_routing = _subagent_routing_for_task(
            effective_config,
            selected_context=selected_context,
            source_hint_manifest=source_hint_manifest,
            retry_feedback_manifest=retry_feedback_manifest,
            resource_budget=resource_budget,
        )
        run_interface = build_deepagents_run_interface(
            files=files,
            subagent_mode=effective_config.subagent_mode,
            subagents_enabled=bool(subagent_routing.subagents),
            subagent_routing_reasons=subagent_routing.reasons,
            resource_budget=resource_budget,
            virtual_to_repo=virtual_to_repo,
            source_hint_manifest=source_hint_manifest,
            retry_feedback_manifest=retry_feedback_manifest,
            target_history_manifest=target_history_manifest,
            context_budget_manifest=context_budget_manifest,
            repo_map_manifest=repo_map_manifest,
            repo_instructions_manifest=repo_instructions_manifest,
            acceptance_rubric_manifest=acceptance_rubric_manifest,
            context_mode=effective_config.context_mode,
            context_window_lines=effective_config.context_window_lines,
            preferred_target_paths=preferred_target_paths,
            preferred_target_symbols=preferred_target_symbols,
        )
        agent_files = run_interface.agent_files
        contract = deepagents_planning_contract(
            config=effective_config,
            virtual_file_paths=files.keys(),
            subagents=subagent_routing.subagents,
            custom_agent_factory=self.agent_factory is not None,
            context_budget_manifest=context_budget_manifest is not None,
            context_budget_metadata=context_budget_metadata,
            repo_map_manifest=repo_map_manifest is not None,
            repo_instructions_manifest=repo_instructions_manifest is not None,
            acceptance_rubric_manifest=acceptance_rubric_manifest is not None,
            source_hint_manifest=source_hint_manifest is not None,
            retry_feedback_manifest=retry_feedback_manifest is not None,
            target_history_manifest=target_history_manifest is not None,
            repair_interface_manifest=True,
            resource_budget=resource_budget,
            patchable_target_paths=preferred_target_paths,
            preferred_target_symbols=preferred_target_symbols,
            historical_target_paths=deprioritized_paths,
            subagent_routing_reasons=subagent_routing.reasons,
        )
        self.last_plan_metadata = _with_target_localization(
            combine_plan_metadata(
                model_call=None,
                deepagents_contract=contract,
            ),
            target_candidates,
        )
        agent = self._build_agent(
            files=agent_files,
            subagents=subagent_routing.subagents,
            config=effective_config,
        )
        invocation = invoke_deepagents_plan(
            agent=agent,
            issue_text=issue_text,
            virtual_to_repo=virtual_to_repo,
            agent_files=agent_files,
            config=effective_config,
            source_hint_manifest=source_hint_manifest,
            repo_map_manifest=repo_map_manifest,
            repo_instructions_manifest=repo_instructions_manifest,
            acceptance_rubric_manifest=acceptance_rubric_manifest,
            retry_feedback_manifest=retry_feedback_manifest,
            target_history_manifest=target_history_manifest,
            context_budget_manifest=context_budget_manifest,
            preferred_target_paths=preferred_target_paths,
            preferred_target_symbols=preferred_target_symbols,
            subagents_enabled=bool(subagent_routing.subagents),
            budget_critical=budget_critical,
        )
        self.last_model_metadata = invocation.model_metadata
        if invocation.failed:
            self.last_plan_metadata = _with_target_localization(
                combine_plan_metadata(
                    model_call=invocation.model_call_dict(),
                    deepagents_contract=contract,
                ),
                target_candidates,
            )
            return None
        result = invocation.result
        metadata = invocation.model_metadata
        self.last_model_metadata = metadata
        self.last_plan_metadata = _with_target_localization(
            combine_plan_metadata(
                model_call=metadata.to_dict(),
                deepagents_contract=contract,
            ),
            target_candidates,
        )

        validation = validate_deepagents_plan_result(
            result=result,
            files=files,
            virtual_to_repo=virtual_to_repo,
            selected_context=selected_context,
            deprioritized_paths=deprioritized_paths,
            target_old_span_hashes=target_old_span_hashes,
            preferred_target_paths=preferred_target_paths,
            preferred_target_symbols=preferred_target_symbols,
            repo_path=repo_path,
            model_metadata=metadata,
            contract=contract,
        )
        if validation.metadata_update and self.last_plan_metadata is not None:
            self.last_plan_metadata = {
                **self.last_plan_metadata,
                **validation.metadata_update,
            }
        return validation.plan

    def _build_agent(
        self,
        *,
        files: dict[str, dict[str, str]],
        config: DeepAgentsPlannerConfig | None = None,
        subagents: list[dict[str, str]] | None = None,
    ) -> Any:
        config = config or self.config
        if self.agent_factory is not None:
            return self.agent_factory(config=config)
        return build_deepagents_agent(
            config=config,
            files=files,
            subagents=subagents,
        )

def _runtime_config_string(runtime_config: object, key: str) -> str | None:
    if not isinstance(runtime_config, dict):
        return None
    value = runtime_config.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _runtime_config_string_list(runtime_config: object, key: str) -> list[str]:
    if not isinstance(runtime_config, dict):
        return []
    value = runtime_config.get(key)
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _runtime_config_string_list_map(
    runtime_config: object,
    key: str,
) -> dict[str, list[str]]:
    if not isinstance(runtime_config, dict):
        return {}
    value = runtime_config.get(key)
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for path, hashes in value.items():
        if not isinstance(path, str) or not path.strip() or not isinstance(hashes, list):
            continue
        normalized_hashes = [
            item.strip() for item in hashes if isinstance(item, str) and item.strip()
        ]
        if normalized_hashes:
            normalized[path.strip().lstrip("/")] = normalized_hashes
    return normalized


def _runtime_config_nonnegative_int(runtime_config: object, key: str) -> int | None:
    if not isinstance(runtime_config, dict):
        return None
    value = runtime_config.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _runtime_config_resource_budget(runtime_config: object) -> dict[str, int] | None:
    if not isinstance(runtime_config, dict):
        return None
    value = runtime_config.get("resource_budget")
    if not isinstance(value, dict):
        return None
    budget: dict[str, int] = {}
    for key in (
        "max_model_responses",
        "max_model_tokens",
        "used_model_responses",
        "used_model_tokens",
        "remaining_model_responses",
        "remaining_model_tokens",
    ):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            continue
        budget[key] = item
    return budget or None


def _runtime_config_subagent_mode(runtime_config: object) -> str | None:
    value = _runtime_config_string(runtime_config, "subagent_mode")
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"full", "auto", "inline"}:
        return normalized
    return None


def _merge_string_lists(*values: list[str]) -> list[str]:
    merged: list[str] = []
    for items in values:
        for item in items:
            if item not in merged:
                merged.append(item)
    return merged


def _with_target_localization(
    metadata: dict[str, Any] | None,
    candidates: list[TargetLocalizationCandidate],
) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if not candidates:
        return metadata
    return {
        **metadata,
        "target_localization": [candidate.to_dict() for candidate in candidates],
    }
