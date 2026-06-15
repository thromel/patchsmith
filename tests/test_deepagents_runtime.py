from pathlib import Path

from patchsmith.deepagents_planner import DeepAgentsPlannerConfig, DeepAgentsRepairPlanner
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
)
from patchsmith.deepagents_schema import patch_plan_response_schema
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RetrievedContext, RunRequest
from patchsmith.planning import ModelBackedRepairPlanner, StaticResponseModelClient
from patchsmith.retrieval import HybridRetriever
from patchsmith.runtime import AgentTask, DeepAgentsRuntime
from patchsmith.workflow import RepairRunner


def test_deepagents_runtime_generates_patch_with_adapter_trace(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )

    result = DeepAgentsRuntime().run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "patch_generated"
    assert result.patch_candidates[0].generation_strategy.startswith("deepagents:")
    assert "return left + right" in (snapshot.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    assert [event["node"] for event in result.runtime_trace] == [
        "harness",
        "todo",
        "context",
        "plan",
        "edit",
        "patch_effect",
        "patch_quality",
        "review",
    ]
    assert result.runtime_trace[0]["framework"] == "deepagents"
    patch_effect_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_effect"
    )
    assert patch_effect_event["effect_kind"] == "behavior_change"
    assert patch_effect_event["import_only"] is False
    assert patch_effect_event["replacement_strategy"] == "exact"
    patch_quality_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_quality"
    )
    assert patch_quality_event["quality"]["severity"] == "low"


