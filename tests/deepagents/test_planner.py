from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from patchsmith.deepagents_agent import (
    DeepAgentsResourceBudgetExceeded,
    deepagents_model_kwargs,
)
from patchsmith.deepagents_planner import (
    DeepAgentsPlannerConfig,
    DeepAgentsRepairPlanner,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
    PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
    deepagents_agents_md,
    deepagents_patch_quality_policy_md,
    deepagents_patch_review_subagents,
    deepagents_planner_prompt,
    deepagents_repair_skill_md,
    deepagents_system_prompt,
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


class _RaisingAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise self.error


def _context(
    excerpt: str,
    *,
    path: str = "src/calc.py",
    score: float = 0.9,
    matched_terms: list[str] | None = None,
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=score,
        method="keyword",
        matched_terms=matched_terms or ["add"],
        excerpt=excerpt,
    )


def test_from_env_reads_configuration() -> None:
    planner = DeepAgentsRepairPlanner.from_env(
        {
            "PATCHSMITH_DEEPAGENTS_MODEL": "gpt-test",
            "PATCHSMITH_DEEPAGENTS_MAX_OUTPUT_TOKENS": "1234",
            "PATCHSMITH_DEEPAGENTS_REPO_MAP": "1",
            "PATCHSMITH_DEEPAGENTS_SUBAGENTS": "inline",
            "PATCHSMITH_DEEPAGENTS_CONTEXT_MODE": "span",
            "PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES": "24",
        }
    )
    assert planner.config.model == "gpt-test"
    assert planner.config.max_output_tokens == 1234
    assert planner.config.enable_repo_map is True
    assert planner.config.subagent_mode == "inline"
    assert planner.config.context_mode == "span"
    assert planner.config.context_window_lines == 24


def test_from_env_defaults_to_full_subagents_for_unknown_value() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_SUBAGENTS": "surprise"})

    assert planner.config.subagent_mode == "full"


def test_from_env_accepts_auto_subagent_mode() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_SUBAGENTS": "auto"})

    assert planner.config.subagent_mode == "auto"


def test_from_env_allows_encrypted_reasoning_override() -> None:
    disabled = DeepAgentsRepairPlanner.from_env(
        {"PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING": "off"}
    )
    enabled = DeepAgentsRepairPlanner.from_env(
        {"PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING": "enabled"}
    )
    auto = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_ENCRYPTED_REASONING": "auto"})

    assert disabled.config.encrypted_reasoning is False
    assert enabled.config.encrypted_reasoning is True
    assert auto.config.encrypted_reasoning is None


def test_deepagents_model_kwargs_omit_responses_only_options_when_disabled() -> None:
    kwargs = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            max_output_tokens=123,
            reasoning_effort="medium",
            use_responses_api=False,
            store=True,
        )
    )

    assert kwargs == {
        "model": "gpt-test",
        "use_responses_api": False,
        "max_completion_tokens": 123,
        "reasoning_effort": "medium",
    }


def test_deepagents_model_kwargs_include_encrypted_reasoning_for_reasoning_model() -> None:
    kwargs = deepagents_model_kwargs(DeepAgentsPlannerConfig(model="gpt-5.4-nano"))

    assert kwargs["include"] == ["reasoning.encrypted_content"]


def test_deepagents_model_kwargs_omit_encrypted_reasoning_for_non_reasoning_model() -> None:
    kwargs = deepagents_model_kwargs(DeepAgentsPlannerConfig(model="gpt-4.1-mini"))

    assert kwargs["use_responses_api"] is True
    assert kwargs["store"] is False
    assert "include" not in kwargs


def test_deepagents_model_kwargs_allows_encrypted_reasoning_override() -> None:
    forced = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(
            model="gpt-4.1-mini",
            encrypted_reasoning=True,
        )
    )
    disabled = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(
            model="gpt-5.4-nano",
            encrypted_reasoning=False,
        )
    )

    assert forced["include"] == ["reasoning.encrypted_content"]
    assert "include" not in disabled


def test_deepagents_model_kwargs_installs_resource_budget_callback() -> None:
    kwargs = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            max_model_responses=2,
            max_model_tokens=100,
        )
    )

    assert len(kwargs["callbacks"]) == 1


def test_deepagents_resource_budget_callback_blocks_next_model_call() -> None:
    kwargs = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(model="gpt-test", max_model_responses=1)
    )
    callback = kwargs["callbacks"][0]

    callback.on_chat_model_start({}, [])

    with pytest.raises(DeepAgentsResourceBudgetExceeded) as exc_info:
        callback.on_chat_model_start({}, [])
    assert exc_info.value.response_count == 1


def test_deepagents_resource_budget_callback_preserves_usage_on_block() -> None:
    class _Message:
        def __init__(self) -> None:
            self.usage_metadata = {
                "input_tokens": 11,
                "output_tokens": 3,
                "total_tokens": 14,
            }

    class _Generation:
        def __init__(self) -> None:
            self.message = _Message()

    class _Response:
        def __init__(self) -> None:
            self.generations = [[_Generation()]]

    kwargs = deepagents_model_kwargs(
        DeepAgentsPlannerConfig(model="gpt-test", max_model_responses=1)
    )
    callback = kwargs["callbacks"][0]
    callback.on_chat_model_start({}, [])
    callback.on_llm_end(_Response())

    with pytest.raises(DeepAgentsResourceBudgetExceeded) as exc_info:
        callback.on_chat_model_start({}, [])
    assert exc_info.value.response_count == 1
    assert exc_info.value.input_tokens == 11
    assert exc_info.value.output_tokens == 3
    assert exc_info.value.total_tokens == 14


def test_deepagents_prompts_reject_import_only_behavioral_patches() -> None:
    prompt = deepagents_planner_prompt(
        "behavioral failure",
        {"/src/example.py": "src/example.py"},
    )

    for text in [
        deepagents_system_prompt(),
        deepagents_agents_md(),
        deepagents_repair_skill_md(),
        prompt,
    ]:
        assert "import-only patch" in text
        assert "ImportError, ModuleNotFoundError, or NameError" in text
        assert "duplicate imports" in text


