from pathlib import Path

from patchsmith.deepagents_planner import DeepAgentsPlannerConfig, DeepAgentsRepairPlanner
from patchsmith.deepagents_prompts import PATCHSMITH_DEEPAGENTS_MEMORY_PATH
from patchsmith.deepagents_schema import patch_plan_response_schema
from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.models import RunRequest
from patchsmith.planning import ModelBackedRepairPlanner, RepairPlan, StaticResponseModelClient
from patchsmith.retrieval import HybridRetriever
from patchsmith.runtime import AgentTask, DeepAgentsRuntime, LangGraphRuntime, OpenAIAgentsRuntime
from patchsmith.workflow import RepairRunner


def test_langgraph_runtime_generates_patch_with_deterministic_planner(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
    )

    result = LangGraphRuntime().run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "patch_generated"
    assert "return left + right" in (snapshot.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    assert [event["node"] for event in result.runtime_trace] == [
        "triage",
        "plan",
        "edit",
        "analyze",
        "retry",
        "review",
    ]


def test_repair_runner_langgraph_runtime_emits_runtime_node_traces(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="langgraph",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    trace_text = result.trace_path.read_text(encoding="utf-8")
    assert "runtime.triage" in trace_text
    assert "runtime.analyze" in trace_text
    assert "runtime.retry" in trace_text
    assert "runtime.review" in trace_text


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
        "review",
    ]
    assert result.runtime_trace[0]["framework"] == "deepagents"


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


def test_openai_agents_runtime_generates_patch_with_adapter_trace(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue_text = (fixture / "issue.md").read_text(encoding="utf-8")
    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue_text,
    )

    result = OpenAIAgentsRuntime().run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=issue_text,
            retrieved_context=contexts,
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "patch_generated"
    assert result.patch_candidates[0].generation_strategy.startswith("openai_agents:")
    assert "return left + right" in (snapshot.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    assert [event["node"] for event in result.runtime_trace] == [
        "harness",
        "agent",
        "guardrails",
        "context",
        "plan",
        "edit",
        "review",
    ]
    assert result.runtime_trace[0]["framework"] == "openai_agents"


def test_repair_runner_openai_agents_runtime_emits_runtime_node_traces(
    tmp_path: Path,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="openai_agents",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    report = result.report_path.read_text(encoding="utf-8")
    assert "Runtime: `openai_agents`" in report
    trace_text = result.trace_path.read_text(encoding="utf-8")
    assert "runtime.harness" in trace_text
    assert "runtime.agent" in trace_text
    assert "runtime.guardrails" in trace_text
    assert "runtime.review" in trace_text


def test_repair_runner_langgraph_fake_model_planner_generates_patch(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="langgraph",
            planner="fake_model",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert "+    return left + right" in result.final_diff_path.read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")
    assert "Planner: `fake_model`" in report
    assert "Model provider: `offline_fake_model`" in report
    trace = result.trace_path.read_text(encoding="utf-8")
    assert "offline_fake_model" in trace


def test_langgraph_runtime_retries_no_plan_until_budget_exhausted(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")

    result = LangGraphRuntime(planner=NoPlanPlanner()).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            retrieved_context=[],
            test_command="python3 -m pytest",
            runtime_config={"max_retries": 1},
        )
    )

    assert result.status == "no_patch_generated"
    assert [event["node"] for event in result.runtime_trace].count("plan") == 2
    retry_events = [event for event in result.runtime_trace if event["node"] == "retry"]
    assert [event["status"] for event in retry_events] == ["scheduled", "exhausted"]
    assert retry_events[-1]["max_retries"] == 1


def test_langgraph_runtime_records_patch_plan_diagnostics_for_rejected_edit(
    tmp_path: Path,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")

    result = LangGraphRuntime(planner=BadSpanPlanner()).run(
        AgentTask(
            run_id="test-run",
            repo_path=str(snapshot.repo_path),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            retrieved_context=[],
            test_command="python3 -m pytest",
        )
    )

    plan_event = next(event for event in result.runtime_trace if event["node"] == "plan")
    edit_event = next(event for event in result.runtime_trace if event["node"] == "edit")
    assert result.status == "no_patch_generated"
    assert edit_event["status"] == "failed"
    assert plan_event["patch_plan"]["old_found"] is False
    assert edit_event["patch_plan"]["old_occurrences"] == 0


class NoPlanPlanner:
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        return None


class BadSpanPlanner:
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        return RepairPlan(
            name="bad_span",
            path="src/simple_calc.py",
            old="return does_not_exist",
            new="return left + right",
            summary="Use an old span that does not exist.",
        )
