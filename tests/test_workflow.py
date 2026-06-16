import hashlib
import json
from pathlib import Path

from patchsmith.models import (
    CommandPolicyDecision,
    CommandResult,
    PatchCandidate,
    RetrievedContext,
    RunRequest,
)
from patchsmith.planning import RepairPlan
from patchsmith.runtime import AgentResult, AgentTask
from patchsmith.workflow import (
    RepairRunner,
    _merge_retrieved_contexts,
    _retry_resource_budget_block,
    _runtime_config_with_resource_usage,
)


def test_repair_runner_writes_report_trace_and_test_output(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
        )
    )

    assert result.status == "completed"
    assert result.report_path.exists()
    assert result.trace_path.exists()
    assert result.final_diff_path.exists()
    assert result.test_result is not None
    assert result.test_result.exit_code == 1
    assert result.retrieved_context[0].path == "src/simple_calc.py"

    report = result.report_path.read_text(encoding="utf-8")
    assert "# PatchSmith Run Report" in report
    assert "src/simple_calc.py" in report
    assert "Test Results" in report
    assert "Context Packing" in report
    assert "Approximate tokens" in report
    assert "Sandbox: `local`" in report
    assert "Repair Analysis" in report
    assert "Final Verdict" in report
    assert "`no_patch_tests_failed`" in report
    trace = result.trace_path.read_text(encoding="utf-8")
    assert '"node_name": "analyze"' in trace
    assert '"event_type": "repair_outcome"' in trace


def test_repair_runner_auto_context_provider_falls_back_to_native(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
            context_provider="auto",
            retrieval_strategy="auto",
        )
    )

    assert result.status == "completed"
    assert result.retrieved_context[0].path == "src/simple_calc.py"
    trace = result.trace_path.read_text(encoding="utf-8")
    assert "context_broker_call" in trace


def test_repair_runner_promotes_context_paths_into_retrieved_context(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "hinted.py").write_text("def hidden_fix_site():\n    pass\n", encoding="utf-8")
    (repo / "README.md").write_text("nothing useful here\n", encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(repo),
            issue_text="a vague external failure with no lexical match",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            top_k=1,
            context_paths=("src/hinted.py#hidden_fix_site",),
        )
    )

    assert result.status == "completed"
    assert [context.path for context in result.retrieved_context] == ["src/hinted.py"]
    assert result.retrieved_context[0].matched_terms[:2] == [
        "reviewed_source_hint",
        "active_path",
    ]
    assert "symbol:hidden_fix_site" in result.retrieved_context[0].matched_terms
    assert "def hidden_fix_site" in result.retrieved_context[0].excerpt


def test_retry_context_merge_prioritizes_reviewed_hints_then_refreshed_source() -> None:
    merged = _merge_retrieved_contexts(
        existing=[
            _retrieved("src/hinted.py", rank=1, terms=["reviewed_source_hint", "active_path"]),
            _retrieved("docs/noisy.py", rank=2, terms=["doc_noise"]),
            _retrieved("tests/noisy_test.py", rank=3, terms=["test_noise"]),
        ],
        refreshed=[
            _retrieved("src/runtime_cache.py", rank=1, terms=["runtime_cache_signal:sys.modules"]),
            _retrieved("docs/noisy.py", rank=2, terms=["doc_noise"]),
        ],
        limit=3,
    )

    assert [context.path for context in merged] == [
        "src/hinted.py",
        "src/runtime_cache.py",
        "docs/noisy.py",
    ]
    assert [context.rank for context in merged] == [1, 2, 3]