def test_deepagents_prompts_include_patch_quality_policy() -> None:
    prompt = deepagents_planner_prompt(
        "moved file keeps stale co_filename",
        {"/src/runner.py": "src/runner.py"},
    )
    policy = deepagents_patch_quality_policy_md()

    for text in [
        deepagents_system_prompt(),
        deepagents_agents_md(),
        deepagents_repair_skill_md(),
        prompt,
        policy,
    ]:
        assert "Patch Quality Policy" in text
        assert "smallest source-behavior change" in text
        assert "broad `except Exception`" in text
        assert "bare `except:`" in text
        assert "catch-and-return" in text
        assert "explicit precondition check" in text
        assert "`__code__`" in text
        assert "`types.CodeType`" in text
        assert "`co_filename`" in text
        assert "`__file__`" in text
        assert "`compile(source.read_text(...), ...)`" in text
        assert "full source-path check" in text
        assert "`importlib.invalidate_caches()`" in text
        assert "helper functions" in text
        assert "not already bound" in text
        assert "syntactically complete" in text
        assert "compound statement header" in text
        assert "identical span" in text
        assert "comment-only" in text
        assert "lower-risk control points are insufficient" in text
        assert "validation scope" in text

    reviewer_prompt = deepagents_patch_review_subagents()[1]["system_prompt"]
    assert "broad exception swallowing" in reviewer_prompt
    assert "bare `except:`" in reviewer_prompt
    assert "catch-and-return fallbacks" in reviewer_prompt
    assert "function `__code__` mutation" in reviewer_prompt
    assert "manual `types.CodeType` rebuilds" in reviewer_prompt
    assert "module `__file__` metadata assignments" in reviewer_prompt
    assert "direct source-text recompilation" in reviewer_prompt
    assert "`compile(source.read_text(...), ...)`" in reviewer_prompt
    assert "naked `importlib.invalidate_caches()`" in reviewer_prompt
    assert "compound statement header" in reviewer_prompt
    assert "comment-only" in reviewer_prompt


def test_deepagents_prompts_reference_acceptance_rubric_when_present() -> None:
    prompt = deepagents_planner_prompt(
        "moved file keeps stale co_filename",
        {"/src/runner.py": "src/runner.py"},
        acceptance_rubric_manifest_path=PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    )

    for text in [
        deepagents_system_prompt(),
        deepagents_agents_md(),
        deepagents_repair_skill_md(),
        prompt,
    ]:
        assert "acceptance-rubric.md" in text
        assert "verifier checklist" in text


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
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
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
    assert plan.metadata is not None
    assert plan.metadata["failure_localization"] == {
        "failure_mechanism": "add() subtracts instead of adding",
        "target_rationale": "src/calc.py contains the returned arithmetic expression",
    }
    assert agent.invocations, "agent should have been invoked"
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in agent.invocations[0]["files"]
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in agent.invocations[0]["files"]
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in agent.invocations[0]["files"]
    interface = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "PatchSmith Repair Interface" in interface
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in interface
    assert "Subagent mode: `full`" in interface
    assert "`src/calc.py` via `/src/calc.py`" in interface
    rubric = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH]["content"]
    assert "PatchSmith Acceptance Rubric" in rubric
    assert "add() subtracts" in rubric
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in prompt
    assert (
        "PatchSmith DeepAgents Repair Contract"
        in agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_MEMORY_PATH]["content"]
    )
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["acceptance_rubric_manifest_path"] == (
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH
    )
    assert contract["planning_policy"]["acceptance_rubric_manifest_read_first"] is True
    assert planner.last_model_metadata is not None
    assert planner.last_model_metadata.provider


def test_plan_inline_subagent_mode_records_inline_contract(tmp_path: Path) -> None:
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
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="inline"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(issue_text="add() subtracts", retrieved_context=[_context(source)])

    assert plan is not None
    assert agent.invocations
    prompt = agent.invocations[0]["messages"][0]["content"]
    files = agent.invocations[0]["files"]
    assert "Subagents are disabled for this run" in prompt
    assert (
        "Subagents are disabled for this run" in files[PATCHSMITH_DEEPAGENTS_MEMORY_PATH]["content"]
    )
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["subagent_mode"] == "inline"
    assert contract["subagents"] == []
    assert (
        contract["planning_policy"]["failure_localizer_subagent_for_validation_fixtures"] is False
    )
    assert contract["planning_policy"]["patch_review_subagent_for_ambiguous_repairs"] is False
    assert contract["planning_policy"]["inline_failure_localization_required"] is True
    assert contract["planning_policy"]["inline_patch_review_required"] is True


def test_plan_auto_subagent_mode_disables_subagents_for_simple_context(
    tmp_path: Path,
) -> None:
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
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(issue_text="add() subtracts", retrieved_context=[_context(source)])

    assert plan is not None
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert "Subagents are disabled for this run" in prompt
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in prompt
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["subagent_mode"] == "auto"
    assert contract["repair_interface_manifest_path"] == PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH
    assert contract["subagents"] == []
    assert contract["subagent_routing"] == {
        "configured_mode": "auto",
        "enabled": False,
        "reasons": ["auto_simple_single_control_point"],
    }
    assert contract["planning_policy"]["repair_interface_manifest_read_first"] is True
    assert contract["planning_policy"]["inline_failure_localization_required"] is True


def test_plan_auto_subagent_mode_enables_subagents_for_reviewed_hints(
    tmp_path: Path,
) -> None:
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
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(
        issue_text="add() subtracts",
        retrieved_context=[
            _context(
                source,
                matched_terms=["reviewed_source_hint", "symbol:add"],
            )
        ],
    )

    assert plan is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert [subagent["name"] for subagent in contract["subagents"]] == [
        "failure-localizer",
        "patch-reviewer",
    ]
    assert contract["subagent_routing"] == {
        "configured_mode": "auto",
        "enabled": True,
        "reasons": ["source_hint_manifest"],
    }
    assert contract["planning_policy"]["failure_localizer_subagent_for_validation_fixtures"] is True


def test_plan_auto_subagent_mode_enables_subagents_for_validation_fixture(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "testing").mkdir(parents=True)
    (repo / "testing" / "test_calc.py").write_text(
        "def test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "testing/test_calc.py",
            "old": "assert add(1, 2) == 3",
            "new": "assert add(1, 2) == 3",
            "summary": "Keep fixture unchanged.",
            "failure_mechanism": "validation fixture documents the failure",
            "target_rationale": "testing/test_calc.py is mounted validation evidence",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="auto"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    planner.plan(
        issue_text="validation fixture fails",
        retrieved_context=[
            _context(
                "def test_add():\n    assert add(1, 2) == 3\n",
                path="testing/test_calc.py",
            )
        ],
    )

    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["subagent_routing"] == {
        "configured_mode": "auto",
        "enabled": True,
        "reasons": ["validation_fixture_context"],
    }


def test_plan_resource_budget_uses_compact_auto_routing_and_manifest(
    tmp_path: Path,
) -> None:
    source = "def add(a, b):\n    return a - b\n"
    test_source = "def test_add():\n    assert add(1, 2) == 3\n"
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(test_source, encoding="utf-8")
    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "src/calc.py",
            "old": "return a - b",
            "new": "return a + b",
            "summary": "Fix the addition operator.",
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    build_configs: list[DeepAgentsPlannerConfig] = []
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **kwargs: build_configs.append(kwargs["config"]) or agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[
                _context(
                    source,
                    matched_terms=["reviewed_source_hint", "symbol:add"],
                ),
                _context(
                    test_source,
                    path="tests/test_calc.py",
                    matched_terms=["validation_fixture"],
                ),
            ],
            runtime_config={
                "resource_budget": {
                    "max_model_responses": 12,
                    "max_model_tokens": 200000,
                }
            },
        )
    )

    assert plan is not None
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["subagent_mode"] == "auto"
    assert contract["subagents"] == []
    assert contract["subagent_routing"] == {
        "configured_mode": "auto",
        "enabled": False,
        "reasons": ["budget_constrained_inline"],
    }
    assert contract["resource_budget"] == {
        "max_model_responses": 12,
        "max_model_tokens": 200000,
    }
    build_config = build_configs[0]
    assert build_config.max_model_responses == 12
    assert build_config.max_model_tokens == 200000
    assert contract["planning_policy"]["resource_budget_read_first"] is True
    repair_interface = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "## Resource Budget" in repair_interface
    assert "Max model responses: `12`" in repair_interface
    assert "Max total model tokens: `200000`" in repair_interface


