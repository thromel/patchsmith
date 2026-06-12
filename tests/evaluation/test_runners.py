import json
from pathlib import Path

from patchsmith.evaluation import (
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_retrieval_evaluation,
    run_scaffold_comparison,
    validate_seeded_dataset,
)
from patchsmith.evaluation_models import RepairEvalResult, RepairEvalSummary
from patchsmith.repair_reports import render_repair_eval_report


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


def test_run_repair_evaluation_langgraph_fake_model_tracks_usage(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="langgraph",
        planner="fake_model",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval_fake_model",
    )

    assert len(results) >= 10
    assert summary.runtime == "langgraph"
    assert summary.planner == "fake_model"
    assert summary.model_provider == "offline_fake_model"
    assert summary.estimated_cost_usd == 0.0
    report = (tmp_path / "repair_eval_fake_model" / "repair_report.md").read_text(encoding="utf-8")
    assert "Model provider: `offline_fake_model`" in report


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
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=0.001,
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
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=0.001,
    )

    report = render_repair_eval_report(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        results=[result],
        summary=summary,
    )

    assert "includes live model-provider evidence (`deepagents_openai_chat`)" in report
    assert "not broad production repair quality" in report


def test_run_scaffold_comparison_writes_outputs(tmp_path: Path) -> None:
    results = run_scaffold_comparison(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        variants=["agentless", "heuristic", "deepagents", "openai_agents"],
        context_provider="native_hybrid",
        output_dir=tmp_path / "scaffold_comparison",
    )

    by_scaffold = {result.scaffold: result for result in results}
    assert by_scaffold["agentless"].patch_generated_rate == 0.0
    assert by_scaffold["agentless"].targeted_test_pass_rate == 0.0
    assert by_scaffold["heuristic"].patch_generated_rate == 1.0
    assert by_scaffold["heuristic"].targeted_test_pass_rate == 1.0
    assert by_scaffold["deepagents"].patch_generated_rate == 1.0
    assert by_scaffold["deepagents"].targeted_test_pass_rate == 1.0
    assert by_scaffold["openai_agents"].patch_generated_rate == 1.0
    assert by_scaffold["openai_agents"].targeted_test_pass_rate == 1.0
    assert by_scaffold["agentless"].avg_runtime_nodes == 0.0
    assert by_scaffold["agentless"].avg_debuggability_score == 4.0
    assert by_scaffold["heuristic"].avg_runtime_nodes > 0
    assert by_scaffold["heuristic"].avg_debuggability_score == 5.0
    assert by_scaffold["deepagents"].avg_runtime_nodes >= 6.0
    assert by_scaffold["deepagents"].avg_debuggability_score == 5.0
    assert by_scaffold["openai_agents"].avg_runtime_nodes >= 7.0
    assert by_scaffold["openai_agents"].avg_debuggability_score == 5.0
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
    assert "openai_agents" in report
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
