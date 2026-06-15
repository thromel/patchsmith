import json
import math
import sys
import urllib.request
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from patchsmith.deepagents_planner import (
    DEFAULT_DEEPAGENTS_CONTEXT_MODE,
    DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE,
    DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES,
    DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES,
    DEFAULT_DEEPAGENTS_MAX_FILE_CHARS,
    DeepAgentsPlannerConfig,
    DeepAgentsRepairPlanner,
    _read_only_filesystem_permissions,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
    deepagents_agents_md,
    deepagents_patch_review_subagents,
    deepagents_planner_prompt,
    deepagents_repair_skill_md,
    deepagents_system_prompt,
)
from patchsmith.deepagents_schema import PatchPlan, patch_plan_response_schema
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, openai_model_pricing
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
    assert completion.metadata.response_count == 1
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


def test_openai_responses_model_client_from_env_uses_documented_default_model_pricing() -> None:
    client = OpenAIResponsesModelClient.from_env({"OPENAI_API_KEY": "test-key"})

    assert client.model == DEFAULT_OPENAI_MODEL
    assert client.input_cost_per_1m == 0.75
    assert client.output_cost_per_1m == 4.50


def test_openai_model_pricing_supports_gpt_5_mini_snapshot_ids() -> None:
    pricing = openai_model_pricing("gpt-5-mini-2025-08-07")

    assert pricing is not None
    assert pricing.input_cost_per_1m == 0.25
    assert pricing.output_cost_per_1m == 2.00


def test_openai_responses_model_client_from_env_uses_gpt_5_mini_pricing() -> None:
    client = OpenAIResponsesModelClient.from_env(
        {"OPENAI_API_KEY": "test-key", "PATCHSMITH_OPENAI_MODEL": "gpt-5-mini"}
    )

    assert client.model == "gpt-5-mini"
    assert client.input_cost_per_1m == 0.25
    assert client.output_cost_per_1m == 2.00


def test_openai_responses_model_client_from_env_allows_model_and_pricing_override() -> None:
    client = OpenAIResponsesModelClient.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "PATCHSMITH_OPENAI_MODEL": "custom-model",
            "PATCHSMITH_OPENAI_INPUT_COST_PER_1M": "1.25",
            "PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M": "9.5",
        }
    )

    assert client.model == "custom-model"
    assert client.input_cost_per_1m == 1.25
    assert client.output_cost_per_1m == 9.5


def test_deepagents_repair_planner_from_env_uses_default_model_pricing() -> None:
    planner = DeepAgentsRepairPlanner.from_env({})

    assert planner.config.model == DEFAULT_OPENAI_MODEL
    assert planner.config.subagent_mode == "full"
    assert planner.config.reasoning_effort is None
    assert planner.config.max_file_chars == DEFAULT_DEEPAGENTS_MAX_FILE_CHARS
    assert DEFAULT_DEEPAGENTS_MAX_FILE_CHARS == 20_000
    assert planner.config.max_context_files == DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES
    assert DEFAULT_DEEPAGENTS_MAX_CONTEXT_FILES == 0
    assert planner.config.context_mode == DEFAULT_DEEPAGENTS_CONTEXT_MODE
    assert DEFAULT_DEEPAGENTS_CONTEXT_MODE == "full"
    assert planner.config.context_selection_mode == DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE
    assert DEFAULT_DEEPAGENTS_CONTEXT_SELECTION_MODE == "retrieved"
    assert planner.config.context_window_lines == DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES
    assert DEFAULT_DEEPAGENTS_CONTEXT_WINDOW_LINES == 80
    assert planner.config.input_cost_per_1m == 0.75
    assert planner.config.output_cost_per_1m == 4.50


def test_deepagents_repair_planner_from_env_uses_gpt_5_mini_pricing() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_MODEL": "gpt-5-mini"})

    assert planner.config.model == "gpt-5-mini"
    assert planner.config.input_cost_per_1m == 0.25
    assert planner.config.output_cost_per_1m == 2.00


def test_deepagents_repair_planner_from_env_allows_reasoning_effort_opt_in() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_REASONING_EFFORT": "low"})

    assert planner.config.reasoning_effort == "low"


def test_deepagents_repair_planner_from_env_allows_inline_subagent_mode() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_SUBAGENTS": "none"})

    assert planner.config.subagent_mode == "inline"


def test_deepagents_repair_planner_from_env_allows_auto_subagent_mode() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_SUBAGENTS": "auto"})

    assert planner.config.subagent_mode == "auto"


