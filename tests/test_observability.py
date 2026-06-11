import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.observability import (
    build_artifact_index,
    render_artifact_dashboard,
    render_artifact_index,
    render_run_detail_page,
    write_failure_report,
)


def test_build_artifact_index_summarizes_experiments_and_runs(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    retrieval_dir = artifacts_dir / "experiments" / "retrieval_eval_v1"
    retrieval_dir.mkdir(parents=True)
    (retrieval_dir / "report.md").write_text("# Retrieval Report\n", encoding="utf-8")
    (retrieval_dir / "summary.json").write_text(
        json.dumps(
            [
                {
                    "provider": "native_hybrid",
                    "attempted_tasks": 2,
                    "completed_tasks": 2,
                    "failed_tasks": 0,
                    "avg_top5_touched_recall": 1.0,
                    "avg_related_test_recall": 0.5,
                    "avg_latency_ms": 12.5,
                    "fallback_count": 0,
                    "source_free_violation_count": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    (retrieval_dir / "results.json").write_text(
        json.dumps([{"task_id": "one"}, {"task_id": "two"}]),
        encoding="utf-8",
    )
    run_a = retrieval_dir / "run_artifacts" / "runs" / "run-a"
    run_a.mkdir(parents=True)
    (run_a / "report.md").write_text("# Run A\n", encoding="utf-8")
    (run_a / "traces.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_name": "retrieve",
                        "event_type": "keyword_search",
                        "status": "completed",
                        "latency_ms": 12,
                        "input_summary": "issue",
                        "output_summary": "src/a.py",
                        "payload": {
                            "contexts": [
                                {
                                    "rank": 1,
                                    "path": "src/a.py",
                                    "method": "keyword",
                                    "score": 4.2,
                                    "matched_terms": ["bug"],
                                    "excerpt": "source text should not be copied",
                                }
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "context_broker",
                        "event_type": "context_broker_call",
                        "status": "completed",
                        "latency_ms": 3,
                        "output_summary": "targets=1",
                        "payload": {
                            "provider": "patchsmith_native_hybrid",
                            "targets": [
                                {
                                    "path": "src/a.py",
                                    "role": "source",
                                    "rank": 1,
                                    "confidence": 9.5,
                                    "reason": "matched bug",
                                }
                            ],
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_a / "final.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")

    scaffold_dir = artifacts_dir / "experiments" / "scaffold_comparison_v1"
    scaffold_dir.mkdir(parents=True)
    (scaffold_dir / "scaffold_report.md").write_text(
        "# Scaffold Comparison Report\n",
        encoding="utf-8",
    )
    (scaffold_dir / "scaffold_results.json").write_text(
        json.dumps(
            [
                {
                    "scaffold": "agentless",
                    "attempted_tasks": 2,
                    "completed_tasks": 1,
                    "patch_generated_rate": 0.0,
                    "targeted_test_pass_rate": 0.0,
                    "avg_latency_ms": 44.0,
                    "failed_trace_event_count": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    run_b = scaffold_dir / "heuristic" / "run_artifacts" / "runs" / "run-b"
    run_b.mkdir(parents=True)
    (run_b / "report.md").write_text("# Run B\n", encoding="utf-8")
    (run_b / "logs").mkdir()
    (run_b / "logs" / "stdout.txt").write_text("ok\n", encoding="utf-8")
    (artifacts_dir / "experiments" / "run-details").mkdir()

    index = build_artifact_index(artifacts_dir=artifacts_dir)

    assert index.experiment_count == 2
    assert index.run_count == 2
    by_name = {entry.name: entry for entry in index.experiments}
    retrieval = by_name["retrieval_eval_v1"]
    assert retrieval.kind == "retrieval"
    assert retrieval.report_path == "experiments/retrieval_eval_v1/report.md"
    assert retrieval.result_count == 2
    assert retrieval.run_count == 1
    assert retrieval.updated_at is not None
    scaffold = by_name["scaffold_comparison_v1"]
    assert scaffold.kind == "scaffold"
    assert scaffold.result_count == 1
    assert scaffold.run_count == 1
    by_run = {run.run_id: run for run in index.runs}
    assert by_run["run-a"].experiment == "retrieval_eval_v1"
    assert by_run["run-a"].trace_path == (
        "experiments/retrieval_eval_v1/run_artifacts/runs/run-a/traces.jsonl"
    )
    assert by_run["run-b"].experiment == "scaffold_comparison_v1"
    assert by_run["run-b"].variant == "heuristic"
    assert by_run["run-b"].stdout_path == (
        "experiments/scaffold_comparison_v1/heuristic/run_artifacts/runs/run-b/logs/stdout.txt"
    )
    assert len(index.metrics) == 2
    by_metric = {(metric.experiment, metric.lane): metric for metric in index.metrics}
    retrieval_metric = by_metric[("retrieval_eval_v1", "native_hybrid")]
    assert retrieval_metric.primary_label == "Top-5 Recall"
    assert retrieval_metric.primary_value == 1.0
    assert retrieval_metric.secondary_label == "Related Tests"
    assert retrieval_metric.secondary_value == 0.5
    assert retrieval_metric.risk_note == ("0 failed; 0 fallback; 0 source-free violations")
    scaffold_metric = by_metric[("scaffold_comparison_v1", "agentless")]
    assert scaffold_metric.primary_label == "Targeted Tests Passed"
    assert scaffold_metric.completed_count == 1
    assert scaffold_metric.risk_note == "1 incomplete; 2 failed trace events"

    report = render_artifact_index(index)
    assert "# PatchSmith Artifact Index" in report
    assert "| retrieval_eval_v1 | retrieval |" in report
    assert "Result Count" in report
    assert "Runs" in report
    assert "## Research Metrics" in report
    assert "Top-5 Recall: 100%" in report
    assert "Related Tests: 50%" in report
    assert "## Recent Runs" in report
    assert "run-a" in report
    report_with_details = render_artifact_index(
        index,
        run_detail_output_dir=artifacts_dir / "experiments" / "run-details",
    )
    assert "experiments/run-details/run-a.html" in report_with_details
    dashboard = render_artifact_dashboard(
        index,
        output_path=artifacts_dir / "experiments" / "index.html",
        run_detail_output_dir=artifacts_dir / "experiments" / "run-details",
    )
    assert "PatchSmith Artifact Dashboard" in dashboard
    assert "Search experiments and metrics" in dashboard
    assert "Research Metrics" in dashboard
    assert 'tbody id="metrics"' in dashboard
    assert 'id="metrics-empty"' in dashboard
    assert 'data-name="retrieval_eval_v1 native_hybrid"' in dashboard
    assert "Targeted Tests Passed: 0%" in dashboard
    assert "retrieval_eval_v1" in dashboard
    assert 'href="retrieval_eval_v1/report.md"' in dashboard
    assert "Recent Runs" in dashboard
    assert 'href="run-details/run-a.html"' in dashboard
    assert 'href="retrieval_eval_v1/run_artifacts/runs/run-a/traces.jsonl"' in dashboard
    assert 'data-kind="scaffold"' in dashboard
    detail = render_run_detail_page(
        by_run["run-a"],
        artifacts_dir=artifacts_dir,
        output_path=artifacts_dir / "experiments" / "run-details" / "run-a.html",
        dashboard_path=artifacts_dir / "experiments" / "index.html",
    )
    assert "Run run-a" in detail
    assert "Trace Timeline" in detail
    assert "Retrieved Context" in detail
    assert "Context Targets" in detail
    assert "src/a.py" in detail
    assert "source text should not be copied" not in detail
    assert "diff --git a/a b/a" in detail


def test_index_artifacts_cli_writes_markdown_and_json(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    experiment_dir = artifacts_dir / "experiments" / "patch_search_eval_v1"
    experiment_dir.mkdir(parents=True)
    (experiment_dir / "patch_search_report.md").write_text(
        "# Patch Search Evaluation Report\n",
        encoding="utf-8",
    )
    (experiment_dir / "patch_search_results.json").write_text(
        json.dumps([{"task_id": "task_001_logic_bug"}]),
        encoding="utf-8",
    )
    (experiment_dir / "patch_search_summary.json").write_text(
        json.dumps(
            [
                {
                    "variant": "candidates_3",
                    "attempted_tasks": 1,
                    "completed_tasks": 1,
                    "success_at_1_rate": 0.0,
                    "success_at_k_rate": 1.0,
                    "selected_success_rate": 1.0,
                    "avg_latency_ms": 20.0,
                    "avg_test_runs": 3.0,
                    "estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    run_dir = experiment_dir / "run_artifacts" / "runs" / "run-c"
    run_dir.mkdir(parents=True)
    (run_dir / "report.md").write_text("# Run C\n", encoding="utf-8")
    (run_dir / "traces.jsonl").write_text(
        json.dumps(
            {
                "node_name": "run",
                "event_type": "lifecycle",
                "status": "completed",
                "latency_ms": 1,
                "output_summary": "done",
                "payload": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "final.diff").write_text("diff\n", encoding="utf-8")

    output_path = tmp_path / "index.md"
    json_output_path = tmp_path / "index.json"
    html_output_path = tmp_path / "index.html"
    run_detail_output_dir = tmp_path / "run-details"
    run_detail_output_dir.mkdir()
    (run_detail_output_dir / "stale.html").write_text("stale\n", encoding="utf-8")
    exit_code = main(
        [
            "index-artifacts",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(output_path),
            "--json-output",
            str(json_output_path),
            "--html-output",
            str(html_output_path),
            "--run-detail-output-dir",
            str(run_detail_output_dir),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["experiment_count"] == 1
    assert payload["run_count"] == 1
    assert payload["metric_count"] == 1
    assert payload["index_path"] == str(output_path)
    assert payload["html_path"] == str(html_output_path)
    assert payload["run_detail_dir"] == str(run_detail_output_dir)
    assert output_path.exists()
    assert json_output_path.exists()
    assert html_output_path.exists()
    assert (run_detail_output_dir / "run-c.html").exists()
    assert not (run_detail_output_dir / "stale.html").exists()
    assert "patch_search_eval_v1" in output_path.read_text(encoding="utf-8")
    assert str(run_detail_output_dir.relative_to(tmp_path)) in output_path.read_text(
        encoding="utf-8"
    )
    assert "PatchSmith Artifact Dashboard" in html_output_path.read_text(encoding="utf-8")
    assert "Success@k: 100%" in html_output_path.read_text(encoding="utf-8")
    assert "Run run-c" in (run_detail_output_dir / "run-c.html").read_text(encoding="utf-8")
    assert (
        json.loads(json_output_path.read_text(encoding="utf-8"))["metrics"][0]["lane"]
        == "candidates_3"
    )
    assert (
        json.loads(json_output_path.read_text(encoding="utf-8"))["experiments"][0]["kind"]
        == "patch_search"
    )


def test_failure_report_summarizes_failed_run_traces(tmp_path: Path, capsys) -> None:
    artifacts_dir = tmp_path / "artifacts"
    failed_run = (
        artifacts_dir
        / "experiments"
        / "scaffold_eval_v1"
        / "agentless"
        / "run_artifacts"
        / "runs"
        / "run-fail"
    )
    failed_run.mkdir(parents=True)
    (failed_run / "report.md").write_text("# Failed Run\n", encoding="utf-8")
    (failed_run / "final.diff").write_text("", encoding="utf-8")
    (failed_run / "traces.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-1",
                        "node_name": "runtime",
                        "event_type": "agent_result",
                        "status": "no_patch_generated",
                        "started_at": "2026-01-01T00:00:00Z",
                        "completed_at": "2026-01-01T00:00:00Z",
                        "latency_ms": 0,
                        "output_summary": "No patch generated.",
                        "payload": {},
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-2",
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "failed",
                        "started_at": "2026-01-01T00:00:01Z",
                        "completed_at": "2026-01-01T00:00:01Z",
                        "latency_ms": 12,
                        "input_summary": "python3 -m pytest",
                        "output_summary": "exit_code=1",
                        "payload": {"exit_code": 1},
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-3",
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "unresolved",
                        "started_at": "2026-01-01T00:00:02Z",
                        "completed_at": "2026-01-01T00:00:02Z",
                        "latency_ms": 0,
                        "output_summary": "No patch candidate was generated.",
                        "payload": {
                            "status": "unresolved",
                            "verdict": "no_patch_tests_failed",
                            "summary": "No patch candidate was generated.",
                            "patch_generated": False,
                            "tests_passed": False,
                            "test_exit_code": 1,
                            "failure_category": "no_patch_generated",
                            "next_action": "Improve retrieval or planning.",
                        },
                        "error": None,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ok_run = (
        artifacts_dir
        / "experiments"
        / "scaffold_eval_v1"
        / "heuristic"
        / "run_artifacts"
        / "runs"
        / "run-ok"
    )
    ok_run.mkdir(parents=True)
    (ok_run / "report.md").write_text("# OK Run\n", encoding="utf-8")
    (ok_run / "traces.jsonl").write_text(
        json.dumps(
            {
                "run_id": "run-ok",
                "event_id": "event-4",
                "node_name": "analyze",
                "event_type": "repair_outcome",
                "status": "validated",
                "started_at": "2026-01-01T00:00:03Z",
                "completed_at": "2026-01-01T00:00:03Z",
                "latency_ms": 0,
                "output_summary": "Patch validated.",
                "payload": {
                    "status": "validated",
                    "verdict": "patch_validated",
                    "failure_category": None,
                },
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "failure_report.md"
    json_output_path = tmp_path / "failure_report.json"
    report = write_failure_report(
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_runs=None,
    )

    assert report.runs_scanned == 2
    assert report.runs_requiring_attention == 1
    assert report.failed_event_count == 1
    assert report.category_counts == {"no_patch_generated": 1}
    assert report.insights[0].run_id == "run-fail"
    assert report.insights[0].variant == "agentless"
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Failure Report" in rendered
    assert "no_patch_generated" in rendered
    assert "Improve retrieval or planning." in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["insights"][0]["failed_nodes"] == ["test"]

    cli_output = tmp_path / "cli_failure_report.md"
    exit_code = main(
        [
            "inspect-failures",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--max-runs",
            "0",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["runs_scanned"] == 2
    assert cli_payload["runs_requiring_attention"] == 1
    assert cli_payload["category_counts"] == {"no_patch_generated": 1}
    assert cli_output.exists()
