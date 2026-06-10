import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.evaluation import (
    load_seeded_tasks,
    preflight_issue_corpus_repositories,
    recall,
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_scaffold_comparison,
    run_retrieval_evaluation,
    top_k_recall,
    validate_issue_corpus,
    validate_seeded_dataset,
)


def test_recall_metrics() -> None:
    assert top_k_recall(["src/a.py", "src/b.py"], ["src/a.py"], 1) == 1.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 1) == 0.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 3) == 1.0
    assert recall(["tests/test_a.py"], ["tests/test_a.py", "tests/test_b.py"]) == 0.5


def test_load_seeded_tasks() -> None:
    tasks = load_seeded_tasks(Path("evals/tasks/seeded_bugs_v1"))

    assert tasks
    assert tasks[0].task_id == "task_001_logic_bug"
    assert tasks[0].expected_touched_files == ["src/simple_calc.py"]


def test_validate_seeded_dataset_writes_outputs(tmp_path: Path) -> None:
    results, summary = validate_seeded_dataset(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        output_dir=tmp_path / "dataset_validation",
    )

    assert len(results) == 10
    assert summary.task_count == 10
    assert summary.valid_tasks == 10
    assert summary.invalid_tasks == 0
    assert summary.error_count == 0
    assert (tmp_path / "dataset_validation" / "validation_report.md").exists()
    assert (tmp_path / "dataset_validation" / "validation_results.csv").exists()
    assert (tmp_path / "dataset_validation" / "validation_summary.json").exists()


def test_validate_seeded_dataset_flags_invalid_task(tmp_path: Path) -> None:
    task_dir = tmp_path / "dataset" / "task_001_bad"
    repo_dir = task_dir / "repo"
    repo_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("Bug report", encoding="utf-8")
    (task_dir / "expected.json").write_text(
        """
{
  "task_id": "task_001_bad",
  "language": "python",
  "test_command": "python3 -m pytest",
  "expected_touched_files": ["src/missing.py"],
  "expected_related_tests": ["tests/test_missing.py"],
  "failure_type": "logic_bug"
}
""",
        encoding="utf-8",
    )

    results, summary = validate_seeded_dataset(
        dataset_dir=tmp_path / "dataset",
        output_dir=tmp_path / "validation",
    )

    assert summary.task_count == 1
    assert summary.valid_tasks == 0
    assert summary.invalid_tasks == 1
    assert "expected_touched_files path does not exist" in ";".join(results[0].errors)
    assert "expected_related_tests path does not exist" in ";".join(results[0].errors)


def test_validate_issue_corpus_writes_outputs(tmp_path: Path) -> None:
    results, summary = validate_issue_corpus(
        corpus_path=Path("evals/issue_corpora/public_issue_smoke_v1/issues.json"),
        output_dir=tmp_path / "public_issue_corpus",
    )

    assert len(results) == 3
    assert summary.corpus_id == "public_issue_smoke_v1"
    assert summary.valid_entries == 3
    assert summary.invalid_entries == 0
    assert summary.open_issue_count == 3
    assert "psf/requests" in summary.repositories
    assert "pytest-dev/pytest" in summary.repositories
    assert (tmp_path / "public_issue_corpus" / "corpus_report.md").exists()
    assert (tmp_path / "public_issue_corpus" / "corpus_results.csv").exists()
    assert (tmp_path / "public_issue_corpus" / "corpus_summary.json").exists()
    report = (tmp_path / "public_issue_corpus" / "corpus_report.md").read_text(
        encoding="utf-8"
    )
    assert "Claim Boundary" in report

    cli_output = tmp_path / "cli_public_issue_corpus"
    exit_code = main(
        [
            "validate-issue-corpus",
            "--corpus",
            "evals/issue_corpora/public_issue_smoke_v1/issues.json",
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "corpus_report.md").exists()


def test_validate_issue_corpus_flags_bad_metadata(tmp_path: Path) -> None:
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "bad",
                "issues": [
                    {
                        "task_id": "bad task",
                        "repository": "requests",
                        "repo_url": "https://example.com/requests",
                        "issue_url": "https://github.com/psf/requests/issues/1",
                        "title": "bad",
                        "language": "python",
                        "task_type": "bug",
                        "state_at_capture": "open",
                        "captured_at": "2026-06-10T08:16:00Z",
                        "expected_workflow": ["clone"],
                        "selection_reason": "bad metadata",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    results, summary = validate_issue_corpus(
        corpus_path=corpus_path,
        output_dir=tmp_path / "out",
    )

    assert summary.invalid_entries == 1
    assert "task_id contains unsafe characters" in ";".join(results[0].errors)
    assert "repository must use owner/name format" in ";".join(results[0].errors)
    assert "repo_url must be a GitHub URL" in ";".join(results[0].errors)


def test_preflight_issue_corpus_repositories_writes_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[3] == "https://github.com/pytest-dev/pytest":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "ref: refs/heads/main\tHEAD\n"
                    "abc123\tHEAD\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "ref: refs/heads/main\tHEAD\n"
                "def456\tHEAD\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("patchsmith.evaluation.subprocess.run", fake_run)

    output_dir = tmp_path / "preflight"
    results, summary = preflight_issue_corpus_repositories(
        corpus_path=Path("evals/issue_corpora/public_issue_smoke_v1/issues.json"),
        output_dir=output_dir,
    )

    assert len(results) == 2
    assert summary.repository_count == 2
    assert summary.reachable_repositories == 2
    assert summary.issue_count == 3
    assert all(result.default_branch == "main" for result in results)
    assert (output_dir / "repo_preflight_report.md").exists()
    assert (output_dir / "repo_preflight_results.csv").exists()
    assert calls and calls[0][:3] == ["git", "ls-remote", "--symref"]

    cli_output = tmp_path / "cli_preflight"
    exit_code = main(
        [
            "preflight-issue-corpus",
            "--corpus",
            "evals/issue_corpora/public_issue_smoke_v1/issues.json",
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "repo_preflight_report.md").exists()


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
    report = (tmp_path / "graph_retrieval_eval" / "report.md").read_text(
        encoding="utf-8"
    )
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
    report = (tmp_path / "repair_eval_fake_model" / "repair_report.md").read_text(
        encoding="utf-8"
    )
    assert "Model provider: `offline_fake_model`" in report


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
        (tmp_path / "scaffold_comparison" / "scaffold_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["avg_trace_events"] > 0
    report = (tmp_path / "scaffold_comparison" / "scaffold_report.md").read_text(
        encoding="utf-8"
    )
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
        (tmp_path / "patch_search_eval" / "patch_search_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["candidate_results"]
    report = (tmp_path / "patch_search_eval" / "patch_search_report.md").read_text(
        encoding="utf-8"
    )
    assert "Patch Search Evaluation Report" in report
    assert "Success@k" in report