def test_deepagents_repair_planner_from_env_prefers_deepagents_model_and_costs() -> None:
    planner = DeepAgentsRepairPlanner.from_env(
        {
            "PATCHSMITH_OPENAI_MODEL": "gpt-5.5",
            "PATCHSMITH_DEEPAGENTS_MODEL": "custom-deepagents-model",
            "PATCHSMITH_OPENAI_INPUT_COST_PER_1M": "1.0",
            "PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M": "2.0",
            "PATCHSMITH_DEEPAGENTS_INPUT_COST_PER_1M": "3.0",
            "PATCHSMITH_DEEPAGENTS_OUTPUT_COST_PER_1M": "4.0",
            "PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS": "1234",
            "PATCHSMITH_DEEPAGENTS_MAX_CONTEXT_FILES": "2",
            "PATCHSMITH_DEEPAGENTS_CONTEXT_MODE": "span",
            "PATCHSMITH_DEEPAGENTS_CONTEXT_SELECTION_MODE": "target-first",
            "PATCHSMITH_DEEPAGENTS_CONTEXT_WINDOW_LINES": "32",
        }
    )

    assert planner.config.model == "custom-deepagents-model"
    assert planner.config.input_cost_per_1m == 3.0
    assert planner.config.output_cost_per_1m == 4.0
    assert planner.config.max_file_chars == 1234
    assert planner.config.max_context_files == 2
    assert planner.config.context_mode == "span"
    assert planner.config.context_selection_mode == "target"
    assert planner.config.context_window_lines == 32


def test_deepagents_read_only_filesystem_permissions_allow_provided_reads_only() -> None:
    class FakePermission:
        def __init__(
            self,
            *,
            operations: list[str],
            paths: list[str],
            mode: str = "allow",
        ) -> None:
            self.operations = operations
            self.paths = paths
            self.mode = mode

    permissions = _read_only_filesystem_permissions(
        ["src/simple_calc.py", "/tests/test_simple_calc.py"],
        permission_cls=FakePermission,
    )

    assert len(permissions) == 2
    assert permissions[0].operations == ["read"]
    assert permissions[0].paths == ["/src/simple_calc.py", "/tests/test_simple_calc.py"]
    assert permissions[0].mode == "allow"
    assert permissions[1].operations == ["read", "write"]
    assert permissions[1].paths == ["/**"]
    assert permissions[1].mode == "deny"


def test_deepagents_prompts_keep_planning_and_bounded_output_contract() -> None:
    system_prompt = deepagents_system_prompt()
    planner_prompt = deepagents_planner_prompt(
        "Fix the bug",
        {"/src/simple_calc.py": "src/simple_calc.py"},
    )
    subagents = deepagents_patch_review_subagents()

    assert "create and update todos" in system_prompt
    assert "validation fixture files" in system_prompt
    assert "failure-localizer" in system_prompt
    assert "target-history manifest" in system_prompt
    assert "failure_mechanism" in system_prompt
    assert "target_rationale" in system_prompt
    assert "exact text span" in system_prompt
    assert "Copy the old span verbatim" in system_prompt
    assert "receiver qualifiers such as `self.`" in system_prompt
    assert "invent in-scope variable names" in system_prompt
    assert "PatchSmith DeepAgents Repair Contract" in deepagents_agents_md()
    assert "failure-localizer" in deepagents_agents_md()
    assert "patch-reviewer" in deepagents_agents_md()
    assert "target-history.md" in deepagents_agents_md()
    repair_skill = deepagents_repair_skill_md()
    assert "name: patchsmith-repair" in repair_skill
    assert "bounded PatchSmith patch plan" in repair_skill
    assert "Read validation fixture files first" in repair_skill
    assert "copy the `old` span exactly" in repair_skill
    assert "do not invent variables" in repair_skill
    assert "target-history.md" in repair_skill
    assert "src/simple_calc.py" in planner_prompt
    assert "copy the old span exactly" in planner_prompt
    assert [subagent["name"] for subagent in subagents] == [
        "failure-localizer",
        "patch-reviewer",
    ]


def test_deepagents_repair_skill_matches_installed_metadata_parser() -> None:
    skills_module = pytest.importorskip("deepagents.middleware.skills")

    metadata = skills_module._parse_skill_metadata(
        deepagents_repair_skill_md(),
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        "patchsmith-repair",
    )

    assert metadata is not None
    assert metadata["name"] == "patchsmith-repair"
    assert metadata["path"] == PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH
    assert metadata["compatibility"] == "deepagents>=0.6.8"


def test_deepagents_patch_plan_schema_is_explicit_and_required() -> None:
    schema = patch_plan_response_schema()

    assert schema == {
        "name": "PatchPlan",
        "fields": [
            "path",
            "old",
            "new",
            "summary",
            "failure_mechanism",
            "target_rationale",
        ],
        "all_fields_required": True,
    }
    assert set(PatchPlan.model_fields) == {
        "path",
        "old",
        "new",
        "summary",
        "failure_mechanism",
        "target_rationale",
    }


