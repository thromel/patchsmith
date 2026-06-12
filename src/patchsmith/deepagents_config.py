"""Configuration loading for the native DeepAgents planner."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from patchsmith.model_config import DEFAULT_OPENAI_MODEL, configured_model_pricing

DEFAULT_DEEPAGENTS_MODEL = DEFAULT_OPENAI_MODEL
DEFAULT_DEEPAGENTS_MAX_FILE_CHARS = 20_000
DEEPAGENTS_PROVIDER = "deepagents_openai_chat"


@dataclass(frozen=True)
class DeepAgentsPlannerConfig:
    model: str = DEFAULT_DEEPAGENTS_MODEL
    max_output_tokens: int = 3200
    max_file_chars: int = DEFAULT_DEEPAGENTS_MAX_FILE_CHARS
    reasoning_effort: str | None = None
    use_responses_api: bool = True
    store: bool = False
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
        reasoning_effort=env.get("PATCHSMITH_DEEPAGENTS_REASONING_EFFORT", "").strip() or None,
        use_responses_api=bool_env(
            env,
            "PATCHSMITH_DEEPAGENTS_USE_RESPONSES_API",
            True,
        ),
        store=bool_env(env, "PATCHSMITH_DEEPAGENTS_STORE", False),
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


_bool_env = bool_env
_int_env = int_env
