import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_demo_media_assets,
    write_demo_readiness_report,
    write_demo_script_report,
    write_docker_smoke_report,
    write_live_calibration_report,
    write_mvp_progress_report,
)
from patchsmith.portfolio import write_final_evaluation_report, write_release_hygiene_report


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
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/demo_media.md",
        "experiments/demo_media.json",
        "experiments/demo_media.svg",
        "experiments/demo_media.png",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
    ]:
        path = artifacts_dir / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "ok\n", encoding="utf-8")


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
    failed_run = (
        scaffold_dir
        / "agentless"
        / "run_artifacts"
        / "runs"
        / "run-fail"
    )
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
        "experiments/public_issue_corpus_v1/corpus_report.md",
        "experiments/public_issue_corpus_v1/corpus_summary.json",
        "experiments/public_issue_corpus_v1/repo_preflight_report.md",
        "experiments/public_issue_corpus_v1/repo_preflight_summary.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/demo_media.md",
        "experiments/demo_media.json",
        "experiments/demo_media.svg",
        "experiments/demo_media.png",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
    ]:
        path = artifacts_dir / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "ok\n", encoding="utf-8")

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
    assert any(check.name == "Git Repository" and check.status == "blocked" for check in hygiene.checks)
    assert any(check.name == "Packaging Config" and check.status == "passed" for check in hygiene.checks)
    assert any(check.name == "Planning Docs" and check.status == "passed" for check in hygiene.checks)
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
        "live DeepAgents model execution remains uncalibrated" in item
        for item in final.limitations
    )
    assert any(
        "live OpenAI Agents model execution remains uncalibrated" in item
        for item in final.limitations
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

    monkeypatch.setattr("patchsmith.portfolio.subprocess.run", fake_run)

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
    payload = json.loads((tmp_path / "docker_smoke.json").read_text(encoding="utf-8"))
    assert payload["smoke_status"] == "not_available"

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

    monkeypatch.setattr("patchsmith.portfolio.subprocess.run", fake_run)

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