def test_deepagents_repair_planner_builds_agent_with_read_only_permissions(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    def fake_create_deep_agent(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    class FakeFilesystemPermission:
        def __init__(
            self,
            *,
            operations: list[str],
            paths: list[str],
            mode: str = "allow",
        ) -> None:
            self.operations = operations
            self.paths = paths
            self.mode = mode

    class FakeStateBackend:
        pass

    deepagents_module = ModuleType("deepagents")
    deepagents_module.create_deep_agent = fake_create_deep_agent
    deepagents_module.FilesystemPermission = FakeFilesystemPermission
    backends_module = ModuleType("deepagents.backends")
    backends_module.StateBackend = FakeStateBackend
    langchain_openai_module = ModuleType("langchain_openai")
    langchain_openai_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "deepagents", deepagents_module)
    monkeypatch.setitem(sys.modules, "deepagents.backends", backends_module)
    monkeypatch.setitem(sys.modules, "langchain_openai", langchain_openai_module)

    planner = DeepAgentsRepairPlanner(DeepAgentsPlannerConfig(model="gpt-5.4-mini"))

    planner._build_agent(
        files={
            "/src/simple_calc.py": {"content": "x"},
            PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH: {"content": "hint"},
            PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH: {"content": "budget"},
        }
    )

    model = captured["model"]
    assert model.kwargs["use_responses_api"] is True
    assert model.kwargs["store"] is False
    assert model.kwargs["include"] == ["reasoning.encrypted_content"]
    assert captured["tools"] == []
    assert captured["skills"] == [PATCHSMITH_DEEPAGENTS_SKILL_DIR]
    assert captured["memory"] == [PATCHSMITH_DEEPAGENTS_MEMORY_PATH]
    assert isinstance(captured["backend"], FakeStateBackend)
    permissions = captured["permissions"]
    assert len(permissions) == 2
    assert permissions[0].operations == ["read"]
    assert permissions[0].paths == [
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
        "/src/simple_calc.py",
    ]
    assert permissions[0].mode == "allow"
    assert permissions[1].operations == ["read", "write"]
    assert permissions[1].paths == ["/**"]
    assert permissions[1].mode == "deny"
    subagents = captured["subagents"]
    assert [subagent["name"] for subagent in subagents] == [
        "failure-localizer",
        "patch-reviewer",
    ]
    assert captured["response_format"] is PatchPlan


def test_deepagents_repair_planner_builds_agent_with_explicit_empty_subagents(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    def fake_create_deep_agent(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    class FakeFilesystemPermission:
        def __init__(
            self,
            *,
            operations: list[str],
            paths: list[str],
            mode: str = "allow",
        ) -> None:
            self.operations = operations
            self.paths = paths
            self.mode = mode

    class FakeStateBackend:
        pass

    deepagents_module = ModuleType("deepagents")
    deepagents_module.create_deep_agent = fake_create_deep_agent
    deepagents_module.FilesystemPermission = FakeFilesystemPermission
    backends_module = ModuleType("deepagents.backends")
    backends_module.StateBackend = FakeStateBackend
    langchain_openai_module = ModuleType("langchain_openai")
    langchain_openai_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "deepagents", deepagents_module)
    monkeypatch.setitem(sys.modules, "deepagents.backends", backends_module)
    monkeypatch.setitem(sys.modules, "langchain_openai", langchain_openai_module)

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", subagent_mode="inline")
    )

    planner._build_agent(
        files={"/src/simple_calc.py": {"content": "x"}},
        subagents=[],
    )

    assert captured["subagents"] == []
    assert "Subagents are disabled for this calibration run" in captured["system_prompt"]


def test_deepagents_repair_planner_maps_virtual_path_and_usage_metadata() -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py","old":"return left - right",'
                            '"new":"return left + right","summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"src/simple_calc.py contains the selected return"}'
                        ),
                        usage_metadata={
                            "input_tokens": 100,
                            "output_tokens": 25,
                            "total_tokens": 125,
                        },
                        response_metadata={
                            "model_name": "gpt-test",
                            "id": "chatcmpl_test",
                        },
                    )
                ],
                "files": {},
            }

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            input_cost_per_1m=1.0,
            output_cost_per_1m=2.0,
        ),
        agent_factory=lambda config: fake_agent,
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.path == "src/simple_calc.py"
    assert plan.old == "return left - right"
    assert plan.new == "return left + right"
    assert plan.metadata is not None
    model_call = plan.metadata["model_call"]
    assert model_call["provider"] == "deepagents_openai_chat"
    assert model_call["model"] == "gpt-test"
    assert model_call["response_id"] == "chatcmpl_test"
    assert model_call["response_count"] == 1
    assert math.isclose(model_call["estimated_cost_usd"], 0.00015)
    assert plan.metadata["failure_localization"] == {
        "failure_mechanism": "add returns subtraction result",
        "target_rationale": "src/simple_calc.py contains the selected return",
    }
    contract = plan.metadata["deepagents_contract"]
    assert contract["framework"] == "deepagents"
    assert contract["mode"] == "custom_agent_factory"
    assert contract["model"] == "gpt-test"
    assert contract["use_responses_api"] is True
    assert contract["store"] is False
    assert contract["encrypted_reasoning"] == {
        "mode": "auto",
        "enabled": False,
        "include": [],
    }
    assert contract["memory_paths"] == [PATCHSMITH_DEEPAGENTS_MEMORY_PATH]
    assert contract["skill_sources"] == [PATCHSMITH_DEEPAGENTS_SKILL_DIR]
    assert contract["skill_paths"] == [PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]
    assert contract["repair_interface_manifest_path"] == PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH
    assert contract["acceptance_rubric_manifest_path"] == (
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH
    )
    assert contract["contextual_verifier"] == {
        "type": "acceptance_rubric",
        "manifest_path": PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        "required": True,
    }
    assert contract["virtual_file_paths"] == ["/src/simple_calc.py"]
    assert contract["filesystem_policy"]["allowed_read_paths"] == [
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        "/src/simple_calc.py",
    ]
    assert [subagent["name"] for subagent in contract["subagents"]] == [
        "failure-localizer",
        "patch-reviewer",
    ]
    assert contract["subagent_routing"] == {
        "configured_mode": "full",
        "enabled": True,
        "reasons": ["configured_full"],
    }
    assert contract["response_format"] == "PatchPlan"
    assert contract["response_schema"] == patch_plan_response_schema()
    assert contract["planning_policy"]["todos_required"] is True
    assert contract["planning_policy"]["repair_interface_manifest_read_first"] is True
    assert contract["planning_policy"]["acceptance_rubric_manifest_read_first"] is True
    assert contract["planning_policy"]["validation_fixtures_read_first"] is True
    assert contract["planning_policy"]["repo_map_manifest_read_first"] is False
    assert contract["planning_policy"]["failure_localizer_subagent_for_validation_fixtures"] is True
    assert contract["planning_policy"]["patch_quality_policy_read_first"] is True
    assert contract["patch_quality_policy"] == {
        "prefer_minimal_control_point_patch": True,
        "avoid_broad_exception_swallowing": True,
        "avoid_bare_except_swallowing": True,
        "avoid_silent_fallbacks": True,
        "prefer_explicit_guards_over_catch_and_fallback": True,
        "avoid_runtime_code_object_mutation": True,
        "avoid_manual_code_type_rebuild": True,
        "avoid_code_object_metadata_rewrite": True,
        "avoid_module_file_metadata_rewrite": True,
        "avoid_naked_import_cache_invalidation": True,
        "avoid_unbound_helper_names": True,
        "reject_no_op_replacements": True,
        "require_complete_python_replacement_spans": True,
        "avoid_test_fixture_doc_targets": True,
        "large_span_expansions_require_rationale": True,
        "high_risk_patterns_require_rationale": True,
        "enforced_as_quality_warning": True,
    }
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/simple_calc.py" in files
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in files
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in files
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in files
    assert PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH in files
    assert "PatchSmith Repair Interface" in files[PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH][
        "content"
    ]
    assert "PatchSmith Acceptance Rubric" in files[
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH
    ]["content"]
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in files[
        PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH
    ]["content"]
    assert "name: patchsmith-repair" in files[PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]["content"]
    assert files["/src/simple_calc.py"]["encoding"] == "utf-8"
    assert files["/src/simple_calc.py"]["created_at"]
    assert files["/src/simple_calc.py"]["modified_at"]


