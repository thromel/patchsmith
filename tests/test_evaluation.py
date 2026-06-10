import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.evaluation import (
    check_focused_test_setup_readiness,
    check_materialized_issue_run_readiness,
    diagnose_focused_test_runs,
    execute_focused_test_setups,
    load_seeded_tasks,
    materialize_issue_corpus_tasks,
    plan_focused_test_setups,
    plan_materialized_issue_focused_tests,
    preflight_issue_corpus_repositories,
    preview_issue_corpus_context,
    recall,
    run_materialized_issue_focused_tests,
    run_patch_search_evaluation,
    run_repair_evaluation,
    run_scaffold_comparison,
    run_retrieval_evaluation,
    top_k_recall,
    validate_issue_corpus,
    validate_materialized_issue_tasks,
    validate_seeded_dataset,
)


def test_recall_metrics() -> None:
    assert top_k_recall(["src/a.py", "src/b.py"], ["src/a.py"], 1) == 1.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 1) == 0.0
    assert top_k_recall(["src/b.py", "src/a.py"], ["src/a.py"], 3) == 1.0
    assert recall(["tests/test_a.py"], ["tests/test_a.py", "tests/test_b.py"]) == 0.5


def test_load_seeded_tasks() -> None:
    tasks = load_seeded_tasks(Path("evals/tasks/seeded_bugs_v1"))

    assert tasks
    assert tasks[0].task_id == "task_001_logic_bug"
    assert tasks[0].expected_touched_files == ["src/simple_calc.py"]


def test_validate_seeded_dataset_writes_outputs(tmp_path: Path) -> None:
    results, summary = validate_seeded_dataset(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        output_dir=tmp_path / "dataset_validation",
    )

    assert len(results) == 10
    assert summary.task_count == 10
    assert summary.valid_tasks == 10
    assert summary.invalid_tasks == 0
    assert summary.error_count == 0
    assert (tmp_path / "dataset_validation" / "validation_report.md").exists()
    assert (tmp_path / "dataset_validation" / "validation_results.csv").exists()
    assert (tmp_path / "dataset_validation" / "validation_summary.json").exists()


def test_validate_seeded_dataset_flags_invalid_task(tmp_path: Path) -> None:
    task_dir = tmp_path / "dataset" / "task_001_bad"
    repo_dir = task_dir / "repo"
    repo_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("Bug report", encoding="utf-8")
    (task_dir / "expected.json").write_text(
        """
{
  "task_id": "task_001_bad",
  "language": "python",
  "test_command": "python3 -m pytest",
  "expected_touched_files": ["src/missing.py"],
  "expected_related_tests": ["tests/test_missing.py"],
  "failure_type": "logic_bug"
}
""",
        encoding="utf-8",
    )

    results, summary = validate_seeded_dataset(
        dataset_dir=tmp_path / "dataset",
        output_dir=tmp_path / "validation",
    )

    assert summary.task_count == 1
    assert summary.valid_tasks == 0
    assert summary.invalid_tasks == 1
    assert "expected_touched_files path does not exist" in ";".join(results[0].errors)
    assert "expected_related_tests path does not exist" in ";".join(results[0].errors)


