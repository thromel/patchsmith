"""Model metadata accounting for native DeepAgents planner results."""

from __future__ import annotations

from typing import Any

from patchsmith.planning import ModelCallMetadata


def metadata_from_result(
    *,
    result: Any,
    provider: str,
    configured_model: str,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> ModelCallMetadata:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    model = configured_model
    response_ids: list[str] = []
    response_count = 0
    saw_usage = False
    for message in messages:
        if type(message).__name__ != "AIMessage":
            continue
        response_count += 1
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            saw_usage = True
            input_tokens += int_or_zero(usage.get("input_tokens"))
            output_tokens += int_or_zero(usage.get("output_tokens"))
            total_tokens += int_or_zero(usage.get("total_tokens"))
        response_metadata = getattr(message, "response_metadata", None)
        if isinstance(response_metadata, dict):
            model = str(response_metadata.get("model_name") or model)
            response_id = response_metadata.get("id")
            if isinstance(response_id, str) and response_id:
                response_ids.append(response_id)
    return ModelCallMetadata(
        provider=provider,
        model=model,
        response_id=",".join(response_ids) or None,
        response_count=response_count or None,
        input_tokens=input_tokens if saw_usage else None,
        output_tokens=output_tokens if saw_usage else None,
        total_tokens=total_tokens if saw_usage else None,
        estimated_cost_usd=(
            estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_cost_per_1m=input_cost_per_1m,
                output_cost_per_1m=output_cost_per_1m,
            )
            if saw_usage
            else None
        ),
        status="completed" if messages else "missing_messages",
    )


def estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> float | None:
    if input_cost_per_1m is None or output_cost_per_1m is None:
        return None
    return (input_tokens / 1_000_000 * input_cost_per_1m) + (
        output_tokens / 1_000_000 * output_cost_per_1m
    )


def int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


_metadata_from_result = metadata_from_result