def test_deepagents_repair_planner_honors_runtime_model_override() -> None:
    captured: dict[str, DeepAgentsPlannerConfig] = {}

    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py","old":"return left - right",'
                            '"new":"return left + right","summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"src/simple_calc.py contains the selected return"}'
                        ),
                        usage_metadata={
                            "input_tokens": 100,
                            "output_tokens": 25,
                            "total_tokens": 125,
                        },
                    )
                ],
                "files": {},
            }

    def fake_agent_factory(*, config: DeepAgentsPlannerConfig) -> FakeAgent:
        captured["config"] = config
        return FakeAgent()

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-5.5",
            input_cost_per_1m=5.0,
            output_cost_per_1m=30.0,
        ),
        agent_factory=fake_agent_factory,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            issue_text="add returns the wrong result",
            retrieved_context=[_context("src/simple_calc.py")],
            runtime_config={"model": "gpt-5-mini"},
        )
    )

    assert plan is not None
    assert captured["config"].model == "gpt-5-mini"
    assert captured["config"].input_cost_per_1m == 0.25
    assert captured["config"].output_cost_per_1m == 2.0
    assert planner.last_model_metadata is not None
    assert planner.last_model_metadata.model == "gpt-5-mini"
    assert math.isclose(planner.last_model_metadata.estimated_cost_usd or 0.0, 0.000075)


