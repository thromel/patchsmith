from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_INPUT_COST_PER_1M = 0.75
DEFAULT_OPENAI_OUTPUT_COST_PER_1M = 4.50


def budget_limit_label(value: int) -> str:
    """Render a resource-budget limit, treating negatives as unlimited."""
    return "unlimited" if value < 0 else str(value)


@dataclass(frozen=True)
class ModelPricing:
    input_cost_per_1m: float
    output_cost_per_1m: float


OPENAI_MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-5-mini": ModelPricing(input_cost_per_1m=0.25, output_cost_per_1m=2.00),
    "gpt-5.5": ModelPricing(input_cost_per_1m=5.00, output_cost_per_1m=30.00),
    "gpt-5.4": ModelPricing(input_cost_per_1m=2.50, output_cost_per_1m=15.00),
    "gpt-5.4-mini": ModelPricing(
        input_cost_per_1m=DEFAULT_OPENAI_INPUT_COST_PER_1M,
        output_cost_per_1m=DEFAULT_OPENAI_OUTPUT_COST_PER_1M,
    ),
    "gpt-5.4-nano": ModelPricing(input_cost_per_1m=0.20, output_cost_per_1m=1.25),
}

OPENAI_ENCRYPTED_REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def openai_model_pricing(model: str) -> ModelPricing | None:
    model = model.strip()
    if model in OPENAI_MODEL_PRICING:
        return OPENAI_MODEL_PRICING[model]
    for prefix, pricing in sorted(
        OPENAI_MODEL_PRICING.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if model.startswith(f"{prefix}-"):
            return pricing
    return None


def openai_model_supports_encrypted_reasoning(model: str) -> bool:
    """Return whether an OpenAI model id is expected to support reasoning items."""

    normalized = model.strip().lower().rsplit("/", 1)[-1]
    if not normalized:
        return False
    for prefix in OPENAI_ENCRYPTED_REASONING_MODEL_PREFIXES:
        if normalized == prefix or normalized.startswith((f"{prefix}-", f"{prefix}.")):
            return True
    return False


def configured_model_pricing(
    *,
    env: Mapping[str, str],
    model: str,
    input_key: str,
    output_key: str,
    input_fallback_key: str | None = None,
    output_fallback_key: str | None = None,
) -> ModelPricing | None:
    input_value = _optional_float_env(env, input_key, fallback_key=input_fallback_key)
    output_value = _optional_float_env(env, output_key, fallback_key=output_fallback_key)
    if input_value is not None and output_value is not None:
        return ModelPricing(input_cost_per_1m=input_value, output_cost_per_1m=output_value)
    return openai_model_pricing(model)


def _optional_float_env(
    env: Mapping[str, str],
    key: str,
    *,
    fallback_key: str | None = None,
) -> float | None:
    value = env.get(key)
    if (value is None or value == "") and fallback_key is not None:
        value = env.get(fallback_key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