def test_deepagents_runtime_preserves_model_usage_metadata(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/simple_calc.py",
              "old": "return left - right",
              "new": "return left + right",
              "summary": "Fix add to return the sum."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    assert result.status == "patch_generated"
    assert plan_event["metadata"]["model_call"]["provider"] == "unit_model"
    assert plan_event["patch_plan"]["path"] == "src/simple_calc.py"
    assert plan_event["patch_plan"]["old_found"] is True
    assert plan_event["patch_plan"]["old_occurrences"] == 2


def test_deepagents_runtime_records_patch_plan_diagnostics_for_rejected_edit(
    tmp_path: Path,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/simple_calc.py",
              "old": "return does_not_exist",
              "new": "return left + right",
              "summary": "Try a bad old span."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert plan_event["patch_plan"]["old_found"] is False
    assert edit_event["patch_plan"]["old_occurrences"] == 0
    assert edit_event["patch_plan"]["old"]["first_line_preview"] == "return does_not_exist"


def test_deepagents_runtime_suggests_nearest_source_excerpt_for_bad_old_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text(
        "def runpytest(self, *args: str | os.PathLike[str], **kwargs: Any) -> RunResult:\n"
        "    \"\"\"Run pytest inline.\"\"\"\n"
        "    if self._request.config.getoption(\"runpytest\") == \"inprocess\":\n"
        "        return self.inline_run(*args, **kwargs)\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "def runpytest(self, *args: str, **kwargs: Any) -> RunResult:\\n    if self._request.config.getoption(\\"runpytest\\") == \\"inprocess\\":\\n        return self.inline_run(*args, **kwargs)",
              "new": "def runpytest(self, *args: str, **kwargs: Any) -> RunResult:\\n    self._cleanup_modules()\\n    if self._request.config.getoption(\\"runpytest\\") == \\"inprocess\\":\\n        return self.inline_run(*args, **kwargs)",
              "summary": "Try to clear stale inline modules."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="inline rerun reuses stale code objects",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["runpytest"],
                    excerpt="1: def runpytest(...):\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    excerpt = edit_event["patch_plan"]["nearest_source_excerpt"]
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert excerpt["start_line"] == 1
    assert "str | os.PathLike[str]" in excerpt["text"]
    assert "return self.inline_run(*args, **kwargs)" in excerpt["text"]


def test_deepagents_runtime_applies_high_similarity_nearest_source_span(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text(
        "def calculate(left: int, right: int) -> int:\n"
        "    return left - right\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "def calculate(left:int, right:int) -> int:\\n    return left - right",
              "new": "def calculate(left:int, right:int) -> int:\\n    return left + right",
              "summary": "Fix addition behavior."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="addition returns subtraction",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["calculate"],
                    excerpt="1: def calculate(left: int, right: int) -> int:\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    alignment_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_alignment"
    )
    patch_effect_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_effect"
    )
    assert result.status == "patch_generated"
    assert "return left + right" in target.read_text(encoding="utf-8")
    assert alignment_event["strategy"] == "nearest_source_span"
    assert alignment_event["similarity"] >= 0.9
    assert patch_effect_event["effect_kind"] == "behavior_change"
    assert patch_effect_event["replacement_strategy"] == "nearest_source_span"
    assert patch_effect_event["replacement_similarity"] >= 0.9


def test_deepagents_runtime_records_high_risk_patch_quality(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "runner.py"
    target.write_text(
        "import types\n"
        "\n"
        "def call(testfunction, filename):\n"
        "    return testfunction()\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/runner.py",
              "old": "def call(testfunction, filename):\\n    return testfunction()",
              "new": "def call(testfunction, filename):\\n    try:\\n        co = testfunction.__code__\\n        if co.co_filename != filename:\\n            try:\\n                testfunction.__code__ = co.replace(co_filename=str(filename))\\n            except Exception:\\n                try:\\n                    testfunction.__code__ = types.CodeType(co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount, co.co_nlocals, co.co_stacksize, co.co_flags, co.co_code, co.co_consts, co.co_names, co.co_varnames, str(filename), co.co_name, co.co_firstlineno, co.co_lnotab, co.co_freevars, co.co_cellvars)\\n                except Exception:\\n                    pass\\n    except Exception:\\n        pass\\n    return testfunction()",
              "summary": "Patch stale code object filenames."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="test function keeps stale co_filename after file move",
            retrieved_context=[
                RetrievedContext(
                    path="src/runner.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["co_filename"],
                    excerpt="1: def call(...):\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    quality_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_quality"
    )
    risk_notes = "\n".join(result.patch_candidates[0].risk_notes)
    assert result.status == "patch_generated"
    assert quality_event["quality"]["severity"] == "high"
    assert "code_object_mutation" in risk_notes
    assert "broad_exception_swallow" in risk_notes


def test_deepagents_runtime_rejects_python_comment_only_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("def value():\n    return 1\n", encoding="utf-8")
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "def value():\\n    return 1",
              "new": "# explain value\\ndef value():\\n    return 1",
              "summary": "Add a comment without changing behavior."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="value returns the wrong result",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["value"],
                    excerpt="1: def value():\n2:     return 1\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert "comments or whitespace" in edit_event["summary"]
    assert target.read_text(encoding="utf-8") == "def value():\n    return 1\n"


def test_deepagents_runtime_rejects_import_only_behavioral_patch(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text(
        "from _pytest.pathlib import import_path\n"
        "\n"
        "def collect(path):\n"
        "    return import_path(path)\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "from _pytest.pathlib import import_path",
              "new": "from _pytest.pathlib import ImportPathMismatchError\\nfrom _pytest.pathlib import import_path",
              "summary": "Try to fix stale co_filename after moved tests by adding an import."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="moved test file keeps old co_filename after collection",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["import_path"],
                    excerpt="1: from _pytest.pathlib import import_path\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert "import statements" in edit_event["summary"]
    assert target.read_text(encoding="utf-8").count("ImportPathMismatchError") == 0


def test_deepagents_runtime_allows_import_only_nameerror_patch(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text(
        "from pathlib import Path\n"
        "\n"
        "def slugify(value):\n"
        "    return re.sub(r'\\\\W+', '-', value)\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "from pathlib import Path",
              "new": "import re\\nfrom pathlib import Path",
              "summary": "Fix NameError by importing re."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="slugify raises NameError because re is unavailable",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["slugify", "NameError"],
                    excerpt="1: from pathlib import Path\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "patch_generated"
    assert target.read_text(encoding="utf-8").startswith("import re\nfrom pathlib import Path")
    patch_effect_event = next(
        event for event in result.runtime_trace if event["node"] == "patch_effect"
    )
    assert patch_effect_event["effect_kind"] == "import_only"
    assert patch_effect_event["import_only"] is True


def test_deepagents_runtime_rejects_python_syntax_error_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("def value():\n    return 1\n", encoding="utf-8")
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/module.py",
              "old": "def value():\\n    return 1",
              "new": "def value():\\n    break",
              "summary": "Try an invalid break."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="value returns the wrong result",
            retrieved_context=[
                RetrievedContext(
                    path="src/module.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["value"],
                    excerpt="1: def value():\n2:     return 1\n",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert "fail Python compilation" in edit_event["summary"]
    assert target.read_text(encoding="utf-8") == "def value():\n    return 1\n"


def test_deepagents_runtime_rejects_python_patch_with_new_unbound_names(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target = src / "rewrite.py"
    target.write_text(
        "def _rewrite_test(fn, config):\n"
        "    return fn.stat(), compile(fn.read_text(), str(fn), 'exec')\n"
        "\n"
        "class Hook:\n"
        "    def exec_module(self, module):\n"
        "        fn = Path(module.__spec__.origin)\n"
        "        source_stat, co = _rewrite_test(fn, self.config)\n",
        encoding="utf-8",
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient(
            """
            {
              "path": "src/rewrite.py",
              "old": "source_stat, co = _rewrite_test(fn, self.config)",
              "new": "source_stat, co = _rewrite_test(path, config)",
              "summary": "Try to use the moved path when rewriting."
            }
            """,
            provider="unit_model",
        )
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="moved tests keep an old co_filename",
            retrieved_context=[
                RetrievedContext(
                    path="src/rewrite.py",
                    rank=1,
                    score=1.0,
                    method="test",
                    matched_terms=["co_filename"],
                    excerpt="source_stat, co = _rewrite_test(fn, self.config)",
                )
            ],
            test_command="python3 -m pytest",
        )
    )

    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert "unbound Python name" in edit_event["summary"]
    assert "`config`" in edit_event["summary"]
    assert "`path`" in edit_event["summary"]
    assert "path, config" not in target.read_text(encoding="utf-8")


def test_deepagents_runtime_preserves_failed_model_usage_metadata(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )
    planner = ModelBackedRepairPlanner(
        StaticResponseModelClient("not a json repair plan", provider="unit_model")
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    assert result.status == "no_patch_generated"
    assert plan_event["status"] == "no_match"
    assert plan_event["metadata"]["model_call"]["provider"] == "unit_model"


def test_deepagents_runtime_records_native_planning_contract_on_no_plan(
    tmp_path: Path,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )

    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {"messages": []}

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    contract = plan_event["metadata"]["deepagents_contract"]
    assert result.status == "no_patch_generated"
    assert plan_event["metadata"]["model_call"]["status"] == "missing_messages"
    assert contract["framework"] == "deepagents"
    assert contract["mode"] == "custom_agent_factory"
    assert contract["virtual_file_count"] >= 1
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in contract["memory_paths"]
    assert contract["response_schema"] == patch_plan_response_schema()
    assert contract["planning_policy"]["filesystem_reads_required"] is True
    assert contract["planning_policy"]["validation_fixtures_read_first"] is True
    assert contract["planning_policy"]["repo_map_manifest_read_first"] is False
    assert contract["planning_policy"]["failure_localizer_subagent_for_validation_fixtures"] is True
    assert contract["planning_policy"]["patch_quality_policy_read_first"] is True
    assert contract["repo_map_manifest_path"] is None
    assert contract["patch_quality_policy"]["avoid_runtime_code_object_mutation"] is True
    assert contract["patch_quality_policy"]["avoid_unbound_helper_names"] is True
    assert contract["patch_quality_policy"]["require_complete_python_replacement_spans"] is True
    assert contract["patch_quality_policy"]["reject_no_op_replacements"] is True
    assert contract["patch_quality_policy"]["enforced_as_quality_warning"] is True


def test_deepagents_runtime_provides_source_hint_manifest_to_native_agent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    hinted_file = src / "hinted.py"
    hinted_file.write_text(
        'def target_symbol():\n    return "old"\n',
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            captured["payload"] = payload
            return {
                "messages": [],
                "structured_response": {
                    "path": "src/hinted.py",
                    "old": '    return "old"',
                    "new": '    return "new"',
                    "summary": "Patch the reviewed source hint symbol.",
                    "failure_mechanism": "target_symbol returns the old sentinel",
                    "target_rationale": "src/hinted.py#target_symbol controls the returned value",
                },
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="external reproduction points to src/hinted.py#target_symbol",
            retrieved_context=[
                RetrievedContext(
                    path="src/hinted.py",
                    rank=1,
                    score=1.0,
                    method="patchsmith_native_hybrid",
                    matched_terms=[
                        "reviewed_source_hint",
                        "active_path",
                        "symbol:target_symbol",
                    ],
                    excerpt='1: def target_symbol():\n2:     return "old"\n',
                )
            ],
            test_command="python3 -m pytest tests/test_bug.py",
        )
    )

    payload = captured["payload"]
    files = payload["files"]
    manifest = files[PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH]["content"]
    prompt = payload["messages"][0]["content"]
    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    contract = plan_event["metadata"]["deepagents_contract"]

    assert result.status == "patch_generated"
    assert "target_symbol" in manifest
    assert "reviewed reproduction source hint" in manifest
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH in prompt
    assert contract["source_hint_manifest_path"] == PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH in (
        contract["filesystem_policy"]["allowed_read_paths"]
    )
    assert contract["planning_policy"]["source_hint_manifest_read_first"] is True
    assert plan_event["metadata"]["failure_localization"] == {
        "failure_mechanism": "target_symbol returns the old sentinel",
        "target_rationale": "src/hinted.py#target_symbol controls the returned value",
    }
    assert 'return "new"' in hinted_file.read_text(encoding="utf-8")


def test_deepagents_runtime_provides_retry_feedback_manifest_to_native_agent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    target_file = src / "retry_target.py"
    target_file.write_text(
        "def repair_site():\n    return 'old'\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAgent:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            captured["payload"] = payload
            return {
                "messages": [],
                "structured_response": {
                    "path": "src/retry_target.py",
                    "old": "    return 'old'",
                    "new": "    return 'new'",
                    "summary": "Use retry feedback to change the controlling branch.",
                    "failure_mechanism": "repair_site still returns the old sentinel after retry",
                    "target_rationale": "retry feedback points to the selected return span",
                },
            }

    planner = DeepAgentsRepairPlanner(
        DeepAgentsPlannerConfig(model="gpt-test"),
        agent_factory=lambda config: FakeAgent(),
    )

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(repo),
            issue_text="retry the failed repair",
            retrieved_context=[
                RetrievedContext(
                    path="src/retry_target.py",
                    rank=1,
                    score=1.0,
                    method="patchsmith_native_hybrid",
                    matched_terms=["repair_site"],
                    excerpt="1: def repair_site():\n2:     return 'old'\n",
                )
            ],
            test_command="python3 -m pytest tests/test_bug.py",
            runtime_config={
                "workflow_attempt": 2,
                "retry_feedback_brief": "# PatchSmith Retry Feedback\n\nDo not repeat diff.",
            },
        )
    )

    payload = captured["payload"]
    files = payload["files"]
    prompt = payload["messages"][0]["content"]
    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    contract = plan_event["metadata"]["deepagents_contract"]

    assert result.status == "patch_generated"
    assert PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH in files
    assert "Do not repeat diff" in files[PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH]["content"]
    assert PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH in prompt
    assert contract["retry_feedback_manifest_path"] == PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH
    assert PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH in (
        contract["filesystem_policy"]["allowed_read_paths"]
    )
    assert contract["planning_policy"]["retry_feedback_manifest_read_first"] is True
    assert plan_event["metadata"]["failure_localization"] == {
        "failure_mechanism": "repair_site still returns the old sentinel after retry",
        "target_rationale": "retry feedback points to the selected return span",
    }
    assert "return 'new'" in target_file.read_text(encoding="utf-8")


def test_deepagents_runtime_handles_native_structured_output_parse_errors(
    tmp_path: Path,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )

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

    result = DeepAgentsRuntime(planner=planner).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    assert result.status == "no_patch_generated"
    assert plan_event["status"] == "no_match"
    assert plan_event["metadata"]["model_call"]["status"] == "structured_output_parse_failed"
    assert "error_summary" in plan_event["metadata"]["model_call"]


def test_repair_runner_deepagents_runtime_emits_runtime_node_traces(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    report = result.report_path.read_text(encoding="utf-8")
    assert "Runtime: `deepagents`" in report
    trace_text = result.trace_path.read_text(encoding="utf-8")
    assert "runtime.harness" in trace_text
    assert "runtime.todo" in trace_text
    assert "runtime.review" in trace_text