def test_retry_context_merge_deprioritizes_ineffective_targets() -> None:
    merged = _merge_retrieved_contexts(
        existing=[
            _retrieved("src/pathlib.py", rank=1, terms=["reviewed_source_hint", "active_path"]),
            _retrieved("src/python.py", rank=2, terms=["reviewed_source_hint", "active_path"]),
            _retrieved("testing/repro.py", rank=3, terms=["validation_fixture"]),
        ],
        refreshed=[
            _retrieved(
                "src/assertion/rewrite.py", rank=1, terms=["runtime_cache_signal:_read_pyc"]
            ),
            _retrieved("src/config.py", rank=2, terms=["runtime_cache_signal:sys.modules"]),
            _retrieved(
                "src/pathlib.py", rank=3, terms=["runtime_cache_signal:module_name_from_path"]
            ),
        ],
        limit=4,
        deprioritized_paths={"src/pathlib.py", "src/assertion/rewrite.py"},
    )

    assert [context.path for context in merged] == [
        "src/python.py",
        "src/config.py",
        "testing/repro.py",
        "src/pathlib.py",
    ]
    assert [context.rank for context in merged] == [1, 2, 3, 4]


def test_runtime_config_with_resource_usage_adds_retry_remaining_budget() -> None:
    runtime_config = {
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
        },
        "subagent_mode": "auto",
    }

    updated = _runtime_config_with_resource_usage(
        runtime_config,
        used_model_responses=9,
        used_model_tokens=165721,
    )

    assert runtime_config["resource_budget"] == {
        "max_model_responses": 12,
        "max_model_tokens": 200000,
    }
    assert updated["resource_budget"] == {
        "max_model_responses": 12,
        "max_model_tokens": 200000,
        "used_model_responses": 9,
        "used_model_tokens": 165721,
        "remaining_model_responses": 3,
        "remaining_model_tokens": 34279,
    }
    assert updated["subagent_mode"] == "auto"


def test_retry_resource_budget_block_stops_after_exhausted_budget() -> None:
    block = _retry_resource_budget_block(
        {
            "resource_budget": {
                "max_model_responses": 12,
                "max_model_tokens": 200000,
            }
        },
        used_model_responses=13,
        used_model_tokens=241742,
    )

    assert block == {
        "reason": "resource_budget_exhausted",
        "reasons": [
            "response_budget_exhausted",
            "token_budget_exhausted",
        ],
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
            "used_model_responses": 13,
            "used_model_tokens": 241742,
            "remaining_model_responses": 0,
            "remaining_model_tokens": 0,
        },
    }


def test_retry_resource_budget_block_stops_when_remaining_budget_is_too_low() -> None:
    block = _retry_resource_budget_block(
        {
            "resource_budget": {
                "max_model_responses": 12,
                "max_model_tokens": 200000,
            }
        },
        used_model_responses=8,
        used_model_tokens=147725,
    )

    assert block == {
        "reason": "resource_budget_insufficient_for_retry",
        "reasons": [
            "response_budget_too_low_for_retry",
            "token_budget_too_low_for_retry",
        ],
        "resource_budget": {
            "max_model_responses": 12,
            "max_model_tokens": 200000,
            "used_model_responses": 8,
            "used_model_tokens": 147725,
            "remaining_model_responses": 4,
            "remaining_model_tokens": 52275,
        },
    }


def test_repair_runner_heuristic_runtime_generates_passing_patch(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=issue,
            test_command="python3 -m pytest",
            runtime="heuristic",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.status == "completed"
    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert "+    return left + right" in result.final_diff_path.read_text(encoding="utf-8")
    report = result.report_path.read_text(encoding="utf-8")
    assert "Patch generation: `patch_generated`" in report
    assert "`patch_validated`" in report
    assert "## Patch Quality" in report
    assert "Risk: `low`" in report


def test_repair_runner_records_selected_sandbox_in_trace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    created: list[tuple[str, str]] = []

    class FakeSandboxRunner:
        def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="ok\n",
                stderr="",
                duration_ms=7,
                timed_out=False,
                policy_decision=CommandPolicyDecision(
                    allowed=True,
                    reason="allowed",
                    tokens=("python3", "-m", "pytest"),
                ),
            )

    def fake_create_sandbox_runner(*, mode: str, image: str):
        created.append((mode, image))
        return FakeSandboxRunner()

    monkeypatch.setattr("patchsmith.workflow.create_sandbox_runner", fake_create_sandbox_runner)

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="heuristic",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            sandbox_mode="docker",
            sandbox_image="patchsmith-test:latest",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert created == [("docker", "patchsmith-test:latest")]
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    sandbox_event = next(
        event for event in trace_events if event["event_type"] == "sandbox_command"
    )
    assert sandbox_event["payload"]["sandbox_mode"] == "docker"
    assert sandbox_event["payload"]["sandbox_image"] == "patchsmith-test:latest"