def test_plan_budget_critical_interface_skips_generic_required_reads(
    tmp_path: Path,
) -> None:
    source = "def _read_pyc(source):\n    return co\n"
    test_source = "def test_moved_file():\n    assert co_filename == __file__\n"
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "src" / "rewrite.py").write_text(source, encoding="utf-8")
    (repo / "testing" / "test_repro.py").write_text(test_source, encoding="utf-8")
    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/rewrite.py",
                "old": "    return co",
                "new": (
                    "    if co.co_filename != str(source):\n        return None\n    return co"
                ),
                "summary": "Reject stale code objects.",
                "failure_mechanism": "cached code object keeps stale co_filename",
                "target_rationale": "_read_pyc returns the cached code object",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[
                _context(
                    source,
                    path="src/rewrite.py",
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:_read_pyc",
                        "co_filename",
                    ],
                ),
                _context(
                    test_source,
                    path="testing/test_repro.py",
                    matched_terms=["validation_fixture"],
                ),
            ],
            runtime_config={
                "resource_budget": {
                    "max_model_responses": 6,
                    "max_model_tokens": 130000,
                }
            },
        )
    )

    assert plan is not None
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["budget_critical_mode"] is True
    assert contract["planning_policy"]["todos_required"] is False
    assert contract["planning_policy"]["source_hint_manifest_read_first"] is False
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert "Budget-critical mode is active" in prompt
    assert "Source hint manifest" not in prompt
    repair_interface = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "## Budget-Critical Mode" in repair_interface
    assert "## Fast Patch Packet" in repair_interface
    assert "def _read_pyc(source):" in repair_interface
    assert "Preferred symbols: `_read_pyc`" in repair_interface
    required_reads = repair_interface.split("## Required Reads", maxsplit=1)[1].split(
        "## Budget-Critical Mode",
        maxsplit=1,
    )[0]
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH not in required_reads
    assert "patchsmith-repair/SKILL.md" not in required_reads
    assert "Read the validation fixture and the first preferred source path/symbol" in (
        repair_interface
    )


def test_plan_retry_resource_budget_pressure_keeps_subagents_inline(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source_path = repo / "src" / "calc.py"
    source = "def add(a, b):\n    return a - b\n"
    source_path.write_text(source, encoding="utf-8")
    test_source = "def test_add():\n    assert add(1, 2) == 3\n"
    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "src/calc.py",
            "old": "return a - b",
            "new": "return a + b",
            "summary": "Fix the addition operator.",
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    build_configs: list[DeepAgentsPlannerConfig] = []
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **kwargs: build_configs.append(kwargs["config"]) or agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[
                _context(
                    source,
                    matched_terms=["reviewed_source_hint", "symbol:add"],
                ),
                _context(
                    test_source,
                    path="tests/test_calc.py",
                    matched_terms=["validation_fixture"],
                ),
            ],
            runtime_config={
                "retry_feedback_brief": "Attempt 1 failed the validation test.",
                "resource_budget": {
                    "max_model_responses": 12,
                    "max_model_tokens": 200000,
                    "used_model_responses": 9,
                    "used_model_tokens": 165721,
                    "remaining_model_responses": 3,
                    "remaining_model_tokens": 34279,
                },
            },
        )
    )

    assert plan is not None
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["subagent_mode"] == "auto"
    assert contract["subagents"] == []
    assert contract["subagent_routing"] == {
        "configured_mode": "auto",
        "enabled": False,
        "reasons": [
            "remaining_response_budget_pressure_inline",
            "retry_feedback_manifest",
            "source_hint_manifest",
            "validation_fixture_context",
        ],
    }
    assert contract["resource_budget"] == {
        "max_model_responses": 12,
        "max_model_tokens": 200000,
        "used_model_responses": 9,
        "used_model_tokens": 165721,
        "remaining_model_responses": 3,
        "remaining_model_tokens": 34279,
    }
    build_config = build_configs[0]
    assert build_config.max_model_responses == 3
    assert build_config.max_model_tokens == 34279
    repair_interface = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "Used model responses before this attempt: `9`" in repair_interface
    assert "Remaining model responses for this attempt: `3`" in repair_interface
    assert "Remaining model tokens for this attempt: `34279`" in repair_interface


def test_plan_span_context_mounts_focused_source_window(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    before = "\n".join(f"def unrelated_{index}():\n    return {index}" for index in range(20))
    target = "def _read_pyc(source):\n    co = load_code(source)\n    return co\n"
    after = "\n".join(f"def later_{index}():\n    return {index}" for index in range(20))
    source = f"{before}\n{target}\n{after}\n"
    (repo / "src" / "rewrite.py").write_text(source, encoding="utf-8")
    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/rewrite.py",
                "old": "    return co",
                "new": "    return None if co.co_filename != str(source) else co",
                "summary": "Reject stale bytecode filenames.",
                "failure_mechanism": "stale bytecode keeps the old source filename",
                "target_rationale": "_read_pyc returns loaded code without checking co_filename",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            context_mode="span",
            context_window_lines=8,
        ),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps stale co_filename from _read_pyc",
            retrieved_context=[
                _context(
                    "def _read_pyc(source):\n    co = load_code(source)\n    return co",
                    path="src/rewrite.py",
                    matched_terms=[
                        "symbol:_read_pyc",
                        "runtime_cache_signal:co_filename",
                    ],
                )
            ],
            runtime_config={},
        )
    )

    assert plan is not None
    assert plan.path == "src/rewrite.py"
    mounted = agent.invocations[0]["files"]["/src/rewrite.py"]["content"]
    assert "def _read_pyc" in mounted
    assert "co_filename" not in mounted
    assert "def unrelated_0" not in mounted
    assert "def later_19" not in mounted
    repair_interface = agent.invocations[0]["files"][PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "Context mode: `span`" in repair_interface
    assert "Context window lines: `8`" in repair_interface
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["context_mode"] == "span"
    assert contract["context_window_lines"] == 8


def test_plan_adds_context_budget_manifest_when_context_is_capped() -> None:
    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/selected.py",
                "old": "return 'old'",
                "new": "return 'new'",
                "summary": "Patch selected mounted file.",
                "failure_mechanism": "selected file returns old sentinel",
                "target_rationale": "src/selected.py is the mounted control point",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            max_context_files=1,
            enable_repo_map=True,
        ),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan(
        issue_text="selected file returns old sentinel",
        retrieved_context=[
            _context(
                "return 'old'",
                path="src/selected.py",
                score=100.0,
                matched_terms=["reviewed_source_hint", "old"],
            ),
            _context(
                "def omitted():\n    return 'old'",
                path="src/omitted.py",
                score=90.0,
                matched_terms=["symbol:omitted", "old"],
            ),
        ],
    )

    assert plan is not None
    assert agent.invocations
    files = agent.invocations[0]["files"]
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in files
    manifest = files[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH]["content"]
    assert "src/selected.py" in manifest
    assert "src/omitted.py" in manifest
    assert "symbol:omitted" in manifest
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in prompt
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["context_budget_manifest_path"] == PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH
    assert contract["planning_policy"]["context_budget_manifest_read_first"] is True


