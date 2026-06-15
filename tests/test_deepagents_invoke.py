from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from patchsmith.deepagents_agent import DeepAgentsResourceBudgetExceeded
from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_invoke import invoke_deepagents_plan
from patchsmith.deepagents_manifests import ManifestContents
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
)

pytestmark = pytest.mark.unit


class _FakeAgent:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {}
        self.invocations: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.invocations.append(payload)
        return self.result


class _RaisingAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise self.error


def test_invoke_deepagents_plan_builds_prompt_and_records_usage() -> None:
    agent = _FakeAgent(
        {
            "messages": [
                AIMessage(
                    content="{}",
                    usage_metadata={
                        "input_tokens": 1_000,
                        "output_tokens": 50,
                        "total_tokens": 1_050,
                    },
                    response_metadata={
                        "model_name": "gpt-test-snapshot",
                        "id": "resp_123",
                    },
                )
            ],
            "structured_response": {"path": "src/calc.py"},
        }
    )

    invocation = invoke_deepagents_plan(
        agent=agent,
        issue_text="add returns subtraction",
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        agent_files={"/src/calc.py": {"content": "def add(): pass", "encoding": "utf-8"}},
        config=DeepAgentsPlannerConfig(
            model="gpt-test",
            input_cost_per_1m=0.25,
            output_cost_per_1m=1.00,
        ),
        source_hint_manifest="source hints",
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest=None,
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest="budget",
        preferred_target_paths=["src/calc.py"],
        preferred_target_symbols={"src/calc.py": ["add"]},
        subagents_enabled=False,
        budget_critical=False,
    )

    assert invocation.failed is False
    assert invocation.result["structured_response"] == {"path": "src/calc.py"}
    assert invocation.model_metadata.provider == "deepagents_openai_chat"
    assert invocation.model_metadata.model == "gpt-test-snapshot"
    assert invocation.model_metadata.response_id == "resp_123"
    assert invocation.model_metadata.input_tokens == 1_000
    assert invocation.model_metadata.output_tokens == 50
    assert invocation.model_metadata.estimated_cost_usd == pytest.approx(0.0003)
    payload = agent.invocations[0]
    prompt = payload["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in prompt
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH in prompt
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in prompt
    assert "Preferred patch paths for this constrained run" in prompt
    assert payload["files"]["/src/calc.py"]["encoding"] == "utf-8"


def test_invoke_deepagents_plan_uses_manifest_contents_for_prompt_paths() -> None:
    agent = _FakeAgent(
        {
            "messages": [
                AIMessage(
                    content="{}",
                    usage_metadata={
                        "input_tokens": 100,
                        "output_tokens": 10,
                        "total_tokens": 110,
                    },
                )
            ],
            "structured_response": {"path": "src/calc.py"},
        }
    )

    invocation = invoke_deepagents_plan(
        agent=agent,
        issue_text="add returns subtraction",
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        agent_files={"/src/calc.py": {"content": "def add(): pass", "encoding": "utf-8"}},
        config=DeepAgentsPlannerConfig(model="gpt-test"),
        source_hint_manifest=None,
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest=None,
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest=None,
        manifest_contents=ManifestContents.from_enabled_flags(
            repair_interface=True,
            repo_map=True,
            acceptance_rubric=True,
        ),
        preferred_target_paths=["src/calc.py"],
        preferred_target_symbols={},
        subagents_enabled=False,
        budget_critical=False,
    )

    assert invocation.failed is False
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in prompt
    assert PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in prompt
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in prompt
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH not in prompt


def test_invoke_deepagents_plan_reports_structured_output_failures() -> None:
    invocation = invoke_deepagents_plan(
        agent=_RaisingAgent(
            RuntimeError(
                "Failed to parse structured output for tool 'PatchPlan': "
                "Native structured output expected valid JSON for PatchPlan, but parsing failed."
            )
        ),
        issue_text="bug",
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        agent_files={},
        config=DeepAgentsPlannerConfig(model="gpt-test"),
        source_hint_manifest=None,
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest=None,
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest=None,
        preferred_target_paths=[],
        preferred_target_symbols={},
        subagents_enabled=False,
        budget_critical=False,
    )

    assert invocation.failed is True
    assert invocation.model_metadata.status == "structured_output_parse_failed"
    assert invocation.model_call_dict()["error_type"] == "RuntimeError"
    assert "Failed to parse structured output" in invocation.model_call_dict()[
        "error_summary"
    ]


def test_invoke_deepagents_plan_preserves_resource_budget_usage() -> None:
    invocation = invoke_deepagents_plan(
        agent=_RaisingAgent(
            DeepAgentsResourceBudgetExceeded(
                "DeepAgents model response budget exhausted before next call: 6 >= 6",
                response_count=6,
                input_tokens=96_000,
                output_tokens=2_000,
                total_tokens=98_000,
            )
        ),
        issue_text="bug",
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        agent_files={},
        config=DeepAgentsPlannerConfig(
            model="gpt-test",
            input_cost_per_1m=0.25,
            output_cost_per_1m=1.00,
        ),
        source_hint_manifest=None,
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest=None,
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest=None,
        preferred_target_paths=[],
        preferred_target_symbols={},
        subagents_enabled=False,
        budget_critical=True,
    )

    assert invocation.failed is True
    assert invocation.model_metadata.status == "resource_budget_exceeded"
    assert invocation.model_metadata.response_count == 6
    assert invocation.model_metadata.input_tokens == 96_000
    assert invocation.model_metadata.output_tokens == 2_000
    assert invocation.model_metadata.total_tokens == 98_000
    assert invocation.model_metadata.estimated_cost_usd == pytest.approx(0.026)