def test_deepagents_runner_retries_with_sandbox_feedback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    planner = SequencedFeedbackPlanner()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 0])

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert len(planner.issue_texts) == 2
    assert planner.runtime_configs[0].get("retry_feedback_brief") is None
    assert "# PatchSmith Retry Feedback" in planner.runtime_configs[1]["retry_feedback_brief"]
    assert planner.runtime_configs[1]["target_history_paths"] == ["src/simple_calc.py"]
    old_hash = hashlib.sha256(b"return left - right").hexdigest()[:12]
    assert planner.runtime_configs[1]["target_history_old_span_hashes"] == {
        "src/simple_calc.py": [old_hash]
    }
    assert "deprioritized_context_paths" not in planner.runtime_configs[1]
    assert "failure from attempt 1" in planner.runtime_configs[1]["retry_feedback_brief"]
    assert "Previous DeepAgents repair attempt 1 did not validate" in planner.issue_texts[1]
    assert "failed patch has been reverted" in planner.issue_texts[1]
    assert "Do not return the same failed diff unchanged" in planner.issue_texts[1]
    assert "Sandbox feedback summary" in planner.issue_texts[1]
    assert "Previous changed hunks" in planner.issue_texts[1]
    assert "previous patch is on the code path reached" in planner.issue_texts[1]
    assert "previous patch applied cleanly, but validation still failed" in planner.issue_texts[1]
    assert "Do not reuse the same old-span hash" in planner.issue_texts[1]
    assert "failure from attempt 1" in planner.issue_texts[1]
    assert len(sandbox.calls) == 2
    assert "return left + right" in (result.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    retry_event = next(event for event in trace_events if event["node_name"] == "feedback_retry")
    assert retry_event["payload"]["next_attempt"] == 2
    assert retry_event["payload"]["retry_labels"] == [
        "test_failure_retry",
        "failure_class_validation_failed",
        "old_span_repair",
    ]
    assert retry_event["payload"]["retry_failure_class"] == "validation_failed"
    assert retry_event["payload"]["retry_feedback_brief_chars"] > 0
    retry_feedback_path = Path(retry_event["payload"]["retry_feedback_path"])
    assert retry_feedback_path.exists()
    retry_feedback_text = retry_feedback_path.read_text(encoding="utf-8")
    assert "# PatchSmith Retry Feedback" in retry_feedback_text
    assert "Failure class: `validation_failed`" in retry_feedback_text
    assert "failure from attempt 1" in retry_feedback_text
    restore_event = next(
        event for event in trace_events if event["node_name"] == "workspace_restore"
    )
    assert restore_event["payload"]["next_attempt"] == 2
    test_events = [event for event in trace_events if event["event_type"] == "sandbox_command"]
    assert [event["payload"]["attempt"] for event in test_events] == [1, 2]


def test_deepagents_runner_carries_rejected_target_history_into_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    runtime = TargetHistoryViolationRuntime()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 1])

    monkeypatch.setattr(
        "patchsmith.workflow._runtime_for",
        lambda runtime_name, planner_name: runtime,
    )
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert runtime.runtime_configs[1]["target_history_paths"] == ["src/rewrite.py"]
    assert "target=src/rewrite.py" in runtime.runtime_configs[1]["retry_feedback_brief"]


def test_deepagents_retry_pins_explicit_context_budget_mounts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    runtime = MountedContextBudgetRuntime()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 1])

    monkeypatch.setattr(
        "patchsmith.workflow._runtime_for",
        lambda runtime_name, planner_name: runtime,
    )
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            runtime_config={"max_context_files": 2},
        )
    )

    assert runtime.runtime_configs[0]["max_context_files"] == 2
    assert "context_selection_pinned_paths" not in runtime.runtime_configs[0]
    assert runtime.runtime_configs[1]["max_context_files"] == 2
    assert runtime.runtime_configs[1]["context_selection_pinned_paths"] == [
        "src/simple_calc.py",
        "tests/test_repro.py",
    ]