def test_plan_adds_repo_map_manifest_for_retrieved_context() -> None:
    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/selected.py",
                "old": "return 'old'",
                "new": "return 'new'",
                "summary": "Patch selected mounted file.",
                "failure_mechanism": "selected() returns old sentinel",
                "target_rationale": "src/selected.py contains selected()",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            max_context_files=1,
            enable_repo_map=True,
        ),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan(
        issue_text="selected() returns old sentinel",
        retrieved_context=[
            _context(
                "def selected():\n    return 'old'",
                path="src/selected.py",
                score=100.0,
                matched_terms=["symbol:selected", "old"],
            ),
            _context(
                "class Omitted:\n    def helper(self):\n        return 'old'",
                path="src/omitted.py",
                score=90.0,
                matched_terms=["symbol:Omitted", "symbol:helper", "old"],
            ),
        ],
    )

    assert plan is not None
    files = agent.invocations[0]["files"]
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in files
    manifest = files[PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH]["content"]
    assert "PatchSmith Retrieved Repo Map" in manifest
    assert "## Mounted Files" in manifest
    assert "## Omitted Retrieved Files" in manifest
    assert "Status: `mounted`" in manifest
    assert "Status: `omitted`" in manifest
    assert "`src/selected.py`" in manifest
    assert "`src/omitted.py`" in manifest
    assert "`def selected():`" in manifest
    assert "`class Omitted:`" in manifest
    assert "`symbol:helper`" in manifest
    assert PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in prompt
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["repo_map_manifest_path"] == PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH
    assert contract["planning_policy"]["repo_map_manifest_read_first"] is True
    assert (
        PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in (contract["filesystem_policy"]["allowed_read_paths"])
    )


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
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "task repo source contains the returned arithmetic expression",
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


def test_plan_for_task_injects_deprioritized_target_history_manifest(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(a, b):\n    return a - b\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    fake_result = {
        "messages": [],
        "structured_response": {
            "path": "src/calc.py",
            "old": "return a - b",
            "new": "return a + b",
            "summary": "Fix the addition operator.",
            "failure_mechanism": "add() subtracts instead of adding",
            "target_rationale": "src/calc.py contains the returned arithmetic expression",
        },
    }
    agent = _FakeAgent(fake_result)
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(source)],
            runtime_config={
                "deprioritized_context_paths": [
                    "src/old_target.py",
                    "src/another_failed_target.py",
                ],
            },
        )
    )

    assert plan is not None
    files = agent.invocations[0]["files"]
    assert PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH in files
    manifest = files[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH]["content"]
    assert "PatchSmith Target History Manifest" in manifest
    assert "PatchSmith rejects a plan" in manifest
    assert "Preferred Untried Source Targets" in manifest
    assert "Required next-path rule" in manifest
    assert "`src/calc.py`" in manifest
    assert "`src/old_target.py`" in manifest
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH in prompt
    assert "Target history manifest" in prompt
    assert "PatchSmith will reject a listed path" in prompt
    assert "choose one of those paths for this retry" in prompt
    assert "Allowed next patch paths for this retry" in prompt
    assert "- `src/calc.py`" in prompt
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["target_history_manifest_path"] == PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH
    assert contract["planning_policy"]["target_history_manifest_read_first"] is True
    assert contract["patch_selection_policy"] == {
        "patchable_paths": ["src/calc.py"],
        "preferred_symbols": {},
        "historical_paths": ["src/another_failed_target.py", "src/old_target.py"],
        "historical_paths_require_old_span_evidence": True,
        "enforced": True,
    }
    assert (
        PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH
        in contract["filesystem_policy"]["allowed_read_paths"]
    )


