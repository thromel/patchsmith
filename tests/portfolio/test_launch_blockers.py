import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_launch_blocker_report,
)


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
