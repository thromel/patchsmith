from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol

from patchsmith.artifacts import dict_or_empty
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, configured_model_pricing
from patchsmith.models import RetrievedContext

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class RepairPlan:
    name: str
    path: str
    old: str
    new: str
    summary: str
    metadata: dict[str, Any] | None = None


class RepairPlanner(Protocol):
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        """Produce one bounded edit plan from issue text and retrieved context."""


@dataclass(frozen=True)
class ModelCallMetadata:
    provider: str
    model: str | None = None
    response_id: str | None = None
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


class ModelBackedRepairPlanner:
    """Prompt/JSON repair planner with retrieval-bound output validation."""

    def __init__(
        self,
        model_client: ModelClient,
        *,
        name: str = "model_json_plan",
        max_contexts: int = 5,
        max_excerpt_chars: int = 1200,
    ) -> None:
        self.model_client = model_client
        self.name = name
        self.max_contexts = max_contexts
        self.max_excerpt_chars = max_excerpt_chars
        self.last_model_metadata: ModelCallMetadata | None = None

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        self.last_model_metadata = None
        prompt = self._build_prompt(issue_text=issue_text, retrieved_context=retrieved_context)
        response = self.model_client.complete(prompt)
        self.last_model_metadata = response.metadata
        payload = _extract_json_object(response.text)
        if payload is None:
            return None
        return _repair_plan_from_payload(
            payload=payload,
            allowed_paths={context.path for context in retrieved_context},
            default_name=self.name,
            model_metadata=response.metadata,
        )

    def _build_prompt(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> str:
        lines = [
            "You are PatchSmith's repair planner.",
            "Return only one JSON object with string fields: path, old, new, summary.",
            "The path must be one of the retrieved source paths.",
            "The old field must be the exact text to replace and must not be empty.",
            "",
            "Issue:",
            issue_text.strip(),
            "",
            "Retrieved context:",
        ]
        for index, context in enumerate(retrieved_context[: self.max_contexts], start=1):
            excerpt = context.excerpt[: self.max_excerpt_chars]
            lines.extend(
                [
                    f"Context {index}",
                    f"Path: {context.path}",
                    f"Method: {context.method}",
                    "Excerpt:",
                    excerpt,
                    "",
                ]
            )
        return "\n".join(lines)


class HeuristicRepairPlanner:
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        issue = issue_text.lower()
        candidate_paths = [context.path for context in retrieved_context]

        for rule in HEURISTIC_RULES:
            if not rule.matches(issue):
                continue
            for path in candidate_paths:
                if not path.startswith("src/"):
                    continue
                return RepairPlan(
                    name=rule.name,
                    path=path,
                    old=rule.old,
                    new=rule.new,
                    summary=f"Apply heuristic rule `{rule.name}` to {path}.",
                )
        return None


@dataclass(frozen=True)
class HeuristicRule:
    name: str
    triggers: tuple[str, ...]
    old: str
    new: str

    def matches(self, issue: str) -> bool:
        return all(trigger in issue for trigger in self.triggers)


HEURISTIC_RULES: tuple[HeuristicRule, ...] = (
    HeuristicRule(
        name="addition_operator",
        triggers=("add", "wrong result"),
        old="return left - right",
        new="return left + right",
    ),
    HeuristicRule(
        name="missing_re_import",
        triggers=("slugify", "nameerror"),
        old="def slugify(value: str) -> str:\n",
        new="import re\n\n\ndef slugify(value: str) -> str:\n",
    ),
    HeuristicRule(
        name="moving_average_exact_window",
        triggers=("moving_average", "exact-window"),
        old="if len(values) <= window:",
        new="if len(values) < window:",
    ),
    HeuristicRule(
        name="integer_timeout_default",
        triggers=("default timeout", "wrong type"),
        old='DEFAULT_TIMEOUT_SECONDS = "30"',
        new="DEFAULT_TIMEOUT_SECONDS = 30",
    ),
    HeuristicRule(
        name="even_validator",
        triggers=("is_even", "opposite"),
        old="return value % 2 == 1",
        new="return value % 2 == 0",
    ),
    HeuristicRule(
        name="username_lowercase",
        triggers=("normalize_username", "uppercase"),
        old='return value.strip().replace(" ", "_")',
        new='return value.strip().lower().replace(" ", "_")',
    ),
    HeuristicRule(
        name="csv_ignore_empty_cells",
        triggers=("parse_csv_line", "empty cells"),
        old='return [part.strip() for part in line.split(",")]',
        new='return [part.strip() for part in line.split(",") if part.strip()]',
    ),
    HeuristicRule(
        name="gregorian_leap_year",
        triggers=("leap-year", "century"),
        old="return year % 4 == 0",
        new="return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)",
    ),
    HeuristicRule(
        name="unique_preserve_order",
        triggers=("unique_preserve_order", "preserving input order"),
        old="return sorted(set(values))",
        new="return list(dict.fromkeys(values))",
    ),
    HeuristicRule(
        name="format_cents_padding",
        triggers=("format_cents", "trailing cents"),
        old='return f"${dollars}.{remainder}"',
        new='return f"${dollars}.{remainder:02d}"',
    ),
)


class SeededFakeRepairModelClient:
    """Offline model double for seeded evals.

    It consumes the same prompt shape as a real model planner and emits the
    JSON contract that `ModelBackedRepairPlanner` validates. This keeps local
    evals deterministic and credential-free while exercising the model seam.
    """

    def complete(self, prompt: str) -> ModelCompletion:
        issue_and_context = prompt.lower()
        path = _first_retrieved_source_path(prompt)
        if path is None:
            return _fake_completion("{}")

        for rule in HEURISTIC_RULES:
            if rule.matches(issue_and_context):
                return _fake_completion(
                    json.dumps(
                        {
                            "name": f"fake_model_{rule.name}",
                            "path": path,
                            "old": rule.old,
                            "new": rule.new,
                            "summary": f"Offline fake model selected {rule.name} for {path}.",
                        }
                    )
                )
        return _fake_completion("{}")


def repair_plan_json_schema() -> dict[str, Any]:
    return {
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


def _extract_json_object(response: str) -> dict[str, Any] | None:
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _repair_plan_from_payload(
    *,
    payload: dict[str, Any],
    allowed_paths: set[str],
    default_name: str,
    model_metadata: ModelCallMetadata | None = None,
) -> RepairPlan | None:
    path = payload.get("path")
    old = payload.get("old")
    new = payload.get("new")
    summary = payload.get("summary")
    name = payload.get("name", default_name)
    if (
        not isinstance(path, str)
        or not isinstance(old, str)
        or not isinstance(new, str)
        or not isinstance(summary, str)
        or not isinstance(name, str)
    ):
        return None

    path = path.strip()
    if not path or not old.strip():
        return None
    if _unsafe_plan_path(path) or path not in allowed_paths:
        return None

    return RepairPlan(
        name=name.strip() or default_name,
        path=path,
        old=old,
        new=new,
        summary=summary.strip() or f"Model planner selected {path}.",
        metadata={
            "model_call": model_metadata.to_dict(),
        }
        if model_metadata
        else None,
    )


def _unsafe_plan_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.startswith("/") or "\\" in path or ".." in parts or path in {"", "."}


def _first_retrieved_source_path(prompt: str) -> str | None:
    paths = re.findall(r"^Path:\s*(\S+)\s*$", prompt, flags=re.MULTILINE)
    for path in paths:
        if path.startswith(("src/", "lib/", "patchsmith/")):
            return path
    return paths[0] if paths else None


def _fake_completion(text: str) -> ModelCompletion:
    return ModelCompletion(
        text=text,
        metadata=ModelCallMetadata(
            provider="offline_fake_model",
            model="seeded_repair_rules",
            estimated_cost_usd=0.0,
            status="completed",
        ),
    )


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