def test_plan_for_task_orders_retry_targets_by_localization_score(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    pathlib_dir = repo / "src" / "_pytest"
    rewrite_source = "def _read_pyc(source, pyc):\n    co = marshal.load(fp)\n    return co\n"
    python_source = (
        "def pytest_pycollect_makemodule(module_path):\n    return import_path(module_path)\n"
    )
    pathlib_source = (
        "module_name = module_name_from_path(path)\n"
        "with contextlib.suppress(KeyError):\n"
        "    return sys.modules[module_name]\n"
        "return importlib.import_module(module_name)\n"
    )
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "python.py").write_text(
        python_source,
        encoding="utf-8",
    )
    (pathlib_dir / "pathlib.py").write_text(pathlib_source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/pathlib.py",
                "old": "return sys.modules[module_name]",
                "new": (
                    "existing = sys.modules[module_name]\n    return importlib.reload(existing)"
                ),
                "summary": "Reload stale cached modules.",
                "failure_mechanism": "sys.modules cache reuse preserves stale co_filename",
                "target_rationale": (
                    "src/_pytest/pathlib.py owns the sys.modules cache-return branch "
                    "that decides whether the renamed path is re-imported."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text=(
                "Moving a test module leaves stale co_filename in f_code because "
                "pytest reuses cached import state instead of the renamed path."
            ),
            retrieved_context=[
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                ),
                _context(python_source, path="src/_pytest/python.py"),
                _context(pathlib_source, path="src/_pytest/pathlib.py"),
            ],
            runtime_config={
                "target_history_paths": ["src/_pytest/assertion/rewrite.py"],
            },
        )
    )

    assert plan is not None
    files = agent.invocations[0]["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH]["content"]
    assert manifest.index("`src/_pytest/pathlib.py`") < manifest.index("`src/_pytest/python.py`")
    assert "python_import_cache_cues" in manifest
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert prompt.index("- `src/_pytest/pathlib.py`") < prompt.index("- `src/_pytest/python.py`")
    assert planner.last_plan_metadata is not None
    assert planner.last_plan_metadata["target_localization"][0]["path"] == (
        "src/_pytest/pathlib.py"
    )


def test_plan_for_task_prefers_stale_code_object_target_on_constrained_first_attempt(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    (repo / "src" / "_pytest").mkdir(exist_ok=True)
    rewrite_source = "def _read_pyc(source, pyc):\n    co = marshal.load(fp)\n    return co\n"
    pathlib_source = (
        "def import_path(path, root):\n"
        "    module_name = module_name_from_path(path, root)\n"
        "    with contextlib.suppress(KeyError):\n"
        "        return sys.modules[module_name]\n"
        "    return importlib.import_module(module_name)\n"
    )
    python_source = (
        "def pytest_pycollect_makemodule(module_path):\n    return import_path(module_path)\n"
    )
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "pathlib.py").write_text(
        pathlib_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "python.py").write_text(
        python_source,
        encoding="utf-8",
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/assertion/rewrite.py",
                "old": rewrite_source.strip(),
                "new": (
                    "def _read_pyc(source, pyc):\n"
                    "    co = marshal.load(fp)\n"
                    "    if co.co_filename != str(source):\n"
                    "        return None\n"
                    "    return co"
                ),
                "summary": "Reject cached pyc objects with stale filenames.",
                "failure_mechanism": "cached pyc code object preserves stale co_filename",
                "target_rationale": "_read_pyc returns the cached code object before pytest executes it.",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", context_mode="span"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text=(
                "Moving a test module leaves stale co_filename in f_code because "
                "pytest reuses cached import state instead of the renamed path."
            ),
            retrieved_context=[
                _context(
                    pathlib_source,
                    path="src/_pytest/pathlib.py",
                    score=40.0,
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:import_path",
                        "sys.modules",
                        "import_path",
                    ],
                ),
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                    score=1.0,
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:_read_pyc",
                        "co_filename",
                    ],
                ),
                _context(python_source, path="src/_pytest/python.py", score=20.0),
            ],
        )
    )

    assert plan is not None
    assert planner.last_plan_metadata is not None
    candidates = planner.last_plan_metadata["target_localization"]
    assert candidates[0]["path"] == "src/_pytest/assertion/rewrite.py"
    assert "stale_code_object_control_point" in ";".join(candidates[0]["reasons"])
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["patch_selection_policy"]["patchable_paths"] == [
        "src/_pytest/assertion/rewrite.py",
    ]
    assert contract["patch_selection_policy"]["preferred_symbols"] == {
        "src/_pytest/assertion/rewrite.py": ["_read_pyc"],
    }
    assert contract["patch_selection_policy"]["historical_paths"] == []
    assert contract["patch_selection_policy"]["enforced"] is True
    assert contract["target_history_manifest_path"] is None
    files = agent.invocations[0]["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH]["content"]
    assert "Preferred Next Patch Paths" in manifest
    assert "Preferred symbol focus within ranked paths" in manifest
    assert "`src/_pytest/assertion/rewrite.py`: `_read_pyc`" in manifest
    assert manifest.index("`src/_pytest/assertion/rewrite.py`") < manifest.index(
        "`src/_pytest/pathlib.py` via"
    )
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert "Preferred patch paths for this constrained run" in prompt
    assert "Preferred symbols within those paths" in prompt
    assert "- `src/_pytest/assertion/rewrite.py`" in prompt
    assert "`src/_pytest/assertion/rewrite.py`: `_read_pyc`" in prompt


def test_plan_for_task_rejects_preferred_path_with_wrong_symbol_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    rewrite_source = (
        "def _rewrite_test(fn, config):\n"
        '    co = compile(fn.read_text(), str(fn), "exec")\n'
        "    return fn.stat(), co\n"
        "\n"
        "def _read_pyc(source, pyc):\n"
        "    co = marshal.load(pyc)\n"
        "    return co\n"
    )
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/assertion/rewrite.py",
                "old": (
                    "def _rewrite_test(fn, config):\n"
                    '    co = compile(fn.read_text(), str(fn), "exec")\n'
                    "    return fn.stat(), co"
                ),
                "new": (
                    "def _rewrite_test(fn, config):\n"
                    '    co = compile(fn.read_text(), str(fn), "exec")\n'
                    "    co = co.replace(co_filename=str(fn))\n"
                    "    return fn.stat(), co"
                ),
                "summary": "Rewrite code object filenames after compile.",
                "failure_mechanism": "cached code object keeps stale co_filename",
                "target_rationale": (
                    "_rewrite_test creates the code object; _read_pyc is only a cache read."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", context_mode="span"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="Moving a test module leaves stale co_filename in f_code.",
            retrieved_context=[
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:_read_pyc",
                        "co_filename",
                    ],
                )
            ],
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_symbol_violation"]
    assert violation["path"] == "src/_pytest/assertion/rewrite.py"
    assert violation["preferred_symbols"] == ["_read_pyc"]
    assert "did not enter a preferred symbol" in violation["reason"]


def test_plan_for_task_rejects_no_op_preferred_symbol_patch(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    rewrite_source = "def _read_pyc(source, pyc):\n    co = marshal.load(pyc)\n    return co\n"
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/assertion/rewrite.py",
                "old": rewrite_source.strip(),
                "new": rewrite_source.strip(),
                "summary": "Reject stale pyc files after moved source paths.",
                "failure_mechanism": "cached code object keeps stale co_filename",
                "target_rationale": "_read_pyc controls whether pytest returns cached code.",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", context_mode="span"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="Moving a test module leaves stale co_filename in f_code.",
            retrieved_context=[
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:_read_pyc",
                        "co_filename",
                    ],
                )
            ],
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["no_op_patch_violation"]
    assert violation["path"] == "src/_pytest/assertion/rewrite.py"
    assert violation["old_sha256_12"] == violation["new_sha256_12"]
    assert "identical" in violation["reason"]


def test_plan_for_task_rejects_deprioritized_target_without_new_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(a, b):\n    return a - b\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a + b",
                "summary": "Fix the addition operator.",
                "failure_mechanism": "add() subtracts instead of adding",
                "target_rationale": "src/calc.py contains the returned arithmetic expression",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(source)],
            runtime_config={"deprioritized_context_paths": ["/src/calc.py"]},
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_history_violation"]
    assert violation["path"] == "src/calc.py"
    assert "without naming distinct branch or call-site evidence" in violation["reason"]
    assert "old span" in violation["reason"]
    assert violation["deprioritized_paths"] == ["src/calc.py"]
    assert violation["preferred_target_paths"] == []


