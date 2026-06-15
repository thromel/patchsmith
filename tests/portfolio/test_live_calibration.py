import json
from pathlib import Path

from patchsmith.portfolio import (
    write_final_evaluation_report,
    write_live_calibration_plan_report,
    write_live_calibration_report,
)


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
    report = write_live_calibration_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "calibration.md",
        json_output_path=tmp_path / "calibration.json",
        environment={},
        package_availability={"openai": True, "deepagents": False},
    )

    assert report.deepagents_package_run_count == 1
    assert report.deepagents_compatibility_run_count == 1
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["Saved DeepAgents Package Evidence"] == "passed"
    rendered = (tmp_path / "calibration.md").read_text(encoding="utf-8")
    assert "DeepAgents package-backed runs: `1`" in rendered
    payload = json.loads((tmp_path / "calibration.json").read_text(encoding="utf-8"))
    assert payload["deepagents_package_run_count"] == 1

    final = write_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "final.md",
        json_output_path=tmp_path / "final.json",
    )
    assert final.deepagents_package_run_count == 1
    assert any("package-backed" in decision for decision in final.decisions)
    assert any(
        "live DeepAgents model execution remains uncalibrated" in item for item in final.limitations
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
        package_availability={"openai": True, "deepagents": True},
    )

    checks = {check.name: check for check in report.checks}
    assert report.saved_live_provider_count == 1
    assert checks["Saved DeepAgents Package Evidence"].status == "passed"
    assert (
        "use saved deepagents_openai_chat rows for live DeepAgents model claims"
        in checks["Saved DeepAgents Package Evidence"].next_action
    )

    final = write_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "final.md",
        json_output_path=tmp_path / "final.json",
    )
    assert any("deepagents_openai_chat" in decision for decision in final.decisions)
    assert any(
        "DeepAgents live-model evidence is present for deepagents_openai_chat" in item
        for item in final.limitations
    )
    assert not any(
        "live DeepAgents model execution remains uncalibrated" in item for item in final.limitations
    )


def test_live_calibration_plan_includes_native_deepagents_live_runs(
    tmp_path: Path,
) -> None:
    plan = write_live_calibration_plan_report(
        artifacts_dir=tmp_path / "artifacts",
        output_path=tmp_path / "live_plan.md",
        json_output_path=tmp_path / "live_plan.json",
        environment={"OPENAI_API_KEY": "test-key"},
        package_availability={"openai": True, "deepagents": True},
    )

    runs = {run.name: run for run in plan.runs}
    smoke = runs["DeepAgents native single-task smoke"]
    suite = runs["DeepAgents native seeded-suite eval"]
    assert smoke.status == "ready"
    assert smoke.runtime == "deepagents"
    assert smoke.planner == "deepagents"
    assert smoke.requires_credentials
    assert "--runtime deepagents --planner deepagents --max-retries 1" in smoke.command
    assert "deepagents_openai_chat" in smoke.success_evidence
    assert suite.status == "waiting_for_smoke"
    assert "deepagents_native_repair_eval_v1" in suite.output_path
    assert "--max-tasks 10" in suite.command

    rendered = (tmp_path / "live_plan.md").read_text(encoding="utf-8")
    assert "DeepAgents native single-task smoke" in rendered
    payload = json.loads((tmp_path / "live_plan.json").read_text(encoding="utf-8"))
    assert payload["run_count"] == 3
    assert payload["ready_runs"] == 2