def test_deepagents_retry_refreshes_context_with_feedback_terms(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "simple_calc.py").write_text(
        "def add(left, right):\n    return left - right\n",
        encoding="utf-8",
    )
    (src / "cache_probe.py").write_text(
        "def cache_probe():\n    return 'stale_cache dispatch site'\n",
        encoding="utf-8",
    )
    planner = SequencedFeedbackPlanner()
    sandbox = FeedbackTextSandboxRunner(
        first_stdout="E   AssertionError: cache_probe stale_cache dispatch still active\n"
    )

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(repo),
            issue_text="add returns the wrong result",
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
            top_k=1,
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert planner.context_paths_by_attempt[0] == ["src/simple_calc.py"]
    assert "src/cache_probe.py" in planner.context_paths_by_attempt[1]
    assert planner.runtime_configs[1]["max_context_files"] == 1
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    refresh_event = next(event for event in trace_events if event["node_name"] == "context_refresh")
    assert refresh_event["payload"]["attempt"] == 2
    assert refresh_event["payload"]["limit"] == 4
    assert refresh_event["payload"]["mounted_context_limit"] == 1
    assert "src/cache_probe.py" in refresh_event["payload"]["refreshed_context_paths"]
    assert "src/cache_probe.py" in refresh_event["payload"]["merged_context_paths"]


def test_deepagents_runner_retries_after_rejected_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    planner = RejectedEditFeedbackPlanner()
    sandbox = SequencedSandboxRunner(exit_codes=[1, 0])

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert len(planner.issue_texts) == 2
    assert "Previous agent status:\nno_patch_generated" in planner.issue_texts[1]
    assert "replacement text not found" in planner.issue_texts[1]
    assert "safety gate rejected the previous bounded edit" in planner.issue_texts[1]
    assert "Previous patch plan diagnostics" in planner.issue_texts[1]
    assert "Patch safety gate rejection" in planner.issue_texts[1]
    assert "Old span found in clean target: False" in planner.issue_texts[1]
    assert "Old span occurrences: 0" in planner.issue_texts[1]
    assert "return does_not_exist" in planner.issue_texts[1]
    assert len(sandbox.calls) == 2
    assert "return left + right" in (result.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    retry_event = next(event for event in trace_events if event["node_name"] == "feedback_retry")
    assert "safety_gate_retry" in retry_event["payload"]["retry_labels"]
    assert retry_event["payload"]["retry_failure_class"] == "safety_gate_rejection"


def test_deepagents_runner_marks_high_risk_passing_patch_as_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "runner.py").write_text(
        "import types\n\ndef call(testfunction, filename):\n    return testfunction()\n",
        encoding="utf-8",
    )
    planner = HighRiskPassingPlanner()

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: SequencedSandboxRunner(exit_codes=[0]),
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(repo),
            issue_text="function keeps stale co_filename after file move",
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    report = result.report_path.read_text(encoding="utf-8")
    assert "`patch_validated_quality_warning`" in report
    assert "Risk: `high`" in report
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    analysis_event = next(
        event for event in trace_events if event["event_type"] == "repair_outcome"
    )
    assert analysis_event["status"] == "validated_with_warnings"
    assert analysis_event["payload"]["verdict"] == "patch_validated_quality_warning"
    assert analysis_event["payload"]["patch_quality_severity"] == "high"


