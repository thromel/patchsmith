import json
import urllib.error
import urllib.request
from io import BytesIO

from patchsmith.cli import main
from patchsmith.model_config import DEFAULT_OPENAI_MODEL
from patchsmith.model_preflight import openai_model_preflight, openai_model_preflight_from_env


def test_openai_model_preflight_reports_available_model() -> None:
    captured: dict[str, object] = {}

    def opener(request: urllib.request.Request, timeout: float) -> bytes:
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return json.dumps(
            {
                "data": [
                    {"id": "gpt-5.4-mini"},
                    {"id": "gpt-5.5"},
                ]
            }
        ).encode("utf-8")

    result = openai_model_preflight(
        api_key="test-key",
        model="gpt-5.4-mini",
        timeout_seconds=12.0,
        opener=opener,
    )

    assert captured["authorization"] == "Bearer test-key"
    assert captured["timeout"] == 12.0
    assert result.status == "available"
    assert result.available is True
    assert result.available_model_count == 2
    assert result.suggestions == []


def test_openai_model_preflight_suggests_nearby_models_when_missing() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> bytes:
        return json.dumps(
            {
                "data": [
                    {"id": "gpt-5.4-mini"},
                    {"id": "gpt-5.4-nano"},
                    {"id": "gpt-5.5"},
                ]
            }
        ).encode("utf-8")

    result = openai_model_preflight(
        api_key="test-key",
        model="gpt-5.5-mini",
        opener=opener,
    )

    assert result.status == "missing_model"
    assert result.available is False
    assert result.suggestions == ["gpt-5.5"]


def test_openai_model_preflight_redacts_http_error_body() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> bytes:
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b'{"error":{"message":"Incorrect API key provided: sk-secret"}}'),
        )

    result = openai_model_preflight(
        api_key="test-key",
        model="gpt-5.4-mini",
        opener=opener,
    )

    assert result.status == "http_error"
    assert result.available is False
    assert result.error == "OpenAI Models API error 401: invalid or unauthorized API key."
    assert "sk-secret" not in result.error


def test_openai_model_preflight_from_env_requires_api_key() -> None:
    result = openai_model_preflight_from_env(environ={})

    assert result.model == DEFAULT_OPENAI_MODEL
    assert result.status == "missing_credentials"
    assert result.available is False
    assert "OPENAI_API_KEY" in (result.error or "")


def test_openai_model_preflight_cli_reports_missing_credentials(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(["openai-model-preflight", "--model", "gpt-5.5-mini", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["model"] == "gpt-5.5-mini"
    assert payload["status"] == "missing_credentials"
