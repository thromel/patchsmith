import json
from pathlib import Path
from types import SimpleNamespace

from patchsmith.cli import main
from patchsmith.evaluation import (
    check_public_issue_repair_readiness,
    discover_public_issue_failure_signals,
    execute_public_issue_repairs,
    execute_public_issue_reproductions,
    plan_public_issue_reproductions,
    validate_public_issue_reproduction_specs,
)


def test_plan_public_issue_reproductions_warns_without_expected_failure_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "test_commands": ["python3 -m pytest"],
                },
                "retrieval_preview": {"retrieved_files": ["tests/test_bug.py"]},
            }
        ),
        encoding="utf-8",
    )
    focused_plan_path = tmp_path / "focused_test_plan_results.json"
    focused_plan_path.write_text(
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
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "reproduction_plan"
    results, summary = plan_public_issue_reproductions(
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        output_dir=output_dir,
    )

    assert summary.warning_tasks == 1
    assert summary.manual_spec_required_tasks == 1
    assert summary.command_count == 1
    assert results[0].status == "warning"
    assert results[0].command_source == "focused_test_plan"
    assert results[0].policy_allowed
    assert results[0].manual_spec_required
    assert "expected failing signal is not encoded" in ";".join(results[0].warnings)
    assert (output_dir / "public_issue_reproduction_plan_report.md").exists()
    assert (output_dir / "public_issue_reproduction_plan_results.csv").exists()
    generated_template = json.loads(
        (output_dir / "public_issue_reproduction_specs_template.json").read_text(encoding="utf-8")
    )
    assert generated_template["specs"][0]["task_id"] == "public_task"
    assert generated_template["specs"][0]["command"] == "python3 -m pytest tests/test_bug.py"
    assert generated_template["specs"][0]["expected_failure_signals"] == []

    cli_output = tmp_path / "cli_reproduction_plan"
    exit_code = main(
        [
            "plan-public-issue-reproductions",
            "--tasks-dir",
            str(tasks_dir),
            "--focused-plan",
            str(focused_plan_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_reproduction_plan_report.md").exists()
    assert (cli_output / "public_issue_reproduction_specs_template.json").exists()


def test_plan_public_issue_reproductions_plans_explicit_failure_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
                "reproduction": {
                    "command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": ["AssertionError: expected public bug"],
                },
            }
        ),
        encoding="utf-8",
    )

    results, summary = plan_public_issue_reproductions(
        tasks_dir=tasks_dir,
        output_dir=tmp_path / "reproduction_plan",
    )

    assert summary.planned_tasks == 1
    assert summary.warning_tasks == 0
    assert results[0].status == "planned"
    assert not results[0].manual_spec_required
    assert results[0].expected_failure_signals == ["AssertionError: expected public bug"]
    assert results[0].command_source == "manifest_reproduction"


def test_plan_public_issue_reproductions_merges_reviewed_spec_file(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "test_commands": ["python3 -m pytest"],
                },
            }
        ),
        encoding="utf-8",
    )
    specs_path = tmp_path / "reproduction_specs.json"
    specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "fixture_files": [
                            {
                                "path": "tests/test_reviewed_repro.py",
                                "content": "def test_reviewed_repro():\n    assert False\n",
                            }
                        ],
                        "expected_failure_signals": [
                            "AssertionError: reviewed public issue signal"
                        ],
                        "source_hints": ["src/example.py"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "reproduction_plan"
    results, summary = plan_public_issue_reproductions(
        tasks_dir=tasks_dir,
        reproduction_specs_path=specs_path,
        output_dir=output_dir,
    )

    assert summary.planned_tasks == 1
    assert summary.manual_spec_required_tasks == 0
    assert summary.fixture_file_tasks == 1
    assert summary.fixture_file_count == 1
    assert results[0].status == "planned"
    assert results[0].command_source == "reproduction_spec"
    assert results[0].fixture_files == [
        {
            "path": "tests/test_reviewed_repro.py",
            "content": "def test_reviewed_repro():\n    assert False\n",
        }
    ]
    assert results[0].expected_failure_signals == ["AssertionError: reviewed public issue signal"]
    assert results[0].source_hints == ["src/example.py"]
    assert "reproduction spec provides an explicit command" in ";".join(results[0].evidence)
    assert "reproduction spec provides 1 reviewed source hint(s)" in ";".join(results[0].evidence)
    assert "expected failing signal is encoded in the reproduction spec" in ";".join(
        results[0].evidence
    )

    cli_output = tmp_path / "cli_reproduction_plan"
    exit_code = main(
        [
            "plan-public-issue-reproductions",
            "--tasks-dir",
            str(tasks_dir),
            "--reproduction-specs",
            str(specs_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    cli_results = json.loads(
        (cli_output / "public_issue_reproduction_plan_results.json").read_text(encoding="utf-8")
    )
    assert cli_results[0]["command_source"] == "reproduction_spec"
    assert cli_results[0]["fixture_files"][0]["path"] == "tests/test_reviewed_repro.py"


def test_validate_public_issue_reproduction_specs_blocks_unfilled_template(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "test_commands": ["python3 -m pytest"],
                },
            }
        ),
        encoding="utf-8",
    )
    specs_path = tmp_path / "public_issue_reproduction_specs_template.json"
    specs_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "specs": [
                    {
                        "task_id": "public_task",
                        "command": "python3 -m pytest tests/test_bug.py",
                        "expected_failure_signals": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "spec_validation"
    results, summary = validate_public_issue_reproduction_specs(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        output_dir=output_dir,
    )

    assert summary.blocked_tasks == 1
    assert summary.empty_signal_tasks == 1
    assert summary.missing_spec_tasks == 0
    assert results[0].status == "blocked"
    assert results[0].spec_present
    assert "expected_failure_signals is empty" in ";".join(results[0].errors)
    assert (output_dir / "public_issue_reproduction_spec_validation_report.md").exists()
    assert (output_dir / "public_issue_reproduction_spec_validation_results.csv").exists()

    cli_output = tmp_path / "cli_spec_validation"
    exit_code = main(
        [
            "validate-public-issue-reproduction-specs",
            "--specs",
            str(specs_path),
            "--tasks-dir",
            str(tasks_dir),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_reproduction_spec_validation_report.md").exists()


def test_validate_public_issue_reproduction_specs_accepts_reviewed_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                },
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        ),
        encoding="utf-8",
    )
    specs_path = tmp_path / "reviewed_specs.json"
    specs_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "source_hints": ["src/example.py"],
                    "expected_failure_signals": ["AssertionError: reviewed signal"],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_public_issue_reproduction_specs(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        output_dir=tmp_path / "spec_validation",
    )

    assert summary.ready_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.empty_signal_tasks == 0
    assert results[0].status == "ready"
    assert results[0].command_source == "reproduction_spec"
    assert results[0].source_hints == ["src/example.py"]
    assert results[0].expected_failure_signals == ["AssertionError: reviewed signal"]


def test_validate_public_issue_reproduction_specs_blocks_unsafe_fixture_path(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue": {"repository": "owner/repo"},
                "repository_snapshot": {"repo_path": str(repo_dir)},
            }
        ),
        encoding="utf-8",
    )
    specs_path = tmp_path / "reviewed_specs.json"
    specs_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "fixture_files": [
                        {
                            "path": "../tests/test_escape.py",
                            "content": "def test_escape():\n    assert False\n",
                        }
                    ],
                    "expected_failure_signals": ["AssertionError: reviewed signal"],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_public_issue_reproduction_specs(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        output_dir=tmp_path / "spec_validation",
    )

    assert summary.blocked_tasks == 1
    assert summary.unsafe_fixture_tasks == 1
    assert results[0].status == "blocked"
    assert "fixture_files[1].path cannot contain traversal" in ";".join(results[0].errors)


