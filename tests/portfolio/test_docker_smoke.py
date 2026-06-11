import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_docker_smoke_report,
)


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