def test_deepagents_repair_planner_mounts_scoped_repo_instructions(
    tmp_path: Path,
) -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/pkg/simple_calc.py",
                    "old": "return left - right",
                    "new": "return left + right",
                    "summary": "Fix add.",
                    "failure_mechanism": "add returns subtraction result",
                    "target_rationale": "src/pkg/simple_calc.py contains the selected return",
                },
            }

    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "AGENTS.md").write_text(
        "Root rule: keep patches minimal.",
        encoding="utf-8",
    )
    (repo / "src" / "pkg" / "AGENTS.md").write_text(
        "Package rule: preserve public API names.",
        encoding="utf-8",
    )

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: fake_agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/pkg/simple_calc.py")],
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    prompt = fake_agent.input_payload["messages"][0]["content"]
    assert "Scoped repository instructions" in prompt
    assert PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH in prompt
    files = fake_agent.input_payload["files"]
    assert PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH in files
    manifest = files[PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH]["content"]
    assert "Root rule: keep patches minimal." in manifest
    assert "Package rule: preserve public API names." in manifest
    repair_interface = files[PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH]["content"]
    assert PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH in repair_interface
    contract = plan.metadata["deepagents_contract"]
    assert (
        contract["repo_instructions_manifest_path"]
        == PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH
    )
    assert contract["repository_instructions"] == {
        "type": "scoped_repo_instructions",
        "manifest_path": PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
        "required": True,
    }
    assert (
        contract["planning_policy"]["repo_instructions_manifest_read_first"]
        is True
    )
    assert (
        PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH
        in contract["filesystem_policy"]["allowed_read_paths"]
    )


def test_deepagents_repair_planner_caps_large_files_to_focused_excerpt(
    tmp_path: Path,
) -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/large.py",'
                            '"old":"def target():\\n    return left - right",'
                            '"new":"def target():\\n    return left + right",'
                            '"summary":"Fix focused target.",'
                            '"failure_mechanism":"target subtracts instead of adds",'
                            '"target_rationale":"src/large.py target contains the failing return"}'
                        )
                    )
                ],
            }

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "large.py").write_text(
        "\n".join(
            [
                "HEADER = True",
                *[f"FILLER_{index} = {index}" for index in range(200)],
                "def target():",
                "    return left - right",
            ]
        ),
        encoding="utf-8",
    )
    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_file_chars=80),
        agent_factory=lambda config: fake_agent,
    )
    planner.prepare_task(SimpleNamespace(repo_path=str(repo)))

    plan = planner.plan(
        issue_text="target returns the wrong result",
        retrieved_context=[
            RetrievedContext(
                path="src/large.py",
                rank=1,
                score=10.0,
                method="native_hybrid",
                matched_terms=["target"],
                excerpt="202: def target():\n203:     return left - right",
            )
        ],
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    content = files["/src/large.py"]["content"]
    assert "def target()" in content
    assert "HEADER = True" not in content


def test_deepagents_repair_planner_caps_context_files_and_preserves_reviewed_hints() -> None:
    class FakeAgent:
        input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/hinted.py",
                    "old": "return 'old'",
                    "new": "return 'new'",
                    "summary": "Patch reviewed hint.",
                    "failure_mechanism": "hinted target returns old sentinel",
                    "target_rationale": "src/hinted.py controls the failing sentinel",
                },
            }

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_context_files=2),
        agent_factory=lambda config: fake_agent,
    )

    plan = planner.plan(
        issue_text="source hint controls the failure",
        retrieved_context=[
            RetrievedContext(
                path="src/top_ranked.py",
                rank=1,
                score=100.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'top'",
            ),
            RetrievedContext(
                path="src/middle.py",
                rank=2,
                score=90.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'middle'",
            ),
            RetrievedContext(
                path="src/hinted.py",
                rank=99,
                score=1.0,
                method="test",
                matched_terms=["reviewed_source_hint", "active_path"],
                excerpt="return 'old'",
            ),
        ],
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/top_ranked.py" in files
    assert "/src/hinted.py" in files
    assert "/src/middle.py" not in files
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in files
    budget_manifest = files[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH]["content"]
    assert "Omitted Retrieved Files" in budget_manifest
    assert "src/middle.py" in budget_manifest
    assert "src/top_ranked.py" in budget_manifest
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["max_context_files"] == 2
    assert contract["context_budget_manifest_path"] == PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH
    assert contract["planning_policy"]["context_budget_manifest_read_first"] is True
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in (
        contract["filesystem_policy"]["allowed_read_paths"]
    )
    assert contract["virtual_file_count"] == 2
    assert contract["virtual_file_paths"] == [
        "/src/hinted.py",
        "/src/top_ranked.py",
    ]


def test_deepagents_repair_planner_rejects_unmounted_context_path_after_cap() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "structured_response": {
                    "path": "src/middle.py",
                    "old": "return 'middle'",
                    "new": "return 'patched'",
                    "summary": "Patch unmounted context.",
                    "failure_mechanism": "middle target returns old sentinel",
                    "target_rationale": "src/middle.py controls the failing sentinel",
                },
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_context_files=1),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="patch middle",
        retrieved_context=[
            RetrievedContext(
                path="src/top_ranked.py",
                rank=1,
                score=100.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'top'",
            ),
            RetrievedContext(
                path="src/middle.py",
                rank=2,
                score=90.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'middle'",
            ),
        ],
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    assert planner.last_plan_metadata["deepagents_contract"]["virtual_file_paths"] == [
        "/src/top_ranked.py"
    ]


