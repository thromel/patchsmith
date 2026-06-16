import json
from dataclasses import replace
from pathlib import Path

import pytest

from patchsmith.cli import main
from patchsmith.evaluation import (
    ComplexBenchmarkSuiteThresholds,
    complex_benchmark_suite_gate,
    load_complex_benchmark_suite_spec,
    resolve_complex_benchmark_suite_config,
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_retrieval_evaluation,
    run_scaffold_comparison,
    summarize_complex_benchmark,
    summarize_complex_benchmark_suite,
    validate_complex_benchmark_suite_inputs,
    validate_seeded_dataset,
)
from patchsmith.evaluation_models import (
    RepairEvalResult,
    RepairEvalSummary,
    ScaffoldComparisonResult,
)
from patchsmith.repair_reports import (
    render_repair_eval_report,
    render_scaffold_comparison_report,
)


def test_graph_retrieval_dataset_validates(tmp_path: Path) -> None:
    results, summary = validate_seeded_dataset(
        dataset_dir=Path("evals/tasks/graph_retrieval_v1"),
        output_dir=tmp_path / "graph_dataset_validation",
    )

    assert len(results) == 3
    assert summary.valid_tasks == 3
    assert summary.invalid_tasks == 0
    assert summary.warning_count == 0


def test_run_retrieval_evaluation_native_writes_outputs(tmp_path: Path) -> None:
    results, summaries = run_retrieval_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        providers=["native", "native_hybrid", "native_graph"],
        output_dir=tmp_path / "retrieval_eval",
    )

    assert len(results) >= 30
    summary_by_provider = {summary.provider: summary for summary in summaries}
    assert summary_by_provider["native"].avg_top5_touched_recall == 1.0
    assert summary_by_provider["native"].avg_related_test_recall == 1.0
    assert summary_by_provider["native"].avg_context_approx_tokens > 0
    assert summary_by_provider["native_hybrid"].avg_top1_touched_recall == 1.0
    assert summary_by_provider["native_graph"].avg_top1_touched_recall == 1.0
    assert (tmp_path / "retrieval_eval" / "report.md").exists()
    assert (tmp_path / "retrieval_eval" / "results.csv").exists()
    results_json = json.loads(
        (tmp_path / "retrieval_eval" / "results.json").read_text(encoding="utf-8")
    )
    assert results_json[0]["context_count"] > 0
    assert results_json[0]["context_approx_tokens"] > 0
    report = (tmp_path / "retrieval_eval" / "report.md").read_text(encoding="utf-8")
    assert "Avg Tokens" in report


def test_graph_retrieval_evaluation_proves_graph_specific_source_localization(
    tmp_path: Path,
) -> None:
    _results, summaries = run_retrieval_evaluation(
        dataset_dir=Path("evals/tasks/graph_retrieval_v1"),
        providers=["native_hybrid", "native_graph"],
        output_dir=tmp_path / "graph_retrieval_eval",
    )

    summary_by_provider = {summary.provider: summary for summary in summaries}
    assert summary_by_provider["native_hybrid"].avg_top1_touched_recall == 0.0
    assert summary_by_provider["native_graph"].avg_top1_touched_recall == 1.0
    assert summary_by_provider["native_graph"].avg_top3_touched_recall == 1.0
    report = (tmp_path / "graph_retrieval_eval" / "report.md").read_text(encoding="utf-8")
    assert "native_graph" in report


def test_run_repair_evaluation_heuristic_writes_outputs(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="heuristic",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval",
    )

    assert len(results) >= 10
    assert summary.runtime == "heuristic"
    assert summary.planner == "heuristic"
    assert summary.context_provider == "native_hybrid"
    assert summary.model_provider is None
    assert summary.patch_generated_rate == 1.0
    assert summary.targeted_test_pass_rate == 1.0
    assert summary.avg_trace_events > 0
    assert summary.avg_runtime_nodes > 0
    assert summary.avg_debuggability_score >= 4.0
    assert results[0].trace_path is not None
    assert results[0].trace_event_count > 0
    assert (tmp_path / "repair_eval" / "repair_report.md").exists()
    assert (tmp_path / "repair_eval" / "repair_results.csv").exists()


def test_run_repair_evaluation_respects_max_tasks(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="heuristic",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval_limited",
        max_tasks=2,
    )

    assert [result.task_id for result in results] == [
        "task_001_logic_bug",
        "task_002_import_bug",
    ]
    assert summary.attempted_tasks == 2
    assert summary.completed_tasks == 2


def test_run_repair_evaluation_deepagents_fake_model_tracks_usage(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="deepagents",
        planner="fake_model",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval_fake_model",
    )

    assert len(results) >= 10
    assert summary.runtime == "deepagents"
    assert summary.planner == "fake_model"
    assert summary.model_provider == "offline_fake_model"
    assert summary.estimated_cost_usd == 0.0
    assert summary.avg_agent_trajectory_score > 0.0
    report = (tmp_path / "repair_eval_fake_model" / "repair_report.md").read_text(encoding="utf-8")
    assert "Model provider: `offline_fake_model`" in report
    assert "Agent trajectory score" in report


def test_repair_eval_report_labels_live_deepagents_evidence() -> None:
    summary = RepairEvalSummary(
        runtime="deepagents",
        planner="deepagents",
        context_provider="native_hybrid",
        attempted_tasks=1,
        completed_tasks=1,
        patch_generated_rate=1.0,
        targeted_test_pass_rate=1.0,
        avg_latency_ms=1000.0,
        model_provider="deepagents_openai_chat",
        response_count=1,
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=0.001,
        retry_label_counts={"old_span_repair": 1, "test_failure_retry": 1},
    )
    result = RepairEvalResult(
        task_id="task_001_logic_bug",
        runtime="deepagents",
        planner="deepagents",
        context_provider="native_hybrid",
        status="completed",
        error=None,
        patch_generated=True,
        targeted_tests_passed=True,
        test_exit_code=0,
        report_path="/tmp/report.md",
        trace_path="/tmp/traces.jsonl",
        final_diff_path="/tmp/final.diff",
        retrieved_files=["src/simple_calc.py"],
        latency_ms=1000,
        model_provider="deepagents_openai_chat",
        response_count=1,
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=0.001,
        retry_labels=("test_failure_retry", "old_span_repair"),
        retry_label_counts={"old_span_repair": 1, "test_failure_retry": 1},
    )

    report = render_repair_eval_report(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        results=[result],
        summary=summary,
    )

    assert "includes live model-provider evidence (`deepagents_openai_chat`)" in report
    assert "not broad production repair quality" in report
    assert "Model responses: `1`" in report
    assert "Retry label counts: `old_span_repair=1, test_failure_retry=1`" in report
    assert "test_failure_retry,old_span_repair" in report


def test_scaffold_comparison_report_includes_retry_label_counts() -> None:
    result = ScaffoldComparisonResult(
        scaffold="deepagents",
        runtime="deepagents",
        planner="deepagents",
        context_provider="native_hybrid",
        attempted_tasks=1,
        completed_tasks=1,
        patch_generated_rate=1.0,
        targeted_test_pass_rate=1.0,
        avg_latency_ms=1000.0,
        avg_trace_events=10.0,
        avg_runtime_nodes=4.0,
        failed_trace_event_count=0,
        avg_retry_events=2.0,
        retry_label_counts={"old_span_repair": 1, "test_failure_retry": 2},
        avg_debuggability_score=5.0,
        avg_agent_trajectory_score=0.8,
        todo_planning_rate=1.0,
        constrained_filesystem_rate=1.0,
        specialist_review_rate=1.0,
        guardrails_rate=1.0,
        structured_output_rate=1.0,
        retry_feedback_rate=1.0,
        patch_diagnostics_rate=1.0,
        contextual_verifier_rate=1.0,
        model_provider="deepagents_openai_chat",
        response_count=1,
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=0.001,
        repair_report_path="/tmp/repair_report.md",
    )

    report = render_scaffold_comparison_report(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        results=[result],
    )

    assert "Retry label counts: `old_span_repair=1, test_failure_retry=2`" in report
    assert "Model responses: `1`" in report
    assert "old_span_repair=1, test_failure_retry=2" in report


def test_run_scaffold_comparison_writes_outputs(tmp_path: Path) -> None:
    results = run_scaffold_comparison(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        variants=["agentless", "heuristic", "deepagents"],
        context_provider="native_hybrid",
        output_dir=tmp_path / "scaffold_comparison",
        max_tasks=2,
    )

    by_scaffold = {result.scaffold: result for result in results}
    assert by_scaffold["agentless"].patch_generated_rate == 0.0
    assert by_scaffold["agentless"].targeted_test_pass_rate == 0.0
    assert by_scaffold["heuristic"].patch_generated_rate == 1.0
    assert by_scaffold["heuristic"].targeted_test_pass_rate == 1.0
    assert by_scaffold["deepagents"].patch_generated_rate == 1.0
    assert by_scaffold["deepagents"].targeted_test_pass_rate == 1.0
    assert by_scaffold["agentless"].avg_runtime_nodes == 0.0
    assert by_scaffold["agentless"].avg_debuggability_score == 4.0
    assert by_scaffold["heuristic"].avg_runtime_nodes > 0
    assert by_scaffold["heuristic"].avg_debuggability_score == 5.0
    assert by_scaffold["deepagents"].avg_runtime_nodes >= 6.0
    assert by_scaffold["deepagents"].avg_debuggability_score == 5.0
    assert by_scaffold["deepagents"].avg_agent_trajectory_score > 0.0
    assert by_scaffold["deepagents"].retry_label_counts == {}
    assert (tmp_path / "scaffold_comparison" / "scaffold_report.md").exists()
    assert (tmp_path / "scaffold_comparison" / "scaffold_results.csv").exists()
    results_json = json.loads(
        (tmp_path / "scaffold_comparison" / "scaffold_results.json").read_text(encoding="utf-8")
    )
    assert results_json[0]["avg_trace_events"] > 0
    report = (tmp_path / "scaffold_comparison" / "scaffold_report.md").read_text(encoding="utf-8")
    assert "Scaffold Comparison Report" in report
    assert "Debug Score" in report
    assert "agentless" in report
    assert "heuristic" in report
    assert "deepagents" in report
    assert "Agent Trajectory" in report
    assert "dependency-gated adapter evidence" in report


