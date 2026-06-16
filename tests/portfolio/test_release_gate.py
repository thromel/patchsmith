import json
from pathlib import Path
from types import SimpleNamespace

from patchsmith.cli import main
from patchsmith.portfolio import command_checks as command_checks_module
from patchsmith.portfolio import write_release_gate_report


def test_release_gate_runs_help_export_and_saved_benchmark_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="help text", stderr="")

    monkeypatch.setattr(command_checks_module.subprocess, "run", fake_run)
    benchmark_results_path = tmp_path / "complex_benchmark_results.json"
    benchmark_results_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "task-1",
                    "repository": "example/repo",
                    "issue_url": None,
                    "status": "validated",
                    "strict_status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduced": True,
                    "patch_generated": True,
                    "validation_passed": True,
                    "test_exit_code": 0,
                    "trace_path": None,
                    "report_path": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    report = write_release_gate_report(
        project_root=Path(),
        artifacts_dir=tmp_path / "artifacts",
        output_path=tmp_path / "release_gate.md",
        json_output_path=tmp_path / "release_gate.json",
        logs_dir=tmp_path / "release_gate_logs",
        include_unit_tests=False,
        include_smoke=True,
        include_build=True,
        include_cli_help=True,
        benchmark_results_path=benchmark_results_path,
    )

    assert report.release_status == "passed_with_skips"
    assert report.passed_count == 8
    assert report.skipped_count == 1
    assert len(calls) == 5
    assert calls[0][-3:] == [
        "tests/chat/test_session_resume.py",
        "tests/session/test_transcript_migration.py",
        "tests/evaluation/complex/test_compatibility.py",
    ]
    assert calls[1][:2] == ["uv", "run"]
    assert calls[2][-1] == "--help"
    assert calls[3][-2:] == ["agent", "--help"]
    assert calls[4][-2:] == ["chat", "--help"]
    assert (tmp_path / "release_gate.md").read_text(encoding="utf-8").startswith(
        "# PatchSmith Release Gate Report"
    )
    payload = json.loads((tmp_path / "release_gate.json").read_text(encoding="utf-8"))
    assert payload["release_status"] == "passed_with_skips"
    assert (
        tmp_path
        / "artifacts"
        / "experiments"
        / "release_gate"
        / "sample_session.md"
    ).is_file()
    benchmark_check = next(
        check for check in report.checks if check.name == "Saved benchmark suite validation"
    )
    assert benchmark_check.status == "passed"
    assert "1 validated" in benchmark_check.summary
    ownership_check = next(
        check for check in report.checks if check.name == "Product boundary ownership docs"
    )
    assert ownership_check.status == "passed"
    assert any(
        artifact.endswith("docs/23_product_boundary_ownership.md")
        for artifact in report.review_artifacts
    )


def test_release_gate_cli_writes_json_summary_without_running_heavy_steps(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "cli_release_gate.md"
    json_output_path = tmp_path / "cli_release_gate.json"

    exit_code = main(
        [
            "release-gate",
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--output",
            str(output_path),
            "--json-output",
            str(json_output_path),
            "--skip-unit-tests",
            "--skip-smoke",
            "--skip-build",
            "--skip-cli-help",
            "--skip-benchmark-validation",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["release_status"] == "passed_with_skips"
    assert payload["passed_count"] == 2
    assert output_path.is_file()
    assert json_output_path.is_file()