def test_deepagents_repair_planner_honors_runtime_context_cap_for_retry() -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/top_ranked.py",
                    "old": "return 'top'",
                    "new": "return 'patched'",
                    "summary": "Patch selected mounted retry context.",
                    "failure_mechanism": "top target returns old sentinel",
                    "target_rationale": "src/top_ranked.py controls the failing sentinel",
                },
            }

    fake_agent = FakeAgent()
    captured_configs: list[DeepAgentsPlannerConfig] = []
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_context_files=0),
        agent_factory=lambda config: captured_configs.append(config) or fake_agent,
    )
    task = SimpleNamespace(
        issue_text="retry after feedback",
        repo_path=None,
        runtime_config={
            "retry_feedback_brief": "# PatchSmith Retry Feedback\n\nUse top target.",
            "max_context_files": 1,
        },
        retrieved_context=[
            RetrievedContext(
                path="src/top_ranked.py",
                rank=1,
                score=100.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'top'",
            ),
            RetrievedContext(
                path="src/extra.py",
                rank=2,
                score=90.0,
                method="test",
                matched_terms=["ranked"],
                excerpt="return 'extra'",
            ),
        ],
    )

    plan = planner.plan_for_task(task=task)

    assert plan is not None
    assert captured_configs[0].max_context_files == 1
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/top_ranked.py" in files
    assert "/src/extra.py" not in files
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in files
    budget_manifest = files[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH]["content"]
    assert "src/extra.py" in budget_manifest
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["max_context_files"] == 1
    assert contract["virtual_file_count"] == 1
    assert contract["context_budget_manifest_path"] == PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH
    assert contract["planning_policy"]["context_budget_manifest_read_first"] is True


