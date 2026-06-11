"""Shared fixtures for portfolio report tests."""

import json
from pathlib import Path

import pytest


def _write_progress_artifact_fixture(artifacts_dir: Path) -> None:
    retrieval_dir = artifacts_dir / "experiments" / "retrieval_eval_v1"
    retrieval_dir.mkdir(parents=True)
    (retrieval_dir / "report.md").write_text("# Retrieval\n", encoding="utf-8")
    (retrieval_dir / "summary.json").write_text(
        json.dumps(
            [
                {
                    "provider": "native_hybrid",
                    "attempted_tasks": 10,
                    "completed_tasks": 10,
                    "failed_tasks": 0,
                    "avg_top5_touched_recall": 1.0,
                    "avg_related_test_recall": 1.0,
                    "avg_latency_ms": 3.0,
                    "fallback_count": 0,
                    "source_free_violation_count": 0,
                }
            ]
        ),
        encoding="utf-8",
    )

    scaffold_dir = artifacts_dir / "experiments" / "scaffold_comparison_v1"
    scaffold_dir.mkdir(parents=True)
    (scaffold_dir / "scaffold_report.md").write_text("# Scaffold\n", encoding="utf-8")
    (scaffold_dir / "scaffold_results.json").write_text(
        json.dumps(
            [
                {
                    "scaffold": "langgraph_fake_model",
                    "runtime": "langgraph",
                    "planner": "fake_model",
                    "attempted_tasks": 10,
                    "completed_tasks": 10,
                    "patch_generated_rate": 1.0,
                    "targeted_test_pass_rate": 1.0,
                    "avg_latency_ms": 450.0,
                    "avg_trace_events": 15.0,
                    "avg_runtime_nodes": 6.0,
                    "failed_trace_event_count": 0,
                    "model_provider": "offline_fake_model",
                    "estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    run_dir = scaffold_dir / "run_artifacts" / "runs" / "run-fail"
    run_dir.mkdir(parents=True)
    (run_dir / "report.md").write_text("# Run\n", encoding="utf-8")
    (run_dir / "final.diff").write_text("diff --git a/a.py b/a.py\n", encoding="utf-8")
    (run_dir / "logs").mkdir()
    (run_dir / "logs" / "stdout.txt").write_text("stdout\n", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("stderr\n", encoding="utf-8")
    (run_dir / "traces.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-1",
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "failed",
                        "latency_ms": 10,
                        "payload": {"exit_code": 1, "sandbox_mode": "local"},
                    }
                ),
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-2",
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "unresolved",
                        "latency_ms": 0,
                        "payload": {
                            "failure_category": "no_patch_generated",
                            "verdict": "no_patch_tests_failed",
                            "next_action": "Improve planning.",
                            "test_exit_code": 1,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    patch_search_dir = artifacts_dir / "experiments" / "patch_search_eval_v1"
    patch_search_dir.mkdir(parents=True)
    (patch_search_dir / "patch_search_report.md").write_text(
        "# Patch Search\n",
        encoding="utf-8",
    )
    (patch_search_dir / "patch_search_summary.json").write_text(
        json.dumps(
            [
                {
                    "variant": "candidates_3",
                    "attempted_tasks": 10,
                    "completed_tasks": 10,
                    "success_at_1_rate": 1.0,
                    "success_at_k_rate": 1.0,
                    "selected_success_rate": 1.0,
                    "avg_latency_ms": 1300.0,
                    "avg_test_runs": 3.0,
                    "estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )


@pytest.fixture
def write_progress_artifacts():
    """Build the saved-artifact fixture used by MVP progress and delivery audit tests."""
    return _write_progress_artifact_fixture
