import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_delivery_audit_report,
)


def test_delivery_audit_maps_objective_to_current_evidence(
    tmp_path: Path,
    capsys,
    write_progress_artifacts,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    write_progress_artifacts(artifacts_dir)
    experiments_dir = artifacts_dir / "experiments"
    public_dir = experiments_dir / "public_issue_corpus_v1"
    public_dir.mkdir(parents=True)
    (experiments_dir / "mvp_progress.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "completion_percent": 100.0,
                "blocked_count": 0,
                "warning_count": 0,
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
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
    )

    assert report.delivery_status == "in_progress_with_blockers"
    assert report.completion_percent > 50.0
    item_statuses = {item.requirement: item.status for item in report.items}
    assert item_statuses["Roadmap is decomposed into sprint plans."] == "passed"
    assert item_statuses["MVP checklist progress is evidence-backed."] == "passed"
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
