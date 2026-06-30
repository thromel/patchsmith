from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field

from patchsmith._http import open_url
from patchsmith.model_config import DEFAULT_OPENAI_MODEL

OPENAI_MODELS_ENDPOINT = "https://api.openai.com/v1/models"
OPENAI_API_KEY_PREFIXES = ("sk-", "sk_proj_", "sk-proj-")


@dataclass(frozen=True)
class ModelPreflightResult:
    provider: str
    model: str
    endpoint: str
    status: str
    available: bool
    available_model_count: int | None = None
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def openai_model_preflight_from_env(
    *,
    model: str | None = None,
    environ: Mapping[str, str] | None = None,
    endpoint: str = OPENAI_MODELS_ENDPOINT,
    timeout_seconds: float = 30.0,
    opener: Callable[[urllib.request.Request, float], bytes] | None = None,
) -> ModelPreflightResult:
    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY", "").strip()
    requested_model = (model or env.get("PATCHSMITH_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL).strip()
    if not api_key:
        return ModelPreflightResult(
            provider="openai_models",
            model=requested_model,
            endpoint=endpoint,
            status="missing_credentials",
            available=False,
            error="OPENAI_API_KEY is required for model availability preflight.",
        )
    return openai_model_preflight(
        api_key=api_key,
        model=requested_model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )


def openai_model_preflight(
    *,
    api_key: str,
    model: str,
    endpoint: str = OPENAI_MODELS_ENDPOINT,
    timeout_seconds: float = 30.0,
    opener: Callable[[urllib.request.Request, float], bytes] | None = None,
) -> ModelPreflightResult:
    api_key = api_key.strip()
    if not api_key:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="missing_credentials",
            available=False,
            error="OPENAI_API_KEY is required for model availability preflight.",
        )
    if _unsafe_header_value(api_key):
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="invalid_credentials",
            available=False,
            error=(
                "OPENAI_API_KEY contains whitespace or non-ASCII characters and cannot "
                "be sent as an HTTP authorization header."
            ),
        )
    if not _looks_like_openai_api_key(api_key):
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="invalid_credentials_format",
            available=False,
            error=(
                "OPENAI_API_KEY does not look like an OpenAI API key. Expected a "
                "`sk-` or `sk-proj-` style value; check that the clipboard or shell "
                "environment did not contain notes, a URL, or another provider key."
            ),
        )
    request = urllib.request.Request(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        response_bytes = (
            opener(request, timeout_seconds) if opener else open_url(request, timeout_seconds)
        )
    except urllib.error.HTTPError as error:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="http_error",
            available=False,
            error=_http_error_message(error),
        )
    except urllib.error.URLError as error:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="request_error",
            available=False,
            error=f"OpenAI Models API request failed: {error.reason}",
        )
    except UnicodeError:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="invalid_credentials",
            available=False,
            error=(
                "OPENAI_API_KEY contains characters that cannot be encoded for the "
                "HTTP authorization header."
            ),
        )

    try:
        response = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="invalid_response",
            available=False,
            error="OpenAI Models API returned invalid JSON.",
        )

    model_ids = _model_ids(response)
    if not model_ids:
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="invalid_response",
            available=False,
            error="OpenAI Models API response did not include model ids.",
        )
    available = model in model_ids
    return ModelPreflightResult(
        provider="openai_models",
        model=model,
        endpoint=endpoint,
        status="available" if available else "missing_model",
        available=available,
        available_model_count=len(model_ids),
        suggestions=[] if available else _suggest_models(model, model_ids),
    )


def _model_ids(response: object) -> list[str]:
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
    return sorted(set(ids))


def _suggest_models(model: str, model_ids: list[str], limit: int = 5) -> list[str]:
    family = model.split("-mini", 1)[0].split("-nano", 1)[0]
    candidates = [item for item in model_ids if item == family or item.startswith(family + "-")]
    if not candidates and model.startswith("gpt-"):
        prefix_parts = model.split("-")[:2]
        prefix = "-".join(prefix_parts)
        candidates = [item for item in model_ids if item.startswith(prefix)]
    return candidates[:limit]


def _http_error_message(error: urllib.error.HTTPError) -> str:
    if error.code == 401:
        return "OpenAI Models API error 401: invalid or unauthorized API key."
    if error.code == 403:
        return "OpenAI Models API error 403: account is not authorized for this request."
    if error.code == 404:
        return "OpenAI Models API error 404: endpoint or model resource was not found."
    return f"OpenAI Models API error {error.code}."


def _unsafe_header_value(value: str) -> bool:
    return any(character.isspace() or ord(character) > 127 for character in value)


def _looks_like_openai_api_key(value: str) -> bool:
    if not value.startswith(OPENAI_API_KEY_PREFIXES):
        return False
    if len(value) < 20:
        return False
    return all(
        character.isascii() and (character.isalnum() or character in {"-", "_"})
        for character in value
    )