def test_deepagents_context_cap_preserves_localized_target_and_fixture() -> None:
    class FakeAgent:
        input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/_pytest/assertion/rewrite.py",
                    "old": (
                        "def _read_pyc(source, pyc):\n"
                        "    co = marshal.load(pyc)\n"
                        "    return co"
                    ),
                    "new": (
                        "def _read_pyc(source, pyc):\n"
                        "    co = marshal.load(pyc)\n"
                        "    if co.co_filename != str(source):\n"
                        "        return None\n"
                        "    return co"
                    ),
                    "summary": "Reject stale rewritten bytecode for moved files.",
                    "failure_mechanism": "_read_pyc reuses a stale co_filename",
                    "target_rationale": (
                        "src/_pytest/assertion/rewrite.py contains _read_pyc, "
                        "which controls rewritten pyc reuse before execution"
                    ),
                },
            }

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_context_files=2),
        agent_factory=lambda config: fake_agent,
    )

    plan = planner.plan(
        issue_text=(
            "Moving a pytest file leaves a stale co_filename after _read_pyc "
            "loads rewritten pyc bytecode."
        ),
        retrieved_context=[
            RetrievedContext(
                path="src/_pytest/python.py",
                rank=1,
                score=100.0,
                method="test",
                matched_terms=["reviewed_source_hint", "python"],
                excerpt="def pytest_pycollect_makeitem():\n    return None",
            ),
            RetrievedContext(
                path="src/_pytest/assertion/rewrite.py",
                rank=50,
                score=1.0,
                method="test",
                matched_terms=[
                    "reviewed_source_hint",
                    "symbol:_read_pyc",
                    "co_filename",
                    "pyc",
                ],
                excerpt=(
                    "def _read_pyc(source, pyc):\n"
                    "    co = marshal.load(pyc)\n"
                    "    return co"
                ),
            ),
            RetrievedContext(
                path="testing/test_issue_14552_repro.py",
                rank=99,
                score=1.0,
                method="test",
                matched_terms=["reviewed_source_hint", "validation_fixture"],
                excerpt=(
                    "def test_moved_test_file_updates_code_filename(pytester):\n"
                    "    assert __file__ in failure"
                ),
            ),
        ],
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/_pytest/assertion/rewrite.py" in files
    assert "/testing/test_issue_14552_repro.py" in files
    assert "/src/_pytest/python.py" not in files
    budget_manifest = files[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH]["content"]
    assert "src/_pytest/python.py" in budget_manifest
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["virtual_file_paths"] == [
        "/src/_pytest/assertion/rewrite.py",
        "/testing/test_issue_14552_repro.py",
    ]
    assert contract["context_budget"]["omitted_paths"] == ["src/_pytest/python.py"]


def test_deepagents_target_context_selection_mounts_only_localized_target() -> None:
    class FakeAgent:
        input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/_pytest/assertion/rewrite.py",
                    "old": (
                        "def _read_pyc(source, pyc):\n"
                        "    co = marshal.load(pyc)\n"
                        "    return co"
                    ),
                    "new": (
                        "def _read_pyc(source, pyc):\n"
                        "    co = marshal.load(pyc)\n"
                        "    if co.co_filename != str(source):\n"
                        "        return None\n"
                        "    return co"
                    ),
                    "summary": "Reject stale rewritten bytecode for moved files.",
                    "failure_mechanism": "_read_pyc reuses a stale co_filename",
                    "target_rationale": "src/_pytest/assertion/rewrite.py controls pyc reuse.",
                },
            }

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            context_selection_mode="target",
        ),
        agent_factory=lambda config: fake_agent,
    )

    plan = planner.plan(
        issue_text=(
            "Moving a pytest file leaves a stale co_filename after _read_pyc "
            "loads rewritten pyc bytecode."
        ),
        retrieved_context=[
            RetrievedContext(
                path="src/_pytest/python.py",
                rank=1,
                score=100.0,
                method="test",
                matched_terms=["reviewed_source_hint", "python"],
                excerpt="def pytest_pycollect_makeitem():\n    return None",
            ),
            RetrievedContext(
                path="src/_pytest/assertion/rewrite.py",
                rank=50,
                score=1.0,
                method="test",
                matched_terms=[
                    "reviewed_source_hint",
                    "symbol:_read_pyc",
                    "co_filename",
                    "pyc",
                ],
                excerpt=(
                    "def _read_pyc(source, pyc):\n"
                    "    co = marshal.load(pyc)\n"
                    "    return co"
                ),
            ),
            RetrievedContext(
                path="testing/test_issue_14552_repro.py",
                rank=99,
                score=1.0,
                method="test",
                matched_terms=["reviewed_source_hint", "validation_fixture"],
                excerpt="def test_moved_test_file_updates_code_filename(pytester): pass",
            ),
        ],
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/_pytest/assertion/rewrite.py" in files
    assert "/src/_pytest/python.py" not in files
    assert "/testing/test_issue_14552_repro.py" not in files
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in files
    budget_manifest = files[PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH]["content"]
    assert "src/_pytest/python.py" in budget_manifest
    assert "testing/test_issue_14552_repro.py" in budget_manifest
    assert planner.last_plan_metadata is not None
    contract = planner.last_plan_metadata["deepagents_contract"]
    assert contract["context_selection_mode"] == "target"
    assert contract["max_context_files"] == 1
    assert contract["virtual_file_count"] == 1
    assert contract["virtual_file_paths"] == ["/src/_pytest/assertion/rewrite.py"]
    assert contract["context_budget"]["mounted_paths"] == [
        "src/_pytest/assertion/rewrite.py"
    ]
    assert contract["context_budget"]["omitted_paths"] == [
        "src/_pytest/python.py",
        "testing/test_issue_14552_repro.py",
    ]


def test_deepagents_context_cap_retry_pins_previous_mounted_paths() -> None:
    class FakeAgent:
        input_payload: dict[str, object] | None = None

        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            self.input_payload = payload
            return {
                "structured_response": {
                    "path": "src/a.py",
                    "old": "def a():\n    return 'old'",
                    "new": "def a():\n    return 'new'",
                    "summary": "Use the pinned mounted source path.",
                    "failure_mechanism": "retry failure remains in the pinned context",
                    "target_rationale": "src/a.py was mounted in the previous attempt.",
                },
            }

    fake_agent = FakeAgent()
    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test", max_context_files=3),
        agent_factory=lambda config: fake_agent,
    )

    plan = planner.plan_for_task(
        task=SimpleNamespace(
            repo_path=None,
            issue_text="Retry still fails after config dispatch.",
            retrieved_context=[
                RetrievedContext(
                    path="src/_pytest/config/__init__.py",
                    rank=1,
                    score=100.0,
                    method="test",
                    matched_terms=["reviewed_source_hint", "symbol:Config"],
                    excerpt="class Config:\n    pass",
                ),
                RetrievedContext(
                    path="src/a.py",
                    rank=50,
                    score=1.0,
                    method="test",
                    matched_terms=[],
                    excerpt="def a():\n    return 'old'",
                ),
                RetrievedContext(
                    path="src/b.py",
                    rank=60,
                    score=1.0,
                    method="test",
                    matched_terms=[],
                    excerpt="def b():\n    return 'old'",
                ),
                RetrievedContext(
                    path="testing/test_repro.py",
                    rank=70,
                    score=1.0,
                    method="test",
                    matched_terms=["validation_fixture"],
                    excerpt="def test_repro():\n    assert False",
                ),
            ],
            runtime_config={
                "max_context_files": 3,
                "context_selection_pinned_paths": ["src/a.py", "src/b.py"],
            },
        )
    )

    assert plan is not None
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/testing/test_repro.py" in files
    assert "/src/a.py" in files
    assert "/src/b.py" in files
    assert "/src/_pytest/config/__init__.py" not in files


