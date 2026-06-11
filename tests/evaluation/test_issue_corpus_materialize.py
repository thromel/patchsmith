import json
from pathlib import Path

from patchsmith.cli import main
from patchsmith.evaluation import (
    check_materialized_issue_run_readiness,
    materialize_issue_corpus_tasks,
    preview_issue_corpus_context,
    validate_materialized_issue_tasks,
)


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
