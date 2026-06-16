from __future__ import annotations

import json

import pytest

from patchsmith.cli import main
from patchsmith.model_preflight import ModelPreflightResult

pytestmark = pytest.mark.unit


def test_openai_model_preflight_command_uses_dedicated_cli_module(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import patchsmith.cli.commands.model_preflight as model_preflight_commands

    captured: dict[str, object] = {}

    def fake_preflight(
        *,
        model: str,
        endpoint: str,
        timeout_seconds: float,
    ) -> ModelPreflightResult:
        captured["model"] = model
        captured["endpoint"] = endpoint
        captured["timeout_seconds"] = timeout_seconds
        return ModelPreflightResult(
            provider="openai_models",
            model=model,
            endpoint=endpoint,
            status="available",
            available=True,
            suggestions=("gpt-test-mini",),
        )

    monkeypatch.setattr(
        model_preflight_commands,
        "openai_model_preflight_from_env",
        fake_preflight,
    )

    exit_code = main(
        [
            "openai-model-preflight",
            "--model",
            "gpt-test",
            "--endpoint",
            "https://example.test/models",
            "--timeout-seconds",
            "3.5",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured == {
        "model": "gpt-test",
        "endpoint": "https://example.test/models",
        "timeout_seconds": 3.5,
    }
    assert payload["model"] == "gpt-test"
    assert payload["status"] == "available"
    assert payload["available"] is True
