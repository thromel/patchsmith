"""DeepAgents subagent routing and resource-budget policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_prompts import deepagents_patch_review_subagents
from patchsmith.models import RetrievedContext


@dataclass(frozen=True)
class SubagentRouting:
    subagents: list[dict[str, str]]
    reasons: list[str]


def subagent_routing_for_task(
    config: DeepAgentsPlannerConfig,
    *,
    selected_context: list[RetrievedContext],
    source_hint_manifest: str | None,
    retry_feedback_manifest: str | None,
    resource_budget: Mapping[str, int] | None = None,
) -> SubagentRouting:
    if config.subagent_mode == "inline":
        return SubagentRouting(subagents=[], reasons=["configured_inline"])
    if config.subagent_mode == "full":
        return SubagentRouting(
            subagents=deepagents_patch_review_subagents(),
            reasons=["configured_full"],
        )
    if config.subagent_mode == "auto":
        if resource_budget is not None and not retry_feedback_manifest:
            return SubagentRouting(
                subagents=[],
                reasons=["budget_constrained_inline"],
            )
        budget_pressure_reason = resource_budget_pressure_reason(
            resource_budget,
            retry_feedback_manifest=retry_feedback_manifest,
        )
        reasons = auto_subagent_reasons(
            selected_context=selected_context,
            source_hint_manifest=source_hint_manifest,
            retry_feedback_manifest=retry_feedback_manifest,
        )
        if budget_pressure_reason is not None:
            return SubagentRouting(
                subagents=[],
                reasons=[budget_pressure_reason, *reasons],
            )
        if reasons:
            return SubagentRouting(
                subagents=deepagents_patch_review_subagents(),
                reasons=reasons,
            )
        return SubagentRouting(
            subagents=[],
            reasons=["auto_simple_single_control_point"],
        )
    return SubagentRouting(
        subagents=deepagents_patch_review_subagents(),
        reasons=["configured_full"],
    )


def auto_subagent_reasons(
    *,
    selected_context: list[RetrievedContext],
    source_hint_manifest: str | None,
    retry_feedback_manifest: str | None,
) -> list[str]:
    reasons: list[str] = []
    if retry_feedback_manifest:
        reasons.append("retry_feedback_manifest")
    if source_hint_manifest:
        reasons.append("source_hint_manifest")
    if has_validation_fixture_context(selected_context):
        reasons.append("validation_fixture_context")
    if len(selected_context) >= 4:
        reasons.append("multiple_mounted_contexts")
    return reasons


def resource_budget_pressure_reason(
    resource_budget: Mapping[str, int] | None,
    *,
    retry_feedback_manifest: str | None,
) -> str | None:
    if resource_budget is None or not retry_feedback_manifest:
        return None
    remaining_responses = resource_budget.get("remaining_model_responses")
    max_responses = resource_budget.get("max_model_responses")
    if remaining_responses is not None:
        if remaining_responses <= 0:
            return "remaining_response_budget_exhausted_inline"
        if low_remaining_budget(
            remaining=remaining_responses,
            maximum=max_responses,
            minimum_threshold=4,
        ):
            return "remaining_response_budget_pressure_inline"
    remaining_tokens = resource_budget.get("remaining_model_tokens")
    max_tokens = resource_budget.get("max_model_tokens")
    if remaining_tokens is not None:
        if remaining_tokens <= 0:
            return "remaining_token_budget_exhausted_inline"
        if low_remaining_budget(
            remaining=remaining_tokens,
            maximum=max_tokens,
            minimum_threshold=100_000,
        ):
            return "remaining_token_budget_pressure_inline"
    return None


def resource_budget_response_limit(resource_budget: Mapping[str, int]) -> int | None:
    remaining = optional_nonnegative_resource_int(
        resource_budget.get("remaining_model_responses")
    )
    if remaining is not None:
        return remaining
    return optional_nonnegative_resource_int(resource_budget.get("max_model_responses"))


def is_budget_critical(resource_budget: Mapping[str, int] | None) -> bool:
    if resource_budget is None:
        return False
    response_limit = resource_budget_response_limit(resource_budget)
    return response_limit is not None and response_limit <= 6


def resource_budget_token_limit(resource_budget: Mapping[str, int]) -> int | None:
    remaining = optional_nonnegative_resource_int(
        resource_budget.get("remaining_model_tokens")
    )
    if remaining is not None:
        return remaining
    return optional_nonnegative_resource_int(resource_budget.get("max_model_tokens"))


def optional_nonnegative_resource_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def estimate_resource_budget_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    config: DeepAgentsPlannerConfig,
) -> float | None:
    if (
        input_tokens is None
        or output_tokens is None
        or config.input_cost_per_1m is None
        or config.output_cost_per_1m is None
    ):
        return None
    return (
        input_tokens * config.input_cost_per_1m
        + output_tokens * config.output_cost_per_1m
    ) / 1_000_000


def low_remaining_budget(
    *,
    remaining: int,
    maximum: int | None,
    minimum_threshold: int,
) -> bool:
    threshold = minimum_threshold
    if maximum is not None and maximum > 0:
        threshold = max(threshold, maximum // 4)
    return remaining <= threshold


def has_validation_fixture_context(selected_context: list[RetrievedContext]) -> bool:
    for context in selected_context:
        normalized_path = context.path.replace("\\", "/").lower()
        terms = {term.lower() for term in context.matched_terms}
        if "validation_fixture" in terms or "reproduction_fixture" in terms:
            return True
        if normalized_path.startswith(("tests/", "testing/")):
            return True
        path_name = normalized_path.rsplit("/", maxsplit=1)[-1]
        if path_name.startswith("test_") or "_repro" in path_name:
            return True
    return False