def test_deepagents_runner_retries_high_risk_passing_patch_when_budget_remains(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "runner.py").write_text(
        "import types\n\ndef call(testfunction, filename):\n    return testfunction()\n",
        encoding="utf-8",
    )
    planner = HighRiskThenSafePlanner()
    sandbox = SequencedSandboxRunner(exit_codes=[0, 0])

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(repo),
            issue_text="function keeps stale co_filename after file move",
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 0
    assert len(planner.issue_texts) == 2
    assert len(sandbox.calls) == 2
    assert "passed the targeted sandbox command" in planner.issue_texts[1]
    assert "high-risk" in planner.issue_texts[1]
    assert "Do not return the same high-risk diff unchanged" in planner.issue_texts[1]
    assert "Patch quality risk: high" in planner.issue_texts[1]
    assert "code_object_mutation" in planner.issue_texts[1]
    assert "return testfunction(filename)" in (result.repo_path / "src/runner.py").read_text(
        encoding="utf-8"
    )
    final_diff = result.final_diff_path.read_text(encoding="utf-8")
    assert "__code__" not in final_diff
    assert "return testfunction(filename)" in final_diff
    report = result.report_path.read_text(encoding="utf-8")
    assert "`patch_validated`" in report
    assert "Risk: `low`" in report

    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    analysis_events = [event for event in trace_events if event["event_type"] == "repair_outcome"]
    assert [event["status"] for event in analysis_events] == [
        "validated_with_warnings",
        "validated",
    ]
    retry_event = next(event for event in trace_events if event["node_name"] == "feedback_retry")
    assert retry_event["payload"]["repair_verdict"] == "patch_validated_quality_warning"
    assert retry_event["payload"]["patch_quality_severity"] == "high"
    assert retry_event["payload"]["retry_failure_class"] == "quality_risk"
    retry_feedback_path = Path(retry_event["payload"]["retry_feedback_path"])
    retry_feedback_text = retry_feedback_path.read_text(encoding="utf-8")
    assert "Risky diff sha256_12" in retry_feedback_text
    assert "Failure class: `quality_risk`" in retry_feedback_text
    assert "same high-risk diff" in retry_feedback_text
    assert "code_object_mutation" in retry_feedback_text


