"""Provider invocation boundary for the native DeepAgents planner."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from patchsmith.deepagents_agent import DeepAgentsResourceBudgetExceeded
from patchsmith.deepagents_config import (
    DEEPAGENTS_PROVIDER,
    DeepAgentsPlannerConfig,
)
from patchsmith.deepagents_manifests import ManifestContents
from patchsmith.deepagents_metadata import metadata_from_result
from patchsmith.deepagents_prompts import (
    deepagents_planner_prompt,
)
from patchsmith.deepagents_routing import estimate_resource_budget_cost
from patchsmith.planning import ModelCallMetadata


@dataclass(frozen=True)
class DeepAgentsInvocation:
    result: Any
    model_metadata: ModelCallMetadata
    error_type: str | None = None
    error_summary: str | None = None

    @property
    def failed(self) -> bool:
        return self.error_type is not None

    def model_call_dict(self) -> dict[str, Any]:
        model_call = self.model_metadata.to_dict()
        if self.error_type is not None:
            model_call["error_type"] = self.error_type
        if self.error_summary is not None:
            model_call["error_summary"] = self.error_summary
        return model_call


def invoke_deepagents_plan(
    *,
    agent: Any,
    issue_text: str,
    virtual_to_repo: Mapping[str, str],
    agent_files: dict[str, dict[str, str]],
    config: DeepAgentsPlannerConfig,
    source_hint_manifest: str | None,
    repo_map_manifest: str | None,
    repo_instructions_manifest: str | None,
    acceptance_rubric_manifest: str | None,
    retry_feedback_manifest: str | None,
    target_history_manifest: str | None,
    context_budget_manifest: str | None,
    manifest_contents: ManifestContents | None = None,
    preferred_target_paths: Iterable[str],
    preferred_target_symbols: Mapping[str, Iterable[str]],
    subagents_enabled: bool,
    budget_critical: bool,
) -> DeepAgentsInvocation:
    prompt_virtual_to_repo = dict(virtual_to_repo)
    prompt_preferred_target_paths = list(preferred_target_paths)
    manifest_presence = manifest_contents or ManifestContents.from_enabled_flags(
        repair_interface=True,
        source_hint=source_hint_manifest is not None,
        repo_map=repo_map_manifest is not None,
        repo_instructions=repo_instructions_manifest is not None,
        acceptance_rubric=acceptance_rubric_manifest is not None,
        retry_feedback=retry_feedback_manifest is not None,
        target_history=target_history_manifest is not None,
        context_budget=context_budget_manifest is not None,
    )
    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": deepagents_planner_prompt(
                            issue_text,
                            prompt_virtual_to_repo,
                            repair_interface_manifest_path=(
                                manifest_presence.path_if_enabled("repair_interface")
                            ),
                            source_hint_manifest_path=(
                                manifest_presence.path_if_enabled("source_hint")
                            ),
                            repo_map_manifest_path=(manifest_presence.path_if_enabled("repo_map")),
                            repo_instructions_manifest_path=(
                                manifest_presence.path_if_enabled("repo_instructions")
                            ),
                            acceptance_rubric_manifest_path=(
                                manifest_presence.path_if_enabled("acceptance_rubric")
                            ),
                            retry_feedback_manifest_path=(
                                manifest_presence.path_if_enabled("retry_feedback")
                            ),
                            target_history_manifest_path=(
                                manifest_presence.path_if_enabled("target_history")
                            ),
                            context_budget_manifest_path=(
                                manifest_presence.path_if_enabled("context_budget")
                            ),
                            preferred_target_paths=prompt_preferred_target_paths,
                            preferred_target_symbols=preferred_target_symbols,
                            subagents_enabled=subagents_enabled,
                            budget_critical=budget_critical,
                        ),
                    }
                ],
                "files": agent_files,
            }
        )
    except Exception as error:
        return DeepAgentsInvocation(
            result=None,
            model_metadata=_failure_metadata(error, config=config),
            error_type=type(error).__name__,
            error_summary=error_summary(error),
        )
    return DeepAgentsInvocation(
        result=result,
        model_metadata=metadata_from_result(
            result=result,
            provider=DEEPAGENTS_PROVIDER,
            configured_model=config.model,
            input_cost_per_1m=config.input_cost_per_1m,
            output_cost_per_1m=config.output_cost_per_1m,
        ),
    )


def agent_failure_status(error: Exception) -> str:
    if isinstance(error, DeepAgentsResourceBudgetExceeded):
        return "resource_budget_exceeded"
    message = str(error).lower()
    if "structured output" in message and "parsing failed" in message:
        return "structured_output_parse_failed"
    return "agent_invoke_failed"


def error_summary(error: Exception, *, limit: int = 360) -> str:
    compact = " ".join(str(error).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 15] + "...[truncated]"


def _failure_metadata(
    error: Exception,
    *,
    config: DeepAgentsPlannerConfig,
) -> ModelCallMetadata:
    return ModelCallMetadata(
        provider=DEEPAGENTS_PROVIDER,
        model=config.model,
        response_count=(
            error.response_count if isinstance(error, DeepAgentsResourceBudgetExceeded) else None
        ),
        input_tokens=(
            error.input_tokens if isinstance(error, DeepAgentsResourceBudgetExceeded) else None
        ),
        output_tokens=(
            error.output_tokens if isinstance(error, DeepAgentsResourceBudgetExceeded) else None
        ),
        total_tokens=(
            error.total_tokens if isinstance(error, DeepAgentsResourceBudgetExceeded) else None
        ),
        estimated_cost_usd=(
            estimate_resource_budget_cost(
                input_tokens=error.input_tokens,
                output_tokens=error.output_tokens,
                config=config,
            )
            if isinstance(error, DeepAgentsResourceBudgetExceeded)
            else None
        ),
        status=agent_failure_status(error),
    )
