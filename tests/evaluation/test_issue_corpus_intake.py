import json
import subprocess
from pathlib import Path

from patchsmith.cli import main
from patchsmith.evaluation import (
    preflight_issue_corpus_repositories,
    preview_issue_corpus_context,
    validate_issue_corpus,
)


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
    report = (tmp_path / "public_issue_corpus" / "corpus_report.md").read_text(encoding="utf-8")
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
                stdout=("ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"),
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=("ref: refs/heads/main\tHEAD\ndef456\tHEAD\n"),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

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
