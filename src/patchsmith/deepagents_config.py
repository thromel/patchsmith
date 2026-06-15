"""Configuration loading for the native DeepAgents planner."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from patchsmith.model_config import (
    DEFAULT_OPENAI_MODEL,
    configured_model_pricing,
    openai_model_supports_encrypted_reasoning,
)

DEFAULT_DEEPAGENTS_MODEL = DEFAULT_OPENAI_MODEL
DEFAULT_DEEPAGENTS_MAX_FILE_CHARS = 20_000
DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES = 0
DEFAULT_DEEPAGENTS_SUBAGENT_MODE = "full"
DEFAULT_DEEPAGENTS_CONTEXT_MODE = "full"
DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE = "retrieved"
DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES = 80
DEEPAGENTS_PROVIDER = "deepagents_openai_chat"


@dataclass(frozen=True)
class DeepAgentsPlannerConfig:
    model: str = DEFAULT_DEEPAGENTS_MODEL
    max_output_tokens: int = 3200
    max_model_responses: int | None = None
    max_model_tokens: int | None = None
    max_file_chars: int = DEFAULT_DEEPAGENTS_MAX_FILE_CHARS
    max_context_files: int = DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES
    context_mode: str = DEFAULT_DEEPAGENTS_CONTEXT_MODE
    context_selection_mode: str = DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE
    context_window_lines: int = DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES
    subagent_mode: str = DEFAULT_DEEPAGENTS_SUBAGENT_MODE
    reasoning_effort: str | None = None
    use_responses_api: bool = True
    store: bool = False
    encrypted_reasoning: bool | None = None
    enable_repo_map: bool = False
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None


def deepagents_config_from_env(
    environ: Mapping[str, str] | None = None,
) -> DeepAgentsPlannerConfig:
    env = os.environ if environ is None else environ
    model = (
        env.get("PATCHSMITH_DEEPAGENTS_MODEL")
        or env.get("PATCHSMITH_OPENAI_MODEL")
        or DEFAULT_DEEPAGENTS_MODEL
    ).strip()
    model = model or DEFAULT_DEEPAGENTS_MODEL
    pricing = configured_model_pricing(
        env=env,
        model=model,
        input_key="PATCHSMITH_DEEPAGENTS_INPUT_COST_PER_1M",
        output_key="PATCHSMITH_DEEPAGENTS_OUTPUT_COST_PER_1M",
        input_fallback_key="PATCHSMITH_OPENAI_INPUT_COST_PER_1M",
        output_fallback_key="PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M",
    )
    return DeepAgentsPlannerConfig(
        model=model,
        max_output_tokens=int_env(env, "PATCHSMITH_DEEPAGENTS_MAX_OUTPUT_TOKENS", 3200),
        max_file_chars=int_env(
            env,
            "PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS",
            DEFAULT_DEEPAGENTS_MAX_FILE_CHARS,
        ),
        max_context_files=int_env(
            env,
            "PATCHSMITH_DEEPAGENTS_MAX_CONTEXT_FILES",
            DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES,
        ),
        context_mode=context_mode_env(env, "PATCHSMITH_DEEPAGENTS_CONTEXT_MODE"),
        context_selection_mode=context_selection_mode_env(
            env,
            "PATCHSMITH_DEEPAGENTS_CONTEXT_SELECTION_MODE",
        ),
        context_window_lines=int_env(
            env,
            "PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES",
            DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES,
        ),
        subagent_mode=subagent_mode_env(env, "PATCHSMITH_DEEPAGENTS_SUBAGENTS"),
        reasoning_effort=env.get("PATCHSMITH_DEEPAGENTS_REASONING_EFFORT", "").strip() or None,
        use_responses_api=bool_env(
            env,
            "PATCHSMITH_DEEPAGENTS_USE_RESPONSES_API",
            True,
        ),
        store=bool_env(env, "PATCHSMITH_DEEPAGENTS_STORE", False),
        encrypted_reasoning=optional_bool_env(
            env,
            "PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING",
        ),
        enable_repo_map=bool_env(env, "PATCHSMITH_DEEPAGENTS_REPO_MAP", False),
        input_cost_per_1m=pricing.input_cost_per_1m if pricing else None,
        output_cost_per_1m=pricing.output_cost_per_1m if pricing else None,
    )


def int_env(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, str(default)))
    except ValueError:
        return default


def bool_env(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def optional_bool_env(env: Mapping[str, str], key: str) -> bool | None:
    value = env.get(key)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"auto", "default"}:
        return None
    return normalized in {"1", "true", "yes", "on", "enabled"}


def deepagents_encrypted_reasoning_enabled(config: DeepAgentsPlannerConfig) -> bool:
    if not config.use_responses_api:
        return False
    if config.encrypted_reasoning is not None:
        return config.encrypted_reasoning
    if config.store:
        return False
    return openai_model_supports_encrypted_reasoning(config.model)


def deepagents_encrypted_reasoning_mode(config: DeepAgentsPlannerConfig) -> str:
    if config.encrypted_reasoning is None:
        return "auto"
    return "enabled" if config.encrypted_reasoning else "disabled"


def subagent_mode_env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip().lower().replace("_", "-")
    if value in {"", "full", "on", "true", "yes", "1"}:
        return "full"
    if value == "auto":
        return "auto"
    if value in {"inline", "off", "none", "false", "no", "0"}:
        return "inline"
    return DEFAULT_DEEPAGENTS_SUBAGENT_MODE


def context_mode_env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip().lower().replace("_", "-")
    if value in {"", "full", "source", "source-file"}:
        return "full"
    if value in {"span", "focused", "focused-span", "source-span"}:
        return "span"
    return DEFAULT_DEEPAGENTS_CONTEXT_MODE


def context_selection_mode_env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip().lower().replace("_", "-")
    if value in {"", "retrieved", "default", "full", "all"}:
        return "retrieved"
    if value in {"target", "target-first", "localized", "focused-target"}:
        return "target"
    return DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE


_bool_env = bool_env
_context_selection_mode_env = context_selection_mode_env
_context_mode_env = context_mode_env
_int_env = int_env
_optional_bool_env = optional_bool_env
_subagent_mode_env = subagent_mode_env
