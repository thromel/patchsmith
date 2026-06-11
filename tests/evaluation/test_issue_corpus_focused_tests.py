import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.evaluation import (
    check_focused_test_setup_readiness,
    diagnose_focused_test_runs,
    execute_focused_test_setups,
    materialize_issue_corpus_tasks,
    plan_focused_test_setups,
    plan_materialized_issue_focused_tests,
    preview_issue_corpus_context,
    run_materialized_issue_focused_tests,
    validate_focused_test_setups,
)


def test_plan_materialized_issue_focused_tests_uses_retrieved_tests(
    tmp_path: Path,
) -> None:
    fixture_repo = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo").resolve()
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "local_focused_tests",
                "issues": [
                    {
                        "task_id": "local_simple_calc",
                        "source": "github_issue",
                        "repository": "local/simple_calc",
                        "repo_url": str(fixture_repo),
                        "issue_url": "https://github.com/example/simple-calc/issues/1",
                        "issue_number": 1,
                        "title": "Addition returns the wrong result in simple_calc",
                        "language": "python",
                        "task_type": "logic_bug",
                        "state_at_capture": "open",
                        "captured_at": "2026-06-10T08:16:00Z",
                        "selection_reason": "Local fixture for focused test planning.",
                        "expected_workflow": ["retrieve simple_calc implementation"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "focused_tests"
    preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=output_dir,
        context_provider="native_hybrid",
    )
    materialize_issue_corpus_tasks(
        corpus_path=corpus_path,
        output_dir=output_dir,
    )

    results, summary = plan_materialized_issue_focused_tests(
        tasks_dir=output_dir / "materialized_tasks",
        output_dir=output_dir,
    )

    assert summary.planned_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.policy_allowed_commands == 1
    assert results[0].status == "planned"
    assert results[0].focused_files == ["tests/test_simple_calc.py"]
    assert results[0].command == "python3 -m pytest tests/test_simple_calc.py"
    assert (output_dir / "focused_test_plan_report.md").exists()
    assert (output_dir / "focused_test_plan_results.csv").exists()

    cli_output = tmp_path / "cli_focused_tests"
    exit_code = main(
        [
            "plan-materialized-focused-tests",
            "--tasks-dir",
            str(output_dir / "materialized_tasks"),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_plan_report.md").exists()


def test_plan_materialized_issue_focused_tests_falls_back_without_retrieved_tests(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "fallback_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_manifest_version": 1,
                "task_id": "fallback_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "file_count": 3,
                    "package_manager": "python/pyproject",
                    "test_commands": ["python3 -m pytest"],
                },
                "retrieval_preview": {
                    "retrieved_files": ["src/example.py", "README.md"],
                },
            }
        ),
        encoding="utf-8",
    )

    results, summary = plan_materialized_issue_focused_tests(
        tasks_dir=tmp_path / "tasks",
        output_dir=tmp_path / "plan",
    )

    assert summary.fallback_tasks == 1
    assert results[0].status == "fallback"
    assert results[0].focused_files == []
    assert results[0].policy_allowed
    assert "fallback" in ";".join(results[0].risk_notes)


def test_run_materialized_issue_focused_tests_executes_planned_command(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "focused_test_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "passing_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                    "repo_path": str(repo_dir),
                    "focused_files": ["tests/test_ok.py"],
                    "command": "python3 -m pytest tests/test_ok.py",
                    "policy_allowed": True,
                    "policy_reason": "allowed",
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "focused_run"
    results, summary = run_materialized_issue_focused_tests(
        plan_path=plan_path,
        output_dir=output_dir,
        sandbox_network="bridge",
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.passed_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.sandbox_network == "bridge"
    assert results[0].status == "passed"
    assert results[0].exit_code == 0
    assert results[0].stdout_path is not None
    assert Path(results[0].stdout_path).exists()
    assert (output_dir / "focused_test_run_report.md").exists()
    assert (output_dir / "focused_test_run_results.csv").exists()

    cli_output = tmp_path / "cli_focused_run"
    exit_code = main(
        [
            "run-materialized-focused-tests",
            "--plan",
            str(plan_path),
            "--output",
            str(cli_output),
            "--timeout-seconds",
            "30",
            "--sandbox-network",
            "bridge",
            "--json",
        ]
    )
    assert exit_code == 0
    report = cli_output / "focused_test_run_report.md"
    assert report.exists()
    assert "Sandbox network: `bridge`" in report.read_text(encoding="utf-8")


def test_run_materialized_issue_focused_tests_blocks_policy_mismatch(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    plan_path = tmp_path / "focused_test_plan_results.json"
    plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "unsafe_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/2",
                    "repo_path": str(repo_dir),
                    "focused_files": [],
                    "command": "python3 -m pytest && printenv",
                    "policy_allowed": True,
                    "policy_reason": "allowed",
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = run_materialized_issue_focused_tests(
        plan_path=plan_path,
        output_dir=tmp_path / "focused_run",
    )

    assert summary.attempted_tasks == 0
    assert summary.blocked_tasks == 1
    assert results[0].status == "blocked"
    assert not results[0].policy_allowed
    assert "rejected by policy" in ";".join(results[0].errors)


def test_diagnose_focused_test_runs_classifies_readiness_failures(
    tmp_path: Path,
) -> None:
    logs_dir = tmp_path / "logs"
    pytest_dir = logs_dir / "pytest_task"
    requests_dir = logs_dir / "requests_task"
    pytest_dir.mkdir(parents=True)
    requests_dir.mkdir(parents=True)
    pytest_stderr = pytest_dir / "stderr.txt"
    pytest_stderr.write_text(
        "ModuleNotFoundError: No module named '_pytest._version'\n",
        encoding="utf-8",
    )
    requests_stdout = requests_dir / "stdout.txt"
    requests_stdout.write_text(
        "ERROR at setup of TestRequests.test_no_content_length\n"
        "E       recursive dependency involving fixture 'httpbin' detected\n",
        encoding="utf-8",
    )
    results_path = tmp_path / "focused_test_run_results.json"
    results_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "pytest_task",
                    "repository": "pytest-dev/pytest",
                    "issue_url": "https://github.com/pytest-dev/pytest/issues/14552",
                    "status": "failed",
                    "stdout_path": str(pytest_dir / "stdout.txt"),
                    "stderr_path": str(pytest_stderr),
                },
                {
                    "task_id": "requests_task",
                    "repository": "psf/requests",
                    "issue_url": "https://github.com/psf/requests/issues/7223",
                    "status": "failed",
                    "stdout_path": str(requests_stdout),
                    "stderr_path": str(requests_dir / "stderr.txt"),
                },
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "diagnosis"
    results, summary = diagnose_focused_test_runs(
        results_path=results_path,
        output_dir=output_dir,
    )

    categories = {result.task_id: result.category for result in results}
    assert categories == {
        "pytest_task": "missing_generated_version_metadata",
        "requests_task": "pytest_fixture_dependency_error",
    }
    assert summary.task_count == 2
    assert summary.dependency_issue_tasks == 1
    assert summary.environment_issue_tasks == 1
    assert summary.category_counts["missing_generated_version_metadata"] == 1
    assert (output_dir / "focused_test_diagnosis_report.md").exists()
    assert (output_dir / "focused_test_diagnosis_results.csv").exists()

    cli_output = tmp_path / "cli_diagnosis"
    exit_code = main(
        [
            "diagnose-focused-test-runs",
            "--results",
            str(results_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_diagnosis_report.md").exists()


def test_plan_focused_test_setups_writes_setup_backlog(
    tmp_path: Path,
) -> None:
    requests_repo = tmp_path / "requests_repo"
    requests_repo.mkdir()
    (requests_repo / "pyproject.toml").write_text(
        """
[project]
name = "requests"

[dependency-groups]
test = ["pytest-httpbin==2.1.0"]
""",
        encoding="utf-8",
    )
    diagnosis_path = tmp_path / "focused_test_diagnosis_results.json"
    diagnosis_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "pytest_task",
                    "repository": "pytest-dev/pytest",
                    "issue_url": "https://github.com/pytest-dev/pytest/issues/14552",
                    "run_status": "failed",
                    "command": "python3 -m pytest testing/test_config.py",
                    "focused_files": ["testing/test_config.py"],
                    "category": "missing_generated_version_metadata",
                    "severity": "dependency",
                    "evidence": ["ModuleNotFoundError: No module named '_pytest._version'"],
                    "suggested_next_actions": [],
                },
                {
                    "task_id": "requests_task",
                    "repository": "psf/requests",
                    "issue_url": "https://github.com/psf/requests/issues/7223",
                    "run_status": "failed",
                    "command": "python3 -m pytest tests/test_requests.py",
                    "repo_path": str(requests_repo),
                    "focused_files": ["tests/test_requests.py"],
                    "category": "pytest_fixture_dependency_error",
                    "severity": "environment",
                    "evidence": ["recursive dependency involving fixture 'httpbin' detected"],
                    "suggested_next_actions": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "setup_plan"
    results, summary = plan_focused_test_setups(
        diagnosis_path=diagnosis_path,
        output_dir=output_dir,
    )

    by_task = {result.task_id: result for result in results}
    assert summary.planned_tasks == 2
    assert summary.dependency_setup_tasks == 1
    assert summary.environment_setup_tasks == 1
    assert summary.network_required_tasks == 2
    assert by_task["pytest_task"].setup_profile == "python_editable_install_build_metadata"
    assert "python3 -m pip install -e ." in by_task["pytest_task"].setup_commands
    assert by_task["requests_task"].setup_profile == "pytest_fixture_environment"
    assert "python3 -m pip install -e . --group test" in by_task["requests_task"].setup_commands
    assert by_task["requests_task"].validation_command == "python3 -m pytest tests/test_requests.py"
    assert (output_dir / "focused_test_setup_plan_report.md").exists()
    assert (output_dir / "focused_test_setup_plan_results.csv").exists()

    cli_output = tmp_path / "cli_setup_plan"
    exit_code = main(
        [
            "plan-focused-test-setups",
            "--diagnosis",
            str(diagnosis_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_setup_plan_report.md").exists()


def test_check_focused_test_setup_readiness_blocks_without_docker(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    setup_plan_path = tmp_path / "focused_test_setup_plan_results.json"
    setup_plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "setup_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                    "status": "planned",
                    "setup_profile": "python_dependency_install",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pip install -e ."],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": True,
                    "sandbox_required": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    docker_smoke_path = tmp_path / "docker_smoke.json"
    docker_smoke_path.write_text(
        json.dumps({"smoke_status": "not_available"}),
        encoding="utf-8",
    )

    output_dir = tmp_path / "readiness"
    results, summary = check_focused_test_setup_readiness(
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        output_dir=output_dir,
    )

    assert summary.blocked_tasks == 1
    assert summary.ready_tasks == 0
    assert results[0].status == "blocked"
    assert results[0].repo_exists
    assert "Docker sandbox smoke is not_available" in ";".join(results[0].errors)
    assert "setup requires network access" in ";".join(results[0].warnings)
    assert (output_dir / "focused_test_setup_readiness_report.md").exists()
    assert (output_dir / "focused_test_setup_readiness_results.csv").exists()

    cli_output = tmp_path / "cli_readiness"
    exit_code = main(
        [
            "check-focused-test-setup-readiness",
            "--setup-plan",
            str(setup_plan_path),
            "--docker-smoke",
            str(docker_smoke_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_setup_readiness_report.md").exists()


def test_check_focused_test_setup_readiness_ready_without_network(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    setup_plan_path = tmp_path / "focused_test_setup_plan_results.json"
    setup_plan_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "setup_task",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                    "status": "planned",
                    "setup_profile": "metadata_check",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pytest --version"],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": False,
                    "sandbox_required": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    docker_smoke_path = tmp_path / "docker_smoke.json"
    docker_smoke_path.write_text(json.dumps({"smoke_status": "passed"}), encoding="utf-8")

    results, summary = check_focused_test_setup_readiness(
        setup_plan_path=setup_plan_path,
        docker_smoke_path=docker_smoke_path,
        output_dir=tmp_path / "readiness",
    )

    assert summary.ready_tasks == 1
    assert summary.blocked_tasks == 0
    assert results[0].status == "ready"


def test_execute_focused_test_setups_blocks_unready_tasks(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "blocked_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                    "status": "blocked",
                    "setup_profile": "python_dependency_install",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pytest --version"],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": False,
                    "sandbox_required": True,
                    "errors": ["Docker sandbox smoke is not_available"],
                    "warnings": [],
                    "next_actions": ["start Docker"],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "execution"
    results, summary = execute_focused_test_setups(
        readiness_path=readiness_path,
        output_dir=output_dir,
    )

    assert summary.blocked_tasks == 1
    assert summary.dry_run_tasks == 0
    assert summary.attempted_tasks == 0
    assert results[0].status == "blocked"
    assert "setup readiness is blocked" in ";".join(results[0].errors)
    assert (output_dir / "focused_test_setup_execution_report.md").exists()
    assert (output_dir / "focused_test_setup_execution_results.csv").exists()

    cli_output = tmp_path / "cli_execution"
    exit_code = main(
        [
            "execute-focused-test-setups",
            "--readiness",
            str(readiness_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_setup_execution_report.md").exists()


def test_execute_focused_test_setups_dry_runs_policy_allowed_commands(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "ready_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/2",
                    "status": "ready",
                    "setup_profile": "metadata_check",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pytest --version"],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": False,
                    "sandbox_required": False,
                    "errors": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_focused_test_setups(
        readiness_path=readiness_path,
        output_dir=tmp_path / "execution",
        sandbox_mode="local",
    )

    assert summary.dry_run_tasks == 1
    assert summary.blocked_tasks == 0
    assert results[0].status == "dry_run"
    assert results[0].command_results[0].status == "dry_run"
    assert results[0].command_results[0].policy_allowed


def test_execute_focused_test_setups_blocks_dependency_installs_without_opt_in(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "dependency_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/4",
                    "status": "ready",
                    "setup_profile": "python_dependency_install",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pip install -e ."],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": True,
                    "sandbox_required": True,
                    "errors": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_focused_test_setups(
        readiness_path=readiness_path,
        output_dir=tmp_path / "execution",
        sandbox_mode="docker",
    )

    assert summary.blocked_tasks == 1
    assert not summary.allow_dependency_installs
    assert results[0].status == "blocked"
    assert results[0].command_results[0].status == "policy_blocked"
    assert not results[0].command_results[0].policy_allowed


def test_execute_focused_test_setups_allows_dependency_install_dry_run_with_opt_in(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "dependency_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/5",
                    "status": "ready",
                    "setup_profile": "python_dependency_install",
                    "repo_path": str(repo_dir),
                    "setup_commands": ['python3 -m pip install -e ".[test]"'],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": True,
                    "sandbox_required": True,
                    "errors": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = execute_focused_test_setups(
        readiness_path=readiness_path,
        output_dir=tmp_path / "execution",
        sandbox_mode="docker",
        sandbox_network="bridge",
        allow_dependency_installs=True,
    )

    assert summary.dry_run_tasks == 1
    assert summary.allow_dependency_installs
    assert summary.sandbox_image == "patchsmith-seeded-smoke:py312"
    assert summary.sandbox_network == "bridge"
    assert results[0].status == "dry_run"
    assert results[0].sandbox_image == "patchsmith-seeded-smoke:py312"
    assert results[0].allow_dependency_installs
    assert results[0].command_results[0].status == "dry_run"
    assert results[0].command_results[0].policy_allowed


def test_execute_focused_test_setups_requires_docker_for_dependency_installs(
    tmp_path: Path,
) -> None:
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text("[]", encoding="utf-8")

    try:
        execute_focused_test_setups(
            readiness_path=readiness_path,
            output_dir=tmp_path / "execution",
            sandbox_mode="local",
            allow_dependency_installs=True,
        )
    except ValueError as error:
        assert "--allow-dependency-installs requires --sandbox-mode docker" in str(error)
    else:
        raise AssertionError("expected dependency install opt-in to require Docker")


def test_execute_focused_test_setups_runs_policy_allowed_local_command(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readiness_path = tmp_path / "focused_test_setup_readiness_results.json"
    readiness_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "ready_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/3",
                    "status": "ready",
                    "setup_profile": "metadata_check",
                    "repo_path": str(repo_dir),
                    "setup_commands": ["python3 -m pytest --version"],
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "requires_network": False,
                    "sandbox_required": False,
                    "errors": [],
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "execution"
    results, summary = execute_focused_test_setups(
        readiness_path=readiness_path,
        output_dir=output_dir,
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.completed_tasks == 1
    assert results[0].status == "passed"
    assert results[0].command_results[0].exit_code == 0
    assert results[0].command_results[0].stdout_path is not None
    assert Path(results[0].command_results[0].stdout_path).exists()


def test_validate_focused_test_setups_blocks_until_setup_execution_passes(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    setup_execution_path = tmp_path / "focused_test_setup_execution_results.json"
    setup_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "blocked_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/6",
                    "status": "blocked",
                    "setup_profile": "python_dependency_install",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "validation"
    results, summary = validate_focused_test_setups(
        setup_execution_path=setup_execution_path,
        output_dir=output_dir,
    )

    assert summary.blocked_tasks == 1
    assert summary.attempted_tasks == 0
    assert results[0].status == "blocked"
    assert "setup execution status is blocked" in ";".join(results[0].errors)
    assert (output_dir / "focused_test_setup_validation_report.md").exists()
    assert (output_dir / "focused_test_setup_validation_results.csv").exists()

    cli_output = tmp_path / "cli_validation"
    exit_code = main(
        [
            "validate-focused-test-setups",
            "--setup-execution",
            str(setup_execution_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_setup_validation_report.md").exists()


def test_validate_focused_test_setups_dry_runs_after_setup_passes(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    setup_execution_path = tmp_path / "focused_test_setup_execution_results.json"
    setup_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "passed_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/7",
                    "status": "passed",
                    "setup_profile": "metadata_check",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_focused_test_setups(
        setup_execution_path=setup_execution_path,
        output_dir=tmp_path / "validation",
        sandbox_mode="local",
    )

    assert summary.dry_run_tasks == 1
    assert summary.blocked_tasks == 0
    assert summary.sandbox_image == "patchsmith-seeded-smoke:py312"
    assert results[0].status == "dry_run"
    assert results[0].sandbox_image == "patchsmith-seeded-smoke:py312"
    assert results[0].command_result is not None
    assert results[0].command_result.policy_allowed


def test_validate_focused_test_setups_runs_policy_allowed_local_command(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    setup_execution_path = tmp_path / "focused_test_setup_execution_results.json"
    setup_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "passed_setup",
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/8",
                    "status": "passed",
                    "setup_profile": "metadata_check",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_focused_test_setups(
        setup_execution_path=setup_execution_path,
        output_dir=tmp_path / "validation",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.passed_tasks == 1
    assert results[0].status == "passed"
    assert results[0].command_result is not None
    assert results[0].command_result.exit_code == 0
    assert results[0].command_result.stdout_path is not None
    assert results[0].failure_category is None
    assert Path(results[0].command_result.stdout_path).exists()


def test_validate_focused_test_setups_classifies_pytest_minversion_failure(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nminversion = "999.0"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    setup_execution_path = tmp_path / "focused_test_setup_execution_results.json"
    setup_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "pytest_version_gap",
                    "repository": "pytest-dev/pytest",
                    "issue_url": "https://github.com/pytest-dev/pytest/issues/14552",
                    "status": "passed",
                    "setup_profile": "python_editable_install_build_metadata",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_ok.py",
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_focused_test_setups(
        setup_execution_path=setup_execution_path,
        output_dir=tmp_path / "validation",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.failed_tasks == 1
    assert summary.failure_category_counts == {"pytest_in_tree_version_metadata": 1}
    assert results[0].status == "failed"
    assert results[0].failure_category == "pytest_in_tree_version_metadata"
    assert results[0].failure_summary is not None
    assert "minversion" in ";".join(results[0].failure_evidence)
    assert "tox/nox" in ";".join(results[0].next_actions)
    report = (tmp_path / "validation" / "focused_test_setup_validation_report.md").read_text(
        encoding="utf-8"
    )
    assert "pytest_in_tree_version_metadata" in report


def test_validate_focused_test_setups_classifies_httpbin_fixture_failure(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture\ndef httpbin(httpbin):\n    return httpbin\n",
        encoding="utf-8",
    )
    (tests_dir / "test_requests.py").write_text(
        "def test_needs_httpbin(httpbin):\n    assert httpbin\n",
        encoding="utf-8",
    )
    setup_execution_path = tmp_path / "focused_test_setup_execution_results.json"
    setup_execution_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "requests_fixture_gap",
                    "repository": "psf/requests",
                    "issue_url": "https://github.com/psf/requests/issues/7223",
                    "status": "passed",
                    "setup_profile": "pytest_fixture_environment",
                    "repo_path": str(repo_dir),
                    "validation_command": "python3 -m pytest tests/test_requests.py",
                    "warnings": [],
                    "next_actions": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    results, summary = validate_focused_test_setups(
        setup_execution_path=setup_execution_path,
        output_dir=tmp_path / "validation",
        sandbox_mode="local",
        dry_run=False,
        timeout_seconds=30,
    )

    assert summary.failed_tasks == 1
    assert summary.failure_category_counts == {"missing_httpbin_fixture_provider": 1}
    assert results[0].status == "failed"
    assert results[0].failure_category == "missing_httpbin_fixture_provider"
    assert results[0].failure_summary is not None
    assert "httpbin" in ";".join(results[0].failure_evidence)
    assert "controlled httpbin fixture provider" in ";".join(results[0].next_actions)
