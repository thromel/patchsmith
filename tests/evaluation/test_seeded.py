from pathlib import Path

from patchsmith.evaluation import (
    load_seeded_tasks,
    validate_seeded_dataset,
)


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