def test_run_patch_search_evaluation_writes_outputs(tmp_path: Path) -> None:
    results, summaries = run_patch_search_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        candidate_counts=[1, 3],
        context_provider="native_hybrid",
        output_dir=tmp_path / "patch_search_eval",
    )

    assert len(results) == 20
    summary_by_variant = {summary.variant: summary for summary in summaries}
    assert summary_by_variant["candidates_1"].success_at_1_rate == 1.0
    assert summary_by_variant["candidates_1"].avg_test_runs == 1.0
    assert summary_by_variant["candidates_3"].success_at_k_rate == 1.0
    assert summary_by_variant["candidates_3"].selected_success_rate == 1.0
    assert summary_by_variant["candidates_3"].avg_test_runs == 3.0
    first_three = next(result for result in results if result.variant == "candidates_3")
    assert len(first_three.candidate_results) == 3
    assert first_three.selected_candidate_index == 1
    assert (tmp_path / "patch_search_eval" / "patch_search_report.md").exists()
    assert (tmp_path / "patch_search_eval" / "patch_search_results.csv").exists()
    results_json = json.loads(
        (tmp_path / "patch_search_eval" / "patch_search_results.json").read_text(encoding="utf-8")
    )
    assert results_json[0]["candidate_results"]
    report = (tmp_path / "patch_search_eval" / "patch_search_report.md").read_text(encoding="utf-8")
    assert "Patch Search Evaluation Report" in report
    assert "Success@k" in report


