import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_demo_media_assets,
    write_demo_readiness_report,
    write_demo_script_report,
)
from patchsmith.portfolio import write_final_evaluation_report, write_release_hygiene_report


def _write_release_hygiene_fixture(project_root: Path, artifacts_dir: Path) -> None:
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


def test_demo_readiness_report_summarizes_launch_evidence(
    tmp_path: Path,
    capsys,
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
    assert cli_final_payload["decision_count"] >= 5
    assert cli_final_output.exists()

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