def test_discover_public_issue_failure_signals_dry_runs_without_expected_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": [],
                    "manual_spec_required": True,
                    "blockers": [],
                    "warnings": ["expected failing signal is not encoded"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "discovery"
    results, summary = discover_public_issue_failure_signals(
        plan_path=plan_path,
        output_dir=output_dir,
        sandbox_mode="local",
    )

    assert summary.dry_run_tasks == 1
    assert summary.blocked_tasks == 0
    assert results[0].status == "dry_run"
    assert results[0].candidate_failure_signals == []
    assert (output_dir / "public_issue_failure_signal_discovery_report.md").exists()
    assert (output_dir / "public_issue_failure_signal_discovery_results.csv").exists()

    cli_output = tmp_path / "cli_discovery"
    exit_code = main(
        [
            "discover-public-issue-failure-signals",
            "--plan",
            str(plan_path),
            "--output",
            str(cli_output),
            "--sandbox-mode",
            "local",
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_failure_signal_discovery_report.md").exists()


def test_discover_public_issue_failure_signals_extracts_local_failure(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text(
        "def test_bug():\n    raise AssertionError('expected public bug')\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": [],
                    "manual_spec_required": True,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = discover_public_issue_failure_signals(
        plan_path=plan_path,
        output_dir=tmp_path / "discovery",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.observed_failure_tasks == 1
    assert summary.candidate_signal_tasks == 1
    assert results[0].status == "observed_failure"
    assert results[0].exit_code == 1
    assert any("AssertionError" in signal for signal in results[0].candidate_failure_signals)
    assert results[0].stdout_path is not None
    assert results[0].stderr_path is not None


def test_discover_public_issue_failure_signals_applies_fixture_to_temp_workspace(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    fixture_path = repo_dir / "tests" / "test_fixture_repro.py"
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_fixture_repro.py",
                    "fixture_files": [
                        {
                            "path": "tests/test_fixture_repro.py",
                            "content": (
                                "def test_fixture_repro():\n"
                                "    raise AssertionError('fixture public bug')\n"
                            ),
                        }
                    ],
                    "expected_failure_signals": [],
                    "manual_spec_required": True,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = discover_public_issue_failure_signals(
        plan_path=plan_path,
        output_dir=tmp_path / "discovery",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.observed_failure_tasks == 1
    assert summary.fixture_file_tasks == 1
    assert results[0].status == "observed_failure"
    assert results[0].fixture_paths == ["tests/test_fixture_repro.py"]
    assert any("AssertionError" in signal for signal in results[0].candidate_failure_signals)
    assert not fixture_path.exists()


def test_discover_public_issue_failure_signals_ignores_xfailed_summary(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_xfail.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.xfail(reason='known')\n"
        "def test_xfail():\n"
        "    assert False\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_xfail.py",
                    "expected_failure_signals": [],
                    "manual_spec_required": True,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = discover_public_issue_failure_signals(
        plan_path=plan_path,
        output_dir=tmp_path / "discovery",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.passed_tasks == 1
    assert summary.candidate_signal_tasks == 0
    assert results[0].status == "passed"
    assert results[0].candidate_failure_signals == []


def test_execute_public_issue_reproductions_blocks_missing_failure_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": [],
                    "manual_spec_required": True,
                    "blockers": [],
                    "warnings": ["expected failing signal is not encoded"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "reproduction_execution"
    results, summary = execute_public_issue_reproductions(
        plan_path=plan_path,
        output_dir=output_dir,
        sandbox_mode="local",
    )

    assert summary.blocked_tasks == 1
    assert summary.manual_spec_required_tasks == 1
    assert results[0].status == "blocked"
    assert "expected failing signal is not encoded" in ";".join(results[0].errors)
    assert (output_dir / "public_issue_reproduction_execution_report.md").exists()
    assert (output_dir / "public_issue_reproduction_execution_results.csv").exists()

    cli_output = tmp_path / "cli_reproduction_execution"
    exit_code = main(
        [
            "execute-public-issue-reproductions",
            "--plan",
            str(plan_path),
            "--output",
            str(cli_output),
            "--sandbox-mode",
            "local",
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_reproduction_execution_report.md").exists()


def test_execute_public_issue_reproductions_dry_runs_explicit_failure_spec(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text(
        'def test_bug():\n    assert False, "expected public bug"\n',
        encoding="utf-8",
    )
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "planned",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": ["AssertionError: expected public bug"],
                    "manual_spec_required": False,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_public_issue_reproductions(
        plan_path=plan_path,
        output_dir=tmp_path / "reproduction_execution",
        sandbox_mode="local",
    )

    assert summary.dry_run_tasks == 1
    assert summary.blocked_tasks == 0
    assert results[0].status == "dry_run"
    assert results[0].policy_allowed
    assert results[0].missing_failure_signals == ["AssertionError: expected public bug"]


def test_execute_public_issue_reproductions_records_failing_signal(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text(
        'def test_bug():\n    assert False, "expected public bug"\n',
        encoding="utf-8",
    )
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "planned",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": ["AssertionError: expected public bug"],
                    "manual_spec_required": False,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "reproduction_execution"
    results, summary = execute_public_issue_reproductions(
        plan_path=plan_path,
        output_dir=output_dir,
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.reproduced_tasks == 1
    assert results[0].status == "reproduced"
    assert results[0].exit_code != 0
    assert results[0].matched_failure_signals == ["AssertionError: expected public bug"]
    assert results[0].missing_failure_signals == []
    assert results[0].stdout_path is not None
    assert Path(results[0].stdout_path).exists()
    assert results[0].stderr_path is not None
    assert Path(results[0].stderr_path).exists()


def test_execute_public_issue_reproductions_applies_fixture_to_temp_workspace(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    fixture_path = repo_dir / "tests" / "test_fixture_repro.py"
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "planned",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_fixture_repro.py",
                    "fixture_files": [
                        {
                            "path": "tests/test_fixture_repro.py",
                            "content": (
                                "def test_fixture_repro():\n"
                                "    assert False, 'fixture public bug'\n"
                            ),
                        }
                    ],
                    "expected_failure_signals": ["AssertionError: fixture public bug"],
                    "manual_spec_required": False,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_public_issue_reproductions(
        plan_path=plan_path,
        output_dir=tmp_path / "reproduction_execution",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.reproduced_tasks == 1
    assert summary.fixture_file_tasks == 1
    assert results[0].status == "reproduced"
    assert results[0].fixture_paths == ["tests/test_fixture_repro.py"]
    assert results[0].matched_failure_signals == ["AssertionError: fixture public bug"]
    assert not fixture_path.exists()


def test_execute_public_issue_reproductions_does_not_count_passing_command(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
    plan_path = tmp_path / "public_issue_reproduction_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/12",
                    "status": "planned",
                    "repo_path": str(repo_dir),
                    "reproduction_command": "python3 -m pytest tests/test_bug.py",
                    "expected_failure_signals": ["AssertionError: expected public bug"],
                    "manual_spec_required": False,
                    "blockers": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_public_issue_reproductions(
        plan_path=plan_path,
        output_dir=tmp_path / "reproduction_execution",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.not_reproduced_tasks == 1
    assert summary.reproduced_tasks == 0
    assert results[0].status == "not_reproduced"
    assert results[0].exit_code == 0
    assert "expected pre-repair failure was absent" in ";".join(results[0].warnings)


def test_check_public_issue_repair_readiness_warns_without_reproduction(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_id = "public_task"
    focused_run_path = tmp_path / "focused_test_run_results.json"
    diagnosis_path = tmp_path / "focused_test_diagnosis_results.json"
    setup_validation_path = tmp_path / "focused_test_setup_validation_results.json"
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    focused_run_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "passed",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                }
            ]
        ),
        encoding="utf-8",
    )
    diagnosis_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "category": "focused_test_passed",
                    "severity": "info",
                }
            ]
        ),
        encoding="utf-8",
    )
    setup_validation_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "passed",
                    "setup_execution_status": "passed",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_bug.py",
                    "sandbox_mode": "docker",
                    "sandbox_network": "bridge",
                    "failure_category": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "suggested_commands": [
                    "PYTHONPATH=src python3 -m patchsmith.cli run --repo repo --json"
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "repair_readiness"
    results, summary = check_public_issue_repair_readiness(
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        output_dir=output_dir,
        tasks_dir=tasks_dir,
    )

    assert summary.task_count == 1
    assert summary.warning_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.repair_command_tasks == 1
    assert summary.missing_reproduction_tasks == 1
    assert results[0].status == "warning"
    assert not results[0].blockers
    assert "issue reproduction is not proven" in ";".join(results[0].warnings)
    assert (output_dir / "public_issue_repair_readiness_report.md").exists()
    assert (output_dir / "public_issue_repair_readiness_results.csv").exists()

    cli_output = tmp_path / "cli_repair_readiness"
    exit_code = main(
        [
            "check-public-issue-repair-readiness",
            "--focused-run",
            str(focused_run_path),
            "--diagnosis",
            str(diagnosis_path),
            "--setup-validation",
            str(setup_validation_path),
            "--tasks-dir",
            str(tasks_dir),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_repair_readiness_report.md").exists()


def test_check_public_issue_repair_readiness_uses_reproduction_execution(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_id = "public_task"
    focused_run_path = tmp_path / "focused_test_run_results.json"
    diagnosis_path = tmp_path / "focused_test_diagnosis_results.json"
    setup_validation_path = tmp_path / "focused_test_setup_validation_results.json"
    reproduction_execution_path = tmp_path / "public_issue_reproduction_execution_results.json"
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    focused_run_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "passed",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                }
            ]
        ),
        encoding="utf-8",
    )
    diagnosis_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "category": "focused_test_passed",
                    "severity": "info",
                }
            ]
        ),
        encoding="utf-8",
    )
    setup_validation_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "passed",
                    "setup_execution_status": "passed",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_bug.py",
                    "sandbox_mode": "docker",
                    "sandbox_network": "none",
                    "failure_category": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    reproduction_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": task_id,
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "reproduced",
                    "reproduction_command": "python3 -m pytest tests/test_repro.py",
                    "fixture_files": [
                        {
                            "path": "tests/test_repro.py",
                            "content": "def test_repro():\n    assert False, 'expected public bug'\n",
                        }
                    ],
                    "source_hints": ["src/example.py"],
                    "stdout_path": str(tmp_path / "stdout.txt"),
                    "stderr_path": str(tmp_path / "stderr.txt"),
                    "matched_failure_signals": ["AssertionError: expected public bug"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "suggested_commands": [
                    "PYTHONPATH=src python3 -m patchsmith.cli run --repo repo --json"
                ],
            }
        ),
        encoding="utf-8",
    )

    results, summary = check_public_issue_repair_readiness(
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=reproduction_execution_path,
        output_dir=tmp_path / "repair_readiness",
        tasks_dir=tasks_dir,
    )

    assert summary.ready_tasks == 1
    assert summary.warning_tasks == 0
    assert summary.missing_reproduction_tasks == 0
    assert summary.reproduced_tasks == 1
    assert results[0].status == "ready"
    assert results[0].reproduction_execution_status == "reproduced"
    assert results[0].validation_command == "python3 -m pytest tests/test_repro.py"
    assert results[0].validation_fixture_paths == ["tests/test_repro.py"]
    assert results[0].validation_source_hints == ["src/example.py"]
    assert results[0].validation_fixture_files[0]["content"].startswith("def test_repro")
    assert "saved failing evidence" in ";".join(results[0].evidence)
    assert "issue-specific validation command is available" in ";".join(results[0].evidence)
    assert "issue reproduction is not proven" not in ";".join(results[0].warnings)


def test_check_public_issue_repair_readiness_blocks_missing_setup_validation(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    focused_run_path = tmp_path / "focused_test_run_results.json"
    diagnosis_path = tmp_path / "focused_test_diagnosis_results.json"
    setup_validation_path = tmp_path / "focused_test_setup_validation_results.json"
    focused_run_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/11",
                    "status": "passed",
                    "command": "python3 -m pytest tests/test_bug.py",
                    "repo_path": str(repo_dir),
                }
            ]
        ),
        encoding="utf-8",
    )
    diagnosis_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "category": "focused_test_passed",
                    "severity": "info",
                }
            ]
        ),
        encoding="utf-8",
    )
    setup_validation_path.write_text("[]", encoding="utf-8")

    results, summary = check_public_issue_repair_readiness(
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        output_dir=tmp_path / "repair_readiness",
    )

    assert summary.blocked_tasks == 1
    assert results[0].status == "blocked"
    assert "setup validation record is missing" in ";".join(results[0].blockers)


