import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_delivery_audit_report,
    write_demo_media_assets,
    write_demo_readiness_report,
    write_demo_script_report,
    write_docker_smoke_report,
    write_environment_readiness_report,
    write_evidence_refresh_report,
    write_final_evaluation_report,
    write_launch_blocker_report,
    write_live_calibration_plan_report,
    write_live_calibration_report,
    write_mvp_progress_report,
    write_project_status_report,
    write_quality_gate_report,
    write_release_hygiene_report,
)


def _write_release_hygiene_fixture(project_root: Path, artifacts_dir: Path) -> None:
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "patchsmith-research"',
                'version = "0.1.0"',
                "",
                "[project.optional-dependencies]",
                'dev = ["build>=1.2", "pytest>=8.0"]',
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/patchsmith"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    for doc_path in [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]:
        path = project_root / doc_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ready_with_caveats offline live LLM calibration\n", encoding="utf-8")
    for artifact_path in [
        "experiments/index.md",
        "experiments/index.json",
        "experiments/index.html",
        "experiments/failure_report.md",
        "experiments/failure_report.json",
        "experiments/demo_readiness.md",
        "experiments/demo_readiness.json",
        "experiments/calibration_readiness.md",
        "experiments/calibration_readiness.json",
        "experiments/live_calibration_plan.md",
        "experiments/live_calibration_plan.json",
        "experiments/launch_blockers.md",
        "experiments/launch_blockers.json",
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/public_issue_corpus_v1/context_preview_report.md",
        "experiments/public_issue_corpus_v1/context_preview_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_validation_summary.json",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "experiments/public_issue_corpus_v1/focused_test_run_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/demo_media.md",
        "experiments/demo_media.json",
        "experiments/demo_media.svg",
        "experiments/demo_media.png",
        "experiments/environment_readiness.md",
        "experiments/environment_readiness.json",
        "experiments/quality_gate.md",
        "experiments/quality_gate.json",
        "experiments/project_status.md",
        "experiments/project_status.json",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
        "experiments/delivery_audit.md",
        "experiments/delivery_audit.json",
    ]:
        path = artifacts_dir / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "ok\n", encoding="utf-8")
    (artifacts_dir / "experiments" / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "ready",
                "passed_count": 10,
                "warning_count": 0,
                "blocked_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_root, check=True, capture_output=True, text=True)


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


def test_demo_readiness_report_summarizes_launch_evidence(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
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
                    "attempted_tasks": 10,
                    "completed_tasks": 10,
                    "patch_generated_rate": 1.0,
                    "targeted_test_pass_rate": 1.0,
                    "avg_latency_ms": 450.0,
                    "failed_trace_event_count": 0,
                    "model_provider": "offline_fake_model",
                    "estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    failed_run = scaffold_dir / "agentless" / "run_artifacts" / "runs" / "run-fail"
    failed_run.mkdir(parents=True)
    (failed_run / "report.md").write_text("# Failed Run\n", encoding="utf-8")
    (failed_run / "traces.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-1",
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "failed",
                        "started_at": "2026-01-01T00:00:00Z",
                        "completed_at": "2026-01-01T00:00:00Z",
                        "latency_ms": 25,
                        "output_summary": "exit_code=1",
                        "payload": {"exit_code": 1},
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "run_id": "run-fail",
                        "event_id": "event-2",
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "unresolved",
                        "started_at": "2026-01-01T00:00:01Z",
                        "completed_at": "2026-01-01T00:00:01Z",
                        "latency_ms": 0,
                        "output_summary": "No patch candidate was generated.",
                        "payload": {
                            "status": "unresolved",
                            "verdict": "no_patch_tests_failed",
                            "failure_category": "no_patch_generated",
                            "next_action": "Improve retrieval or planning.",
                            "test_exit_code": 1,
                        },
                        "error": None,
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

    output_path = tmp_path / "demo_readiness.md"
    json_output_path = tmp_path / "demo_readiness.json"
    report = write_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
    )

    assert report.readiness_status == "ready_with_caveats"
    assert report.experiment_count == 3
    assert report.run_count == 1
    assert report.metric_count == 3
    assert report.runs_requiring_attention == 1
    assert report.failure_categories == {"no_patch_generated": 1}
    assert report.model_providers == {"offline_fake_model": 1}
    statuses = {gate.name: gate.status for gate in report.gates}
    assert statuses["Experiment Evidence"] == "passed"
    assert statuses["Retrieval Evidence"] == "passed"
    assert statuses["Patch Search Evidence"] == "passed"
    assert statuses["Failure Visibility"] == "passed"
    assert statuses["Live LLM Calibration"] == "warning"
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Demo Readiness Report" in rendered
    assert "ready_with_caveats" in rendered
    assert "demo-readiness" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "ready_with_caveats"

    cli_output = tmp_path / "cli_demo_readiness.md"
    exit_code = main(
        [
            "demo-readiness",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["readiness_status"] == "ready_with_caveats"
    assert cli_payload["model_providers"] == {"offline_fake_model": 1}
    assert cli_output.exists()

    calibration_output = tmp_path / "calibration_readiness.md"
    calibration_json_output = tmp_path / "calibration_readiness.json"
    calibration = write_live_calibration_report(
        artifacts_dir=artifacts_dir,
        output_path=calibration_output,
        json_output_path=calibration_json_output,
        environment={},
        package_availability={"openai": True, "deepagents": False, "agents": False},
    )
    assert calibration.calibration_status == "not_configured"
    assert calibration.saved_live_provider_count == 0
    assert calibration.deepagents_package_run_count == 0
    assert calibration.openai_agents_package_run_count == 0
    calibration_statuses = {check.name: check.status for check in calibration.checks}
    assert calibration_statuses["OpenAI SDK"] == "passed"
    assert calibration_statuses["OpenAI Credentials"] == "missing"
    assert calibration_statuses["DeepAgents Package"] == "warning"
    assert calibration_statuses["Saved DeepAgents Package Evidence"] == "warning"
    assert calibration_statuses["OpenAI Agents Package"] == "warning"
    assert calibration_statuses["Saved OpenAI Agents Package Evidence"] == "warning"
    assert calibration_statuses["Saved Live Provider Evidence"] == "missing"
    calibration_text = calibration_output.read_text(encoding="utf-8")
    assert "# PatchSmith Live Calibration Readiness" in calibration_text
    assert "offline seeded-suite evidence" in calibration_text
    calibration_payload = json.loads(calibration_json_output.read_text(encoding="utf-8"))
    assert calibration_payload["calibration_status"] == "not_configured"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_calibration_output = tmp_path / "cli_calibration_readiness.md"
    exit_code = main(
        [
            "live-calibration",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_calibration_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_calibration_payload = json.loads(capsys.readouterr().out)
    assert cli_calibration_payload["calibration_status"] == "not_configured"
    assert cli_calibration_payload["deepagents_package_run_count"] == 0
    assert cli_calibration_payload["openai_agents_package_run_count"] == 0
    assert cli_calibration_output.exists()

    calibration_plan_output = tmp_path / "live_calibration_plan.md"
    calibration_plan_json_output = tmp_path / "live_calibration_plan.json"
    calibration_plan = write_live_calibration_plan_report(
        artifacts_dir=artifacts_dir,
        output_path=calibration_plan_output,
        json_output_path=calibration_plan_json_output,
        environment={},
        package_availability={"openai": True, "deepagents": False, "agents": False},
    )
    assert calibration_plan.plan_status == "blocked"
    assert calibration_plan.credentials_configured is False
    assert len(calibration_plan.runs) == 4
    assert calibration_plan.runs[0].status == "blocked"
    assert calibration_plan.runs[0].requires_credentials
    assert "--planner openai" in calibration_plan.runs[0].command
    assert calibration_plan.runs[1].status == "blocked"
    plan_text = calibration_plan_output.read_text(encoding="utf-8")
    assert "# PatchSmith Live Calibration Plan" in plan_text
    assert "does not prove live model execution" in plan_text
    plan_payload = json.loads(calibration_plan_json_output.read_text(encoding="utf-8"))
    assert plan_payload["plan_status"] == "blocked"
    assert plan_payload["run_count"] == 4
    assert plan_payload["ready_runs"] == 0
    assert plan_payload["blocked_runs"] == 2

    ready_plan = write_live_calibration_plan_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "ready_live_calibration_plan.md",
        environment={"OPENAI_API_KEY": "test-key"},
        package_availability={"openai": True, "deepagents": True, "agents": True},
    )
    assert ready_plan.plan_status == "ready_to_run"
    assert ready_plan.runs[0].status == "ready"
    assert ready_plan.runs[1].status == "waiting_for_smoke"

    cli_calibration_plan_output = tmp_path / "cli_live_calibration_plan.md"
    cli_calibration_plan_json_output = tmp_path / "cli_live_calibration_plan.json"
    exit_code = main(
        [
            "live-calibration-plan",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_calibration_plan_output),
            "--json-output",
            str(cli_calibration_plan_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_calibration_plan_payload = json.loads(capsys.readouterr().out)
    assert cli_calibration_plan_payload["run_count"] == 4
    assert cli_calibration_plan_payload["plan_status"] in {"blocked", "ready_to_run"}
    assert cli_calibration_plan_output.exists()

    script_output = tmp_path / "demo_script.md"
    script_json_output = tmp_path / "demo_script.json"
    script = write_demo_script_report(
        artifacts_dir=artifacts_dir,
        output_path=script_output,
        json_output_path=script_json_output,
    )
    assert script.readiness_status == "ready_with_caveats"
    assert script.target_duration_seconds == 190
    assert len(script.sections) == 6
    assert script.sections[0].title == "Problem And Thesis"
    script_text = script_output.read_text(encoding="utf-8")
    assert "# PatchSmith Demo Script" in script_text
    assert "Failure Transparency" in script_text
    assert "Do not claim live LLM calibration" in script_text
    script_payload = json.loads(script_json_output.read_text(encoding="utf-8"))
    assert script_payload["target_duration_seconds"] == 190

    cli_script_output = tmp_path / "cli_demo_script.md"
    exit_code = main(
        [
            "demo-script",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_script_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_script_payload = json.loads(capsys.readouterr().out)
    assert cli_script_payload["readiness_status"] == "ready_with_caveats"
    assert cli_script_payload["section_count"] == 6
    assert cli_script_output.exists()

    media_output = tmp_path / "demo_media.md"
    media_svg_output = tmp_path / "demo_media.svg"
    media_png_output = tmp_path / "demo_media.png"
    media_json_output = tmp_path / "demo_media.json"
    media = write_demo_media_assets(
        artifacts_dir=artifacts_dir,
        output_path=media_output,
        svg_output_path=media_svg_output,
        png_output_path=media_png_output,
        json_output_path=media_json_output,
    )
    assert media.readiness_status == "ready_with_caveats"
    assert media.width == 1200
    assert media.height == 675
    assert media_svg_output.read_text(encoding="utf-8").startswith("<svg")
    assert media_png_output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    media_payload = json.loads(media_json_output.read_text(encoding="utf-8"))
    assert media_payload["png_path"] == str(media_png_output)

    cli_media_output = tmp_path / "cli_demo_media.md"
    cli_media_svg = tmp_path / "cli_demo_media.svg"
    cli_media_png = tmp_path / "cli_demo_media.png"
    exit_code = main(
        [
            "demo-media",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_media_output),
            "--svg-output",
            str(cli_media_svg),
            "--png-output",
            str(cli_media_png),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_media_payload = json.loads(capsys.readouterr().out)
    assert cli_media_payload["readiness_status"] == "ready_with_caveats"
    assert cli_media_payload["png_path"] == str(cli_media_png)
    assert cli_media_output.exists()
    assert cli_media_svg.exists()
    assert cli_media_png.exists()

    final_output = tmp_path / "final_evaluation.md"
    final_json_output = tmp_path / "final_evaluation.json"
    final = write_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        output_path=final_output,
        json_output_path=final_json_output,
    )
    assert final.readiness_status == "ready_with_caveats"
    assert final.experiment_count == 3
    assert final.run_count == 1
    assert final.metric_count == 3
    assert len(final.metrics) == 3
    assert any(metric.kind == "retrieval" for metric in final.metrics)
    assert any(metric.kind == "scaffold" for metric in final.metrics)
    assert any(metric.kind == "patch_search" for metric in final.metrics)
    assert any("offline-only" in decision for decision in final.decisions)
    assert any("No non-offline model provider" in item for item in final.limitations)
    final_text = final_output.read_text(encoding="utf-8")
    assert "# PatchSmith Final Evaluation Report" in final_text
    assert "Metric Evidence" in final_text
    assert "Public Claim Boundary" in final_text
    final_payload = json.loads(final_json_output.read_text(encoding="utf-8"))
    assert final_payload["metric_count"] == 3
    assert final_payload["deepagents_package_run_count"] == 0
    assert final_payload["openai_agents_package_run_count"] == 0

    cli_final_output = tmp_path / "cli_final_evaluation.md"
    exit_code = main(
        [
            "final-evaluation",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_final_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_final_payload = json.loads(capsys.readouterr().out)
    assert cli_final_payload["readiness_status"] == "ready_with_caveats"
    assert cli_final_payload["metric_count"] == 3
    assert cli_final_payload["deepagents_package_run_count"] == 0
    assert cli_final_payload["openai_agents_package_run_count"] == 0
    assert cli_final_payload["decision_count"] >= 5
    assert cli_final_output.exists()

    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "patchsmith-research"',
                'version = "0.1.0"',
                "",
                "[project.optional-dependencies]",
                'dev = ["build>=1.2", "pytest>=8.0"]',
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/patchsmith"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    for doc_path in [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]:
        path = tmp_path / doc_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "ready_with_caveats offline live LLM calibration\n",
            encoding="utf-8",
        )
    for artifact_path in [
        "experiments/index.md",
        "experiments/index.json",
        "experiments/index.html",
        "experiments/failure_report.md",
        "experiments/failure_report.json",
        "experiments/demo_readiness.md",
        "experiments/demo_readiness.json",
        "experiments/calibration_readiness.md",
        "experiments/calibration_readiness.json",
        "experiments/live_calibration_plan.md",
        "experiments/live_calibration_plan.json",
        "experiments/launch_blockers.md",
        "experiments/launch_blockers.json",
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/public_issue_corpus_v1/context_preview_report.md",
        "experiments/public_issue_corpus_v1/context_preview_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_summary.json",
        "experiments/public_issue_corpus_v1/materialized_task_validation_report.md",
        "experiments/public_issue_corpus_v1/materialized_task_validation_summary.json",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_report.md",
        "experiments/public_issue_corpus_v1/materialized_run_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_run_report.md",
        "experiments/public_issue_corpus_v1/focused_test_run_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_report.md",
        "experiments/public_issue_corpus_v1/focused_test_diagnosis_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_plan_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_readiness_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_execution_summary.json",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_report.md",
        "experiments/public_issue_corpus_v1/focused_test_setup_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_plan_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_report.md",
        "experiments/public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_report.md",
        "experiments/public_issue_corpus_v1/public_issue_reproduction_execution_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_readiness_summary.json",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_report.md",
        "experiments/public_issue_corpus_v1/public_issue_repair_attempt_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/demo_media.md",
        "experiments/demo_media.json",
        "experiments/demo_media.svg",
        "experiments/demo_media.png",
        "experiments/environment_readiness.md",
        "experiments/environment_readiness.json",
        "experiments/quality_gate.md",
        "experiments/quality_gate.json",
        "experiments/project_status.md",
        "experiments/project_status.json",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
        "experiments/delivery_audit.md",
        "experiments/delivery_audit.json",
    ]:
        path = artifacts_dir / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "ok\n", encoding="utf-8")
    (artifacts_dir / "experiments" / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "ready",
                "passed_count": 10,
                "warning_count": 0,
                "blocked_count": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    hygiene_output = tmp_path / "release_hygiene.md"
    hygiene_json_output = tmp_path / "release_hygiene.json"
    hygiene = write_release_hygiene_report(
        project_root=tmp_path,
        artifacts_dir=artifacts_dir,
        output_path=hygiene_output,
        json_output_path=hygiene_json_output,
    )
    assert hygiene.release_status == "blocked"
    assert hygiene.blocked_count == 1
    assert any(
        check.name == "Git Repository" and check.status == "blocked" for check in hygiene.checks
    )
    assert any(
        check.name == "Packaging Config" and check.status == "passed" for check in hygiene.checks
    )
    assert any(
        check.name == "Planning Docs" and check.status == "passed" for check in hygiene.checks
    )
    hygiene_text = hygiene_output.read_text(encoding="utf-8")
    assert "# PatchSmith Release Hygiene Report" in hygiene_text
    assert "No .git directory found" in hygiene_text
    hygiene_payload = json.loads(hygiene_json_output.read_text(encoding="utf-8"))
    assert hygiene_payload["release_status"] == "blocked"

    cli_hygiene_output = tmp_path / "cli_release_hygiene.md"
    exit_code = main(
        [
            "release-hygiene",
            "--project-root",
            str(tmp_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_hygiene_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_hygiene_payload = json.loads(capsys.readouterr().out)
    assert cli_hygiene_payload["release_status"] == "blocked"
    assert cli_hygiene_payload["blocked_count"] == 1
    assert cli_hygiene_output.exists()


def test_launch_blocker_report_prioritizes_readiness_artifacts(tmp_path: Path, capsys) -> None:
    artifacts_dir = tmp_path / "artifacts"
    experiments_dir = artifacts_dir / "experiments"
    public_issue_dir = experiments_dir / "public_issue_corpus_v1"
    public_issue_dir.mkdir(parents=True)

    (experiments_dir / "docker_smoke.json").write_text(
        json.dumps(
            {
                "smoke_status": "not_available",
                "checks": [
                    {
                        "name": "Docker Daemon",
                        "status": "missing",
                        "evidence": "Docker daemon is not reachable.",
                        "next_action": "Start Docker Desktop.",
                    }
                ],
                "build_command": "docker build -f docker/seeded-smoke.Dockerfile -t patchsmith-seeded-smoke:py312 .",
                "smoke_command": "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke --json",
            }
        ),
        encoding="utf-8",
    )
    (public_issue_dir / "focused_test_setup_readiness_summary.json").write_text(
        json.dumps(
            {
                "docker_smoke_status": "not_available",
                "task_count": 3,
                "ready_tasks": 0,
                "warning_tasks": 0,
                "blocked_tasks": 3,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "calibration_readiness.json").write_text(
        json.dumps(
            {
                "calibration_status": "not_configured",
                "saved_live_provider_count": 0,
                "deepagents_package_run_count": 10,
                "deepagents_compatibility_run_count": 30,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "release_hygiene.json").write_text(
        json.dumps(
            {
                "release_status": "ready_with_warnings",
                "passed_count": 10,
                "warning_count": 1,
                "blocked_count": 0,
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "launch_blockers.md"
    json_output_path = tmp_path / "launch_blockers.json"
    report = write_launch_blocker_report(
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
    )

    assert report.launch_status == "blocked"
    assert report.blocked_count == 3
    assert report.warning_count == 2
    assert report.ready_count == 0
    assert [item.blocker_id for item in report.items[:2]] == [
        "docker_smoke",
        "focused_setup_readiness",
    ]
    assert {item.blocker_id for item in report.items} == {
        "docker_smoke",
        "focused_setup_readiness",
        "public_repair_readiness",
        "live_calibration",
        "release_hygiene",
    }
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Launch Blocker Backlog" in rendered
    assert "## Dependency Chain" in rendered
    assert "## Remediation Commands" in rendered
    assert "Start Docker Desktop" in rendered
    assert "check-focused-test-setup-readiness" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["launch_status"] == "blocked"
    assert payload["blocked_count"] == 3
    payload_items = {item["blocker_id"]: item for item in payload["items"]}
    assert payload_items["focused_setup_readiness"]["dependencies"] == ["docker_smoke"]
    assert payload_items["public_repair_readiness"]["dependencies"] == ["focused_setup_readiness"]
    assert any(
        "docker build -f docker/seeded-smoke.Dockerfile" in command
        for command in payload_items["docker_smoke"]["remediation_commands"]
    )
    assert any(
        "execute-focused-test-setups" in command
        for command in payload_items["focused_setup_readiness"]["remediation_commands"]
    )

    cli_output = tmp_path / "cli_launch_blockers.md"
    cli_json_output = tmp_path / "cli_launch_blockers.json"
    exit_code = main(
        [
            "launch-blockers",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["launch_status"] == "blocked"
    assert cli_payload["blocked_count"] == 3
    assert cli_payload["warning_count"] == 2
    assert cli_output.exists()
    assert cli_json_output.exists()


def test_live_calibration_report_counts_saved_deepagents_package_runs(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    package_trace = (
        artifacts_dir
        / "experiments"
        / "deepagents_package_smoke_v1"
        / "run_artifacts"
        / "runs"
        / "package-run"
        / "traces.jsonl"
    )
    package_trace.parent.mkdir(parents=True)
    package_trace.write_text(
        json.dumps(
            {
                "run_id": "package-run",
                "event_type": "runtime_node",
                "status": "package_available",
                "payload": {
                    "runtime": "deepagents",
                    "framework": "deepagents",
                    "node": "harness",
                    "status": "package_available",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    compatibility_trace = (
        artifacts_dir
        / "experiments"
        / "deepagents_compatibility_v1"
        / "run_artifacts"
        / "runs"
        / "compatibility-run"
        / "traces.jsonl"
    )
    compatibility_trace.parent.mkdir(parents=True)
    compatibility_trace.write_text(
        json.dumps(
            {
                "run_id": "compatibility-run",
                "event_type": "runtime_node",
                "status": "compatibility_mode",
                "payload": {
                    "runtime": "deepagents",
                    "framework": "deepagents",
                    "node": "harness",
                    "status": "compatibility_mode",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    openai_agents_package_trace = (
        artifacts_dir
        / "experiments"
        / "openai_agents_package_smoke_v1"
        / "run_artifacts"
        / "runs"
        / "openai-agents-package-run"
        / "traces.jsonl"
    )
    openai_agents_package_trace.parent.mkdir(parents=True)
    openai_agents_package_trace.write_text(
        json.dumps(
            {
                "run_id": "openai-agents-package-run",
                "event_type": "runtime_node",
                "status": "package_available",
                "payload": {
                    "runtime": "openai_agents",
                    "framework": "openai_agents",
                    "node": "harness",
                    "status": "package_available",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    openai_agents_compatibility_trace = (
        artifacts_dir
        / "experiments"
        / "openai_agents_compatibility_v1"
        / "run_artifacts"
        / "runs"
        / "openai-agents-compatibility-run"
        / "traces.jsonl"
    )
    openai_agents_compatibility_trace.parent.mkdir(parents=True)
    openai_agents_compatibility_trace.write_text(
        json.dumps(
            {
                "run_id": "openai-agents-compatibility-run",
                "event_type": "runtime_node",
                "status": "compatibility_mode",
                "payload": {
                    "runtime": "openai_agents",
                    "framework": "openai_agents",
                    "node": "harness",
                    "status": "compatibility_mode",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_live_calibration_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "calibration.md",
        json_output_path=tmp_path / "calibration.json",
        environment={},
        package_availability={"openai": True, "deepagents": False, "agents": False},
    )

    assert report.deepagents_package_run_count == 1
    assert report.deepagents_compatibility_run_count == 1
    assert report.openai_agents_package_run_count == 1
    assert report.openai_agents_compatibility_run_count == 1
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["Saved DeepAgents Package Evidence"] == "passed"
    assert statuses["Saved OpenAI Agents Package Evidence"] == "passed"
    rendered = (tmp_path / "calibration.md").read_text(encoding="utf-8")
    assert "DeepAgents package-backed runs: `1`" in rendered
    assert "OpenAI Agents package-backed runs: `1`" in rendered
    payload = json.loads((tmp_path / "calibration.json").read_text(encoding="utf-8"))
    assert payload["deepagents_package_run_count"] == 1
    assert payload["openai_agents_package_run_count"] == 1

    final = write_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "final.md",
        json_output_path=tmp_path / "final.json",
    )
    assert final.deepagents_package_run_count == 1
    assert final.openai_agents_package_run_count == 1
    assert any("package-backed" in decision for decision in final.decisions)
    assert any(
        "live DeepAgents model execution remains uncalibrated" in item for item in final.limitations
    )
    assert any(
        "live OpenAI Agents model execution remains uncalibrated" in item
        for item in final.limitations
    )


def test_live_calibration_report_separates_deepagents_package_and_live_claims(
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    experiment_dir = artifacts_dir / "experiments" / "deepagents_live"
    experiment_dir.mkdir(parents=True)
    (experiment_dir / "repair_results.json").write_text(
        json.dumps(
            [
                {
                    "runtime": "deepagents",
                    "model_provider": "deepagents_openai_chat",
                }
            ]
        ),
        encoding="utf-8",
    )
    run_dir = experiment_dir / "run_artifacts" / "runs" / "live-run"
    run_dir.mkdir(parents=True)
    (run_dir / "traces.jsonl").write_text(
        json.dumps(
            {
                "event_type": "runtime_node",
                "payload": {
                    "runtime": "deepagents",
                    "framework": "deepagents",
                    "node": "harness",
                    "status": "package_available",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_live_calibration_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "calibration.md",
        environment={"OPENAI_API_KEY": "test-key"},
        package_availability={"openai": True, "deepagents": True, "agents": False},
    )

    checks = {check.name: check for check in report.checks}
    assert report.saved_live_provider_count == 1
    assert checks["Saved DeepAgents Package Evidence"].status == "passed"
    assert (
        "use saved deepagents_openai_chat rows for live DeepAgents model claims"
        in checks["Saved DeepAgents Package Evidence"].next_action
    )


def test_mvp_progress_report_scores_checklist_from_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_progress_artifact_fixture(artifacts_dir)

    output_path = tmp_path / "mvp_progress.md"
    json_output_path = tmp_path / "mvp_progress.json"
    report = write_mvp_progress_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=None,
    )

    assert report.status == "ready_with_caveats"
    assert report.completion_percent >= 85.0
    assert report.item_count == 30
    assert report.missing_count == 0
    assert report.blocked_count == 0
    assert report.warning_count >= 2
    item_statuses = {item.item: item.status for item in report.items}
    assert item_statuses["Tests run in Docker sandbox."] == "warning"
    assert item_statuses["Live LLM calibration has been run."] == "warning"
    assert item_statuses["Real-world task breadth is proven."] == "warning"
    assert item_statuses["Agent can read files through bounded tool."] == "passed"
    assert item_statuses["LangGraph repair loop runs."] == "passed"
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith MVP Progress Report" in rendered
    assert "Evidence-weighted completion" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["completion_percent"] == report.completion_percent

    cli_output = tmp_path / "cli_mvp_progress.md"
    exit_code = main(
        [
            "mvp-progress",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["status"] == "ready_with_caveats"
    assert cli_payload["completion_percent"] >= 85.0
    assert cli_output.exists()


def test_mvp_progress_report_counts_validated_public_issue_corpus(
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_progress_artifact_fixture(artifacts_dir)
    corpus_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "corpus_summary.json").write_text(
        json.dumps({"valid_entries": 3, "invalid_entries": 0}),
        encoding="utf-8",
    )

    report = write_mvp_progress_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "mvp_progress.md",
    )

    item_statuses = {item.item: item.status for item in report.items}
    assert item_statuses["Real-world task breadth is proven."] == "passed"
    assert report.warning_count == 2


def test_delivery_audit_maps_objective_to_current_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_progress_artifact_fixture(artifacts_dir)
    experiments_dir = artifacts_dir / "experiments"
    public_dir = experiments_dir / "public_issue_corpus_v1"
    public_dir.mkdir(parents=True)
    (experiments_dir / "mvp_progress.json").write_text(
        json.dumps(
            {
                "status": "ready_with_caveats",
                "completion_percent": 96.7,
                "blocked_count": 0,
                "warning_count": 2,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "release_hygiene.json").write_text(
        json.dumps(
            {
                "release_status": "ready_with_warnings",
                "blocked_count": 0,
                "warning_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "blocked",
                "passed_count": 3,
                "warning_count": 6,
                "blocked_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "launch_blockers.json").write_text(
        json.dumps(
            {
                "launch_status": "blocked",
                "blocked_count": 2,
                "warning_count": 2,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "docker_smoke.json").write_text(
        json.dumps({"smoke_status": "not_available"}),
        encoding="utf-8",
    )
    (experiments_dir / "calibration_readiness.json").write_text(
        json.dumps(
            {
                "calibration_status": "not_configured",
                "saved_live_provider_count": 0,
                "deepagents_package_run_count": 10,
                "openai_agents_package_run_count": 10,
            }
        ),
        encoding="utf-8",
    )
    (experiments_dir / "live_calibration_plan.json").write_text(
        json.dumps(
            {
                "plan_status": "blocked",
                "runs": [
                    {"status": "blocked"},
                    {"status": "blocked"},
                    {"status": "setup_required"},
                    {"status": "setup_required"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "focused_test_setup_validation_summary.json").write_text(
        json.dumps(
            {
                "blocked_tasks": 3,
                "attempted_tasks": 0,
                "passed_tasks": 0,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_plan_summary.json").write_text(
        json.dumps(
            {
                "planned_tasks": 0,
                "warning_tasks": 3,
                "blocked_tasks": 0,
                "manual_spec_required_tasks": 3,
                "command_count": 3,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_failure_signal_discovery_summary.json").write_text(
        json.dumps(
            {
                "dry_run_tasks": 3,
                "attempted_tasks": 0,
                "observed_failure_tasks": 0,
                "passed_tasks": 0,
                "timed_out_tasks": 0,
                "blocked_tasks": 0,
                "candidate_signal_tasks": 0,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_spec_validation_summary.json").write_text(
        json.dumps(
            {
                "ready_tasks": 0,
                "warning_tasks": 0,
                "blocked_tasks": 3,
                "missing_spec_tasks": 0,
                "empty_signal_tasks": 3,
                "policy_blocked_tasks": 0,
                "extra_spec_tasks": 0,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_summary.json").write_text(
        json.dumps(
            {
                "reproduced_tasks": 0,
                "dry_run_tasks": 0,
                "attempted_tasks": 0,
                "blocked_tasks": 3,
                "manual_spec_required_tasks": 3,
                "failed_tasks": 0,
                "timed_out_tasks": 0,
                "not_reproduced_tasks": 0,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_repair_readiness_summary.json").write_text(
        json.dumps(
            {
                "ready_tasks": 0,
                "warning_tasks": 3,
                "blocked_tasks": 0,
                "repair_command_tasks": 3,
                "missing_reproduction_tasks": 3,
            }
        ),
        encoding="utf-8",
    )
    (public_dir / "public_issue_repair_attempt_summary.json").write_text(
        json.dumps(
            {
                "validated_tasks": 0,
                "attempted_tasks": 0,
                "blocked_tasks": 3,
                "failed_tasks": 0,
                "dry_run_tasks": 0,
                "reproduced_input_tasks": 0,
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "delivery_audit.md"
    json_output_path = tmp_path / "delivery_audit.json"
    report = write_delivery_audit_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
    )

    assert report.delivery_status == "in_progress_with_blockers"
    assert report.completion_percent > 50.0
    item_statuses = {item.requirement: item.status for item in report.items}
    assert item_statuses["Roadmap is decomposed into sprint plans."] == "passed"
    assert item_statuses["Environment readiness prerequisites are captured."] == "blocked"
    assert item_statuses["Docker sandbox smoke has executable evidence."] == "blocked"
    assert item_statuses["Public issue reproduction execution is safely gated."] == "warning"
    assert item_statuses["Public issue failure-signal discovery is available."] == "warning"
    assert item_statuses["Public issue reproduction specs are validated."] == "blocked"
    assert item_statuses["Public issue repair attempts are safely gated."] == "warning"
    assert item_statuses["Live LLM calibration has provider evidence."] == "blocked"
    item_evidence = {item.requirement: item.evidence for item in report.items}
    assert "run_count=4" in item_evidence["Live calibration execution plan is saved."]
    assert "blocked_runs=2" in item_evidence["Live calibration execution plan is saved."]
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Delivery Audit" in rendered
    assert "objective-to-evidence" not in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["delivery_status"] == "in_progress_with_blockers"

    cli_output = tmp_path / "cli_delivery_audit.md"
    cli_json_output = tmp_path / "cli_delivery_audit.json"
    exit_code = main(
        [
            "delivery-audit",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["delivery_status"] == "in_progress_with_blockers"
    assert cli_output.exists()


def test_quality_gate_report_runs_quick_verifiers(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "quality_gate.md"
    json_output_path = tmp_path / "quality_gate.json"
    logs_dir = tmp_path / "quality_gate_logs"
    report = write_quality_gate_report(
        project_root=Path("."),
        artifacts_dir=tmp_path / "artifacts",
        output_path=output_path,
        json_output_path=json_output_path,
        logs_dir=logs_dir,
        include_tests=False,
        include_build=False,
    )

    assert report.quality_status == "passed_with_skips"
    assert report.passed_count == 2
    assert report.skipped_count == 2
    assert all(check.status != "failed" for check in report.checks)
    assert any(check.stdout_path for check in report.checks if check.status == "passed")
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Quality Gate Report" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["quality_status"] == "passed_with_skips"

    cli_output = tmp_path / "cli_quality_gate.md"
    cli_json_output = tmp_path / "cli_quality_gate.json"
    exit_code = main(
        [
            "quality-gate",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--logs-dir",
            str(tmp_path / "cli_quality_gate_logs"),
            "--skip-tests",
            "--skip-build",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["quality_status"] == "passed_with_skips"
    assert cli_output.exists()


def test_project_status_report_summarizes_saved_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    experiments_dir = artifacts_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    fresh_generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stale_generated_at = (
        (datetime.now(UTC) - timedelta(days=2))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    payloads = {
        "mvp_progress.json": {
            "status": "ready_with_caveats",
            "completion_percent": 96.7,
            "passed_count": 28,
            "warning_count": 2,
            "blocked_count": 0,
        },
        "delivery_audit.json": {
            "delivery_status": "in_progress_with_blockers",
            "completion_percent": 71.4,
            "passed_count": 9,
            "warning_count": 2,
            "blocked_count": 3,
        },
        "quality_gate.json": {
            "quality_status": "passed",
            "passed_count": 4,
            "failed_count": 0,
            "skipped_count": 0,
        },
        "launch_blockers.json": {
            "launch_status": "blocked",
            "blocked_count": 2,
            "warning_count": 2,
            "ready_count": 0,
        },
        "docker_smoke.json": {
            "smoke_status": "not_available",
            "image": "patchsmith-seeded-smoke:py312",
            "run_id": None,
            "test_exit_code": None,
        },
        "environment_readiness.json": {
            "readiness_status": "blocked",
            "passed_count": 4,
            "warning_count": 5,
            "blocked_count": 1,
        },
        "release_hygiene.json": {
            "release_status": "ready_with_warnings",
            "passed_count": 10,
            "warning_count": 1,
            "blocked_count": 0,
        },
        "calibration_readiness.json": {
            "calibration_status": "not_configured",
            "saved_live_provider_count": 0,
            "deepagents_package_run_count": 10,
            "deepagents_compatibility_run_count": 30,
            "openai_agents_package_run_count": 10,
            "openai_agents_compatibility_run_count": 20,
            "model_providers": {"offline_fake_model": 23},
        },
        "public_issue_corpus_v1/public_issue_repair_readiness_summary.json": {
            "task_count": 3,
            "ready_tasks": 0,
            "warning_tasks": 3,
            "blocked_tasks": 0,
            "repair_command_tasks": 3,
            "missing_reproduction_tasks": 3,
        },
        "public_issue_corpus_v1/public_issue_repair_attempt_summary.json": {
            "task_count": 3,
            "validated_tasks": 0,
            "attempted_tasks": 0,
            "blocked_tasks": 3,
            "failed_tasks": 0,
            "dry_run_tasks": 0,
            "reproduced_input_tasks": 0,
        },
        "public_issue_corpus_v1/public_issue_reproduction_plan_summary.json": {
            "task_count": 3,
            "planned_tasks": 0,
            "warning_tasks": 3,
            "blocked_tasks": 0,
            "manual_spec_required_tasks": 3,
            "command_count": 3,
        },
        "public_issue_corpus_v1/public_issue_failure_signal_discovery_summary.json": {
            "task_count": 3,
            "dry_run_tasks": 3,
            "attempted_tasks": 0,
            "observed_failure_tasks": 0,
            "passed_tasks": 0,
            "timed_out_tasks": 0,
            "blocked_tasks": 0,
            "candidate_signal_tasks": 0,
        },
        "public_issue_corpus_v1/public_issue_reproduction_spec_validation_summary.json": {
            "task_count": 3,
            "ready_tasks": 0,
            "warning_tasks": 0,
            "blocked_tasks": 3,
            "missing_spec_tasks": 0,
            "empty_signal_tasks": 3,
            "policy_blocked_tasks": 0,
            "extra_spec_tasks": 0,
        },
        "public_issue_corpus_v1/public_issue_reproduction_execution_summary.json": {
            "task_count": 3,
            "reproduced_tasks": 0,
            "dry_run_tasks": 0,
            "attempted_tasks": 0,
            "blocked_tasks": 3,
            "manual_spec_required_tasks": 3,
            "failed_tasks": 0,
            "timed_out_tasks": 0,
        },
        "final_evaluation.json": {
            "readiness_status": "ready_with_caveats",
            "experiment_count": 17,
            "run_count": 443,
            "metric_count": 29,
        },
        "index.json": {
            "experiment_count": 17,
            "run_count": 443,
            "metric_count": 29,
        },
    }
    for payload in payloads.values():
        payload["generated_at"] = fresh_generated_at
    payloads["docker_smoke.json"]["generated_at"] = stale_generated_at
    for name, payload in payloads.items():
        path = experiments_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

    output_path = tmp_path / "project_status.md"
    json_output_path = tmp_path / "project_status.json"
    report = write_project_status_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
    )

    assert report.overall_status == "in_progress_with_blockers"
    assert report.mvp_completion_percent == 96.7
    assert report.delivery_completion_percent == 71.4
    assert report.quality_status == "passed"
    assert report.launch_status == "blocked"
    assert report.docker_smoke_status == "not_available"
    assert report.environment_readiness_status == "blocked"
    assert report.saved_live_provider_count == 0
    assert report.deepagents_package_run_count == 10
    assert report.evidence_freshness_status == "stale"
    assert report.stale_source_count == 1
    assert report.undated_source_count == 0
    assert report.missing_sources == []
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Project Status Report" in rendered
    assert "Live LLM Calibration" in rendered
    assert "Environment Readiness" in rendered
    assert "## Evidence Freshness" in rendered
    assert "experiments/docker_smoke.json" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "in_progress_with_blockers"
    assert payload["evidence_freshness_status"] == "stale"

    cli_output = tmp_path / "cli_project_status.md"
    cli_json_output = tmp_path / "cli_project_status.json"
    exit_code = main(
        [
            "project-status",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["overall_status"] == "in_progress_with_blockers"
    assert cli_payload["environment_readiness_status"] == "blocked"
    assert cli_payload["evidence_freshness_status"] == "stale"
    assert cli_payload["stale_source_count"] == 1
    assert cli_payload["missing_source_count"] == 0
    assert cli_output.exists()


def test_evidence_refresh_report_runs_lightweight_status_refresh(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    output_path = tmp_path / "evidence_refresh.md"
    json_output_path = tmp_path / "evidence_refresh.json"

    report = write_evidence_refresh_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_quality_gate=False,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 8
    assert report.docker_smoke_refreshed is False
    assert any(step.name == "Docker smoke" and step.status == "skipped" for step in report.steps)
    assert any(step.name == "Quality gate" and step.status == "skipped" for step in report.steps)
    assert any(
        step.name == "Public issue repair readiness" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue repair attempts" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction plan" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue failure-signal discovery" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction spec validation" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction execution" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Environment readiness" and step.status == "passed" for step in report.steps
    )
    assert (artifacts_dir / "experiments" / "project_status.json").exists()
    assert (artifacts_dir / "experiments" / "release_hygiene.json").exists()
    assert (artifacts_dir / "experiments" / "environment_readiness.json").exists()
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Evidence Refresh Report" in rendered
    assert "--include-quality-gate" in rendered
    assert "--include-docker-smoke" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["refresh_status"] == "passed_with_skips"
    assert payload["docker_smoke_refreshed"] is False

    cli_output = tmp_path / "cli_evidence_refresh.md"
    cli_json_output = tmp_path / "cli_evidence_refresh.json"
    exit_code = main(
        [
            "refresh-evidence",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--max-failure-runs",
            "5",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["refresh_status"] == "passed_with_skips"
    assert cli_payload["skipped_count"] == 8
    assert cli_payload["docker_smoke_refreshed"] is False
    assert cli_output.exists()


def test_evidence_refresh_prefers_reviewed_public_reproduction_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "focused_test_plan_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                    "focused_files": ["tests/test_bug.py"],
                    "policy_allowed": True,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    reviewed_specs_path = (
        project_root
        / "evals"
        / "issue_corpora"
        / "public_issue_smoke_v1"
        / "reproduction_specs.reviewed.json"
    )
    reviewed_specs_path.parent.mkdir(parents=True)
    reviewed_specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "fixture_files": [
                            {
                                "path": "tests/test_bug.py",
                                "content": "def test_bug():\n    assert False\n",
                            }
                        ],
                        "expected_failure_signals": ["AssertionError"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    assert report.failed_count == 0
    plan_summary = json.loads(
        (public_dir / "public_issue_reproduction_plan_summary.json").read_text(encoding="utf-8")
    )
    validation_summary = json.loads(
        (public_dir / "public_issue_reproduction_spec_validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    execution_summary = json.loads(
        (public_dir / "public_issue_reproduction_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan_summary["planned_tasks"] == 1
    assert plan_summary["fixture_file_tasks"] == 1
    assert validation_summary["ready_tasks"] == 1
    assert validation_summary["fixture_file_tasks"] == 1
    assert execution_summary["dry_run_tasks"] == 1
    assert execution_summary["fixture_file_tasks"] == 1


def test_evidence_refresh_preserves_executed_public_reproduction_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "focused_test_plan_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                    "policy_allowed": True,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    reviewed_specs_path = (
        project_root
        / "evals"
        / "issue_corpora"
        / "public_issue_smoke_v1"
        / "reproduction_specs.reviewed.json"
    )
    reviewed_specs_path.parent.mkdir(parents=True)
    reviewed_specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "expected_failure_signals": ["AssertionError"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-11T00:00:00Z",
                "dry_run": False,
                "attempted_tasks": 1,
                "reproduced_tasks": 1,
                "dry_run_tasks": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "status": "reproduced",
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "matched_failure_signals": ["AssertionError"],
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_report.md").write_text(
        "executed reproduction evidence\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    preserved_step = next(
        step for step in report.steps if step.name == "Public issue reproduction execution"
    )
    assert preserved_step.status == "passed"
    assert "Preserved existing executed reproduction evidence" in preserved_step.summary
    execution_summary = json.loads(
        (public_dir / "public_issue_reproduction_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert execution_summary["dry_run"] is False
    assert execution_summary["reproduced_tasks"] == 1


def test_evidence_refresh_preserves_executed_public_repair_attempt_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue_file": str(task_dir / "issue.md"),
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
                "suggested_commands": ["PYTHONPATH=src python3 -m patchsmith.cli run --json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "issue.md").write_text("public issue\n", encoding="utf-8")
    for name in [
        "focused_test_run_results.json",
        "focused_test_diagnosis_results.json",
        "focused_test_setup_validation_results.json",
    ]:
        (public_dir / name).write_text("[]\n", encoding="utf-8")
    (public_dir / "public_issue_repair_attempt_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-11T00:00:00Z",
                "dry_run": False,
                "attempted_tasks": 3,
                "validated_tasks": 1,
                "failed_tasks": 2,
                "blocked_tasks": 0,
                "reproduced_input_tasks": 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_repair_attempt_report.md").write_text(
        "executed repair evidence\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    preserved_step = next(
        step for step in report.steps if step.name == "Public issue repair attempts"
    )
    assert preserved_step.status == "passed"
    assert "Preserved existing executed repair-attempt evidence" in preserved_step.summary
    attempt_summary = json.loads(
        (public_dir / "public_issue_repair_attempt_summary.json").read_text(encoding="utf-8")
    )
    assert attempt_summary["dry_run"] is False
    assert attempt_summary["attempted_tasks"] == 3


def test_evidence_refresh_can_refresh_docker_smoke(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["docker", "version"],
            1,
            stdout="",
            stderr="Cannot connect to the Docker daemon",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    artifacts_dir = tmp_path / "artifacts"
    output_path = tmp_path / "evidence_refresh.md"
    json_output_path = tmp_path / "evidence_refresh.json"
    report = write_evidence_refresh_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_docker_smoke=True,
        docker_smoke_skip_run=True,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 7
    assert report.docker_smoke_refreshed is True
    docker_step = next(step for step in report.steps if step.name == "Docker smoke")
    assert docker_step.status == "passed"
    assert "smoke_status=not_available" in docker_step.summary
    docker_payload = json.loads(
        (artifacts_dir / "experiments" / "docker_smoke.json").read_text(encoding="utf-8")
    )
    assert docker_payload["smoke_status"] == "not_available"

    cli_output = tmp_path / "cli_evidence_refresh.md"
    cli_json_output = tmp_path / "cli_evidence_refresh.json"
    exit_code = main(
        [
            "refresh-evidence",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--max-failure-runs",
            "5",
            "--include-docker-smoke",
            "--docker-smoke-skip-run",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["docker_smoke_refreshed"] is True
    assert cli_payload["skipped_count"] == 7
    assert cli_output.exists()


def test_environment_readiness_report_summarizes_external_prerequisites(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    experiments_dir = artifacts_dir / "experiments"
    experiments_dir.mkdir(parents=True)
    (experiments_dir / "docker_smoke.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-10T00:00:00Z",
                "smoke_status": "not_available",
                "environment": {
                    "docker_cli_path": "/usr/local/bin/docker",
                    "DOCKER_HOST": "unset",
                    "docker_desktop_application": "exists",
                    "colima_binary": "missing",
                },
                "remediation_commands": ["docker version"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "environment_readiness.md"
    json_output_path = tmp_path / "environment_readiness.json"
    report = write_environment_readiness_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        environment={},
        package_availability={"openai": True, "deepagents": False, "agents": False},
    )

    assert report.readiness_status == "blocked"
    assert report.blocked_count == 1
    assert report.warning_count > 0
    checks = {(check.area, check.name): check.status for check in report.checks}
    assert checks[("Docker", "Saved Docker Smoke Evidence")] == "blocked"
    docker_check = next(
        check
        for check in report.checks
        if check.area == "Docker" and check.name == "Saved Docker Smoke Evidence"
    )
    assert "docker_desktop_application=`exists`" in docker_check.evidence
    assert "colima_binary=`missing`" in docker_check.evidence
    assert checks[("Model Providers", "OpenAI SDK")] == "passed"
    assert checks[("Model Providers", "OpenAI Credentials")] == "warning"
    assert "docker version" in report.remediation_commands
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Environment Readiness" in rendered
    assert "does not call live model providers" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "blocked"

    cli_output = tmp_path / "cli_environment_readiness.md"
    cli_json_output = tmp_path / "cli_environment_readiness.json"
    exit_code = main(
        [
            "environment-readiness",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["readiness_status"] in {"blocked", "ready_with_warnings"}
    assert cli_output.exists()


def test_release_hygiene_blocks_stale_project_status(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)
    (artifacts_dir / "experiments" / "project_status.json").write_text(
        json.dumps(
            {
                "evidence_freshness_status": "stale",
                "stale_source_count": 1,
                "undated_source_count": 0,
                "missing_sources": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "release_hygiene.md",
    )

    freshness_check = next(
        check for check in report.checks if check.name == "Project Status Freshness"
    )
    assert freshness_check.status == "blocked"
    assert "1 stale" in freshness_check.evidence
    assert "refresh-evidence" in freshness_check.next_action


def test_release_hygiene_warns_on_blocked_environment_readiness(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)
    (artifacts_dir / "experiments" / "environment_readiness.json").write_text(
        json.dumps(
            {
                "readiness_status": "blocked",
                "passed_count": 3,
                "warning_count": 6,
                "blocked_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "release_hygiene.md",
    )

    environment_check = next(
        check for check in report.checks if check.name == "Environment Readiness"
    )
    assert environment_check.status == "warning"
    assert "1 blocked" in environment_check.evidence
    assert "offline evidence" in environment_check.next_action


def test_docker_smoke_report_records_unavailable_daemon(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["docker", "version"],
            1,
            stdout="",
            stderr="Cannot connect to the Docker daemon",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = write_docker_smoke_report(
        project_root=Path("."),
        artifacts_dir=tmp_path / "artifacts",
        output_path=tmp_path / "docker_smoke.md",
        json_output_path=tmp_path / "docker_smoke.json",
    )

    assert report.smoke_status == "not_available"
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["Docker Daemon"] == "missing"
    assert statuses["Smoke Image"] == "skipped"
    assert statuses["Seeded Docker Test Run"] == "skipped"
    rendered = (tmp_path / "docker_smoke.md").read_text(encoding="utf-8")
    assert "# PatchSmith Docker Smoke Report" in rendered
    assert "## Environment" in rendered
    assert "docker context ls" in rendered
    payload = json.loads((tmp_path / "docker_smoke.json").read_text(encoding="utf-8"))
    assert payload["smoke_status"] == "not_available"
    assert payload["environment"]["docker_binary"] == "docker"
    assert "docker_cli_path" in payload["environment"]
    assert "DOCKER_CONFIG" in payload["environment"]
    assert payload["environment"]["docker_desktop_application"] in {"exists", "missing"}
    assert "colima_binary" in payload["environment"]
    assert payload["remediation_commands"][0] == "docker context ls"

    cli_output = tmp_path / "cli_docker_smoke.md"
    cli_json_output = tmp_path / "cli_docker_smoke.json"
    exit_code = main(
        [
            "docker-smoke",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["smoke_status"] == "not_available"
    assert cli_payload["environment"]["docker_binary"] == "docker"
    assert "docker_cli_path" in cli_payload["environment"]
    assert "docker_desktop_application" in cli_payload["environment"]
    assert "docker version" in cli_payload["remediation_commands"]
    assert cli_output.exists()


def test_docker_smoke_report_can_stop_after_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["docker", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="24.0.0\n", stderr="")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0, stdout="[]\n", stderr="")
        raise AssertionError(f"unexpected subprocess call: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = write_docker_smoke_report(
        project_root=Path("."),
        artifacts_dir=tmp_path / "artifacts",
        output_path=tmp_path / "docker_smoke.md",
        image="patchsmith-seeded-smoke:py312",
        run_seeded=False,
    )

    assert report.smoke_status == "skipped"
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["Docker Daemon"] == "passed"
    assert statuses["Smoke Image"] == "passed"
    assert statuses["Seeded Docker Test Run"] == "skipped"
    assert "docker/seeded-smoke.Dockerfile" in report.build_command
    assert report.remediation_commands[-1].startswith(
        "PYTHONPATH=src python3 -m patchsmith.cli docker-smoke"
    )


def test_release_hygiene_requires_committed_clean_git_repository(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    artifacts_dir = tmp_path / "artifacts"
    project_root.mkdir()
    _write_release_hygiene_fixture(project_root, artifacts_dir)

    _git(project_root, "init", "--initial-branch=main")
    empty_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "empty_git_hygiene.md",
    )
    assert empty_repo_report.release_status == "blocked"
    assert any(
        check.name == "Git Repository"
        and check.status == "blocked"
        and "has no commit yet" in check.evidence
        for check in empty_repo_report.checks
    )

    _git(project_root, "config", "user.email", "patchsmith@example.invalid")
    _git(project_root, "config", "user.name", "PatchSmith Test")
    _git(project_root, "add", ".")
    _git(project_root, "commit", "-m", "Initial release baseline")

    clean_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "clean_git_hygiene.md",
    )
    git_check = next(check for check in clean_repo_report.checks if check.name == "Git Repository")
    assert git_check.status == "passed"
    assert "worktree clean" in git_check.evidence
    assert any(
        check.name == "Packaging Config" and check.status == "passed"
        for check in clean_repo_report.checks
    )

    (project_root / "README.md").write_text(
        "ready_with_caveats offline live LLM calibration\nmodified\n",
        encoding="utf-8",
    )
    dirty_repo_report = write_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "dirty_git_hygiene.md",
    )
    assert dirty_repo_report.release_status == "blocked"
    assert any(
        check.name == "Git Repository"
        and check.status == "blocked"
        and "uncommitted file changes" in check.evidence
        for check in dirty_repo_report.checks
    )
