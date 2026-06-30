from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from patchsmith.artifacts import dict_or_empty
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, configured_model_pricing

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class ModelCallMetadata:
    provider: str
    model: str | None = None
    response_id: str | None = None
    response_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "response_id": self.response_id,
            "response_count": self.response_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "status": self.status,
        }


@dataclass(frozen=True)
class ModelCompletion:
    text: str
    metadata: ModelCallMetadata


class ModelClientError(RuntimeError):
    pass


class ModelClient(Protocol):
    def complete(self, prompt: str) -> ModelCompletion:
        """Return a model completion for a repair-planning prompt."""


@dataclass(frozen=True)
class StaticResponseModelClient:
    response: str
    provider: str = "static"

    def complete(self, prompt: str) -> ModelCompletion:
        return ModelCompletion(
            text=self.response,
            metadata=ModelCallMetadata(provider=self.provider, model="static"),
        )


@dataclass(frozen=True)
class OpenAIResponsesModelClient:
    api_key: str
    model: str = DEFAULT_OPENAI_MODEL
    endpoint: str = OPENAI_RESPONSES_ENDPOINT
    timeout_seconds: float = 60.0
    max_output_tokens: int = 1200
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None
    opener: Callable[[urllib.request.Request, float], bytes] | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> OpenAIResponsesModelClient:
        env = os.environ if environ is None else environ
        api_key = env.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ModelClientError(
                "OPENAI_API_KEY is required for planner `openai`; "
                "use `fake_model` for offline evals"
            )
        model = (
            env.get("PATCHSMITH_OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
        )
        pricing = configured_model_pricing(
            env=env,
            model=model,
            input_key="PATCHSMITH_OPENAI_INPUT_COST_PER_1M",
            output_key="PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M",
        )
        return cls(
            api_key=api_key,
            model=model,
            endpoint=env.get("PATCHSMITH_OPENAI_RESPONSES_ENDPOINT", OPENAI_RESPONSES_ENDPOINT),
            timeout_seconds=_float_env(env, "PATCHSMITH_OPENAI_TIMEOUT_SECONDS", 60.0),
            max_output_tokens=_int_env(env, "PATCHSMITH_OPENAI_MAX_OUTPUT_TOKENS", 1200),
            input_cost_per_1m=pricing.input_cost_per_1m if pricing else None,
            output_cost_per_1m=pricing.output_cost_per_1m if pricing else None,
            opener=opener,
        )

    def complete(self, prompt: str) -> ModelCompletion:
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self.max_output_tokens,
            "store": False,
            "text": {"format": repair_plan_json_schema()},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            response_bytes = (
                self.opener(request, self.timeout_seconds)
                if self.opener
                else _open_url(request, self.timeout_seconds)
            )
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise ModelClientError(f"OpenAI Responses API error {error.code}: {body}") from error
        except urllib.error.URLError as error:
            raise ModelClientError(
                f"OpenAI Responses API request failed: {error.reason}"
            ) from error

        try:
            response = json.loads(response_bytes.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ModelClientError("OpenAI Responses API returned invalid JSON") from error

        if isinstance(response, dict) and response.get("error"):
            raise ModelClientError(f"OpenAI Responses API error: {response['error']}")
        if not isinstance(response, dict):
            raise ModelClientError("OpenAI Responses API returned a non-object response")

        text = _extract_openai_output_text(response)
        usage = dict_or_empty(response.get("usage"))
        input_tokens = _int_or_none(usage.get("input_tokens"))
        output_tokens = _int_or_none(usage.get("output_tokens"))
        total_tokens = _int_or_none(usage.get("total_tokens"))
        metadata = ModelCallMetadata(
            provider="openai_responses",
            model=str(response.get("model") or self.model),
            response_id=str(response.get("id")) if response.get("id") else None,
            response_count=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=_estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_cost_per_1m=self.input_cost_per_1m,
                output_cost_per_1m=self.output_cost_per_1m,
            ),
            status=str(response.get("status")) if response.get("status") else None,
        )
        return ModelCompletion(text=text, metadata=metadata)


_REPAIR_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "name": "repair_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "path": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["name", "path", "old", "new", "summary"],
    },
}


def repair_plan_json_schema() -> dict[str, Any]:
    """Return the (immutable, read-only) repair-plan response schema.

    The schema is a module-level constant to avoid rebuilding it on every
    model call; callers must treat the returned dict as read-only.
    """
    return _REPAIR_PLAN_JSON_SCHEMA


def _open_url(request: urllib.request.Request, timeout_seconds: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _extract_openai_output_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    texts: list[str] = []
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                ):
                    texts.append(part["text"])
    if texts:
        return "".join(texts)
    raise ModelClientError("OpenAI Responses API response did not include output text")


def _estimate_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> float | None:
    if (
        input_tokens is None
        or output_tokens is None
        or input_cost_per_1m is None
        or output_cost_per_1m is None
    ):
        return None
    return (input_tokens * input_cost_per_1m + output_tokens * output_cost_per_1m) / 1_000_000


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ModelClientError(f"{key} must be an integer") from error


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    value = env.get(key, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise ModelClientError(f"{key} must be a number") from error
