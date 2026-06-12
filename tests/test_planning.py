import json
import math
import sys
import urllib.request
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from patchsmith.deepagents_planner import (
    DeepAgentsPlannerConfig,
    DeepAgentsRepairPlanner,
    _read_only_filesystem_permissions,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
    deepagents_agents_md,
    deepagents_patch_review_subagents,
    deepagents_planner_prompt,
    deepagents_repair_skill_md,
    deepagents_system_prompt,
)
from patchsmith.deepagents_schema import PatchPlan, patch_plan_response_schema
from patchsmith.model_config import DEFAULT_OPENAI_MODEL
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


def test_openai_responses_model_client_from_env_uses_documented_default_model_pricing() -> None:
    client = OpenAIResponsesModelClient.from_env({"OPENAI_API_KEY": "test-key"})

    assert client.model == DEFAULT_OPENAI_MODEL
    assert client.input_cost_per_1m == 0.75
    assert client.output_cost_per_1m == 4.50


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
    assert planner.config.reasoning_effort is None
    assert planner.config.input_cost_per_1m == 0.75
    assert planner.config.output_cost_per_1m == 4.50


def test_deepagents_repair_planner_from_env_allows_reasoning_effort_opt_in() -> None:
    planner = DeepAgentsRepairPlanner.from_env({"PATCHSMITH_DEEPAGENTS_REASONING_EFFORT": "low"})

    assert planner.config.reasoning_effort == "low"


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
        }
    )

    assert planner.config.model == "custom-deepagents-model"
    assert planner.config.input_cost_per_1m == 3.0
    assert planner.config.output_cost_per_1m == 4.0
    assert planner.config.max_file_chars == 1234


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
    assert "exact text span" in system_prompt
    assert "PatchSmith DeepAgents Repair Contract" in deepagents_agents_md()
    assert "patch-reviewer" in deepagents_agents_md()
    repair_skill = deepagents_repair_skill_md()
    assert "name: patchsmith-repair" in repair_skill
    assert "bounded PatchSmith patch plan" in repair_skill
    assert "src/simple_calc.py" in planner_prompt
    assert subagents[0]["name"] == "patch-reviewer"


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
        "fields": ["path", "old", "new", "summary"],
        "all_fields_required": True,
    }
    assert set(PatchPlan.model_fields) == {"path", "old", "new", "summary"}


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

    planner = DeepAgentsRepairPlanner(DeepAgentsPlannerConfig(model="gpt-test"))

    planner._build_agent(files={"/src/simple_calc.py": {"content": "x"}})

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
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        "/src/simple_calc.py",
    ]
    assert permissions[0].mode == "allow"
    assert permissions[1].operations == ["read", "write"]
    assert permissions[1].paths == ["/**"]
    assert permissions[1].mode == "deny"
    subagents = captured["subagents"]
    assert subagents[0]["name"] == "patch-reviewer"
    assert captured["response_format"] is PatchPlan


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
                            '"new":"return left + right","summary":"Fix add."}'
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
    assert math.isclose(model_call["estimated_cost_usd"], 0.00015)
    contract = plan.metadata["deepagents_contract"]
    assert contract["framework"] == "deepagents"
    assert contract["mode"] == "custom_agent_factory"
    assert contract["model"] == "gpt-test"
    assert contract["use_responses_api"] is True
    assert contract["store"] is False
    assert contract["memory_paths"] == [PATCHSMITH_DEEPAGENTS_MEMORY_PATH]
    assert contract["skill_sources"] == [PATCHSMITH_DEEPAGENTS_SKILL_DIR]
    assert contract["skill_paths"] == [PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]
    assert contract["virtual_file_paths"] == ["/src/simple_calc.py"]
    assert contract["filesystem_policy"]["allowed_read_paths"] == [
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        "/src/simple_calc.py",
    ]
    assert contract["subagents"][0]["name"] == "patch-reviewer"
    assert contract["response_format"] == "PatchPlan"
    assert contract["response_schema"] == patch_plan_response_schema()
    assert contract["planning_policy"]["todos_required"] is True
    assert fake_agent.input_payload is not None
    files = fake_agent.input_payload["files"]
    assert "/src/simple_calc.py" in files
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in files
    assert PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH in files
    assert "name: patchsmith-repair" in files[PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH]["content"]
    assert files["/src/simple_calc.py"]["encoding"] == "utf-8"
    assert files["/src/simple_calc.py"]["created_at"]
    assert files["/src/simple_calc.py"]["modified_at"]


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
                            '"summary":"Fix focused target."}'
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
                            '"summary":"Fix add."}'
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
                            '"summary":"Fix add."}'
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
                            '"summary":"Fix add."}'
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
                            '"summary":"Fix add."}'
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
