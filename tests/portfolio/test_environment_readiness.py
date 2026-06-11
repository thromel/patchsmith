import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_environment_readiness_report,
)


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
