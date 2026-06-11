import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_project_status_report,
)


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
