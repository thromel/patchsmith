from __future__ import annotations

import pytest

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_routing import (
    estimate_resource_budget_cost,
    has_validation_fixture_context,
    is_budget_critical,
    resource_budget_pressure_reason,
    resource_budget_response_limit,
    resource_budget_token_limit,
    subagent_routing_for_task,
)
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


def test_subagent_routing_honors_inline_and_full_modes() -> None:
    context = [_context()]

    inline = subagent_routing_for_task(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="inline"),
        selected_context=context,
        source_hint_manifest=None,
        retry_feedback_manifest=None,
    )
    full = subagent_routing_for_task(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="full"),
        selected_context=context,
        source_hint_manifest=None,
        retry_feedback_manifest=None,
    )

    assert inline.subagents == []
    assert inline.reasons == ["configured_inline"]
    assert [subagent["name"] for subagent in full.subagents] == [
        "failure-localizer",
        "patch-reviewer",
    ]
    assert full.reasons == ["configured_full"]


def test_auto_routing_uses_context_and_budget_signals() -> None:
    rich_context = [
        _context(matched_terms=["reviewed_source_hint"]),
        _context(path="tests/test_calc.py", matched_terms=["validation_fixture"]),
    ]

    enabled = subagent_routing_for_task(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        selected_context=rich_context,
        source_hint_manifest="hints",
        retry_feedback_manifest="retry",
    )
    pressured = subagent_routing_for_task(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        selected_context=rich_context,
        source_hint_manifest="hints",
        retry_feedback_manifest="retry",
        resource_budget={
            "max_model_responses": 12,
            "remaining_model_responses": 3,
        },
    )
    budgeted_first_attempt = subagent_routing_for_task(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        selected_context=rich_context,
        source_hint_manifest="hints",
        retry_feedback_manifest=None,
        resource_budget={"max_model_responses": 12},
    )

    assert [subagent["name"] for subagent in enabled.subagents] == [
        "failure-localizer",
        "patch-reviewer",
    ]
    assert enabled.reasons == [
        "retry_feedback_manifest",
        "source_hint_manifest",
        "validation_fixture_context",
    ]
    assert pressured.subagents == []
    assert pressured.reasons == [
        "remaining_response_budget_pressure_inline",
        "retry_feedback_manifest",
        "source_hint_manifest",
        "validation_fixture_context",
    ]
    assert budgeted_first_attempt.subagents == []
    assert budgeted_first_attempt.reasons == ["budget_constrained_inline"]


def test_resource_budget_limits_and_pressure_are_pure_policy() -> None:
    budget = {
        "max_model_responses": 12,
        "max_model_tokens": 200_000,
        "remaining_model_responses": 3,
        "remaining_model_tokens": 34_279,
    }

    assert resource_budget_response_limit(budget) == 3
    assert resource_budget_token_limit(budget) == 34_279
    assert is_budget_critical(budget) is True
    assert (
        resource_budget_pressure_reason(
            budget,
            retry_feedback_manifest="retry",
        )
        == "remaining_response_budget_pressure_inline"
    )
    assert (
        resource_budget_pressure_reason(
            {"max_model_tokens": 200_000, "remaining_model_tokens": 90_000},
            retry_feedback_manifest="retry",
        )
        == "remaining_token_budget_pressure_inline"
    )
    assert (
        resource_budget_pressure_reason(
            {"remaining_model_responses": 0},
            retry_feedback_manifest="retry",
        )
        == "remaining_response_budget_exhausted_inline"
    )


def test_cost_estimation_and_validation_fixture_detection() -> None:
    config = DeepAgentsPlannerConfig(
        model="gpt-test",
        input_cost_per_1m=0.25,
        output_cost_per_1m=1.00,
    )

    assert (
        estimate_resource_budget_cost(
            input_tokens=1_000_000,
            output_tokens=500_000,
            config=config,
        )
        == 0.75
    )
    assert (
        estimate_resource_budget_cost(
            input_tokens=None,
            output_tokens=500_000,
            config=config,
        )
        is None
    )
    assert has_validation_fixture_context([_context(path="testing/test_repro.py")])
    assert has_validation_fixture_context(
        [_context(path="src/calc.py", matched_terms=["reproduction_fixture"])]
    )
    assert not has_validation_fixture_context([_context(path="src/calc.py")])


def _context(
    *,
    path: str = "src/calc.py",
    matched_terms: list[str] | None = None,
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=0.9,
        method="keyword",
        matched_terms=matched_terms or ["add"],
        excerpt="def add(a, b):\n    return a - b\n",
    )
