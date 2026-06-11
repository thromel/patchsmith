from pathlib import Path

from patchsmith.evaluation.issue_corpus.focused_diagnosis import (
    diagnose_focused_test_run_record,
    focused_test_log_text,
)


def test_focused_test_log_text_concatenates_existing_logs(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    stdout_path.write_text("stdout line\n", encoding="utf-8")
    stderr_path.write_text("stderr line\n", encoding="utf-8")

    logs = focused_test_log_text(
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )

    assert logs == "stdout line\n\nstderr line\n"


def test_focused_test_log_text_ignores_missing_paths(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.txt"
    stdout_path.write_text("captured\n", encoding="utf-8")

    logs = focused_test_log_text(
        stdout_path=str(stdout_path),
        stderr_path=str(tmp_path / "missing-stderr.txt"),
    )

    assert logs == "captured\n"


def test_diagnose_focused_test_run_record_detects_missing_pytest_metadata(
    tmp_path: Path,
) -> None:
    stderr_path = tmp_path / "stderr.txt"
    stderr_path.write_text(
        "ModuleNotFoundError: No module named '_pytest._version'\n",
        encoding="utf-8",
    )

    result = diagnose_focused_test_run_record(
        record={
            "task_id": "pytest_task",
            "repository": "pytest-dev/pytest",
            "status": "failed",
            "stderr_path": str(stderr_path),
        },
    )

    assert result.category == "missing_generated_version_metadata"
    assert result.severity == "dependency"
    assert any("_pytest._version" in evidence for evidence in result.evidence)


def test_diagnose_focused_test_run_record_detects_fixture_dependency_error(
    tmp_path: Path,
) -> None:
    stdout_path = tmp_path / "stdout.txt"
    stdout_path.write_text(
        "ERROR at setup of test_client\n"
        "E       recursive dependency involving fixture 'httpbin' detected\n",
        encoding="utf-8",
    )

    result = diagnose_focused_test_run_record(
        record={
            "task_id": "requests_task",
            "repository": "psf/requests",
            "status": "failed",
            "stdout_path": str(stdout_path),
        },
    )

    assert result.category == "pytest_fixture_dependency_error"
    assert result.severity == "environment"
    assert any("recursive dependency" in evidence for evidence in result.evidence)


def test_diagnose_focused_test_run_record_classifies_missing_logs() -> None:
    result = diagnose_focused_test_run_record(
        record={
            "task_id": "empty_task",
            "repository": "owner/repo",
            "status": "failed",
        },
    )

    assert result.category == "missing_logs"
    assert result.severity == "environment"
    assert result.evidence == []


def test_diagnose_focused_test_run_record_uses_errors_without_logs() -> None:
    result = diagnose_focused_test_run_record(
        record={
            "task_id": "blocked_late",
            "repository": "owner/repo",
            "status": "failed",
            "errors": ["exit code 2"],
        },
    )

    assert result.category == "nonzero_exit"
    assert result.severity == "unknown"
    assert result.evidence == ["exit code 2"]
