from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from patchsmith.deepagents_planner import (
    DeepAgentsPlannerConfig,
    DeepAgentsRepairPlanner,
)
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


class _FakeAgent:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result
        self.invocations: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.invocations.append(payload)
        return self._result


def _context(excerpt: str) -> RetrievedContext:
    return RetrievedContext(
        path="src/calc.py",
        rank=1,
        score=0.9,
        method="keyword",
        matched_terms=["add"],
        excerpt=excerpt,
    )


def test_from_env_reads_configuration() -> None:
    planner = DeepAgentsRepairPlanner.from_env(
        {
            "PATCHSMITH_DEEPAGENTS_MODEL": "gpt-test",
            "PATCHSMITH_DEEPAGENTS_MAX_OUTPUT_TOKENS": "1234",
        }
    )
    assert planner.config.model == "gpt-test"
    assert planner.config.max_output_tokens == 1234


def test_plan_returns_none_without_context() -> None:
    planner = DeepAgentsRepairPlanner(agent_factory=lambda **_kwargs: _FakeAgent({}))
    assert planner.plan(issue_text="bug", retrieved_context=[]) is None
    assert planner.last_model_metadata is None


def test_plan_builds_repair_plan_from_structured_response(tmp_path: Path) -> None:
    source = "def add(a, b):\n    return a - b\n"
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "src/calc.py",
            "old": "return a - b",
            "new": "return a + b",
            "summary": "Fix the addition operator.",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(issue_text="add() subtracts", retrieved_context=[_context(source)])

    assert plan is not None
    assert plan.path == "src/calc.py"
    assert plan.old == "return a - b"
    assert plan.new == "return a + b"
    assert agent.invocations, "agent should have been invoked"
    assert planner.last_model_metadata is not None
    assert planner.last_model_metadata.provider


def test_plan_for_task_uses_explicit_task_repo_path(tmp_path: Path) -> None:
    stale_repo = tmp_path / "stale"
    task_repo = tmp_path / "task"
    (stale_repo / "src").mkdir(parents=True)
    (task_repo / "src").mkdir(parents=True)
    (stale_repo / "src" / "calc.py").write_text(
        "def add(a, b):\n    return 'stale'\n",
        encoding="utf-8",
    )
    task_source = "def add(a, b):\n    return a - b\n"
    (task_repo / "src" / "calc.py").write_text(task_source, encoding="utf-8")

    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "src/calc.py",
            "old": "return a - b",
            "new": "return a + b",
            "summary": "Fix the addition operator.",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(stale_repo)))

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(task_repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(task_source)],
        )
    )

    assert plan is not None
    assert agent.invocations
    files = agent.invocations[0]["files"]
    assert files["/src/calc.py"]["content"] == task_source


def test_plan_returns_none_for_unparseable_result(tmp_path: Path) -> None:
    planner = DeepAgentsRepairPlanner(
        agent_factory=lambda **_kwargs: _FakeAgent({"messages": []}),
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(tmp_path)))
    source = "def add(a, b):\n    return a - b\n"
    assert planner.plan(issue_text="bug", retrieved_context=[_context(source)]) is None
