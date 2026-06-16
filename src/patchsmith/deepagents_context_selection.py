"""Context and target-focus selection for the native DeepAgents planner."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_files import select_contexts_for_deepagents
from patchsmith.models import RetrievedContext
from patchsmith.target_localization import (
    TargetLocalizationCandidate,
    is_revived_historical_control_point,
    target_localization_candidates,
)


@dataclass(frozen=True)
class DeepAgentsContextSelection:
    config: DeepAgentsPlannerConfig
    localization_issue_text: str
    preliminary_target_candidates: list[TargetLocalizationCandidate]
    selected_context: list[RetrievedContext]
    selected_max_context_files: int
    target_candidates: list[TargetLocalizationCandidate]
    preferred_target_paths: list[str]
    preferred_target_reasons: dict[str, tuple[str, ...]]
    preferred_target_symbols: dict[str, list[str]]


def select_deepagents_context(
    *,
    issue_text: str,
    retrieved_context: list[RetrievedContext],
    config: DeepAgentsPlannerConfig,
    retry_feedback_manifest: str | None,
    deprioritized_paths: list[str],
    context_selection_pinned_paths: list[str] | None,
    resource_budget: Mapping[str, int] | None,
) -> DeepAgentsContextSelection:
    localization_issue_text = localization_issue_text_for_retry(
        issue_text,
        retry_feedback_manifest,
    )
    preliminary_target_candidates = target_localization_candidates(
        issue_text=localization_issue_text,
        retrieved_context=retrieved_context,
        historical_paths=deprioritized_paths,
        include_historical=bool(retry_feedback_manifest),
    )
    selected_max_context_files = context_selection_max_files(
        config=config,
        candidates=preliminary_target_candidates,
        retrieved_context=retrieved_context,
    )
    effective_config = config
    if selected_max_context_files != config.max_context_files:
        effective_config = dataclass_replace(
            config,
            max_context_files=selected_max_context_files,
        )
    selected_context = select_contexts_for_deepagents(
        retrieved_context,
        max_context_files=selected_max_context_files,
        preferred_paths=_merge_string_lists(
            context_selection_pinned_paths or [],
            context_selection_preferred_paths(preliminary_target_candidates),
        ),
    )
    target_candidates = target_localization_candidates(
        issue_text=localization_issue_text,
        retrieved_context=selected_context,
        historical_paths=deprioritized_paths,
        include_historical=bool(retry_feedback_manifest),
    )
    preferred_target_paths = preferred_target_paths_for_plan(
        target_candidates,
        config=effective_config,
        retry_feedback_manifest=retry_feedback_manifest,
        deprioritized_paths=deprioritized_paths,
        resource_budget=resource_budget,
    )
    return DeepAgentsContextSelection(
        config=effective_config,
        localization_issue_text=localization_issue_text,
        preliminary_target_candidates=preliminary_target_candidates,
        selected_context=selected_context,
        selected_max_context_files=selected_max_context_files,
        target_candidates=target_candidates,
        preferred_target_paths=preferred_target_paths,
        preferred_target_reasons={
            candidate.path: candidate.reasons for candidate in target_candidates
        },
        preferred_target_symbols=preferred_target_symbols(
            target_candidates,
            preferred_target_paths=preferred_target_paths,
        ),
    )


def localization_issue_text_for_retry(
    issue_text: str,
    retry_feedback_manifest: str | None,
) -> str:
    if not retry_feedback_manifest:
        return issue_text
    return f"{issue_text}\n\n{retry_feedback_manifest}"


def preferred_target_paths(
    candidates: list[TargetLocalizationCandidate],
    *,
    limit: int = 5,
) -> list[str]:
    revived_historical = [
        candidate.path for candidate in candidates if is_revived_historical_control_point(candidate)
    ]
    untried = [candidate.path for candidate in candidates if not candidate.historical]
    preferred: list[str] = []
    for path in [*revived_historical, *untried]:
        if path not in preferred:
            preferred.append(path)
    return preferred[: max(limit, 0)]


def preferred_target_paths_for_plan(
    candidates: list[TargetLocalizationCandidate],
    *,
    config: DeepAgentsPlannerConfig,
    retry_feedback_manifest: str | None,
    deprioritized_paths: list[str],
    resource_budget: Mapping[str, int] | None,
) -> list[str]:
    if deprioritized_paths:
        return preferred_target_paths(candidates)
    if retry_feedback_manifest:
        return []
    if not uses_constrained_first_attempt_target_policy(
        config,
        resource_budget=resource_budget,
    ):
        return []
    return first_attempt_preferred_target_paths(candidates)


def uses_constrained_first_attempt_target_policy(
    config: DeepAgentsPlannerConfig,
    *,
    resource_budget: Mapping[str, int] | None,
) -> bool:
    if resource_budget is not None:
        return True
    if config.context_mode == "span":
        return True
    return config.max_context_files > 0


def first_attempt_preferred_target_paths(
    candidates: list[TargetLocalizationCandidate],
    *,
    limit: int = 1,
) -> list[str]:
    strong_candidates = [
        candidate for candidate in candidates if has_strong_first_attempt_reason(candidate)
    ]
    if not strong_candidates:
        return []
    top_candidate = strong_candidates[0]
    if has_reason(top_candidate, "stale_code_object_control_point"):
        strong_candidates = [
            candidate
            for candidate in strong_candidates
            if has_reason(candidate, "stale_code_object_control_point")
        ]
    preferred: list[str] = []
    for candidate in strong_candidates:
        if candidate.path not in preferred:
            preferred.append(candidate.path)
    return preferred[: max(limit, 0)]


def preferred_target_symbols(
    candidates: list[TargetLocalizationCandidate],
    *,
    preferred_target_paths: Iterable[str],
) -> dict[str, list[str]]:
    preferred_paths = [path.strip().lstrip("/") for path in preferred_target_paths if path.strip()]
    if not preferred_paths:
        return {}
    preferred = set(preferred_paths)
    symbol_focus: dict[str, list[str]] = {}
    for candidate in candidates:
        path = candidate.path.strip().lstrip("/")
        if path not in preferred:
            continue
        symbols = candidate_symbol_focus(candidate)
        if symbols:
            symbol_focus[path] = symbols
    return symbol_focus


def candidate_symbol_focus(candidate: TargetLocalizationCandidate) -> list[str]:
    symbols: list[str] = []
    for reason in candidate.reasons:
        if reason.startswith(("reviewed_symbols:", "symbol_identifiers:")):
            symbols.extend(_reason_values(reason))
    return _ordered_unique_symbols(symbols)


def context_selection_preferred_paths(
    candidates: list[TargetLocalizationCandidate],
) -> list[str]:
    preferred: list[str] = []
    for candidate in candidates:
        if not has_strong_context_selection_reason(candidate):
            continue
        if candidate.path not in preferred:
            preferred.append(candidate.path)
    return preferred


def context_selection_max_files(
    *,
    config: DeepAgentsPlannerConfig,
    candidates: list[TargetLocalizationCandidate],
    retrieved_context: list[RetrievedContext],
) -> int:
    if config.max_context_files > 0:
        return config.max_context_files
    if config.context_selection_mode != "target":
        return config.max_context_files
    if len(retrieved_context) <= 1:
        return config.max_context_files
    if not context_selection_preferred_paths(candidates):
        return config.max_context_files
    return 1


def has_strong_context_selection_reason(candidate: TargetLocalizationCandidate) -> bool:
    strong_prefixes = (
        "symbol_identifiers:",
        "python_import_cache_cues:",
        "stale_path_control_point_cues:",
        "stale_code_object_control_point",
    )
    return any(reason.startswith(strong_prefixes) for reason in candidate.reasons)


def has_strong_first_attempt_reason(candidate: TargetLocalizationCandidate) -> bool:
    if has_strong_context_selection_reason(candidate):
        return True
    reasons = ";".join(candidate.reasons)
    return "reviewed_source_hint" in reasons and (
        "exact_identifiers" in reasons or "matched_terms" in reasons
    )


def has_reason(candidate: TargetLocalizationCandidate, prefix: str) -> bool:
    return any(reason.startswith(prefix) for reason in candidate.reasons)


def _reason_values(reason: str) -> list[str]:
    _, _, values = reason.partition(":")
    return [value.strip() for value in values.split(",") if value.strip()]


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered


def _merge_string_lists(*values: list[str]) -> list[str]:
    merged: list[str] = []
    for items in values:
        for item in items:
            if item not in merged:
                merged.append(item)
    return merged
