import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.portfolio import (
    write_evidence_refresh_report,
)


def test_evidence_refresh_report_runs_lightweight_status_refresh(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    output_path = tmp_path / "evidence_refresh.md"
    json_output_path = tmp_path / "evidence_refresh.json"

    report = write_evidence_refresh_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_quality_gate=False,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 8
    assert report.docker_smoke_refreshed is False
    assert any(step.name == "Docker smoke" and step.status == "skipped" for step in report.steps)
    assert any(step.name == "Quality gate" and step.status == "skipped" for step in report.steps)
    assert any(
        step.name == "Public issue repair readiness" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue repair attempts" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction plan" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue failure-signal discovery" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction spec validation" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Public issue reproduction execution" and step.status == "skipped"
        for step in report.steps
    )
    assert any(
        step.name == "Environment readiness" and step.status == "passed" for step in report.steps
    )
    assert (artifacts_dir / "experiments" / "project_status.json").exists()
    assert (artifacts_dir / "experiments" / "release_hygiene.json").exists()
    assert (artifacts_dir / "experiments" / "environment_readiness.json").exists()
    rendered = output_path.read_text(encoding="utf-8")
    assert "# PatchSmith Evidence Refresh Report" in rendered
    assert "--include-quality-gate" in rendered
    assert "--include-docker-smoke" in rendered
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["refresh_status"] == "passed_with_skips"
    assert payload["docker_smoke_refreshed"] is False

    cli_output = tmp_path / "cli_evidence_refresh.md"
    cli_json_output = tmp_path / "cli_evidence_refresh.json"
    exit_code = main(
        [
            "refresh-evidence",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--max-failure-runs",
            "5",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["refresh_status"] == "passed_with_skips"
    assert cli_payload["skipped_count"] == 8
    assert cli_payload["docker_smoke_refreshed"] is False
    assert cli_output.exists()


def test_evidence_refresh_prefers_reviewed_public_reproduction_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "focused_test_plan_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                    "focused_files": ["tests/test_bug.py"],
                    "policy_allowed": True,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    reviewed_specs_path = (
        project_root
        / "evals"
        / "issue_corpora"
        / "public_issue_smoke_v1"
        / "reproduction_specs.reviewed.json"
    )
    reviewed_specs_path.parent.mkdir(parents=True)
    reviewed_specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "fixture_files": [
                            {
                                "path": "tests/test_bug.py",
                                "content": "def test_bug():\n    assert False\n",
                            }
                        ],
                        "expected_failure_signals": ["AssertionError"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    assert report.failed_count == 0
    plan_summary = json.loads(
        (public_dir / "public_issue_reproduction_plan_summary.json").read_text(encoding="utf-8")
    )
    validation_summary = json.loads(
        (public_dir / "public_issue_reproduction_spec_validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    execution_summary = json.loads(
        (public_dir / "public_issue_reproduction_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan_summary["planned_tasks"] == 1
    assert plan_summary["fixture_file_tasks"] == 1
    assert validation_summary["ready_tasks"] == 1
    assert validation_summary["fixture_file_tasks"] == 1
    assert execution_summary["dry_run_tasks"] == 1
    assert execution_summary["fixture_file_tasks"] == 1


def test_evidence_refresh_preserves_executed_public_reproduction_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "focused_test_plan_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                    "policy_allowed": True,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    reviewed_specs_path = (
        project_root
        / "evals"
        / "issue_corpora"
        / "public_issue_smoke_v1"
        / "reproduction_specs.reviewed.json"
    )
    reviewed_specs_path.parent.mkdir(parents=True)
    reviewed_specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "expected_failure_signals": ["AssertionError"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-11T00:00:00Z",
                "dry_run": False,
                "attempted_tasks": 1,
                "reproduced_tasks": 1,
                "dry_run_tasks": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "status": "reproduced",
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "matched_failure_signals": ["AssertionError"],
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_reproduction_execution_report.md").write_text(
        "executed reproduction evidence\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    preserved_step = next(
        step for step in report.steps if step.name == "Public issue reproduction execution"
    )
    assert preserved_step.status == "passed"
    assert "Preserved existing executed reproduction evidence" in preserved_step.summary
    execution_summary = json.loads(
        (public_dir / "public_issue_reproduction_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert execution_summary["dry_run"] is False
    assert execution_summary["reproduced_tasks"] == 1


def test_evidence_refresh_preserves_executed_public_repair_attempt_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    artifacts_dir = project_root / "artifacts"
    public_dir = artifacts_dir / "experiments" / "public_issue_corpus_v1"
    tasks_dir = public_dir / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue_file": str(task_dir / "issue.md"),
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
                "suggested_commands": ["PYTHONPATH=src python3 -m patchsmith.cli run --json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "issue.md").write_text("public issue\n", encoding="utf-8")
    for name in [
        "focused_test_run_results.json",
        "focused_test_diagnosis_results.json",
        "focused_test_setup_validation_results.json",
    ]:
        (public_dir / name).write_text("[]\n", encoding="utf-8")
    (public_dir / "public_issue_repair_attempt_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-11T00:00:00Z",
                "dry_run": False,
                "attempted_tasks": 3,
                "validated_tasks": 1,
                "failed_tasks": 2,
                "blocked_tasks": 0,
                "reproduced_input_tasks": 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / "public_issue_repair_attempt_report.md").write_text(
        "executed repair evidence\n",
        encoding="utf-8",
    )

    report = write_evidence_refresh_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        output_path=tmp_path / "evidence_refresh.md",
        json_output_path=tmp_path / "evidence_refresh.json",
        max_failure_runs=5,
        include_quality_gate=False,
    )

    preserved_step = next(
        step for step in report.steps if step.name == "Public issue repair attempts"
    )
    assert preserved_step.status == "passed"
    assert "Preserved existing executed repair-attempt evidence" in preserved_step.summary
    attempt_summary = json.loads(
        (public_dir / "public_issue_repair_attempt_summary.json").read_text(encoding="utf-8")
    )
    assert attempt_summary["dry_run"] is False
    assert attempt_summary["attempted_tasks"] == 3


def test_evidence_refresh_can_refresh_docker_smoke(
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

    artifacts_dir = tmp_path / "artifacts"
    output_path = tmp_path / "evidence_refresh.md"
    json_output_path = tmp_path / "evidence_refresh.json"
    report = write_evidence_refresh_report(
        project_root=Path("."),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_docker_smoke=True,
        docker_smoke_skip_run=True,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 7
    assert report.docker_smoke_refreshed is True
    docker_step = next(step for step in report.steps if step.name == "Docker smoke")
    assert docker_step.status == "passed"
    assert "smoke_status=not_available" in docker_step.summary
    docker_payload = json.loads(
        (artifacts_dir / "experiments" / "docker_smoke.json").read_text(encoding="utf-8")
    )
    assert docker_payload["smoke_status"] == "not_available"

    cli_output = tmp_path / "cli_evidence_refresh.md"
    cli_json_output = tmp_path / "cli_evidence_refresh.json"
    exit_code = main(
        [
            "refresh-evidence",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(cli_output),
            "--json-output",
            str(cli_json_output),
            "--max-failure-runs",
            "5",
            "--include-docker-smoke",
            "--docker-smoke-skip-run",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["docker_smoke_refreshed"] is True
    assert cli_payload["skipped_count"] == 7
    assert cli_output.exists()