def test_deepagents_runner_does_not_retry_validation_environment_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug")
    planner = CorrectThenBadFeedbackPlanner()
    sandbox = EnvironmentFailureSandboxRunner()

    monkeypatch.setattr("patchsmith.workflow._planner_for", lambda planner_name: planner)
    monkeypatch.setattr(
        "patchsmith.workflow.create_sandbox_runner",
        lambda *, mode, image: sandbox,
    )

    result = RepairRunner(artifacts_dir=tmp_path / "artifacts").run(
        RunRequest(
            repo=str(fixture / "repo"),
            issue_text=(fixture / "issue.md").read_text(encoding="utf-8"),
            test_command="python3 -m pytest",
            runtime="deepagents",
            planner="deepagents",
            max_retries=1,
            context_provider="native_hybrid",
            retrieval_strategy="native_hybrid",
        )
    )

    assert result.test_result is not None
    assert result.test_result.exit_code == 1
    assert len(planner.issue_texts) == 1
    assert len(sandbox.calls) == 1
    assert "return left + right" in (result.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )
    trace_events = [
        json.loads(line) for line in result.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    assert not any(event["node_name"] == "feedback_retry" for event in trace_events)
    analysis_event = next(
        event for event in trace_events if event["event_type"] == "repair_outcome"
    )
    assert analysis_event["payload"]["failure_category"] == "test_environment_missing_pytest"


class SequencedFeedbackPlanner:
    def __init__(self) -> None:
        self.issue_texts: list[str] = []
        self.runtime_configs: list[dict[str, object]] = []
        self.context_paths_by_attempt: list[list[str]] = []

    def prepare_task(self, task: object) -> None:
        self.runtime_configs.append(dict(getattr(task, "runtime_config", {})))
        self.context_paths_by_attempt.append(
            [context.path for context in getattr(task, "retrieved_context", [])]
        )

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return RepairPlan(
                name="bad_first_patch",
                path="src/simple_calc.py",
                old="return left - right",
                new="return left + 0",
                summary="Intentionally incomplete first patch.",
            )
        return RepairPlan(
            name="feedback_patch",
            path="src/simple_calc.py",
            old="return left - right",
            new="return left + right",
            summary="Use sandbox feedback to repair the failed attempt.",
        )


class TargetHistoryViolationRuntime:
    def __init__(self) -> None:
        self.runtime_configs: list[dict[str, object]] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.runtime_configs.append(dict(task.runtime_config))
        if len(self.runtime_configs) == 1:
            runtime_trace = [
                {
                    "node": "plan",
                    "status": "no_match",
                    "summary": "Repeated target rejected.",
                    "metadata": {
                        "target_history_violation": {
                            "path": "src/rewrite.py",
                            "reason": "selected target path was deprioritized",
                        }
                    },
                }
            ]
            return AgentResult(
                status="no_patch_generated",
                summary="DeepAgents adapter produced no bounded repair plan.",
                final_diff="",
                patch_candidates=[
                    PatchCandidate(
                        candidate_id=f"{task.run_id}-candidate-1",
                        candidate_index=1,
                        generation_strategy="deepagents:target_history_violation",
                        diff="",
                        files_changed=[],
                        selected=True,
                        status="no_patch_generated",
                        risk_notes=["Target-history guard rejected repeated target."],
                    )
                ],
                test_results=[],
                runtime_trace=runtime_trace,
            )
        return AgentResult(
            status="no_patch_generated",
            summary="Stop after observing retry config.",
            final_diff="",
            patch_candidates=[
                PatchCandidate(
                    candidate_id=f"{task.run_id}-candidate-1",
                    candidate_index=1,
                    generation_strategy="deepagents:no_plan",
                    diff="",
                    files_changed=[],
                    selected=True,
                    status="no_patch_generated",
                    risk_notes=["No second patch attempted."],
                )
            ],
            test_results=[],
            runtime_trace=[],
        )


class MountedContextBudgetRuntime:
    def __init__(self) -> None:
        self.runtime_configs: list[dict[str, object]] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.runtime_configs.append(dict(task.runtime_config))
        runtime_trace = []
        if len(self.runtime_configs) == 1:
            runtime_trace = [
                {
                    "node": "plan",
                    "status": "completed",
                    "summary": "Generated a patch with a capped context budget.",
                    "patch_plan": {
                        "path": "src/simple_calc.py",
                        "old": {"sha256_12": hashlib.sha256(b"old").hexdigest()[:12]},
                    },
                    "metadata": {
                        "deepagents_contract": {
                            "context_budget": {
                                "mounted_paths": [
                                    "src/simple_calc.py",
                                    "tests/test_repro.py",
                                ]
                            }
                        }
                    },
                }
            ]
        return AgentResult(
            status="patch_generated",
            summary="Generated a patch.",
            final_diff="diff --git a/src/simple_calc.py b/src/simple_calc.py\n+return 0\n",
            patch_candidates=[
                PatchCandidate(
                    candidate_id=f"{task.run_id}-candidate-1",
                    candidate_index=1,
                    generation_strategy="deepagents:test",
                    diff="",
                    files_changed=["src/simple_calc.py"],
                    selected=True,
                    status="patch_generated",
                    risk_notes=[],
                )
            ],
            test_results=[],
            runtime_trace=runtime_trace,
        )


class CorrectThenBadFeedbackPlanner:
    def __init__(self) -> None:
        self.issue_texts: list[str] = []

    def prepare_task(self, task: object) -> None:
        pass

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return RepairPlan(
                name="correct_patch",
                path="src/simple_calc.py",
                old="return left - right",
                new="return left + right",
                summary="Fix addition.",
            )
        return RepairPlan(
            name="bad_retry_patch",
            path="src/simple_calc.py",
            old="return left + right",
            new="return left - right",
            summary="This retry should not run for environment failures.",
        )


class RejectedEditFeedbackPlanner:
    def __init__(self) -> None:
        self.issue_texts: list[str] = []

    def prepare_task(self, task: object) -> None:
        pass

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return RepairPlan(
                name="bad_span",
                path="src/simple_calc.py",
                old="return does_not_exist",
                new="return left + right",
                summary="Use an old span that does not exist.",
            )
        return RepairPlan(
            name="feedback_patch",
            path="src/simple_calc.py",
            old="return left - right",
            new="return left + right",
            summary="Use feedback to provide the exact old span.",
        )


class HighRiskPassingPlanner:
    def prepare_task(self, task: object) -> None:
        pass

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        return RepairPlan(
            name="high_risk_patch",
            path="src/runner.py",
            old="def call(testfunction, filename):\n    return testfunction()",
            new=(
                "def call(testfunction, filename):\n"
                "    try:\n"
                "        co = testfunction.__code__\n"
                "        if co.co_filename != filename:\n"
                "            try:\n"
                "                testfunction.__code__ = co.replace(co_filename=str(filename))\n"
                "            except Exception:\n"
                "                try:\n"
                "                    testfunction.__code__ = types.CodeType(\n"
                "                        co.co_argcount,\n"
                "                        co.co_posonlyargcount,\n"
                "                        co.co_kwonlyargcount,\n"
                "                        co.co_nlocals,\n"
                "                        co.co_stacksize,\n"
                "                        co.co_flags,\n"
                "                        co.co_code,\n"
                "                        co.co_consts,\n"
                "                        co.co_names,\n"
                "                        co.co_varnames,\n"
                "                        str(filename),\n"
                "                        co.co_name,\n"
                "                        co.co_firstlineno,\n"
                "                        co.co_lnotab,\n"
                "                        co.co_freevars,\n"
                "                        co.co_cellvars,\n"
                "                    )\n"
                "                except Exception:\n"
                "                    pass\n"
                "    except Exception:\n"
                "        pass\n"
                "    return testfunction()"
            ),
            summary="Update stale code-object filenames before calling the test function.",
        )


class HighRiskThenSafePlanner(HighRiskPassingPlanner):
    def __init__(self) -> None:
        self.issue_texts: list[str] = []

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[object],
    ) -> RepairPlan | None:
        self.issue_texts.append(issue_text)
        if len(self.issue_texts) == 1:
            return super().plan(issue_text=issue_text, retrieved_context=retrieved_context)
        return RepairPlan(
            name="low_risk_followup_patch",
            path="src/runner.py",
            old="return testfunction()",
            new="return testfunction(filename)",
            summary="Move to a smaller source behavior change after quality feedback.",
        )


