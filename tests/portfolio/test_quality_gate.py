import json
import sys
from pathlib import Path
from types import SimpleNamespace

from patchsmith.cli import main
from patchsmith.portfolio import command_checks as command_checks_module
from patchsmith.portfolio import quality_gate as quality_gate_module
from patchsmith.portfolio import (
    write_quality_gate_report,
)
from patchsmith.portfolio.quality_gate import DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS


def test_quality_gate_default_timeout_allows_optional_integration_imports() -> None:
    assert DEFAULT_QUALITY_GATE_TIMEOUT_SECONDS >= 600


def test_quality_gate_report_runs_quick_verifiers(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "quality_gate.md"
    json_output_path = tmp_path / "quality_gate.json"
    logs_dir = tmp_path / "quality_gate_logs"
    report = write_quality_gate_report(
        project_root=Path(),
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
    assert report.checks[0].command[0] == sys.executable
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


def test_quality_gate_package_build_uses_uv_provisioned_nonisolated_backend(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(command_checks_module.subprocess, "run", fake_run)

    report = quality_gate_module.build_quality_gate_report(
        project_root=Path(),
        artifacts_dir=tmp_path / "artifacts",
        logs_dir=tmp_path / "quality_gate_logs",
        include_tests=False,
        include_build=True,
    )

    assert report.quality_status == "passed_with_skips"
    build_check = next(check for check in report.checks if check.name == "Package build")
    assert build_check.command[:2] == ["uv", "run"]
    assert "build" in build_check.command
    assert "hatchling>=1.27" in build_check.command
    assert "--no-isolation" in build_check.command
    assert calls[-1] == build_check.command