def test_validate_issue_corpus_writes_outputs(tmp_path: Path) -> None:
    results, summary = validate_issue_corpus(
        corpus_path=Path("evals/issue_corpora/public_issue_smoke_v1/issues.json"),
        output_dir=tmp_path / "public_issue_corpus",
    )

    assert len(results) == 3
    assert summary.corpus_id == "public_issue_smoke_v1"
    assert summary.valid_entries == 3
    assert summary.invalid_entries == 0
    assert summary.open_issue_count == 3
    assert "psf/requests" in summary.repositories
    assert "pytest-dev/pytest" in summary.repositories
    assert (tmp_path / "public_issue_corpus" / "corpus_report.md").exists()
    assert (tmp_path / "public_issue_corpus" / "corpus_results.csv").exists()
    assert (tmp_path / "public_issue_corpus" / "corpus_summary.json").exists()
    report = (tmp_path / "public_issue_corpus" / "corpus_report.md").read_text(
        encoding="utf-8"
    )
    assert "Claim Boundary" in report

    cli_output = tmp_path / "cli_public_issue_corpus"
    exit_code = main(
        [
            "validate-issue-corpus",
            "--corpus",
            "evals/issue_corpora/public_issue_smoke_v1/issues.json",
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "corpus_report.md").exists()


def test_validate_issue_corpus_flags_bad_metadata(tmp_path: Path) -> None:
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "bad",
                "issues": [
                    {
                        "task_id": "bad task",
                        "repository": "requests",
                        "repo_url": "https://example.com/requests",
                        "issue_url": "https://github.com/psf/requests/issues/1",
                        "title": "bad",
                        "language": "python",
                        "task_type": "bug",
                        "state_at_capture": "open",
                        "captured_at": "2026-06-10T08:16:00Z",
                        "expected_workflow": ["clone"],
                        "selection_reason": "bad metadata",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    results, summary = validate_issue_corpus(
        corpus_path=corpus_path,
        output_dir=tmp_path / "out",
    )

    assert summary.invalid_entries == 1
    assert "task_id contains unsafe characters" in ";".join(results[0].errors)
    assert "repository must use owner/name format" in ";".join(results[0].errors)
    assert "repo_url must be a GitHub URL" in ";".join(results[0].errors)


def test_preflight_issue_corpus_repositories_writes_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[3] == "https://github.com/pytest-dev/pytest":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "ref: refs/heads/main\tHEAD\n"
                    "abc123\tHEAD\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "ref: refs/heads/main\tHEAD\n"
                "def456\tHEAD\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("patchsmith.evaluation.subprocess.run", fake_run)

    output_dir = tmp_path / "preflight"
    results, summary = preflight_issue_corpus_repositories(
        corpus_path=Path("evals/issue_corpora/public_issue_smoke_v1/issues.json"),
        output_dir=output_dir,
    )

    assert len(results) == 2
    assert summary.repository_count == 2
    assert summary.reachable_repositories == 2
    assert summary.issue_count == 3
    assert all(result.default_branch == "main" for result in results)
    assert (output_dir / "repo_preflight_report.md").exists()
    assert (output_dir / "repo_preflight_results.csv").exists()
    assert calls and calls[0][:3] == ["git", "ls-remote", "--symref"]

    cli_output = tmp_path / "cli_preflight"
    exit_code = main(
        [
            "preflight-issue-corpus",
            "--corpus",
            "evals/issue_corpora/public_issue_smoke_v1/issues.json",
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "repo_preflight_report.md").exists()


def test_preview_issue_corpus_context_writes_source_free_outputs(
    tmp_path: Path,
) -> None:
    fixture_repo = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo").resolve()
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "local_preview",
                "issues": [
                    {
                        "task_id": "local_simple_calc",
                        "repository": "local/simple_calc",
                        "repo_url": str(fixture_repo),
                        "issue_url": "https://github.com/example/simple-calc/issues/1",
                        "title": "Addition returns the wrong result in simple_calc",
                        "task_type": "logic_bug",
                        "selection_reason": "Local fixture for source-free preview coverage.",
                        "expected_workflow": ["retrieve simple_calc implementation"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "preview"
    results, summary = preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=output_dir,
        context_provider="native_hybrid",
    )

    assert summary.attempted_issues == 1
    assert summary.completed_issues == 1
    assert summary.source_free
    assert results[0].retrieved_files
    assert "src/simple_calc.py" in results[0].retrieved_files
    assert "excerpt" not in results[0].top_contexts[0]
    assert (output_dir / "context_preview_report.md").exists()
    assert (output_dir / "context_preview_results.csv").exists()

    cli_output = tmp_path / "cli_preview"
    exit_code = main(
        [
            "preview-issue-corpus-context",
            "--corpus",
            str(corpus_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "context_preview_report.md").exists()


def test_materialize_issue_corpus_tasks_writes_source_free_manifests(
    tmp_path: Path,
) -> None:
    fixture_repo = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo").resolve()
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "local_materialization",
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
                        "selection_reason": "Local fixture for materialization coverage.",
                        "expected_workflow": ["retrieve simple_calc implementation"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "materialization"
    preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=output_dir,
        context_provider="native_hybrid",
    )

    results, summary = materialize_issue_corpus_tasks(
        corpus_path=corpus_path,
        output_dir=output_dir,
    )

    assert summary.attempted_issues == 1
    assert summary.materialized_tasks == 1
    assert summary.source_free
    assert results[0].status == "materialized"
    assert results[0].source_free
    manifest_path = output_dir / "materialized_tasks" / "local_simple_calc" / "task_manifest.json"
    runbook_path = output_dir / "materialized_tasks" / "local_simple_calc" / "RUNBOOK.md"
    issue_path = output_dir / "materialized_tasks" / "local_simple_calc" / "issue.md"
    assert manifest_path.exists()
    assert runbook_path.exists()
    assert issue_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["retrieval_preview"]["retrieved_files"]
    assert '"excerpt"' not in manifest_path.read_text(encoding="utf-8")
    assert (output_dir / "materialized_task_report.md").exists()
    assert (output_dir / "materialized_task_results.csv").exists()

    cli_output = tmp_path / "cli_materialization"
    preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=cli_output,
        context_provider="native_hybrid",
    )
    exit_code = main(
        [
            "materialize-issue-corpus-tasks",
            "--corpus",
            str(corpus_path),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "materialized_task_report.md").exists()


def test_validate_materialized_issue_tasks_checks_manifest_contract(
    tmp_path: Path,
) -> None:
    fixture_repo = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo").resolve()
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "local_validation",
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
                        "selection_reason": "Local fixture for validation coverage.",
                        "expected_workflow": ["retrieve simple_calc implementation"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "materialized_validation"
    preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=output_dir,
        context_provider="native_hybrid",
    )
    materialize_issue_corpus_tasks(
        corpus_path=corpus_path,
        output_dir=output_dir,
    )

    results, summary = validate_materialized_issue_tasks(
        tasks_dir=output_dir / "materialized_tasks",
        output_dir=output_dir,
    )

    assert summary.task_count == 1
    assert summary.valid_tasks == 1
    assert summary.invalid_tasks == 0
    assert summary.source_free
    assert results[0].retrieved_files
    assert results[0].source_free
    assert (output_dir / "materialized_task_validation_report.md").exists()
    assert (output_dir / "materialized_task_validation_results.csv").exists()

    cli_output = tmp_path / "cli_validation"
    exit_code = main(
        [
            "validate-materialized-issue-tasks",
            "--tasks-dir",
            str(output_dir / "materialized_tasks"),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "materialized_task_validation_report.md").exists()


def test_validate_materialized_issue_tasks_flags_source_excerpt(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "bad_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("# Bad\n\n## Claim Boundary\n", encoding="utf-8")
    (task_dir / "RUNBOOK.md").write_text(
        "# Runbook\n\n## Suggested Commands\n",
        encoding="utf-8",
    )
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_manifest_version": 1,
                "task_id": "bad_task",
                "source_corpus": "bad",
                "issue": {
                    "repository": "owner/repo",
                    "repo_url": "https://github.com/owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                    "language": "python",
                    "expected_workflow": ["clone"],
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "commit_hash": "abc123456",
                    "file_count": 1,
                    "test_commands": ["python3 -m pytest"],
                },
                "retrieval_preview": {
                    "context_provider": "native_hybrid",
                    "context_count": 1,
                    "retrieved_files": ["src/example.py"],
                    "top_contexts": [
                        {
                            "path": "src/example.py",
                            "rank": 1,
                            "excerpt": "source text should not be present",
                        }
                    ],
                },
                "suggested_commands": ["python3 -m patchsmith.cli run --repo repo"],
                "claim_boundary": ["not solved"],
                "source_free": True,
            }
        ),
        encoding="utf-8",
    )

    results, summary = validate_materialized_issue_tasks(
        tasks_dir=tmp_path / "tasks",
        output_dir=tmp_path / "validation",
    )

    assert summary.invalid_tasks == 1
    assert not summary.source_free
    assert "source-free" in ";".join(results[0].errors)


def test_check_materialized_issue_run_readiness_reports_policy(
    tmp_path: Path,
) -> None:
    fixture_repo = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo").resolve()
    corpus_path = tmp_path / "issues.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_id": "local_run_readiness",
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
                        "selection_reason": "Local fixture for run-readiness coverage.",
                        "expected_workflow": ["retrieve simple_calc implementation"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "run_readiness"
    preview_issue_corpus_context(
        corpus_path=corpus_path,
        output_dir=output_dir,
        context_provider="native_hybrid",
    )
    materialize_issue_corpus_tasks(
        corpus_path=corpus_path,
        output_dir=output_dir,
    )

    results, summary = check_materialized_issue_run_readiness(
        tasks_dir=output_dir / "materialized_tasks",
        output_dir=output_dir,
    )

    assert summary.task_count == 1
    assert summary.blocked_tasks == 0
    assert summary.allowed_test_commands == 1
    assert results[0].command_checks[0]["allowed"]
    assert (output_dir / "materialized_run_readiness_report.md").exists()
    assert (output_dir / "materialized_run_readiness_results.csv").exists()

    cli_output = tmp_path / "cli_run_readiness"
    exit_code = main(
        [
            "check-materialized-run-readiness",
            "--tasks-dir",
            str(output_dir / "materialized_tasks"),
            "--output",
            str(cli_output),
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "materialized_run_readiness_report.md").exists()


def test_check_materialized_issue_run_readiness_blocks_unsafe_test_command(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "bad_task"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (task_dir / "task_manifest.json").write_text(
        json.dumps(
            {
                "task_manifest_version": 1,
                "task_id": "bad_task",
                "issue": {
                    "repository": "owner/repo",
                    "issue_url": "https://github.com/owner/repo/issues/1",
                },
                "repository_snapshot": {
                    "repo_path": str(repo_dir),
                    "file_count": 1,
                    "package_manager": "python/pyproject",
                    "test_commands": ["python3 -m pytest && printenv"],
                },
                "suggested_commands": ["python3 -m patchsmith.cli run --repo repo"],
            }
        ),
        encoding="utf-8",
    )

    results, summary = check_materialized_issue_run_readiness(
        tasks_dir=tmp_path / "tasks",
        output_dir=tmp_path / "readiness",
    )

    assert summary.blocked_tasks == 1
    assert summary.blocked_test_commands == 1
    assert results[0].status == "blocked"
    assert "rejected by policy" in ";".join(results[0].errors)


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
        timeout_seconds=30,
    )

    assert summary.attempted_tasks == 1
    assert summary.passed_tasks == 1
    assert summary.blocked_tasks == 0
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
            "--json",
        ]
    )
    assert exit_code == 0
    assert (cli_output / "focused_test_run_report.md").exists()


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
    assert summary.sandbox_network == "bridge"
    assert results[0].status == "dry_run"
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


def test_graph_retrieval_dataset_validates(tmp_path: Path) -> None:
    results, summary = validate_seeded_dataset(
        dataset_dir=Path("evals/tasks/graph_retrieval_v1"),
        output_dir=tmp_path / "graph_dataset_validation",
    )

    assert len(results) == 3
    assert summary.valid_tasks == 3
    assert summary.invalid_tasks == 0
    assert summary.warning_count == 0


def test_run_retrieval_evaluation_native_writes_outputs(tmp_path: Path) -> None:
    results, summaries = run_retrieval_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        providers=["native", "native_hybrid", "native_graph"],
        output_dir=tmp_path / "retrieval_eval",
    )

    assert len(results) >= 30
    summary_by_provider = {summary.provider: summary for summary in summaries}
    assert summary_by_provider["native"].avg_top5_touched_recall == 1.0
    assert summary_by_provider["native"].avg_related_test_recall == 1.0
    assert summary_by_provider["native"].avg_context_approx_tokens > 0
    assert summary_by_provider["native_hybrid"].avg_top1_touched_recall == 1.0
    assert summary_by_provider["native_graph"].avg_top1_touched_recall == 1.0
    assert (tmp_path / "retrieval_eval" / "report.md").exists()
    assert (tmp_path / "retrieval_eval" / "results.csv").exists()
    results_json = json.loads(
        (tmp_path / "retrieval_eval" / "results.json").read_text(encoding="utf-8")
    )
    assert results_json[0]["context_count"] > 0
    assert results_json[0]["context_approx_tokens"] > 0
    report = (tmp_path / "retrieval_eval" / "report.md").read_text(encoding="utf-8")
    assert "Avg Tokens" in report


def test_graph_retrieval_evaluation_proves_graph_specific_source_localization(
    tmp_path: Path,
) -> None:
    _results, summaries = run_retrieval_evaluation(
        dataset_dir=Path("evals/tasks/graph_retrieval_v1"),
        providers=["native_hybrid", "native_graph"],
        output_dir=tmp_path / "graph_retrieval_eval",
    )

    summary_by_provider = {summary.provider: summary for summary in summaries}
    assert summary_by_provider["native_hybrid"].avg_top1_touched_recall == 0.0
    assert summary_by_provider["native_graph"].avg_top1_touched_recall == 1.0
    assert summary_by_provider["native_graph"].avg_top3_touched_recall == 1.0
    report = (tmp_path / "graph_retrieval_eval" / "report.md").read_text(
        encoding="utf-8"
    )
    assert "native_graph" in report


def test_run_repair_evaluation_heuristic_writes_outputs(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="heuristic",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval",
    )

    assert len(results) >= 10
    assert summary.runtime == "heuristic"
    assert summary.planner == "heuristic"
    assert summary.context_provider == "native_hybrid"
    assert summary.model_provider is None
    assert summary.patch_generated_rate == 1.0
    assert summary.targeted_test_pass_rate == 1.0
    assert summary.avg_trace_events > 0
    assert summary.avg_runtime_nodes > 0
    assert summary.avg_debuggability_score >= 4.0
    assert results[0].trace_path is not None
    assert results[0].trace_event_count > 0
    assert (tmp_path / "repair_eval" / "repair_report.md").exists()
    assert (tmp_path / "repair_eval" / "repair_results.csv").exists()


def test_run_repair_evaluation_langgraph_fake_model_tracks_usage(tmp_path: Path) -> None:
    results, summary = run_repair_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        runtime="langgraph",
        planner="fake_model",
        context_provider="native_hybrid",
        output_dir=tmp_path / "repair_eval_fake_model",
    )

    assert len(results) >= 10
    assert summary.runtime == "langgraph"
    assert summary.planner == "fake_model"
    assert summary.model_provider == "offline_fake_model"
    assert summary.estimated_cost_usd == 0.0
    report = (tmp_path / "repair_eval_fake_model" / "repair_report.md").read_text(
        encoding="utf-8"
    )
    assert "Model provider: `offline_fake_model`" in report


def test_run_scaffold_comparison_writes_outputs(tmp_path: Path) -> None:
    results = run_scaffold_comparison(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        variants=["agentless", "heuristic", "deepagents", "openai_agents"],
        context_provider="native_hybrid",
        output_dir=tmp_path / "scaffold_comparison",
    )

    by_scaffold = {result.scaffold: result for result in results}
    assert by_scaffold["agentless"].patch_generated_rate == 0.0
    assert by_scaffold["agentless"].targeted_test_pass_rate == 0.0
    assert by_scaffold["heuristic"].patch_generated_rate == 1.0
    assert by_scaffold["heuristic"].targeted_test_pass_rate == 1.0
    assert by_scaffold["deepagents"].patch_generated_rate == 1.0
    assert by_scaffold["deepagents"].targeted_test_pass_rate == 1.0
    assert by_scaffold["openai_agents"].patch_generated_rate == 1.0
    assert by_scaffold["openai_agents"].targeted_test_pass_rate == 1.0
    assert by_scaffold["agentless"].avg_runtime_nodes == 0.0
    assert by_scaffold["agentless"].avg_debuggability_score == 4.0
    assert by_scaffold["heuristic"].avg_runtime_nodes > 0
    assert by_scaffold["heuristic"].avg_debuggability_score == 5.0
    assert by_scaffold["deepagents"].avg_runtime_nodes >= 6.0
    assert by_scaffold["deepagents"].avg_debuggability_score == 5.0
    assert by_scaffold["openai_agents"].avg_runtime_nodes >= 7.0
    assert by_scaffold["openai_agents"].avg_debuggability_score == 5.0
    assert (tmp_path / "scaffold_comparison" / "scaffold_report.md").exists()
    assert (tmp_path / "scaffold_comparison" / "scaffold_results.csv").exists()
    results_json = json.loads(
        (tmp_path / "scaffold_comparison" / "scaffold_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["avg_trace_events"] > 0
    report = (tmp_path / "scaffold_comparison" / "scaffold_report.md").read_text(
        encoding="utf-8"
    )
    assert "Scaffold Comparison Report" in report
    assert "Debug Score" in report
    assert "agentless" in report
    assert "heuristic" in report
    assert "deepagents" in report
    assert "openai_agents" in report
    assert "dependency-gated adapter evidence" in report


def test_run_patch_search_evaluation_writes_outputs(tmp_path: Path) -> None:
    results, summaries = run_patch_search_evaluation(
        dataset_dir=Path("evals/tasks/seeded_bugs_v1"),
        candidate_counts=[1, 3],
        context_provider="native_hybrid",
        output_dir=tmp_path / "patch_search_eval",
    )

    assert len(results) == 20
    summary_by_variant = {summary.variant: summary for summary in summaries}
    assert summary_by_variant["candidates_1"].success_at_1_rate == 1.0
    assert summary_by_variant["candidates_1"].avg_test_runs == 1.0
    assert summary_by_variant["candidates_3"].success_at_k_rate == 1.0
    assert summary_by_variant["candidates_3"].selected_success_rate == 1.0
    assert summary_by_variant["candidates_3"].avg_test_runs == 3.0
    first_three = next(result for result in results if result.variant == "candidates_3")
    assert len(first_three.candidate_results) == 3
    assert first_three.selected_candidate_index == 1
    assert (tmp_path / "patch_search_eval" / "patch_search_report.md").exists()
    assert (tmp_path / "patch_search_eval" / "patch_search_results.csv").exists()
    results_json = json.loads(
        (tmp_path / "patch_search_eval" / "patch_search_results.json").read_text(
            encoding="utf-8"
        )
    )
    assert results_json[0]["candidate_results"]
    report = (tmp_path / "patch_search_eval" / "patch_search_report.md").read_text(
        encoding="utf-8"
    )
    assert "Patch Search Evaluation Report" in report
    assert "Success@k" in report
