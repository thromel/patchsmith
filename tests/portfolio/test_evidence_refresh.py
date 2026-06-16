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
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_quality_gate=False,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 9
    assert report.docker_smoke_refreshed is False
    assert report.complex_suite_refreshed is False
    assert any(step.name == "Docker smoke" and step.status == "skipped" for step in report.steps)
    assert any(step.name == "Quality gate" and step.status == "skipped" for step in report.steps)
    assert any(
        step.name == "Complex benchmark suite" and step.status == "skipped" for step in report.steps
    )
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
    assert payload["complex_suite_refreshed"] is False

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
    assert cli_payload["skipped_count"] == 9
    assert cli_payload["docker_smoke_refreshed"] is False
    assert cli_payload["complex_suite_refreshed"] is False
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
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_docker_smoke=True,
        docker_smoke_skip_run=True,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 8
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
    assert cli_payload["skipped_count"] == 8
    assert cli_output.exists()


def test_evidence_refresh_can_refresh_complex_benchmark_suite(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    attempt_dir = _write_complex_attempt_dir(
        tmp_path / "attempts" / "attempt_a",
        task_id="suite_task_a",
        cost=0.04,
        total_tokens=400,
    )
    output_path = tmp_path / "evidence_refresh.md"
    json_output_path = tmp_path / "evidence_refresh.json"
    suite_output_dir = tmp_path / "suite"

    report = write_evidence_refresh_report(
        project_root=Path(),
        artifacts_dir=artifacts_dir,
        output_path=output_path,
        json_output_path=json_output_path,
        max_failure_runs=5,
        include_complex_suite=True,
        complex_suite_attempt_dirs=(attempt_dir,),
        complex_suite_output_dir=suite_output_dir,
        complex_suite_min_validation_rate=1.0,
        complex_suite_min_live_provider_tasks=1,
        complex_suite_min_unique_tasks=1,
        complex_suite_max_selected_cost_per_validated_task_usd=0.05,
        complex_suite_max_selected_tokens_per_validated_task=500.0,
        complex_suite_max_selected_virtual_files_per_validated_task=4.0,
        complex_suite_max_selected_tokens_per_virtual_file=100.0,
        complex_suite_max_selected_responses_per_virtual_file=0.25,
        complex_suite_min_selected_progress_score=1.0,
        complex_suite_min_selected_context_target_recall=1.0,
        complex_suite_min_selected_context_target_precision=0.25,
        complex_suite_min_repo_instructions_manifest_rate=1.0,
        complex_suite_min_repo_instructions_read_first_rate=1.0,
        complex_suite_min_acceptance_rubric_manifest_rate=1.0,
        complex_suite_min_acceptance_rubric_read_first_rate=1.0,
        complex_suite_min_acceptance_rubric_alignment_rate=1.0,
        complex_suite_min_agent_trajectory_score=0.80,
        complex_suite_min_contextual_verifier_rate=1.0,
    )

    assert report.refresh_status == "passed_with_skips"
    assert report.failed_count == 0
    assert report.skipped_count == 8
    assert report.complex_suite_refreshed is True
    complex_step = next(step for step in report.steps if step.name == "Complex benchmark suite")
    assert complex_step.status == "passed"
    assert "suite_status=passed" in complex_step.summary
    assert "validated=1" in complex_step.summary
    assert "progress=1.00" in complex_step.summary
    assert "selected_progress=1.00" in complex_step.summary
    assert "partial_progress=0" in complex_step.summary
    assert "failure_classes=validated=1" in complex_step.summary
    assert "selected_failure_classes=validated=1" in complex_step.summary
    assert "harness_layers=none=1" in complex_step.summary
    assert "selected_harness_layers=none=1" in complex_step.summary
    assert "retry_failure_classes=none" in complex_step.summary
    assert "process_quality=solid=1" in complex_step.summary
    assert "process_flags=none" in complex_step.summary
    assert "cost_per_validated=$0.040000" in complex_step.summary
    assert "tokens_per_virtual_file=100.00" in complex_step.summary
    assert "responses_per_virtual_file=0.25" in complex_step.summary
    assert "context_target_recall=1.00" in complex_step.summary
    assert "context_target_precision=0.25" in complex_step.summary
    assert "repo_instructions_manifest_rate=1.00" in complex_step.summary
    assert "repo_instructions_read_first_rate=1.00" in complex_step.summary
    assert "acceptance_rubric_manifest_rate=1.00" in complex_step.summary
    assert "acceptance_rubric_read_first_rate=1.00" in complex_step.summary
    assert "acceptance_rubric_alignment_rate=1.00" in complex_step.summary
    assert "contextual_verifier=1.00" in complex_step.summary
    assert (suite_output_dir / "complex_benchmark_suite_report.md").exists()
    gate_payload = json.loads(
        (suite_output_dir / "complex_benchmark_suite_gate.json").read_text(encoding="utf-8")
    )
    assert gate_payload["status"] == "passed"
    assert gate_payload["min_selected_progress_score"] == 1.0
    assert gate_payload["min_selected_context_target_recall"] == 1.0
    assert gate_payload["min_selected_context_target_precision"] == 0.25
    assert gate_payload["min_repo_instructions_manifest_rate"] == 1.0
    assert gate_payload["min_repo_instructions_read_first_rate"] == 1.0
    assert gate_payload["min_acceptance_rubric_manifest_rate"] == 1.0
    assert gate_payload["min_acceptance_rubric_read_first_rate"] == 1.0
    assert gate_payload["min_acceptance_rubric_alignment_rate"] == 1.0
    assert gate_payload["min_contextual_verifier_rate"] == 1.0
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["complex_suite_refreshed"] is True
    rendered = output_path.read_text(encoding="utf-8")
    assert "Complex suite refreshed: `true`" in rendered
    assert "Complex benchmark suite" in rendered

    cli_output = tmp_path / "cli_evidence_refresh.md"
    cli_json_output = tmp_path / "cli_evidence_refresh.json"
    cli_suite_output_dir = tmp_path / "cli_suite"
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
            "--include-complex-suite",
            "--complex-suite-attempt-dir",
            str(attempt_dir),
            "--complex-suite-output-dir",
            str(cli_suite_output_dir),
            "--complex-suite-min-validation-rate",
            "1.0",
            "--complex-suite-min-live-provider-tasks",
            "1",
            "--complex-suite-min-unique-tasks",
            "1",
            "--complex-suite-max-selected-cost-per-validated-task-usd",
            "0.05",
            "--complex-suite-max-selected-tokens-per-validated-task",
            "500",
            "--complex-suite-max-selected-virtual-files-per-validated-task",
            "4",
            "--complex-suite-max-selected-tokens-per-virtual-file",
            "100",
            "--complex-suite-max-selected-responses-per-virtual-file",
            "0.25",
            "--complex-suite-min-selected-progress-score",
            "1.0",
            "--complex-suite-min-selected-context-target-recall",
            "1.0",
            "--complex-suite-min-selected-context-target-precision",
            "0.25",
            "--complex-suite-min-acceptance-rubric-manifest-rate",
            "1.0",
            "--complex-suite-min-acceptance-rubric-read-first-rate",
            "1.0",
            "--complex-suite-min-acceptance-rubric-alignment-rate",
            "1.0",
            "--complex-suite-min-agent-trajectory-score",
            "0.80",
            "--complex-suite-min-contextual-verifier-rate",
            "1.0",
            "--json",
        ]
    )
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["complex_suite_refreshed"] is True
    assert cli_payload["skipped_count"] == 8
    assert (cli_suite_output_dir / "complex_benchmark_suite_gate.json").exists()

    spec_suite_output_dir = tmp_path / "spec_suite"
    suite_spec_path = tmp_path / "complex_suite_spec.json"
    suite_spec_path.write_text(
        json.dumps(
            {
                "benchmark": "public_issue_repair_attempts",
                "attempt_dirs": [str(attempt_dir)],
                "output_dir": str(spec_suite_output_dir),
                "gate": {
                    "min_validation_rate": 1.0,
                    "min_live_provider_tasks": 1,
                    "min_unique_tasks": 1,
                    "max_selected_cost_per_validated_task_usd": 0.05,
                    "max_selected_tokens_per_validated_task": 500.0,
                    "max_selected_virtual_files_per_validated_task": 4.0,
                    "max_selected_tokens_per_virtual_file": 100.0,
                    "max_selected_responses_per_virtual_file": 0.25,
                    "min_selected_progress_score": 1.0,
                    "min_selected_context_target_recall": 1.0,
                    "min_selected_context_target_precision": 0.25,
                    "min_repo_instructions_manifest_rate": 1.0,
                    "min_repo_instructions_read_first_rate": 1.0,
                    "min_acceptance_rubric_manifest_rate": 1.0,
                    "min_acceptance_rubric_read_first_rate": 1.0,
                    "min_acceptance_rubric_alignment_rate": 1.0,
                    "min_agent_trajectory_score": 0.80,
                    "min_contextual_verifier_rate": 1.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    spec_cli_output = tmp_path / "spec_cli_evidence_refresh.md"
    spec_cli_json_output = tmp_path / "spec_cli_evidence_refresh.json"
    exit_code = main(
        [
            "refresh-evidence",
            "--project-root",
            ".",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(spec_cli_output),
            "--json-output",
            str(spec_cli_json_output),
            "--max-failure-runs",
            "5",
            "--complex-suite-spec",
            str(suite_spec_path),
            "--json",
        ]
    )
    assert exit_code == 0
    spec_cli_payload = json.loads(capsys.readouterr().out)
    assert spec_cli_payload["complex_suite_refreshed"] is True
    assert (spec_suite_output_dir / "complex_benchmark_suite_gate.json").exists()


def _write_complex_attempt_dir(
    attempt_dir: Path,
    *,
    task_id: str,
    cost: float,
    total_tokens: int,
) -> Path:
    attempt_dir.mkdir(parents=True)
    trace_path = attempt_dir / "runs" / task_id / "traces.jsonl"
    trace_path.parent.mkdir(parents=True)
    final_diff_path = trace_path.parent / "final.diff"
    final_diff_path.write_text(
        "diff --git a/src/pkg.py b/src/pkg.py\n"
        "--- a/src/pkg.py\n"
        "+++ b/src/pkg.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "node_name": "runtime.todo",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {"node": "todo"},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.plan",
                        "event_type": "runtime_node",
                        "status": "completed",
                        "payload": {
                            "node": "plan",
                            "metadata": {
                                "model_call": {
                                    "provider": "deepagents_openai_chat",
                                    "response_count": 1,
                                    "input_tokens": total_tokens - 10,
                                    "output_tokens": 10,
                                    "total_tokens": total_tokens,
                                    "estimated_cost_usd": cost,
                                },
                                "deepagents_contract": {
                                    "virtual_file_count": 4,
                                    "filesystem_policy": {
                                        "allowed_read_paths": [
                                            "/.patchsmith/acceptance-rubric.md",
                                            "/.patchsmith/repo-instructions.md",
                                            "/src/pkg.py",
                                            "/src/unused.py",
                                            "/tests/test_pkg.py",
                                            "/docs/pkg.md",
                                        ]
                                    },
                                    "repo_instructions_manifest_path": (
                                        "/.patchsmith/repo-instructions.md"
                                    ),
                                    "acceptance_rubric_manifest_path": (
                                        "/.patchsmith/acceptance-rubric.md"
                                    ),
                                    "subagents": [{"name": "patch-reviewer"}],
                                    "response_format": "PatchPlan",
                                    "planning_policy": {
                                        "repo_instructions_manifest_read_first": True,
                                        "acceptance_rubric_manifest_read_first": True,
                                        "todos_required": True,
                                        "one_bounded_replacement": True,
                                    },
                                },
                                "failure_localization": {
                                    "failure_mechanism": "The validation inspects src/pkg.py.",
                                    "target_rationale": "src/pkg.py owns the failing behavior.",
                                },
                            },
                            "patch_plan": {"path": "src/pkg.py", "status": "matched"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "runtime.patch_quality",
                        "event_type": "runtime_node",
                        "status": "low",
                        "payload": {
                            "node": "patch_quality",
                            "quality": {"severity": "low", "score": 0, "findings": []},
                        },
                    }
                ),
                json.dumps(
                    {
                        "node_name": "test",
                        "event_type": "sandbox_command",
                        "status": "completed",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "node_name": "analyze",
                        "event_type": "repair_outcome",
                        "status": "validated",
                        "payload": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "org/repo",
                    "status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 0,
                    "trace_path": str(trace_path),
                    "final_diff_path": str(final_diff_path),
                    "report_path": str(trace_path.parent / "report.md"),
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return attempt_dir