def test_plan_for_task_rejected_target_metadata_suggests_untried_sources(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    calc_source = "def add(a, b):\n    return a - b\n"
    fallback_source = "def dispatch_add(a, b):\n    return add(a, b)\n"
    (repo / "src" / "calc.py").write_text(calc_source, encoding="utf-8")
    (repo / "src" / "dispatch.py").write_text(fallback_source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a + b",
                "summary": "Fix the addition operator.",
                "failure_mechanism": "add() subtracts instead of adding",
                "target_rationale": "src/calc.py contains the returned arithmetic expression",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[
                _context(calc_source, path="src/calc.py"),
                _context("def test_add():\n    assert add(1, 2) == 3\n", path="tests/test_calc.py"),
                _context(fallback_source, path="src/dispatch.py"),
            ],
            runtime_config={"target_history_paths": ["src/calc.py"]},
        )
    )

    assert plan is None
    files = agent.invocations[0]["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH]["content"]
    assert "Preferred Untried Source Targets" in manifest
    assert "choose one of these preferred paths" in manifest
    assert "`src/dispatch.py`" in manifest
    assert "`tests/test_calc.py`" not in manifest
    prompt = agent.invocations[0]["messages"][0]["content"]
    assert "Allowed next patch paths for this retry" in prompt
    assert "- `src/dispatch.py`" in prompt
    assert "- `tests/test_calc.py`" not in prompt
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_history_violation"]
    assert violation["preferred_target_paths"] == ["src/dispatch.py"]


def test_plan_for_task_rejects_non_patchable_retry_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    calc_source = "def add(a, b):\n    return a - b\n"
    dispatch_source = "def dispatch_add(a, b):\n    return add(a, b)\n"
    test_source = "def test_add():\n    assert add(1, 2) == 3\n"
    (repo / "src" / "calc.py").write_text(calc_source, encoding="utf-8")
    (repo / "src" / "dispatch.py").write_text(dispatch_source, encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(test_source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "tests/test_calc.py",
                "old": "assert add(1, 2) == 3",
                "new": "assert add(1, 2) == 2",
                "summary": "Change the reproduction instead of the source.",
                "failure_mechanism": "test expectation is too strict",
                "target_rationale": "The test asserts the old expected value.",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[
                _context(calc_source, path="src/calc.py"),
                _context(dispatch_source, path="src/dispatch.py"),
                _context(test_source, path="tests/test_calc.py"),
            ],
            runtime_config={"target_history_paths": ["src/calc.py"]},
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_selection_violation"]
    assert violation["path"] == "tests/test_calc.py"
    assert violation["preferred_target_paths"] == ["src/dispatch.py"]
    assert violation["deprioritized_paths"] == ["src/calc.py"]


def test_plan_for_task_rejects_deprioritized_target_with_generic_distinct_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(total, fee):\n    return total - fee\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return total - fee",
                "new": "return total + fee",
                "summary": "Fix the addition operator.",
                "failure_mechanism": "add() subtracts instead of adding",
                "target_rationale": (
                    "The previous attempt targeted a different guard. This plan targets "
                    "a different branch at line 2 that was not exercised by failed attempts."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(source)],
            runtime_config={"deprioritized_context_paths": ["src/calc.py"]},
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_history_violation"]
    assert violation["path"] == "src/calc.py"
    assert "old span" in violation["reason"]


def test_plan_for_task_allows_deprioritized_target_with_source_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(total, fee):\n    return total - fee\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return total - fee",
                "new": "return total + fee",
                "summary": "Fix the addition operator.",
                "failure_mechanism": "add() subtracts instead of adding",
                "target_rationale": (
                    "The previous attempt targeted a different guard. This plan targets "
                    "a different branch at line 2 where the old span binds `total`; that "
                    "branch was not exercised by failed attempts."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(source)],
            runtime_config={"deprioritized_context_paths": ["src/calc.py"]},
        )
    )

    assert plan is not None
    assert plan.path == "src/calc.py"
    assert planner.last_plan_metadata is not None
    assert "target_history_violation" not in planner.last_plan_metadata


def test_plan_for_task_rejects_live_style_generic_historical_target_rationale(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "with contextlib.suppress(KeyError):\n    return sys.modules[module_name]\n"
    (repo / "src" / "pathlib.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/pathlib.py",
                "old": "with contextlib.suppress(KeyError):\n    return sys.modules[module_name]",
                "new": (
                    "with contextlib.suppress(KeyError):\n"
                    "    existing = sys.modules[module_name]\n"
                    '    if Path(getattr(existing, "__file__", "")).resolve() == path.resolve():\n'
                    "        return existing"
                ),
                "summary": "Reload moved test modules when the cached module points elsewhere.",
                "failure_mechanism": "cached module reuse preserves stale co_filename",
                "target_rationale": (
                    "src/pathlib.py owns the importlib dispatch and cache-return branch "
                    "that decides whether pytest reuses an existing module or recompiles "
                    "from the current path. Prior attempts were downstream of this import "
                    "decision, and this branch directly gates whether a moved file is "
                    "reloaded or an old module is reused."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[_context(source, path="src/pathlib.py")],
            runtime_config={"target_history_paths": ["src/pathlib.py"]},
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_history_violation"]
    assert violation["path"] == "src/pathlib.py"
    assert "old span" in violation["reason"]


def test_plan_for_task_allows_live_style_historical_target_with_old_span_identifier(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "with contextlib.suppress(KeyError):\n    return sys.modules[module_name]\n"
    (repo / "src" / "pathlib.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/pathlib.py",
                "old": "with contextlib.suppress(KeyError):\n    return sys.modules[module_name]",
                "new": (
                    "with contextlib.suppress(KeyError):\n"
                    "    existing = sys.modules[module_name]\n"
                    '    if Path(getattr(existing, "__file__", "")).resolve() == path.resolve():\n'
                    "        return existing"
                ),
                "summary": "Reload moved test modules when the cached module points elsewhere.",
                "failure_mechanism": "cached module reuse preserves stale co_filename",
                "target_rationale": (
                    "The previous attempt targeted a different branch. This plan targets "
                    "the untried sys.modules[module_name] cache-return branch in the old "
                    "span, where pytest decides whether to reuse an existing module or "
                    "recompile from the moved path."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[_context(source, path="src/pathlib.py")],
            runtime_config={"target_history_paths": ["src/pathlib.py"]},
        )
    )

    assert plan is not None
    assert plan.path == "src/pathlib.py"
    assert planner.last_plan_metadata is not None
    assert "target_history_violation" not in planner.last_plan_metadata


def test_plan_for_task_rejects_reused_historical_old_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = (
        "if not isinstance(co, types.CodeType):\n"
        '    trace(f"_read_pyc({source}): not a code object")\n'
        "    return None\n"
        "return co\n"
    )
    old_hash = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()[:12]
    (repo / "src" / "rewrite.py").write_text(source, encoding="utf-8")

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/rewrite.py",
                "old": source,
                "new": source.replace("return co", "return co.replace(co_filename=str(source))"),
                "summary": "Retry the same pyc return branch.",
                "failure_mechanism": "cached pyc code object keeps old co_filename",
                "target_rationale": (
                    "The previous attempt targeted a different branch. This plan targets "
                    "the untried return co branch in the old span."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[_context(source, path="src/rewrite.py")],
            runtime_config={
                "target_history_paths": ["src/rewrite.py"],
                "target_history_old_span_hashes": {"src/rewrite.py": [old_hash]},
            },
        )
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    violation = planner.last_plan_metadata["target_history_violation"]
    assert violation["path"] == "src/rewrite.py"
    assert "reuses an old span" in violation["reason"]
    assert violation["reused_old_span_sha256_12"] == old_hash


def test_plan_for_task_prefers_stale_path_control_point_from_retry_feedback(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    (repo / "src" / "_pytest").mkdir(exist_ok=True)
    rewrite_source = (
        "def _read_pyc(source, pyc):\n"
        "    co = marshal.load(fp)\n"
        "    if co.co_filename != str(source):\n"
        "        return None\n"
        "    return co\n"
    )
    pytester_source = (
        "def copy_example(self, example_path):\n"
        "    result = self.path.joinpath(example_path.name)\n"
        "    shutil.copy(example_path, result)\n"
        "    importlib.invalidate_caches()\n"
        "    return result\n"
    )
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "pytester.py").write_text(
        pytester_source,
        encoding="utf-8",
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/assertion/rewrite.py",
                "old": (
                    "    if co.co_filename != str(source):\n        return None\n    return co"
                ),
                "new": (
                    "    if co.co_filename != str(source):\n"
                    '        trace(f"_read_pyc({source}): stale co_filename {co.co_filename!r}")\n'
                    "        return None\n"
                    "    return co"
                ),
                "summary": "Reject stale pyc code objects before reuse.",
                "failure_mechanism": "cached pyc code object preserves stale co_filename",
                "target_rationale": (
                    "_read_pyc returns the cached code object that directly carries "
                    "the old path, unlike the prior late cache side effect."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[
                _context(pytester_source, path="src/_pytest/pytester.py", score=30.0),
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                    score=1.0,
                    matched_terms=["symbol:_read_pyc", "co_filename"],
                ),
            ],
            runtime_config={
                "retry_feedback_brief": (
                    "# PatchSmith Retry Feedback\n\n"
                    "The previous patch only invalidated importlib caches, but the "
                    "sandbox still reported the stale path mismatch. Move the repair "
                    "to the branch that directly returns the old path."
                ),
                "deprioritized_context_paths": ["src/_pytest/pytester.py"],
            },
        )
    )

    assert plan is not None
    assert plan.path == "src/_pytest/assertion/rewrite.py"
    assert planner.last_plan_metadata is not None
    candidates = planner.last_plan_metadata["target_localization"]
    assert candidates[0]["path"] == "src/_pytest/assertion/rewrite.py"
    assert "stale_path_control_point_cues" in ";".join(candidates[0]["reasons"])
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["patch_selection_policy"]["patchable_paths"][0] == (
        "src/_pytest/assertion/rewrite.py"
    )


def test_plan_for_task_revives_historical_stale_path_control_point(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest" / "assertion").mkdir(parents=True)
    (repo / "src" / "_pytest").mkdir(exist_ok=True)
    rewrite_source = (
        "def _read_pyc(source, pyc):\n"
        "    data = pyc.read_bytes()\n"
        "    co = marshal.load(fp)\n"
        "    if not isinstance(co, types.CodeType):\n"
        "        return None\n"
        "    return co\n"
    )
    pytester_source = (
        "def copy_example(self, example_path):\n"
        "    result = self.path.joinpath(example_path.name)\n"
        "    shutil.copy(example_path, result)\n"
        "    importlib.invalidate_caches()\n"
        "    return result\n"
    )
    (repo / "src" / "_pytest" / "assertion" / "rewrite.py").write_text(
        rewrite_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "pytester.py").write_text(
        pytester_source,
        encoding="utf-8",
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/assertion/rewrite.py",
                "old": rewrite_source.strip(),
                "new": (
                    "def _read_pyc(source, pyc):\n"
                    "    data = pyc.read_bytes()\n"
                    "    co = marshal.load(fp)\n"
                    "    if not isinstance(co, types.CodeType):\n"
                    "        return None\n"
                    "    if co.co_filename != str(source):\n"
                    "        return None\n"
                    "    return co"
                ),
                "summary": "Reject stale pyc code objects before reuse.",
                "failure_mechanism": "cached pyc code object preserves stale co_filename",
                "target_rationale": (
                    "The previous attempt targeted a different branch. This plan targets "
                    "the untried _read_pyc branch where marshal.load returns the cached "
                    "code object, so the old span directly controls whether pytest reuses "
                    "a stale co_filename."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[
                _context(
                    pytester_source,
                    path="src/_pytest/pytester.py",
                    score=30.0,
                ),
                _context(
                    rewrite_source,
                    path="src/_pytest/assertion/rewrite.py",
                    score=1.0,
                    matched_terms=["symbol:_read_pyc", "co_filename"],
                ),
            ],
            runtime_config={
                "retry_feedback_brief": (
                    "# PatchSmith Retry Feedback\n\n"
                    "The sandbox still reported the stale path mismatch. Prefer "
                    "`_read_pyc`, bytecode cache validation, `compile`, or `exec`; "
                    "avoid late call-site side effects like only calling "
                    "`importlib.invalidate_caches()`."
                ),
                "deprioritized_context_paths": [
                    "src/_pytest/assertion/rewrite.py",
                    "src/_pytest/pytester.py",
                ],
            },
        )
    )

    assert plan is not None
    assert plan.path == "src/_pytest/assertion/rewrite.py"
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["patch_selection_policy"]["patchable_paths"][0] == (
        "src/_pytest/assertion/rewrite.py"
    )
    files = agent.invocations[0]["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH]["content"]
    assert "Revived Historical Control Points" in manifest
    assert "`src/_pytest/assertion/rewrite.py`" in manifest
    assert "stale_path_control_point_cues" in manifest
    assert "target_history_violation" not in planner.last_plan_metadata


def test_plan_for_task_allows_revived_historical_pathlib_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "_pytest").mkdir(parents=True)
    pathlib_source = (
        "def import_path(path, root):\n"
        "    module_name = module_name_from_path(path, root)\n"
        "    with contextlib.suppress(KeyError):\n"
        "        return sys.modules[module_name]\n"
        "    return importlib.import_module(module_name)\n"
    )
    config_source = "def parse(args):\n    return args\n"
    (repo / "src" / "_pytest" / "pathlib.py").write_text(
        pathlib_source,
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "config.py").write_text(
        config_source,
        encoding="utf-8",
    )
    old_span = "    with contextlib.suppress(KeyError):\n        return sys.modules[module_name]"

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/_pytest/pathlib.py",
                "old": old_span,
                "new": (
                    "    with contextlib.suppress(KeyError):\n"
                    "        mod = sys.modules[module_name]\n"
                    '        if Path(getattr(mod, "__file__", "")) == path:\n'
                    "            return mod"
                ),
                "summary": "Avoid reusing stale moved modules.",
                "failure_mechanism": "cached module preserves stale code filename",
                "target_rationale": "import_path controls module reuse for moved test files.",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="moved file keeps old co_filename",
            retrieved_context=[
                _context(
                    pathlib_source,
                    path="src/_pytest/pathlib.py",
                    score=1.0,
                    matched_terms=[
                        "reviewed_source_hint",
                        "symbol:import_path",
                        "sys.modules",
                        "module_name_from_path",
                    ],
                ),
                _context(config_source, path="src/_pytest/config.py", score=30.0),
            ],
            runtime_config={
                "retry_feedback_brief": (
                    "# PatchSmith Retry Feedback\n\n"
                    "The sandbox still reported the stale path mismatch. Prefer a "
                    "`sys.modules` cache-return guard or `_read_pyc` control point; "
                    "post-import metadata rewrites are too late."
                ),
                "deprioritized_context_paths": ["src/_pytest/pathlib.py"],
            },
        )
    )

    assert plan is not None
    assert plan.path == "src/_pytest/pathlib.py"
    assert planner.last_plan_metadata is not None
    candidates = planner.last_plan_metadata["target_localization"]
    assert candidates[0]["path"] == "src/_pytest/pathlib.py"
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["patch_selection_policy"]["patchable_paths"][0] == ("src/_pytest/pathlib.py")
    assert "target_history_violation" not in planner.last_plan_metadata


def test_plan_for_task_revives_historical_reviewed_docstring_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "requests").mkdir(parents=True)
    exceptions_source = (
        "class RequestException(IOError):\n"
        "    pass\n\n"
        "class ChunkedEncodingError(RequestException):\n"
        '    """The server declared chunked encoding but sent an invalid chunk."""\n'
    )
    models_source = (
        "def iter_content(self, chunk_size=1, decode_unicode=False):\n"
        "    for chunk in self.raw.stream(chunk_size, decode_content=True):\n"
        "        yield chunk\n"
    )
    (repo / "src" / "requests" / "exceptions.py").write_text(
        exceptions_source,
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "models.py").write_text(
        models_source,
        encoding="utf-8",
    )
    old_span = (
        "class ChunkedEncodingError(RequestException):\n"
        '    """The server declared chunked encoding but sent an invalid chunk."""'
    )

    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/requests/exceptions.py",
                "old": old_span,
                "new": (
                    "class ChunkedEncodingError(RequestException):\n"
                    '    """The server declared chunked encoding but sent an invalid chunk.\n\n'
                    "    This can also surface when a transient connection reset interrupts a\n"
                    "    chunked response.\n"
                    '    """'
                ),
                "summary": "Clarify transient reset ChunkedEncodingError documentation.",
                "failure_mechanism": (
                    "The validation fixture imports ChunkedEncodingError and inspects "
                    "the class docstring."
                ),
                "target_rationale": (
                    "The old span is the ChunkedEncodingError class docstring directly "
                    "read by the reproduction fixture, so this historical path has fresh "
                    "old-span evidence despite the previous failed edit."
                ),
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text=(
                "The reproduction imports ChunkedEncodingError and asserts its __doc__ "
                "mentions transient connection resets."
            ),
            retrieved_context=[
                _context(
                    models_source,
                    path="src/requests/models.py",
                    score=40.0,
                    matched_terms=["chunked", "connection", "transient"],
                ),
                _context(
                    exceptions_source,
                    path="src/requests/exceptions.py",
                    score=1.0,
                    matched_terms=[
                        "reviewed_source_hint",
                        "chunkedencodingerror",
                        "connection",
                    ],
                ),
            ],
            runtime_config={
                "retry_feedback_brief": (
                    "# PatchSmith Retry Feedback\n\n"
                    "The previous patch touched ChunkedEncodingError documentation but "
                    "dropped existing invalid-chunk semantics."
                ),
                "deprioritized_context_paths": ["src/requests/exceptions.py"],
            },
        )
    )

    assert plan is not None
    assert plan.path == "src/requests/exceptions.py"
    assert planner.last_plan_metadata is not None
    candidates = planner.last_plan_metadata["target_localization"]
    assert candidates[0]["path"] == "src/requests/exceptions.py"
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["patch_selection_policy"]["patchable_paths"][0] == (
        "src/requests/exceptions.py"
    )
    files = agent.invocations[0]["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH]["content"]
    assert "Revived Historical Control Points" in manifest
    assert "`src/requests/exceptions.py`" in manifest
    assert "reviewed_source_hint" in manifest
    assert "target_history_violation" not in planner.last_plan_metadata


def test_plan_returns_none_for_unparseable_result(tmp_path: Path) -> None:
    planner = DeepAgentsRepairPlanner(
        agent_factory=lambda **_kwargs: _FakeAgent({"messages": []}),
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(tmp_path)))
    source = "def add(a, b):\n    return a - b\n"
    assert planner.plan(issue_text="bug", retrieved_context=[_context(source)]) is None