def test_execute_public_issue_repairs_blocks_without_reproduction(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "public_issue_repair_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "warning",
                    "repo_path": str(repo_dir),
                    "repo_exists": True,
                    "repair_command": "PYTHONPATH=src python3 -m patchsmith.cli run --json",
                    "validation_command": "python3 -m pytest tests/test_bug.py",
                    "reproduction_execution_status": "blocked",
                    "blockers": [],
                    "warnings": ["public issue reproduction execution is blocked"],
                    "evidence": ["saved PatchSmith repair command is available"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "repair_attempts"
    results, summary = execute_public_issue_repairs(
        readiness_path=readiness_path,
        output_dir=output_dir,
    )

    assert summary.blocked_tasks == 1
    assert summary.attempted_tasks == 0
    assert results[0].status == "blocked"
    assert "public issue reproduction has not been proven" in ";".join(results[0].errors)
    assert (output_dir / "public_issue_repair_attempt_report.md").exists()
    assert (output_dir / "public_issue_repair_attempt_results.csv").exists()

    cli_output = tmp_path / "cli_repair_attempts"
    exit_code = main(
        [
            "execute-public-issue-repairs",
            "--readiness",
            str(readiness_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "public_issue_repair_attempt_report.md").exists()


def test_execute_public_issue_repairs_dry_runs_ready_task(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    issue_path = task_dir / "issue.md"
    issue_path.write_text("add returns wrong result\n", encoding="utf-8")
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue_file": str(issue_path),
                "suggested_commands": ["PYTHONPATH=src python3 -m patchsmith.cli run --json"],
            }
        ),
        encoding="utf-8",
    )
    readiness_path = tmp_path / "public_issue_repair_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "ready",
                    "repo_path": str(repo_dir),
                    "repo_exists": True,
                    "repair_command": "PYTHONPATH=src python3 -m patchsmith.cli run --json",
                    "validation_command": "python3 -m pytest tests/test_bug.py",
                    "reproduction_execution_status": "reproduced",
                    "blockers": [],
                    "warnings": [],
                    "evidence": ["public issue reproduction execution saved failing evidence"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_public_issue_repairs(
        readiness_path=readiness_path,
        output_dir=tmp_path / "repair_attempts",
        tasks_dir=tasks_dir,
        runtime="heuristic",
        planner="heuristic",
        sandbox_mode="local",
    )

    assert summary.dry_run_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.reproduced_input_tasks == 1
    assert summary.max_retries == 0
    assert results[0].status == "dry_run"
    assert "repair attempt passed dry-run gating" in ";".join(results[0].evidence)


def test_execute_public_issue_repairs_passes_source_hints_as_context_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_dir = tmp_path / "repo"
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "example.py").write_text("def target_symbol():\n    pass\n", encoding="utf-8")
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    issue_path = task_dir / "issue.md"
    issue_path.write_text("external failure needs reviewed source context\n", encoding="utf-8")
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue_file": str(issue_path),
                "suggested_commands": ["PYTHONPATH=src python3 -m patchsmith.cli run --json"],
            }
        ),
        encoding="utf-8",
    )
    readiness_path = tmp_path / "public_issue_repair_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "ready",
                    "repo_path": str(repo_dir),
                    "repo_exists": True,
                    "repair_command": "PYTHONPATH=src python3 -m patchsmith.cli run --json",
                    "validation_command": "python3 -m pytest tests/test_bug.py",
                    "validation_source_hints": ["src/example.py#target_symbol"],
                    "reproduction_execution_status": "reproduced",
                    "blockers": [],
                    "warnings": [],
                    "evidence": ["public issue reproduction execution saved failing evidence"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    captured_requests = []

    class FakeRepairRunner:
        def __init__(self, *, artifacts_dir: Path) -> None:
            self.artifacts_dir = artifacts_dir

        def run(self, request):
            captured_requests.append(request)
            run_dir = self.artifacts_dir / "runs" / "fake-run"
            run_dir.mkdir(parents=True)
            report_path = run_dir / "report.md"
            trace_path = run_dir / "traces.jsonl"
            diff_path = run_dir / "final.diff"
            report_path.write_text("fake report\n", encoding="utf-8")
            trace_path.write_text("", encoding="utf-8")
            diff_path.write_text("", encoding="utf-8")
            return SimpleNamespace(
                run_id="fake-run",
                status="completed",
                report_path=report_path,
                trace_path=trace_path,
                final_diff_path=diff_path,
                test_result=SimpleNamespace(exit_code=1),
            )

    monkeypatch.setattr(
        "patchsmith.evaluation.issue_corpus.public_issues.RepairRunner",
        FakeRepairRunner,
    )

    results, summary = execute_public_issue_repairs(
        readiness_path=readiness_path,
        output_dir=tmp_path / "repair_attempts",
        tasks_dir=tasks_dir,
        dry_run=False,
    )

    assert summary.attempted_tasks == 1
    assert results[0].status == "failed"
    assert len(captured_requests) == 1
    assert captured_requests[0].context_paths == ("src/example.py",)
    assert "`src/example.py#target_symbol`" in captured_requests[0].issue_text


def test_execute_public_issue_repairs_executes_local_heuristic_repair(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    src_dir = repo_dir / "src"
    tests_dir = repo_dir / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.pytest.ini_options]",
                'pythonpath = ["src"]',
                'testpaths = ["tests"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (src_dir / "simple_calc.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    (tests_dir / "test_simple_calc.py").write_text(
        "from simple_calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / "materialized_tasks"
    task_dir = tasks_dir / "public_task"
    task_dir.mkdir(parents=True)
    issue_path = task_dir / "issue.md"
    issue_path.write_text("add returns wrong result\n", encoding="utf-8")
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_id": "public_task",
                "issue_file": str(issue_path),
                "suggested_commands": ["PYTHONPATH=src python3 -m patchsmith.cli run --json"],
            }
        ),
        encoding="utf-8",
    )
    readiness_path = tmp_path / "public_issue_repair_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "public_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/10",
                    "status": "ready",
                    "repo_path": str(repo_dir),
                    "repo_exists": True,
                    "repair_command": "PYTHONPATH=src python3 -m patchsmith.cli run --json",
                    "validation_command": "python3 -m pytest tests/test_issue_repro.py",
                    "validation_fixture_files": [
                        {
                            "path": "tests/test_issue_repro.py",
                            "content": (
                                "from simple_calc import add\n\n\n"
                                "def test_public_issue_repro():\n"
                                "    assert add(2, 3) == 5\n"
                            ),
                        }
                    ],
                    "validation_fixture_paths": ["tests/test_issue_repro.py"],
                    "validation_source_hints": ["src/simple_calc.py"],
                    "reproduction_execution_status": "reproduced",
                    "blockers": [],
                    "warnings": [],
                    "evidence": ["public issue reproduction execution saved failing evidence"],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "repair_attempts"
    results, summary = execute_public_issue_repairs(
        readiness_path=readiness_path,
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        runtime="heuristic",
        planner="heuristic",
        sandbox_mode="local",
        max_retries=2,
        dry_run=False,
    )

    assert summary.attempted_tasks == 1
    assert summary.validated_tasks == 1
    assert summary.max_retries == 2
    assert results[0].status == "validated"
    assert results[0].patch_generated
    assert results[0].test_exit_code == 0
    assert results[0].validation_fixture_paths == ["tests/test_issue_repro.py"]
    assert results[0].report_path is not None
    assert Path(results[0].report_path).exists()
    report_text = Path(results[0].report_path).read_text(encoding="utf-8")
    assert "Reviewed source files and fixture import hints" in report_text
    assert "src/simple_calc.py" in report_text