def test_summarize_complex_benchmark_reads_public_issue_attempts(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    trace_path = attempt_dir / "runs" / "run-1" / "traces.jsonl"
    trace_path.parent.mkdir(parents=True)
    retry_feedback_path = trace_path.parent / "feedback" / "retry_feedback_attempt_1_to_2.md"
    retry_feedback_path.parent.mkdir()
    retry_feedback_path.write_text("# PatchSmith Retry Feedback\n", encoding="utf-8")
    final_diff_path = trace_path.parent / "final.diff"
    final_diff_path.write_text(
        """diff --git a/src/_pytest/python.py b/src/_pytest/python.py
--- a/src/_pytest/python.py
+++ b/src/_pytest/python.py
@@ -160,3 +160,20 @@
 def pytest_pyfunc_call(pyfuncitem):
     testfunction = pyfuncitem.obj
+    try:
+        co = testfunction.__code__
+        if co.co_filename != filename:
+            try:
+                testfunction.__code__ = co.replace(co_filename=str(filename))
+            except Exception:
+                try:
+                    testfunction.__code__ = types.CodeType(
+                        co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
+                        co.co_nlocals, co.co_stacksize, co.co_flags, co.co_code,
+                        co.co_consts, co.co_names, co.co_varnames, str(filename),
+                        co.co_name, co.co_firstlineno, co.co_lnotab,
+                        co.co_freevars, co.co_cellvars,
+                    )
+                except Exception:
+                    pass
+    except Exception:
+        pass
     return None
""",
        encoding="utf-8",
    )
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_name": "retrieve",
                        "event_type": "keyword_search",
                        "status": "completed",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.todo",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {"node": "todo"},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.plan",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {
                            "node": "plan",
                            "metadata": {
                                "model_call": {
                                    "provider": "deepagents_openai_chat",
                                    "response_id": "resp_alpha,resp_beta",
                                    "input_tokens": 100,
                                    "output_tokens": 20,
                                    "total_tokens": 120,
                                    "estimated_cost_usd": 0.001,
                                },
                                "target_localization": [
                                    {"path": "src/_pytest/python.py", "score": 10.0}
                                ],
                                "deepagents_contract": {
                                    "virtual_file_count": 1,
                                    "max_context_files": 0,
                                    "filesystem_policy": {"allowed_read_paths": ["/src/pkg.py"]},
                                    "subagents": [{"name": "patch-reviewer"}],
                                    "patch_selection_policy": {
                                        "patchable_paths": ["src/_pytest/python.py"],
                                        "enforced": True,
                                    },
                                    "response_format": "PatchPlan",
                                    "planning_policy": {
                                        "todos_required": True,
                                        "one_bounded_replacement": True,
                                    },
                                },
                            },
                            "patch_plan": {"status": "matched"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "feedback_retry",
                        "event_type": "repair_retry",
                        "status": "scheduled",
                        "payload": {
                            "retry_feedback_path": str(retry_feedback_path),
                            "retry_labels": [
                                "test_failure_retry",
                                "same_target_retry",
                                "old_span_repair",
                            ],
                            "retry_failure_class": "repeated_target_failure",
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.patch_quality",
                        "event_type": "runtime_node",
                        "status": "low",
                        "payload": {
                            "node": "patch_quality",
                            "quality": {
                                "severity": "low",
                                "score": 0,
                                "findings": [],
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "completed",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "validated",
                        "payload": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "complex_task",
                    "attempt_index": 1,
                    "attempt_count": 2,
                    "repository": "org/repo",
                    "issue_url": "https://example.test/issue",
                    "status": "failed",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 1,
                    "trace_path": str(trace_path),
                    "report_path": str(trace_path.parent / "report.md"),
                    "final_diff_path": str(final_diff_path),
                },
                {
                    "task_id": "complex_task",
                    "attempt_index": 2,
                    "attempt_count": 2,
                    "repository": "org/repo",
                    "issue_url": "https://example.test/issue",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_path),
                    "report_path": str(trace_path.parent / "report.md"),
                    "final_diff_path": str(final_diff_path),
                },
            ]
        ),
        encoding="utf-8",
    )

    results, summary = summarize_complex_benchmark(
        attempt_dir=attempt_dir,
        output_dir=tmp_path / "complex_benchmark",
    )

    assert len(results) == 2
    assert summary.task_count == 2
    assert summary.unique_task_count == 1
    assert summary.repeat_count == 2
    assert summary.unique_attempted_tasks == 1
    assert summary.validated_tasks == 0
    assert summary.failed_tasks == 2
    assert summary.validation_rate == 0.0
    assert summary.tasks_with_validated_attempt == 0
    assert summary.tasks_with_failed_attempts_only == 1
    assert summary.validated_task_pass_at_n_rate == 0.0
    assert summary.live_provider_tasks == 2
    assert summary.model_provider == "deepagents_openai_chat"
    assert summary.response_count == 4
    assert summary.total_tokens == 240
    assert summary.estimated_cost_usd == 0.002
    assert summary.attempted_cost_per_validated_task_usd is None
    assert summary.attempted_tokens_per_validated_task is None
    assert summary.selected_cost_per_validated_task_usd is None
    assert summary.selected_tokens_per_validated_task is None
    assert summary.avg_agent_trajectory_score > 0.0
    assert summary.todo_planning_rate == 1.0
    assert summary.constrained_filesystem_rate == 1.0
    assert summary.specialist_review_rate == 1.0
    assert summary.guardrails_rate == 1.0
    assert summary.structured_output_rate == 1.0
    assert summary.retry_feedback_rate == 1.0
    assert summary.patch_diagnostics_rate == 1.0
    assert summary.avg_process_quality_score == 1.0
    assert summary.process_quality_label_counts == {"solid": 2}
    assert summary.process_quality_flag_counts == {}
    assert summary.process_risky_validated_tasks == 0
    assert summary.avg_retry_events == 1.0
    assert summary.retry_feedback_artifact_tasks == 2
    assert summary.retry_feedback_artifact_count == 2
    assert summary.retry_label_counts == {
        "old_span_repair": 2,
        "same_target_retry": 2,
        "test_failure_retry": 2,
    }
    assert summary.retry_failure_class_counts == {"repeated_target_failure": 2}
    assert summary.avg_deepagents_virtual_file_count == 1.0
    assert summary.context_budgeted_tasks == 0
    assert summary.avg_deepagents_max_context_files == 0.0
    assert summary.quality_warning_tasks == 2
    assert summary.quality_warning_rate == 1.0
    assert summary.target_alignment_available_tasks == 2
    assert summary.target_aligned_tasks == 2
    assert summary.target_misaligned_tasks == 0
    assert summary.target_alignment_rate == 1.0
    assert summary.partial_progress_tasks == 2
    assert summary.avg_progress_score == pytest.approx(0.75)
    assert summary.selected_avg_progress_score == pytest.approx(0.85)
    assert summary.failure_class_counts == {"quality_risk": 2}
    assert summary.selected_failure_class_counts == {"quality_risk": 1}
    assert summary.harness_layer_counts == {"patch_quality": 2}
    assert summary.selected_harness_layer_counts == {"patch_quality": 1}
    assert summary.selected_attempt_count == 1
    assert summary.selected_response_count == 2
    assert summary.selected_validated_tasks == 0
    assert summary.selected_validation_rate == 0.0
    assert results[0].attempt_index == 1
    assert results[0].attempt_count == 2
    assert results[0].response_count == 2
    assert results[1].attempt_index == 2
    assert results[1].attempt_count == 2
    assert results[0].retry_feedback_artifact_count == 1
    assert results[0].retry_event_count == 1
    assert results[0].retry_feedback_artifacts == (str(retry_feedback_path),)
    assert results[0].retry_labels == (
        "test_failure_retry",
        "same_target_retry",
        "old_span_repair",
    )
    assert results[0].retry_label_counts == {
        "old_span_repair": 1,
        "same_target_retry": 1,
        "test_failure_retry": 1,
    }
    assert results[0].retry_failure_classes == ("repeated_target_failure",)
    assert results[0].retry_failure_class_counts == {"repeated_target_failure": 1}
    assert results[0].process_quality_label == "solid"
    assert results[0].process_quality_score == 1.0
    assert results[0].process_quality_flags == ()
    assert results[0].todo_planning is True
    assert results[0].constrained_filesystem is True
    assert results[0].specialist_review is True
    assert results[0].guardrails is True
    assert results[0].structured_output is True
    assert results[0].retry_feedback is True
    assert results[0].patch_diagnostics is True
    assert results[0].patch_quality_severity == "high"
    assert results[0].patch_quality_warning is True
    assert results[0].patch_target_paths == ("src/_pytest/python.py",)
    assert results[0].localized_target_paths == ("src/_pytest/python.py",)
    assert results[0].target_alignment_status == "aligned"
    assert results[0].patch_target_aligned is True
    assert results[0].progress_score == pytest.approx(0.65)
    assert results[0].progress_stage == "target_aligned_patch"
    assert results[0].failure_class == "quality_risk"
    assert results[0].harness_layer == "patch_quality"
    assert results[0].strict_status == "failed"
    assert results[1].status == "validated"
    assert results[1].strict_status == "failed_quality"
    assert results[1].progress_score == pytest.approx(0.85)
    assert results[1].progress_stage == "validated_quality_warning"
    assert results[1].failure_class == "quality_risk"
    assert results[1].harness_layer == "patch_quality"
    assert "manual_code_type_rebuild" in results[0].patch_quality_codes
    report = (tmp_path / "complex_benchmark" / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "Complex Benchmark Report" in report
    assert "complex_task" in report
    assert "deepagents_openai_chat" in report
    assert "Model responses: `4`" in report
    assert "Repeat count: `2`" in report
    assert "Validated task pass@N rate: `0.00`" in report
    assert "Selected progress score: `0.85`" in report
    assert "Partial-progress failed tasks: `2`" in report
    assert "Failure class counts: `quality_risk=2`" in report
    assert "Selected failure class counts: `quality_risk=1`" in report
    assert "Harness layer counts: `patch_quality=2`" in report
    assert "Selected harness layer counts: `patch_quality=1`" in report
    assert "complex_task | 1/2" in report
    assert "Selected Attempts" in report
    assert "Selected validation rate: `0.00`" in report
    assert "strict validation first" in report
    assert "Retry feedback artifacts: `2`" in report
    assert (
        "Retry label counts: `old_span_repair=2, same_target_retry=2, "
        "test_failure_retry=2`" in report
    )
    assert "Retry failure class counts: `repeated_target_failure=2`" in report
    assert "Process quality labels: `solid=2`" in report
    assert "Process quality flags: `none`" in report
    assert "Process-risky validated tasks: `0`" in report
    assert "test_failure_retry,same_target_retry,old_span_repair" in report
    assert "repeated_target_failure" in report
    assert "Average DeepAgents virtual files: `1.00`" in report
    assert "Context-budgeted tasks: `0`" in report
    assert "Quality warning tasks: `2`" in report
    assert "Target alignment rate: `1.00`" in report
    assert "aligned | src/_pytest/python.py | src/_pytest/python.py" in report
    assert "Todo planning rate: `1.00`" in report
    assert "Trajectory Signals" in report
    assert "Process Quality" in report
    assert "todo,filesystem,review,guardrails,structured,retry,diagnostics" in report
    assert "final patch quality was not high-risk" in report
    assert "strict quality-gated validation" in report
    assert "do not count as clean validation" in report
    assert "Raw Status | Strict Status" in report
    assert "Harness Layer" in report
    assert "Follow-up Candidates" in report
    assert "quality_gate_rerun" in report
    assert "acceptance_rubric_verifier" in report
    assert "strict_not_validated" in report
    assert "harness_layer:patch_quality" in report
    assert "failed_quality" in report
    assert "manual_code_type_rebuild" in report
    selected_results = json.loads(
        (tmp_path / "complex_benchmark" / "complex_benchmark_selected_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert selected_results[0]["task_id"] == "complex_task"
    assert selected_results[0]["selected_attempt_index"] == 2
    assert selected_results[0]["strict_status"] == "failed_quality"
    assert selected_results[0]["progress_score"] == pytest.approx(0.85)
    assert selected_results[0]["progress_stage"] == "validated_quality_warning"
    assert selected_results[0]["failure_class"] == "quality_risk"
    assert "manual_code_type_rebuild" in selected_results[0]["patch_quality_codes"]
    followup_candidates = json.loads(
        (tmp_path / "complex_benchmark" / "complex_benchmark_followup_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(followup_candidates) == 2
    assert followup_candidates[0]["task_id"] == "complex_task"
    assert followup_candidates[0]["attempt_index"] == 1
    assert followup_candidates[0]["action"] == "quality_gate_rerun"
    assert followup_candidates[0]["suggested_profile"] == "acceptance_rubric_verifier"
    assert followup_candidates[0]["recommended_env"] == {"OPENAI_API_KEY": "<required>"}
    assert "--task-id" in followup_candidates[0]["recommended_command"]
    assert "complex_task" in followup_candidates[0]["recommended_command"]
    assert "--min-validation-rate" in followup_candidates[0]["validation_command"]
    assert "validation_rate >= 1.0" in followup_candidates[0]["success_criteria"]
    assert followup_candidates[0]["priority"] == 430
    assert "strict_not_validated" in followup_candidates[0]["reasons"]
    assert "quality_risk" in followup_candidates[0]["reasons"]
    assert "failure_class:quality_risk" in followup_candidates[0]["reasons"]
    assert "harness_layer:patch_quality" in followup_candidates[0]["reasons"]
    assert "retry_failure:repeated_target_failure" in followup_candidates[0]["reasons"]
    runbook = (tmp_path / "complex_benchmark" / "complex_benchmark_followup_runbook.md").read_text(
        encoding="utf-8"
    )
    assert "Complex Benchmark Follow-up Runbook" in runbook
    assert "quality_gate_rerun" in runbook
    assert "acceptance_rubric_verifier" in runbook
    assert "OPENAI_API_KEY" in runbook
    assert "execute-public-issue-repairs" in runbook
    assert "eval-complex-suite" in runbook
    progress_gate = complex_benchmark_suite_gate(
        summary,
        min_selected_progress_score=0.90,
    )
    assert progress_gate.status == "failed"
    assert progress_gate.failures == ("selected progress score 0.85 below required 0.90",)
    target_alignment_gate = complex_benchmark_suite_gate(
        summary,
        min_target_alignment_rate=1.0,
    )
    assert target_alignment_gate.status == "passed"
    process_quality_gate = complex_benchmark_suite_gate(
        summary,
        min_process_quality_score=1.0,
        max_process_risky_validated_tasks=0,
    )
    assert process_quality_gate.status == "passed"
    risky_summary = replace(summary, process_risky_validated_tasks=1)
    process_risk_gate = complex_benchmark_suite_gate(
        risky_summary,
        max_process_risky_validated_tasks=0,
    )
    assert process_risk_gate.status == "failed"
    assert process_risk_gate.failures == ("process-risky validated tasks 1 exceeds 0",)


def test_summarize_complex_benchmark_aligns_failure_localized_patch_plan(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    trace_path = attempt_dir / "runs" / "run-1" / "traces.jsonl"
    trace_path.parent.mkdir(parents=True)
    final_diff_path = trace_path.parent / "final.diff"
    final_diff_path.write_text(
        """diff --git a/src/requests/exceptions.py b/src/requests/exceptions.py
--- a/src/requests/exceptions.py
+++ b/src/requests/exceptions.py
@@ -84,1 +84,4 @@
-    \"\"\"The server declared chunked encoding but sent an invalid chunk.\"\"\"
+    \"\"\"The server declared chunked encoding but sent an invalid chunk.
+
+    This can include transient connection resets.
+    \"\"\"
""",
        encoding="utf-8",
    )
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_name": "runtime.plan",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {
                            "node": "plan",
                            "metadata": {
                                "model_call": {
                                    "provider": "deepagents_openai_chat",
                                    "input_tokens": 100,
                                    "output_tokens": 20,
                                    "total_tokens": 120,
                                    "estimated_cost_usd": 0.001,
                                },
                                "deepagents_contract": {
                                    "virtual_file_count": 1,
                                    "max_context_files": 2,
                                    "context_budget_manifest_path": (
                                        "/.patchsmith/context-budget.md"
                                    ),
                                    "repo_map_manifest_path": "/.patchsmith/repo-map.md",
                                    "repo_instructions_manifest_path": (
                                        "/.patchsmith/repo-instructions.md"
                                    ),
                                    "acceptance_rubric_manifest_path": (
                                        "/.patchsmith/acceptance-rubric.md"
                                    ),
                                    "repair_interface_manifest_path": (
                                        "/.patchsmith/repair-interface.md"
                                    ),
                                    "resource_budget": {
                                        "max_model_responses": 12,
                                        "max_model_tokens": 200000,
                                    },
                                    "context_budget": {
                                        "max_context_files": 2,
                                        "retrieved_file_count": 4,
                                        "mounted_file_count": 1,
                                        "omitted_file_count": 3,
                                        "mounted_paths": ["src/requests/exceptions.py"],
                                        "omitted_paths": [
                                            "src/requests/models.py",
                                            "src/requests/sessions.py",
                                            "tests/test_requests.py",
                                        ],
                                    },
                                    "filesystem_policy": {
                                        "allowed_read_paths": [
                                            "/.patchsmith/acceptance-rubric.md",
                                            "/.patchsmith/context-budget.md",
                                            "/.patchsmith/repo-map.md",
                                            "/.patchsmith/repo-instructions.md",
                                            "/.patchsmith/repair-interface.md",
                                            "/src/requests/exceptions.py",
                                        ]
                                    },
                                    "subagents": [{"name": "failure-localizer"}],
                                    "response_format": "PatchPlan",
                                    "planning_policy": {
                                        "todos_required": True,
                                        "one_bounded_replacement": True,
                                        "context_budget_manifest_read_first": True,
                                        "repo_map_manifest_read_first": True,
                                        "repo_instructions_manifest_read_first": True,
                                        "acceptance_rubric_manifest_read_first": True,
                                        "repair_interface_manifest_read_first": True,
                                        "resource_budget_read_first": True,
                                    },
                                },
                                "failure_localization": {
                                    "failure_mechanism": (
                                        "The validation inspects ChunkedEncodingError.__doc__."
                                    ),
                                    "target_rationale": (
                                        "The controlling docstring is defined in "
                                        "src/requests/exceptions.py."
                                    ),
                                },
                            },
                            "patch_plan": {
                                "path": "src/requests/exceptions.py",
                                "status": "matched",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "completed",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "validated",
                        "payload": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "requests_7341_chunked_encoding_docs",
                    "repository": "psf/requests",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_path),
                    "final_diff_path": str(final_diff_path),
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    results, summary = summarize_complex_benchmark(
        attempt_dir=attempt_dir,
        output_dir=tmp_path / "complex_benchmark",
    )

    assert summary.target_alignment_available_tasks == 1
    assert summary.target_aligned_tasks == 1
    assert summary.target_alignment_rate == 1.0
    assert summary.selected_context_target_available_tasks == 1
    assert summary.selected_context_target_covered_tasks == 1
    assert summary.selected_context_target_recall == 1.0
    assert summary.selected_context_target_precision == 1.0
    assert summary.avg_deepagents_virtual_file_count == 1.0
    assert summary.context_budgeted_tasks == 1
    assert summary.context_budget_manifest_tasks == 1
    assert summary.context_budget_omitted_file_count == 3
    assert summary.avg_context_budget_omitted_files == 3.0
    assert summary.repo_map_manifest_tasks == 1
    assert summary.repo_instructions_manifest_tasks == 1
    assert summary.repo_instructions_read_first_rate == 1.0
    assert summary.acceptance_rubric_manifest_tasks == 1
    assert summary.acceptance_rubric_read_first_rate == 1.0
    assert summary.acceptance_rubric_aligned_tasks == 1
    assert summary.acceptance_rubric_alignment_rate == 1.0
    rubric_gate = complex_benchmark_suite_gate(
        summary,
        min_acceptance_rubric_manifest_rate=1.0,
        min_acceptance_rubric_read_first_rate=1.0,
        min_acceptance_rubric_alignment_rate=1.0,
    )
    assert rubric_gate.status == "passed"
    assert summary.repair_interface_manifest_tasks == 1
    assert summary.repair_interface_read_first_rate == 1.0
    assert summary.avg_deepagents_max_context_files == 2.0
    assert summary.resource_budgeted_tasks == 1
    assert summary.resource_budget_read_first_rate == 1.0
    assert summary.avg_resource_budget_max_model_responses == 12.0
    assert summary.avg_resource_budget_max_model_tokens == 200000.0
    assert results[0].patch_target_paths == ("src/requests/exceptions.py",)
    assert results[0].localized_target_paths == ("src/requests/exceptions.py",)
    assert results[0].target_alignment_status == "aligned"
    assert results[0].patch_target_aligned is True
    assert results[0].deepagents_virtual_file_count == 1
    assert results[0].deepagents_virtual_file_paths == ("src/requests/exceptions.py",)
    assert results[0].deepagents_max_context_files == 2
    assert results[0].deepagents_context_budgeted is True
    assert results[0].deepagents_context_budget_manifest_path == ("/.patchsmith/context-budget.md")
    assert results[0].deepagents_context_budget_manifest_read_first is True
    assert results[0].deepagents_context_budget_omitted_file_count == 3
    assert results[0].deepagents_context_budget_omitted_paths == (
        "src/requests/models.py",
        "src/requests/sessions.py",
        "tests/test_requests.py",
    )
    assert results[0].deepagents_repo_map_manifest_path == "/.patchsmith/repo-map.md"
    assert results[0].deepagents_repo_map_manifest_read_first is True
    assert results[0].deepagents_repo_instructions_manifest_path == (
        "/.patchsmith/repo-instructions.md"
    )
    assert results[0].deepagents_repo_instructions_manifest_read_first is True
    assert results[0].deepagents_acceptance_rubric_manifest_path == (
        "/.patchsmith/acceptance-rubric.md"
    )
    assert results[0].deepagents_acceptance_rubric_manifest_read_first is True
    assert results[0].deepagents_acceptance_rubric_aligned is True
    assert results[0].deepagents_repair_interface_manifest_path == (
        "/.patchsmith/repair-interface.md"
    )
    assert results[0].deepagents_repair_interface_manifest_read_first is True
    assert results[0].deepagents_resource_budgeted is True
    assert results[0].deepagents_resource_budget_read_first is True
    assert results[0].deepagents_resource_budget_max_model_responses == 12
    assert results[0].deepagents_resource_budget_max_model_tokens == 200000
    report = (tmp_path / "complex_benchmark" / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "Context-budget manifest tasks: `1`" in report
    assert "Context-budget omitted files: `3`" in report
    assert "Repo-map manifest tasks: `1`" in report
    assert "Repo-instructions manifest tasks: `1`" in report
    assert "Repo-instructions read-first rate: `1.00`" in report
    assert "Acceptance-rubric manifest tasks: `1`" in report
    assert "Acceptance-rubric read-first rate: `1.00`" in report
    assert "Acceptance-rubric aligned tasks: `1`" in report
    assert "Acceptance-rubric alignment rate: `1.00`" in report
    assert "Repair-interface manifest tasks: `1`" in report
    assert "Repair-interface read-first rate: `1.00`" in report
    assert "Resource-budgeted tasks: `1`" in report
    assert "Resource-budget read-first rate: `1.00`" in report
    assert "Average resource response cap: `12.00`" in report
    assert "Average resource token cap: `200000.00`" in report
    assert "Selected context-target available tasks: `1`" in report
    assert "Selected context-target covered tasks: `1`" in report
    assert "Selected context-target recall: `1.00`" in report
    assert "Selected context-target precision: `1.00`" in report
    assert "/.patchsmith/context-budget.md" in report
    assert "/.patchsmith/repo-map.md" in report
    assert "/.patchsmith/acceptance-rubric.md" in report
    assert "/.patchsmith/repair-interface.md" in report


def test_summarize_complex_benchmark_selects_low_cost_validated_attempt(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    runs_dir = attempt_dir / "runs"
    runs_dir.mkdir()
    expensive_trace = _write_complex_trace(
        runs_dir / "expensive" / "traces.jsonl",
        cost=0.50,
        total_tokens=5000,
    )
    cheap_trace = _write_complex_trace(
        runs_dir / "cheap" / "traces.jsonl",
        cost=0.05,
        total_tokens=500,
    )
    failed_trace = _write_complex_trace(
        runs_dir / "failed" / "traces.jsonl",
        cost=0.01,
        total_tokens=100,
        test_status="failed",
        outcome_status="failed",
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "selector_task",
                    "attempt_index": 1,
                    "attempt_count": 3,
                    "repository": "org/repo",
                    "status": "failed",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 1,
                    "trace_path": str(failed_trace),
                },
                {
                    "task_id": "selector_task",
                    "attempt_index": 2,
                    "attempt_count": 3,
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(expensive_trace),
                    "report_path": "/tmp/expensive.md",
                },
                {
                    "task_id": "selector_task",
                    "attempt_index": 3,
                    "attempt_count": 3,
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(cheap_trace),
                    "report_path": "/tmp/cheap.md",
                },
            ]
        ),
        encoding="utf-8",
    )

    _results, summary = summarize_complex_benchmark(
        attempt_dir=attempt_dir,
        output_dir=tmp_path / "complex_selector",
    )

    assert summary.validated_tasks == 2
    assert summary.selected_attempt_count == 1
    assert summary.selected_validated_tasks == 1
    assert summary.selected_validation_rate == 1.0
    assert summary.selected_total_tokens == 500
    assert summary.selected_response_count == 1
    assert summary.selected_estimated_cost_usd == 0.05
    assert summary.selected_virtual_file_count == 3
    assert summary.selected_virtual_files_per_validated_task == 3.0
    assert summary.selected_tokens_per_virtual_file == 500 / 3
    assert summary.selected_responses_per_virtual_file == 1 / 3
    assert summary.attempted_cost_per_validated_task_usd == 0.28
    assert summary.attempted_tokens_per_validated_task == 2800.0
    assert summary.selected_cost_per_validated_task_usd == 0.05
    assert summary.selected_tokens_per_validated_task == 500.0
    assert summary.selected_avg_progress_score == 1.0
    assert summary.failure_class_counts == {
        "tool_or_runtime_failure": 1,
        "validated": 2,
    }
    assert summary.selected_failure_class_counts == {"validated": 1}
    selected_results = json.loads(
        (tmp_path / "complex_selector" / "complex_benchmark_selected_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert selected_results == [
        {
            "task_id": "selector_task",
            "selected_attempt_index": 3,
            "selected_attempt_count": 3,
            "status": "validated",
            "strict_status": "validated",
            "validation_passed": True,
            "patch_quality_severity": "low",
            "patch_quality_codes": [],
            "retry_event_count": 0,
            "response_count": 1,
            "total_tokens": 500,
            "estimated_cost_usd": 0.05,
            "agent_trajectory_score": 0.8571428571428571,
            "report_path": "/tmp/cheap.md",
            "selection_reason": (
                "strict validated, raw_status=validated, quality=low, "
                "target_alignment=unavailable, retries=0, progress=1.00:validated, "
                "failure_class=validated, "
                "cost=$0.050000, tokens=500, responses=1, virtual_files=3, "
                "trajectory=0.86"
            ),
            "progress_score": 1.0,
            "progress_stage": "validated",
            "failure_class": "validated",
        }
    ]
    followup_candidates = json.loads(
        (tmp_path / "complex_selector" / "complex_benchmark_followup_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    expensive_followup = next(
        candidate for candidate in followup_candidates if candidate["attempt_index"] == 2
    )
    assert expensive_followup["action"] == "cost_optimization_rerun"
    assert expensive_followup["suggested_profile"] == "budget_critical_context_cap"
    assert expensive_followup["reasons"] == ["high_cost"]
    assert expensive_followup["recommended_env"] == {"OPENAI_API_KEY": "<required>"}
    assert expensive_followup["recommended_command"] == [
        "uv",
        "run",
        "python",
        "-m",
        "patchsmith.cli",
        "execute-public-issue-repairs",
        "--task-id",
        "selector_task",
        "--runtime",
        "deepagents",
        "--planner",
        "deepagents",
        "--context-provider",
        "native_hybrid",
        "--sandbox-mode",
        "docker",
        "--deepagents-subagents",
        "auto",
        "--deepagents-max-context-files",
        "4",
        "--max-retries",
        "0",
        "--max-actual-model-responses",
        "6",
        "--max-actual-model-tokens",
        "90000",
        "--max-live-cost-usd",
        "0.07",
        "--estimated-cost-per-attempt-usd",
        "0.07",
        "--output",
        (
            "artifacts/experiments/public_issue_corpus_v1/"
            "followup_selector_task_budget_critical_context_cap"
        ),
        "--execute",
        "--json",
    ]
    assert expensive_followup["validation_command"] == [
        "uv",
        "run",
        "python",
        "-m",
        "patchsmith.cli",
        "eval-complex-suite",
        "--attempt-dir",
        (
            "artifacts/experiments/public_issue_corpus_v1/"
            "followup_selector_task_budget_critical_context_cap"
        ),
        "--output",
        "artifacts/experiments/complex_followup_selector_task_budget_critical_context_cap",
        "--min-validation-rate",
        "1.0",
        "--min-live-provider-tasks",
        "1",
        "--min-unique-tasks",
        "1",
        "--max-attempted-cost-per-validated-task-usd",
        "0.07",
        "--max-attempted-tokens-per-validated-task",
        "90000",
        "--max-attempted-responses-per-validated-task",
        "6",
        "--max-attempted-task-cost-usd",
        "0.07",
        "--max-attempted-task-tokens",
        "90000",
        "--max-attempted-task-responses",
        "6",
        "--max-selected-cost-per-validated-task-usd",
        "0.07",
        "--max-selected-tokens-per-validated-task",
        "90000",
        "--max-selected-responses-per-validated-task",
        "6",
        "--max-selected-task-cost-usd",
        "0.07",
        "--max-selected-task-tokens",
        "90000",
        "--max-selected-task-responses",
        "6",
        "--min-process-quality-score",
        "1.0",
        "--max-process-risky-validated-tasks",
        "0",
        "--min-target-alignment-rate",
        "1.0",
        "--json",
    ]
    assert expensive_followup["success_criteria"] == [
        "validation_rate >= 1.0",
        "live_provider_tasks >= 1",
        "max_attempted_task_responses <= 6",
        "max_attempted_task_tokens <= 90000",
        "max_attempted_task_cost_usd <= 0.07",
        "avg_process_quality_score >= 1.0",
        "process_risky_validated_tasks == 0",
        "target_alignment_rate >= 1.0",
    ]
    report = (tmp_path / "complex_selector" / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "Selected validation rate: `1.00`" in report
    assert "Attempted cost per validated task: `$0.280000`" in report
    assert "Attempted tokens per validated task: `2800.00`" in report
    assert "Selected cost per validated task: `$0.050000`" in report
    assert "Selected tokens per validated task: `500.00`" in report
    assert "Selected virtual files: `3`" in report
    assert "Selected virtual files per validated task: `3.00`" in report
    assert "Selected tokens per virtual file: `166.67`" in report
    assert "Selected responses per virtual file: `0.33`" in report
    assert "selector_task | 3/3 | validated | validated" in report
    assert "cost_optimization_rerun" in report
    assert "budget_critical_context_cap" in report
    runbook = (tmp_path / "complex_selector" / "complex_benchmark_followup_runbook.md").read_text(
        encoding="utf-8"
    )
    assert "cost_optimization_rerun" in runbook
    assert "budget_critical_context_cap" in runbook
    assert "--max-actual-model-responses 6" in runbook
    assert "--max-actual-model-tokens 90000" in runbook


def test_summarize_complex_benchmark_aggregates_preflight_gates(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "blocked_task",
                    "repository": "org/repo",
                    "status": "blocked",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": False,
                    "test_exit_code": None,
                    "preflight_status": "blocked",
                    "preflight_gates": [
                        {
                            "name": "sandbox",
                            "status": "skipped",
                            "detail": "sandbox preflight skipped for local mode",
                        },
                        {
                            "name": "model",
                            "status": "blocked",
                            "detail": "OPENAI_API_KEY is required.",
                            "provider": "openai_models",
                            "model": "gpt-test",
                            "provider_status": "missing_credentials",
                        },
                    ],
                },
                {
                    "task_id": "passed_task",
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "preflight_status": "passed",
                    "preflight_gates": [
                        {
                            "name": "sandbox",
                            "status": "skipped",
                            "detail": "sandbox preflight skipped for local mode",
                        },
                        {
                            "name": "model",
                            "status": "passed",
                            "detail": "model visible in provider catalog",
                            "provider": "openai_models",
                            "model": "gpt-test",
                            "provider_status": "available",
                        },
                    ],
                },
                {
                    "task_id": "budget_blocked_task",
                    "repository": "org/repo",
                    "status": "blocked",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": False,
                    "test_exit_code": None,
                    "preflight_status": "blocked",
                    "preflight_gates": [
                        {
                            "name": "sandbox",
                            "status": "skipped",
                            "detail": "sandbox preflight skipped for local mode",
                        },
                        {
                            "name": "model",
                            "status": "passed",
                            "detail": "model visible in provider catalog",
                            "provider": "openai_models",
                            "model": "gpt-test",
                            "provider_status": "available",
                        },
                        {
                            "name": "budget",
                            "status": "blocked",
                            "detail": "projected maximum live cost exceeds configured cap",
                            "projected_cost_usd": "0.020000",
                            "max_live_cost_usd": "0.001000",
                        },
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )

    results, summary = summarize_complex_benchmark(
        attempt_dir=attempt_dir,
        output_dir=tmp_path / "complex_preflight",
    )

    assert summary.task_count == 3
    assert summary.attempted_tasks == 1
    assert summary.validated_tasks == 1
    assert summary.blocked_tasks == 2
    assert summary.preflight_passed_tasks == 1
    assert summary.preflight_skipped_tasks == 0
    assert summary.preflight_blocked_tasks == 2
    assert summary.sandbox_preflight_blocked_tasks == 0
    assert summary.model_preflight_blocked_tasks == 1
    assert summary.budget_preflight_blocked_tasks == 1
    assert summary.failure_class_counts == {"validated": 1}
    assert summary.selected_failure_class_counts == {"validated": 1}
    assert summary.attempted_cost_per_validated_task_usd is None
    assert summary.selected_cost_per_validated_task_usd is None
    assert results[0].preflight_status == "blocked"
    assert results[0].failure_class == "model_preflight_blocked"
    assert results[2].failure_class == "budget_preflight_blocked"
    assert results[0].preflight_gates[1]["name"] == "model"
    assert results[0].preflight_gates[1]["status"] == "blocked"
    report = (tmp_path / "complex_preflight" / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "Preflight blocked tasks: `2`" in report
    assert "Model preflight blocked tasks: `1`" in report
    assert "Budget preflight blocked tasks: `1`" in report
    assert "blocked (sandbox:skipped; model:blocked)" in report
    assert "passed (sandbox:skipped; model:passed)" in report
    assert "blocked (sandbox:skipped; model:passed; budget:blocked)" in report
    results_json = json.loads(
        (tmp_path / "complex_preflight" / "complex_benchmark_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["preflight_gates"][1]["provider_status"] == "missing_credentials"


def test_summarize_complex_benchmark_flags_post_run_budget_overage(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    trace_path = _write_complex_trace(
        attempt_dir / "runs" / "expensive" / "traces.jsonl",
        cost=0.4252785,
        total_tokens=553483,
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "expensive_retry",
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_path),
                    "report_path": "/tmp/report.md",
                    "preflight_status": "passed",
                    "preflight_gates": [
                        {
                            "name": "budget",
                            "status": "passed",
                            "detail": "projected maximum live cost is within configured cap",
                            "max_live_cost_usd": "0.320000",
                            "projected_cost_usd": "0.300000",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = summarize_complex_benchmark(
        attempt_dir=attempt_dir,
        output_dir=tmp_path / "complex_budget_overage",
    )

    assert results[0].live_cost_budget_usd == 0.32
    assert results[0].live_cost_budget_overage is True
    assert results[0].live_cost_budget_overage_usd == pytest.approx(0.1052785)
    assert summary.live_cost_budgeted_tasks == 1
    assert summary.live_cost_budget_overage_tasks == 1
    assert summary.max_live_cost_budget_overage_usd == pytest.approx(0.1052785)
    gate = complex_benchmark_suite_gate(
        summary,
        max_live_cost_budget_overage_tasks=0,
    )
    assert gate.status == "failed"
    assert gate.failures == ("live cost budget overage tasks 1 exceeds 0",)
    report = (tmp_path / "complex_budget_overage" / "complex_benchmark_report.md").read_text(
        encoding="utf-8"
    )
    assert "Live cost budget overage tasks: `1`" in report
    assert "Max live cost budget overage: `$0.105278`" in report
    assert "budget_overage=$0.105278" in report
    results_json = json.loads(
        (tmp_path / "complex_budget_overage" / "complex_benchmark_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["live_cost_budget_overage"] is True


def test_summarize_complex_benchmark_suite_aggregates_saved_attempt_dirs(
    tmp_path: Path,
) -> None:
    attempt_a = tmp_path / "attempt_a"
    attempt_b = tmp_path / "attempt_b"
    attempt_a.mkdir()
    attempt_b.mkdir()
    trace_a = _write_complex_trace(
        attempt_a / "runs" / "a" / "traces.jsonl",
        cost=0.04,
        total_tokens=400,
    )
    trace_b = _write_complex_trace(
        attempt_b / "runs" / "b" / "traces.jsonl",
        cost=0.06,
        total_tokens=600,
    )
    (attempt_a / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "suite_task_a",
                    "repository": "org/repo-a",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_a),
                    "report_path": "/tmp/a.md",
                }
            ]
        ),
        encoding="utf-8",
    )
    (attempt_b / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "suite_task_b",
                    "repository": "org/repo-b",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_b),
                    "report_path": "/tmp/b.md",
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary, attempt_summaries, followup_candidates = summarize_complex_benchmark_suite(
        attempt_dirs=[attempt_a, attempt_b],
        output_dir=tmp_path / "suite",
    )

    assert len(results) == 2
    assert len(attempt_summaries) == 2
    assert followup_candidates == []
    runbook = (tmp_path / "suite" / "complex_benchmark_followup_runbook.md").read_text(
        encoding="utf-8"
    )
    assert "No follow-up candidates" in runbook
    assert summary.task_count == 2
    assert summary.unique_task_count == 2
    assert summary.validated_tasks == 2
    assert summary.validation_rate == 1.0
    assert summary.validated_task_pass_at_n_rate == 1.0
    assert summary.selected_total_tokens == 1000
    assert summary.selected_response_count == 2
    assert summary.selected_estimated_cost_usd == 0.10
    assert summary.selected_cost_per_validated_task_usd == 0.05
    assert summary.selected_tokens_per_validated_task == 500.0
    assert summary.selected_responses_per_validated_task == 1.0
    assert summary.selected_virtual_file_count == 6
    assert summary.selected_virtual_files_per_validated_task == 3.0
    assert summary.selected_tokens_per_virtual_file == pytest.approx(1000 / 6)
    assert summary.selected_responses_per_virtual_file == pytest.approx(2 / 6)
    assert summary.selected_context_target_available_tasks == 2
    assert summary.selected_context_target_covered_tasks == 2
    assert summary.selected_context_target_recall == 1.0
    assert summary.selected_context_target_precision == pytest.approx(2 / 6)
    assert summary.attempted_responses_per_validated_task == 1.0
    assert summary.max_attempted_task_cost_usd == 0.06
    assert summary.max_attempted_task_tokens == 600
    assert summary.max_attempted_task_responses == 1
    assert summary.max_selected_task_cost_usd == 0.06
    assert summary.max_selected_task_tokens == 600
    assert summary.max_selected_task_responses == 1
    assert summary.live_provider_tasks == 2
    assert summary.model_provider == "deepagents_openai_chat"

    suite_report = (tmp_path / "suite" / "complex_benchmark_suite_report.md").read_text(
        encoding="utf-8"
    )
    assert "Complex Benchmark Suite Report" in suite_report
    assert "Attempt directories: `2`" in suite_report
    assert "Selected cost per validated task: `$0.050000`" in suite_report
    assert "Selected responses per validated task: `1.00`" in suite_report
    assert "Selected virtual files: `6`" in suite_report
    assert "Selected tokens per virtual file: `166.67`" in suite_report
    assert "Max selected task tokens: `600`" in suite_report
    assert "Max selected task responses: `1`" in suite_report
    assert str(attempt_a) in suite_report
    assert str(attempt_b) in suite_report
    attempt_summaries_json = json.loads(
        (tmp_path / "suite" / "complex_benchmark_attempt_summaries.json").read_text(
            encoding="utf-8"
        )
    )
    assert [row["validated_tasks"] for row in attempt_summaries_json] == [1, 1]

    passing_gate = complex_benchmark_suite_gate(
        summary,
        min_validation_rate=1.0,
        min_live_provider_tasks=2,
        min_unique_tasks=2,
        max_attempted_cost_per_validated_task_usd=0.05,
        max_attempted_tokens_per_validated_task=500.0,
        max_attempted_responses_per_validated_task=1.0,
        max_attempted_task_cost_usd=0.06,
        max_attempted_task_tokens=600,
        max_attempted_task_responses=1,
        max_selected_cost_per_validated_task_usd=0.05,
        max_selected_tokens_per_validated_task=500.0,
        max_selected_responses_per_validated_task=1.0,
        max_selected_virtual_files_per_validated_task=3.0,
        max_selected_tokens_per_virtual_file=167.0,
        max_selected_responses_per_virtual_file=0.34,
        min_selected_progress_score=1.0,
        min_selected_context_target_recall=1.0,
        min_selected_context_target_precision=0.33,
        max_selected_task_cost_usd=0.06,
        max_selected_task_tokens=600,
        max_selected_task_responses=1,
        max_live_cost_budget_overage_tasks=0,
        min_agent_trajectory_score=0.80,
    )
    assert passing_gate.status == "passed"
    assert passing_gate.failures == ()

    failing_gate = complex_benchmark_suite_gate(
        summary,
        min_unique_tasks=3,
        max_selected_cost_per_validated_task_usd=0.04,
        max_selected_responses_per_validated_task=0.5,
        min_target_alignment_rate=1.0,
    )
    assert failing_gate.status == "failed"
    assert failing_gate.failures == (
        "unique_task_count 2 below required 3",
        "selected cost per validated task $0.050000 exceeds $0.040000",
        "selected responses per validated task 1.00 exceeds 0.50",
        "target alignment rate 0.00 below required 1.00",
    )

    attempted_spend_gate = complex_benchmark_suite_gate(
        summary,
        max_attempted_cost_per_validated_task_usd=0.04,
        max_attempted_tokens_per_validated_task=499.0,
        max_attempted_responses_per_validated_task=0.5,
    )
    assert attempted_spend_gate.status == "failed"
    assert attempted_spend_gate.failures == (
        "attempted cost per validated task $0.050000 exceeds $0.040000",
        "attempted tokens per validated task 500.00 exceeds 499.00",
        "attempted responses per validated task 1.00 exceeds 0.50",
    )

    context_efficiency_gate = complex_benchmark_suite_gate(
        summary,
        max_selected_virtual_files_per_validated_task=2.0,
        max_selected_tokens_per_virtual_file=100.0,
        max_selected_responses_per_virtual_file=0.25,
        min_selected_context_target_precision=0.50,
    )
    assert context_efficiency_gate.status == "failed"
    assert context_efficiency_gate.failures == (
        "selected virtual files per validated task 3.00 exceeds 2.00",
        "selected tokens per virtual file 166.67 exceeds 100.00",
        "selected responses per virtual file 0.33 exceeds 0.25",
        "selected context-target precision 0.33 below required 0.50",
    )

    repo_instructions_gate = complex_benchmark_suite_gate(
        summary,
        min_repo_instructions_manifest_rate=1.0,
        min_repo_instructions_read_first_rate=1.0,
    )
    assert repo_instructions_gate.status == "failed"
    assert repo_instructions_gate.failures == (
        "repo-instructions manifest rate 0.00 below required 1.00",
        "repo-instructions read-first rate 0.00 below required 1.00",
    )

    rubric_gate = complex_benchmark_suite_gate(
        summary,
        min_contextual_verifier_rate=1.0,
        min_acceptance_rubric_manifest_rate=1.0,
        min_acceptance_rubric_read_first_rate=1.0,
        min_acceptance_rubric_alignment_rate=1.0,
    )
    assert rubric_gate.status == "failed"
    assert rubric_gate.failures == (
        "contextual verifier rate 0.00 below required 1.00",
        "acceptance-rubric manifest rate 0.00 below required 1.00",
        "acceptance-rubric read-first rate 0.00 below required 1.00",
        "acceptance-rubric alignment rate 0.00 below required 1.00",
    )

    _, verifier_summary, _, verifier_followups = summarize_complex_benchmark_suite(
        attempt_dirs=[attempt_a, attempt_b],
        output_dir=tmp_path / "suite_verifier_debt",
        thresholds=ComplexBenchmarkSuiteThresholds(
            min_contextual_verifier_rate=1.0,
            min_acceptance_rubric_manifest_rate=1.0,
            min_acceptance_rubric_read_first_rate=1.0,
            min_acceptance_rubric_alignment_rate=1.0,
        ),
    )

    assert verifier_summary.validation_rate == 1.0
    assert len(verifier_followups) == 2
    assert {candidate.task_id for candidate in verifier_followups} == {
        "suite_task_a",
        "suite_task_b",
    }
    first_followup = verifier_followups[0]
    assert first_followup.action == "verifier_contract_rerun"
    assert first_followup.suggested_profile == "acceptance_rubric_verifier"
    assert first_followup.priority == 400
    assert first_followup.reasons == (
        "contextual_verifier_missing",
        "acceptance_rubric_manifest_missing",
        "acceptance_rubric_read_first_missing",
        "acceptance_rubric_alignment_missing",
    )
    assert "--min-contextual-verifier-rate" in first_followup.validation_command
    assert "--min-acceptance-rubric-alignment-rate" in first_followup.validation_command
    assert "contextual_verifier_rate >= 1.0" in first_followup.success_criteria
    assert "acceptance_rubric_alignment_rate >= 1.0" in first_followup.success_criteria
    verifier_runbook = (
        tmp_path / "suite_verifier_debt" / "complex_benchmark_followup_runbook.md"
    ).read_text(encoding="utf-8")
    assert "verifier_contract_rerun" in verifier_runbook
    assert "--min-contextual-verifier-rate 1.0" in verifier_runbook
    verifier_suite_report = (
        tmp_path / "suite_verifier_debt" / "complex_benchmark_suite_report.md"
    ).read_text(encoding="utf-8")
    assert "verifier_contract_rerun" in verifier_suite_report

    task_outlier_gate = complex_benchmark_suite_gate(
        summary,
        max_attempted_task_cost_usd=0.05,
        max_attempted_task_tokens=500,
        max_attempted_task_responses=0,
        max_selected_task_cost_usd=0.05,
        max_selected_task_tokens=500,
        max_selected_task_responses=0,
    )
    assert task_outlier_gate.status == "failed"
    assert task_outlier_gate.failures == (
        "max attempted task cost $0.060000 exceeds $0.050000",
        "max attempted task tokens 600 exceeds 500",
        "max attempted task responses 1 exceeds 0",
        "max selected task cost $0.060000 exceeds $0.050000",
        "max selected task tokens 600 exceeds 500",
        "max selected task responses 1 exceeds 0",
    )


def test_eval_complex_suite_accepts_suite_spec(tmp_path: Path, capsys) -> None:
    attempt_a = tmp_path / "attempt_a"
    attempt_b = tmp_path / "attempt_b"
    attempt_a.mkdir()
    attempt_b.mkdir()
    trace_a = _write_complex_trace(
        attempt_a / "runs" / "a" / "traces.jsonl",
        cost=0.04,
        total_tokens=400,
        repo_instructions=True,
        acceptance_rubric=True,
    )
    trace_b = _write_complex_trace(
        attempt_b / "runs" / "b" / "traces.jsonl",
        cost=0.06,
        total_tokens=600,
        repo_instructions=True,
        acceptance_rubric=True,
    )
    _write_complex_attempt_results(
        attempt_a,
        task_id="suite_spec_task_a",
        trace_path=trace_a,
        report_path="/tmp/a.md",
    )
    _write_complex_attempt_results(
        attempt_b,
        task_id="suite_spec_task_b",
        trace_path=trace_b,
        report_path="/tmp/b.md",
    )
    output_dir = tmp_path / "suite_from_spec"
    suite_spec_path = tmp_path / "suite_spec.json"
    suite_spec_path.write_text(
        json.dumps(
            {
                "benchmark": "public_issue_repair_attempts",
                "attempt_dirs": [str(attempt_a), str(attempt_b)],
                "output_dir": str(output_dir),
                "gate": {
                    "min_validation_rate": 1.0,
                    "min_live_provider_tasks": 2,
                    "min_unique_tasks": 2,
                    "max_attempted_cost_per_validated_task_usd": 0.05,
                    "max_attempted_tokens_per_validated_task": 500.0,
                    "max_attempted_responses_per_validated_task": 1.0,
                    "max_selected_cost_per_validated_task_usd": 0.05,
                    "max_selected_tokens_per_validated_task": 500.0,
                    "max_selected_responses_per_validated_task": 1.0,
                    "max_selected_virtual_files_per_validated_task": 3.0,
                    "max_selected_tokens_per_virtual_file": 167.0,
                    "max_selected_responses_per_virtual_file": 0.34,
                    "min_selected_progress_score": 0.90,
                    "min_selected_context_target_recall": 1.0,
                    "min_selected_context_target_precision": 0.33,
                    "max_live_cost_budget_overage_tasks": 0,
                    "min_agent_trajectory_score": 0.80,
                    "min_contextual_verifier_rate": 0.90,
                    "min_process_quality_score": 1.0,
                    "max_process_risky_validated_tasks": 0,
                    "min_repo_instructions_manifest_rate": 0.90,
                    "min_repo_instructions_read_first_rate": 0.90,
                    "min_acceptance_rubric_manifest_rate": 0.90,
                    "min_acceptance_rubric_read_first_rate": 0.90,
                    "min_acceptance_rubric_alignment_rate": 0.90,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    spec = load_complex_benchmark_suite_spec(suite_spec_path)

    assert spec.attempt_dirs == (attempt_a, attempt_b)
    assert spec.output_dir == output_dir
    assert spec.min_live_provider_tasks == 2
    assert spec.max_attempted_responses_per_validated_task == 1.0
    assert spec.max_selected_responses_per_validated_task == 1.0
    assert spec.max_selected_virtual_files_per_validated_task == 3.0
    assert spec.max_selected_tokens_per_virtual_file == 167.0
    assert spec.max_selected_responses_per_virtual_file == 0.34
    assert spec.min_selected_progress_score == 0.90
    assert spec.min_selected_context_target_recall == 1.0
    assert spec.min_selected_context_target_precision == 0.33
    assert spec.max_live_cost_budget_overage_tasks == 0
    assert spec.min_contextual_verifier_rate == 0.90
    assert spec.min_process_quality_score == 1.0
    assert spec.max_process_risky_validated_tasks == 0
    assert spec.min_repo_instructions_manifest_rate == 0.90
    assert spec.min_repo_instructions_read_first_rate == 0.90
    assert spec.min_acceptance_rubric_manifest_rate == 0.90
    assert spec.min_acceptance_rubric_read_first_rate == 0.90
    assert spec.min_acceptance_rubric_alignment_rate == 0.90

    validate_exit_code = main(
        [
            "eval-complex-suite",
            "--suite-spec",
            str(suite_spec_path),
            "--validate-only",
            "--json",
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)

    assert validate_exit_code == 0
    assert validate_payload["preflight"]["status"] == "passed"
    assert validate_payload["preflight"]["attempt_dir_count"] == 2
    assert validate_payload["preflight"]["result_file_count"] == 2
    assert validate_payload["preflight"]["gate_threshold_count"] == 25

    exit_code = main(["eval-complex-suite", "--suite-spec", str(suite_spec_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["followup_candidates"] == []
    assert (output_dir / "complex_benchmark_suite_report.md").exists()
    gate = json.loads(
        (output_dir / "complex_benchmark_suite_gate.json").read_text(encoding="utf-8")
    )
    assert gate["status"] == "passed"

    missing_preflight = validate_complex_benchmark_suite_inputs(
        attempt_dirs=[tmp_path / "missing_attempt"],
        output_dir=tmp_path / "missing_suite",
        benchmark="public_issue_repair_attempts",
        gate_threshold_count=1,
    )

    assert missing_preflight.status == "failed"
    assert missing_preflight.missing_attempt_dirs == (str(tmp_path / "missing_attempt"),)


def test_public_issue_verifier_suite_template_requires_verifier_gates() -> None:
    spec = load_complex_benchmark_suite_spec(
        Path("evals/issue_corpora/public_issue_smoke_v1/complex_suite_verifier.template.json")
    )

    assert spec.benchmark == "public_issue_repair_attempts"
    assert len(spec.attempt_dirs) == 3
    assert spec.min_contextual_verifier_rate == 1.0
    assert spec.min_acceptance_rubric_manifest_rate == 1.0
    assert spec.min_acceptance_rubric_read_first_rate == 1.0
    assert spec.min_acceptance_rubric_alignment_rate == 1.0
    assert spec.thresholds.count == 28


def test_complex_suite_config_resolves_spec_and_explicit_overrides(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "suite_spec.json"
    attempt_a = tmp_path / "attempt_a"
    attempt_b = tmp_path / "attempt_b"
    spec_output = tmp_path / "spec_output"
    explicit_output = tmp_path / "explicit_output"
    spec_path.write_text(
        json.dumps(
            {
                "benchmark": "spec_benchmark",
                "attempt_dirs": [str(attempt_a)],
                "output_dir": str(spec_output),
                "gate": {
                    "min_validation_rate": 0.50,
                    "min_unique_tasks": 1,
                    "max_attempted_tokens_per_validated_task": 1200.0,
                    "max_attempted_responses_per_validated_task": 12.0,
                    "max_attempted_task_tokens": 900,
                    "max_attempted_task_responses": 9,
                    "max_selected_tokens_per_validated_task": 1000.0,
                    "max_selected_responses_per_validated_task": 10.0,
                    "max_selected_virtual_files_per_validated_task": 4.0,
                    "max_selected_tokens_per_virtual_file": 250.0,
                    "max_selected_responses_per_virtual_file": 2.5,
                    "min_selected_progress_score": 0.85,
                    "min_selected_context_target_recall": 0.90,
                    "min_selected_context_target_precision": 0.50,
                    "max_selected_task_tokens": 800,
                    "max_selected_task_responses": 8,
                    "max_live_cost_budget_overage_tasks": 0,
                    "min_contextual_verifier_rate": 0.60,
                    "min_target_alignment_rate": 0.75,
                    "min_repo_instructions_manifest_rate": 0.65,
                    "min_repo_instructions_read_first_rate": 0.55,
                    "min_acceptance_rubric_manifest_rate": 0.80,
                    "min_acceptance_rubric_read_first_rate": 0.70,
                    "min_acceptance_rubric_alignment_rate": 0.60,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    spec = load_complex_benchmark_suite_spec(spec_path)

    config = resolve_complex_benchmark_suite_config(
        suite_spec=spec,
        attempt_dirs=[attempt_b],
        output_dir=explicit_output,
        benchmark="explicit_benchmark",
        min_validation_rate=0.90,
        min_live_provider_tasks=2,
        max_live_cost_budget_overage_tasks=1,
    )

    assert config.benchmark == "explicit_benchmark"
    assert config.attempt_dirs == (attempt_b,)
    assert config.output_dir == explicit_output
    assert config.gate_requested is True
    assert config.thresholds.min_validation_rate == 0.90
    assert config.thresholds.min_live_provider_tasks == 2
    assert config.thresholds.min_unique_tasks == 1
    assert config.thresholds.max_attempted_tokens_per_validated_task == 1200.0
    assert config.thresholds.max_attempted_responses_per_validated_task == 12.0
    assert config.thresholds.max_attempted_task_tokens == 900
    assert config.thresholds.max_attempted_task_responses == 9
    assert config.thresholds.max_selected_tokens_per_validated_task == 1000.0
    assert config.thresholds.max_selected_responses_per_validated_task == 10.0
    assert config.thresholds.max_selected_virtual_files_per_validated_task == 4.0
    assert config.thresholds.max_selected_tokens_per_virtual_file == 250.0
    assert config.thresholds.max_selected_responses_per_virtual_file == 2.5
    assert config.thresholds.min_selected_progress_score == 0.85
    assert config.thresholds.min_selected_context_target_recall == 0.90
    assert config.thresholds.min_selected_context_target_precision == 0.50
    assert config.thresholds.max_selected_task_tokens == 800
    assert config.thresholds.max_selected_task_responses == 8
    assert config.thresholds.max_live_cost_budget_overage_tasks == 1
    assert config.thresholds.min_contextual_verifier_rate == 0.60
    assert config.thresholds.min_target_alignment_rate == 0.75
    assert config.thresholds.min_repo_instructions_manifest_rate == 0.65
    assert config.thresholds.min_repo_instructions_read_first_rate == 0.55
    assert config.thresholds.min_acceptance_rubric_manifest_rate == 0.80
    assert config.thresholds.min_acceptance_rubric_read_first_rate == 0.70
    assert config.thresholds.min_acceptance_rubric_alignment_rate == 0.60
    assert config.thresholds.count == 25

    default_config = resolve_complex_benchmark_suite_config()

    assert default_config.benchmark == "public_issue_repair_attempts"
    assert default_config.attempt_dirs == ()
    assert default_config.gate_requested is False
    assert default_config.thresholds.count == 0


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        (
            {"min_validation_rate": 1.1},
            "complex benchmark suite threshold min_validation_rate must be between 0 and 1",
        ),
        (
            {"min_live_provider_tasks": -1},
            "complex benchmark suite threshold min_live_provider_tasks must be non-negative",
        ),
        (
            {"min_unique_tasks": -1},
            "complex benchmark suite threshold min_unique_tasks must be non-negative",
        ),
        (
            {"max_attempted_cost_per_validated_task_usd": -1.0},
            (
                "complex benchmark suite threshold "
                "max_attempted_cost_per_validated_task_usd must be non-negative"
            ),
        ),
        (
            {"max_attempted_tokens_per_validated_task": -1.0},
            (
                "complex benchmark suite threshold "
                "max_attempted_tokens_per_validated_task must be non-negative"
            ),
        ),
        (
            {"max_attempted_responses_per_validated_task": -1.0},
            (
                "complex benchmark suite threshold "
                "max_attempted_responses_per_validated_task must be non-negative"
            ),
        ),
        (
            {"max_attempted_task_cost_usd": -1.0},
            ("complex benchmark suite threshold max_attempted_task_cost_usd must be non-negative"),
        ),
        (
            {"max_attempted_task_tokens": -1},
            ("complex benchmark suite threshold max_attempted_task_tokens must be non-negative"),
        ),
        (
            {"max_attempted_task_responses": -1},
            ("complex benchmark suite threshold max_attempted_task_responses must be non-negative"),
        ),
        (
            {"max_selected_cost_per_validated_task_usd": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_cost_per_validated_task_usd must be non-negative"
            ),
        ),
        (
            {"max_selected_tokens_per_validated_task": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_tokens_per_validated_task must be non-negative"
            ),
        ),
        (
            {"max_selected_responses_per_validated_task": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_responses_per_validated_task must be non-negative"
            ),
        ),
        (
            {"max_selected_virtual_files_per_validated_task": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_virtual_files_per_validated_task must be non-negative"
            ),
        ),
        (
            {"max_selected_tokens_per_virtual_file": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_tokens_per_virtual_file must be non-negative"
            ),
        ),
        (
            {"max_selected_responses_per_virtual_file": -1.0},
            (
                "complex benchmark suite threshold "
                "max_selected_responses_per_virtual_file must be non-negative"
            ),
        ),
        (
            {"min_selected_context_target_recall": 1.1},
            (
                "complex benchmark suite threshold "
                "min_selected_context_target_recall must be between 0 and 1"
            ),
        ),
        (
            {"min_selected_context_target_precision": -0.1},
            (
                "complex benchmark suite threshold "
                "min_selected_context_target_precision must be between 0 and 1"
            ),
        ),
        (
            {"min_acceptance_rubric_manifest_rate": 1.1},
            (
                "complex benchmark suite threshold "
                "min_acceptance_rubric_manifest_rate must be between 0 and 1"
            ),
        ),
        (
            {"min_repo_instructions_manifest_rate": 1.1},
            (
                "complex benchmark suite threshold "
                "min_repo_instructions_manifest_rate must be between 0 and 1"
            ),
        ),
        (
            {"min_repo_instructions_read_first_rate": -0.1},
            (
                "complex benchmark suite threshold "
                "min_repo_instructions_read_first_rate must be between 0 and 1"
            ),
        ),
        (
            {"min_acceptance_rubric_read_first_rate": -0.1},
            (
                "complex benchmark suite threshold "
                "min_acceptance_rubric_read_first_rate must be between 0 and 1"
            ),
        ),
        (
            {"min_acceptance_rubric_alignment_rate": 1.1},
            (
                "complex benchmark suite threshold "
                "min_acceptance_rubric_alignment_rate must be between 0 and 1"
            ),
        ),
        (
            {"max_selected_task_cost_usd": -1.0},
            ("complex benchmark suite threshold max_selected_task_cost_usd must be non-negative"),
        ),
        (
            {"max_selected_task_tokens": -1},
            ("complex benchmark suite threshold max_selected_task_tokens must be non-negative"),
        ),
        (
            {"max_selected_task_responses": -1},
            ("complex benchmark suite threshold max_selected_task_responses must be non-negative"),
        ),
        (
            {"max_live_cost_budget_overage_tasks": -1},
            (
                "complex benchmark suite threshold "
                "max_live_cost_budget_overage_tasks must be non-negative"
            ),
        ),
        (
            {"min_agent_trajectory_score": 1.1},
            (
                "complex benchmark suite threshold "
                "min_agent_trajectory_score must be between 0 and 1"
            ),
        ),
        (
            {"min_selected_progress_score": 1.1},
            (
                "complex benchmark suite threshold "
                "min_selected_progress_score must be between 0 and 1"
            ),
        ),
        (
            {"min_contextual_verifier_rate": -0.1},
            (
                "complex benchmark suite threshold "
                "min_contextual_verifier_rate must be between 0 and 1"
            ),
        ),
        (
            {"min_target_alignment_rate": -0.1},
            ("complex benchmark suite threshold min_target_alignment_rate must be between 0 and 1"),
        ),
    ],
)
def test_complex_suite_config_rejects_invalid_explicit_thresholds(
    overrides: dict[str, float | int],
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        resolve_complex_benchmark_suite_config(**overrides)


def test_eval_complex_suite_rejects_invalid_explicit_threshold(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "complex benchmark suite threshold "
            "max_attempted_tokens_per_validated_task must be non-negative"
        ),
    ):
        main(
            [
                "eval-complex-suite",
                "--attempt-dir",
                str(tmp_path),
                "--max-attempted-tokens-per-validated-task",
                "-1",
                "--validate-only",
            ]
        )


def test_complex_suite_spec_rejects_invalid_thresholds(tmp_path: Path) -> None:
    spec_path = tmp_path / "bad_suite_spec.json"
    invalid_specs = [
        (
            {"min_validation_rate": 1.1},
            "gate.min_validation_rate must be between 0 and 1",
        ),
        (
            {"min_live_provider_tasks": -1},
            "gate.min_live_provider_tasks must be non-negative",
        ),
        (
            {"max_selected_tokens_per_validated_task": -1},
            "gate.max_selected_tokens_per_validated_task must be non-negative",
        ),
        (
            {"max_attempted_cost_per_validated_task_usd": -1},
            "gate.max_attempted_cost_per_validated_task_usd must be non-negative",
        ),
        (
            {"max_attempted_tokens_per_validated_task": -1},
            "gate.max_attempted_tokens_per_validated_task must be non-negative",
        ),
        (
            {"max_attempted_responses_per_validated_task": -1},
            "gate.max_attempted_responses_per_validated_task must be non-negative",
        ),
        (
            {"max_attempted_task_cost_usd": -1},
            "gate.max_attempted_task_cost_usd must be non-negative",
        ),
        (
            {"max_attempted_task_tokens": -1},
            "gate.max_attempted_task_tokens must be non-negative",
        ),
        (
            {"max_attempted_task_responses": -1},
            "gate.max_attempted_task_responses must be non-negative",
        ),
        (
            {"min_agent_trajectory_score": True},
            "gate.min_agent_trajectory_score must be a number",
        ),
        (
            {"min_selected_progress_score": -0.1},
            "gate.min_selected_progress_score must be between 0 and 1",
        ),
        (
            {"min_contextual_verifier_rate": 1.1},
            "gate.min_contextual_verifier_rate must be between 0 and 1",
        ),
        (
            {"max_selected_task_cost_usd": -1},
            "gate.max_selected_task_cost_usd must be non-negative",
        ),
        (
            {"max_selected_task_tokens": -1},
            "gate.max_selected_task_tokens must be non-negative",
        ),
        (
            {"max_selected_responses_per_validated_task": -1},
            "gate.max_selected_responses_per_validated_task must be non-negative",
        ),
        (
            {"max_selected_virtual_files_per_validated_task": -1},
            "gate.max_selected_virtual_files_per_validated_task must be non-negative",
        ),
        (
            {"max_selected_tokens_per_virtual_file": -1},
            "gate.max_selected_tokens_per_virtual_file must be non-negative",
        ),
        (
            {"max_selected_responses_per_virtual_file": -1},
            "gate.max_selected_responses_per_virtual_file must be non-negative",
        ),
        (
            {"min_selected_context_target_recall": 1.1},
            "gate.min_selected_context_target_recall must be between 0 and 1",
        ),
        (
            {"min_selected_context_target_precision": -0.1},
            "gate.min_selected_context_target_precision must be between 0 and 1",
        ),
        (
            {"min_repo_instructions_manifest_rate": 1.1},
            "gate.min_repo_instructions_manifest_rate must be between 0 and 1",
        ),
        (
            {"min_repo_instructions_read_first_rate": -0.1},
            "gate.min_repo_instructions_read_first_rate must be between 0 and 1",
        ),
        (
            {"min_acceptance_rubric_manifest_rate": 1.1},
            "gate.min_acceptance_rubric_manifest_rate must be between 0 and 1",
        ),
        (
            {"min_acceptance_rubric_read_first_rate": -0.1},
            "gate.min_acceptance_rubric_read_first_rate must be between 0 and 1",
        ),
        (
            {"min_acceptance_rubric_alignment_rate": 1.1},
            "gate.min_acceptance_rubric_alignment_rate must be between 0 and 1",
        ),
        (
            {"max_selected_task_responses": -1},
            "gate.max_selected_task_responses must be non-negative",
        ),
        (
            {"max_live_cost_budget_overage_tasks": -1},
            "gate.max_live_cost_budget_overage_tasks must be non-negative",
        ),
        (
            {"min_target_alignment_rate": 1.1},
            "gate.min_target_alignment_rate must be between 0 and 1",
        ),
    ]

    for gate, expected_error in invalid_specs:
        spec_path.write_text(
            json.dumps(
                {
                    "benchmark": "public_issue_repair_attempts",
                    "attempt_dirs": [str(tmp_path / "attempt")],
                    "gate": gate,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=expected_error):
            load_complex_benchmark_suite_spec(spec_path)


def _write_complex_trace(
    path: Path,
    *,
    cost: float,
    total_tokens: int,
    response_count: int | None = 1,
    virtual_file_count: int = 3,
    max_context_files: int = 0,
    repo_instructions: bool = False,
    acceptance_rubric: bool = False,
    test_status: str = "completed",
    outcome_status: str = "validated",
) -> Path:
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_name": "runtime.todo",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {"node": "todo"},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.plan",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {
                            "node": "plan",
                            "metadata": {
                                "model_call": {
                                    "provider": "deepagents_openai_chat",
                                    **(
                                        {"response_count": response_count}
                                        if response_count is not None
                                        else {}
                                    ),
                                    "input_tokens": total_tokens - 10,
                                    "output_tokens": 10,
                                    "total_tokens": total_tokens,
                                    "estimated_cost_usd": cost,
                                },
                                "deepagents_contract": {
                                    "virtual_file_count": virtual_file_count,
                                    "max_context_files": max_context_files,
                                    **(
                                        {
                                            "repo_instructions_manifest_path": (
                                                "/.patchsmith/repo-instructions.md"
                                            )
                                        }
                                        if repo_instructions
                                        else {}
                                    ),
                                    **(
                                        {
                                            "acceptance_rubric_manifest_path": (
                                                "/.patchsmith/acceptance-rubric.md"
                                            )
                                        }
                                        if acceptance_rubric
                                        else {}
                                    ),
                                    "filesystem_policy": {
                                        "allowed_read_paths": [
                                            *(
                                                ["/.patchsmith/repo-instructions.md"]
                                                if repo_instructions
                                                else []
                                            ),
                                            *(
                                                ["/.patchsmith/acceptance-rubric.md"]
                                                if acceptance_rubric
                                                else []
                                            ),
                                            "/src/pkg.py",
                                            "/src/unused.py",
                                            "/tests/test_pkg.py",
                                        ]
                                    },
                                    "subagents": [{"name": "patch-reviewer"}],
                                    "response_format": "PatchPlan",
                                    "planning_policy": {
                                        "todos_required": True,
                                        "one_bounded_replacement": True,
                                        **(
                                            {"repo_instructions_manifest_read_first": True}
                                            if repo_instructions
                                            else {}
                                        ),
                                        **(
                                            {"acceptance_rubric_manifest_read_first": True}
                                            if acceptance_rubric
                                            else {}
                                        ),
                                    },
                                },
                                "failure_localization": {
                                    "failure_mechanism": "The saved validation inspects src/pkg.py.",
                                    "target_rationale": "src/pkg.py owns the failing behavior.",
                                },
                            },
                            "patch_plan": {"path": "src/pkg.py", "status": "matched"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.patch_quality",
                        "event_type": "runtime_node",
                        "status": "low",
                        "payload": {
                            "node": "patch_quality",
                            "quality": {"severity": "low", "score": 0, "findings": []},
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": test_status,
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": outcome_status,
                        "payload": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_complex_attempt_results(
    attempt_dir: Path,
    *,
    task_id: str,
    trace_path: Path,
    report_path: str,
) -> None:
    final_diff_path = trace_path.parent / "final.diff"
    final_diff_path.write_text(
        "diff --git a/src/pkg.py b/src/pkg.py\n"
        "--- a/src/pkg.py\n"
        "+++ b/src/pkg.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n",
        encoding="utf-8",
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_path),
                    "final_diff_path": str(final_diff_path),
                    "report_path": report_path,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
