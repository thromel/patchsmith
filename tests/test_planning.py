import json
import math
import urllib.request

from patchsmith.models import RetrievedContext
from patchsmith.planning import (
    ModelBackedRepairPlanner,
    ModelClientError,
    OpenAIResponsesModelClient,
    StaticResponseModelClient,
)


def test_model_backed_repair_planner_parses_json_plan() -> None:
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """The edit is:
```json
{
  "path": "src/simple_calc.py",
  "old": "return left - right",
  "new": "return left + right",
  "summary": "Fix add."
}
```
"""
        )
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.path == "src/simple_calc.py"
    assert plan.old == "return left - right"
    assert plan.new == "return left + right"


def test_model_backed_repair_planner_rejects_unretrieved_path() -> None:
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            '{"path": "src/secret.py", "old": "x", "new": "y", "summary": "Unsafe target."}'
        )
    )

    plan = planner.plan(
        issue_text="change the file",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is None


def test_model_backed_repair_planner_rejects_path_escape() -> None:
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            '{"path": "../secret.py", "old": "x", "new": "y", "summary": "Unsafe target."}'
        )
    )

    plan = planner.plan(
        issue_text="change the file",
        retrieved_context=[_context("../secret.py")],
    )

    assert plan is None


def test_model_backed_repair_planner_rejects_empty_old_text() -> None:
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            '{"path": "src/simple_calc.py", "old": " ", "new": "y", "summary": "Bad edit."}'
        )
    )

    plan = planner.plan(
        issue_text="change the file",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is None


def test_openai_responses_model_client_builds_request_and_parses_usage() -> None:
    captured: dict[str, object] = {}

    def opener(request: urllib.request.Request, timeout: float) -> bytes:
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return json.dumps(
            {
                "id": "resp_test",
                "status": "completed",
                "model": "gpt-test-2026-06-09",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"path":"src/simple_calc.py"}',
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                },
            }
        ).encode("utf-8")

    client = OpenAIResponsesModelClient(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=12.0,
        input_cost_per_1m=1.0,
        output_cost_per_1m=2.0,
        opener=opener,
    )

    completion = client.complete("Return JSON.")

    payload = captured["payload"]
    assert captured["authorization"] == "Bearer test-key"
    assert captured["timeout"] == 12.0
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-test"
    assert payload["input"] == "Return JSON."
    assert payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert completion.text == '{"path":"src/simple_calc.py"}'
    assert completion.metadata.provider == "openai_responses"
    assert completion.metadata.response_id == "resp_test"
    assert completion.metadata.input_tokens == 100
    assert completion.metadata.output_tokens == 50
    assert completion.metadata.total_tokens == 150
    assert completion.metadata.estimated_cost_usd is not None
    assert math.isclose(completion.metadata.estimated_cost_usd, 0.0002)


def test_openai_responses_model_client_from_env_requires_api_key() -> None:
    try:
        OpenAIResponsesModelClient.from_env({})
    except ModelClientError as error:
        assert "OPENAI_API_KEY" in str(error)
    else:
        raise AssertionError("expected missing OPENAI_API_KEY to fail")


def _context(path: str) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=10.0,
        method="test",
        matched_terms=["simple"],
        excerpt="1: def add(left, right):\n2:     return left - right",
    )