def test_plan_records_resource_budget_exceeded_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(a, b):\n    return a - b\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: _RaisingAgent(
            DeepAgentsResourceBudgetExceeded(
                "DeepAgents model response budget exhausted before next call: 6 >= 6",
                response_count=6,
                input_tokens=96000,
                output_tokens=2000,
                total_tokens=122000,
            )
        ),
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=str(repo),
            issue_text="add() subtracts",
            retrieved_context=[_context(source)],
            runtime_config={
                "resource_budget": {
                    "max_model_responses": 6,
                    "max_model_tokens": 130000,
                }
            },
        )
    )

    assert plan is None
    assert planner.last_model_metadata is not None
    assert planner.last_model_metadata.status == "resource_budget_exceeded"
    assert planner.last_model_metadata.response_count == 6
    assert planner.last_model_metadata.input_tokens == 96000
    assert planner.last_model_metadata.output_tokens == 2000
    assert planner.last_model_metadata.total_tokens == 122000


def test_plan_rejects_native_payload_without_failure_localization(tmp_path: Path) -> None:
    source = "def add(a, b):\n    return a - b\n"
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")
    agent = _FakeAgent(
        {
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a + b",
                "summary": "Fix the addition operator.",
            },
        }
    )
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda **_kwargs: agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(issue_text="add() subtracts", retrieved_context=[_context(source)])

    assert plan is None
    assert planner.last_plan_metadata is not None
    assert planner.last_plan_metadata["structured_output_error"] == {
        "missing_required_fields": ["failure_mechanism", "target_rationale"],
    }