class SequencedSandboxRunner:
    def __init__(self, *, exit_codes: list[int]) -> None:
        self.exit_codes = exit_codes
        self.calls: list[str] = []

    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        self.calls.append(command)
        exit_code = self.exit_codes[len(self.calls) - 1]
        attempt = len(self.calls)
        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=f"stdout from attempt {attempt}\n",
            stderr="" if exit_code == 0 else f"failure from attempt {attempt}\n",
            duration_ms=7,
            timed_out=False,
            policy_decision=CommandPolicyDecision(
                allowed=True,
                reason="allowed",
                tokens=("python3", "-m", "pytest"),
            ),
        )


class EnvironmentFailureSandboxRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        self.calls.append(command)
        return CommandResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr="/Applications/Xcode.app/Contents/Developer/usr/bin/python3: No module named pytest\n",
            duration_ms=7,
            timed_out=False,
            policy_decision=CommandPolicyDecision(
                allowed=True,
                reason="allowed",
                tokens=("python3", "-m", "pytest"),
            ),
        )


class FeedbackTextSandboxRunner:
    def __init__(self, *, first_stdout: str) -> None:
        self.first_stdout = first_stdout
        self.calls: list[str] = []

    def run(self, *, command: str, workspace: Path, timeout_seconds: int = 60) -> CommandResult:
        self.calls.append(command)
        attempt = len(self.calls)
        return CommandResult(
            command=command,
            exit_code=1 if attempt == 1 else 0,
            stdout=self.first_stdout if attempt == 1 else "ok\n",
            stderr="",
            duration_ms=7,
            timed_out=False,
            policy_decision=CommandPolicyDecision(
                allowed=True,
                reason="allowed",
                tokens=("python3", "-m", "pytest"),
            ),
        )


def _retrieved(path: str, *, rank: int, terms: list[str]) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=rank,
        score=1.0,
        method="test",
        matched_terms=terms,
        excerpt=f"excerpt for {path}",
    )