def test_deepagents_repair_planner_preserves_usage_when_json_is_invalid() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content="not json",
                        usage_metadata={
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        },
                    )
                ],
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(
            model="gpt-test",
            input_cost_per_1m=1.0,
            output_cost_per_1m=2.0,
        ),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is None
    assert planner.last_model_metadata is not None
    assert planner.last_model_metadata.provider == "deepagents_openai_chat"
    assert planner.last_model_metadata.input_tokens == 10
    assert planner.last_model_metadata.estimated_cost_usd == 0.00002
    assert planner.last_plan_metadata is not None
    assert planner.last_plan_metadata["model_call"]["provider"] == "deepagents_openai_chat"
    assert planner.last_plan_metadata["deepagents_contract"]["virtual_file_count"] == 1
    assert (
        planner.last_plan_metadata["deepagents_contract"]["planning_policy"][
            "one_bounded_replacement"
        ]
        is True
    )


def test_deepagents_repair_planner_preserves_contract_when_agent_invoke_fails() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            raise RuntimeError(
                "Failed to parse structured output for tool 'PatchPlan': "
                "Native structured output expected valid JSON for PatchPlan, but parsing failed."
            )

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is None
    assert planner.last_plan_metadata is not None
    model_call = planner.last_plan_metadata["model_call"]
    assert model_call["provider"] == "deepagents_openai_chat"
    assert model_call["model"] == "gpt-test"
    assert model_call["status"] == "structured_output_parse_failed"
    assert model_call["error_type"] == "RuntimeError"
    assert "Failed to parse structured output" in model_call["error_summary"]
    assert planner.last_plan_metadata["deepagents_contract"]["virtual_file_count"] == 1


def test_deepagents_repair_planner_normalizes_line_numbered_old_span() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py",'
                            '"old":"1: def add(left, right):\\n2:     return left - right",'
                            '"new":"def add(left, right):\\n    return left + right",'
                            '"summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"selected add body controls the arithmetic"}'
                        )
                    )
                ],
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.old == "def add(left, right):\n    return left - right"


def test_deepagents_repair_planner_normalizes_tab_prefixed_python_replacement() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py",'
                            '"old":"def add(left, right):\\n    return left - right",'
                            '"new":"\\tdef add(left, right):\\n\\t    return left + right",'
                            '"summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"selected add body controls the arithmetic"}'
                        )
                    )
                ],
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.new == "def add(left, right):\n    return left + right"


def test_deepagents_repair_planner_prefers_compile_valid_replacement_candidate() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py",'
                            '"old":"1: def add(left, right):\\n2:     return left - right",'
                            '"new":"\\tdef add(left, right):\\n\\t    return left + right",'
                            '"summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"selected add body controls the arithmetic"}'
                        )
                    )
                ],
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.old == "def add(left, right):\n    return left - right"
    assert plan.new == "def add(left, right):\n    return left + right"


def test_deepagents_repair_planner_normalizes_unique_stripped_old_span() -> None:
    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            '{"path":"/src/simple_calc.py",'
                            '"old":"def add(left, right):\\nreturn left - right",'
                            '"new":"def add(left, right):\\n    return left + right",'
                            '"summary":"Fix add.",'
                            '"failure_mechanism":"add returns subtraction result",'
                            '"target_rationale":"selected add body controls the arithmetic"}'
                        )
                    )
                ],
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    plan = planner.plan(
        issue_text="add returns the wrong result",
        retrieved_context=[_context("src/simple_calc.py")],
    )

    assert plan is not None
    assert plan.old == "def add(left, right):\n    return left - right"
    assert plan.new == "def add(left, right):\n    return left + right"


def _context(path: str) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=10.0,
        method="test",
        matched_terms=["simple"],
        excerpt="1: def add(left, right):\n2:     return left - right",
    )
