from pathlib import Path

import pytest

from patchsmith.ingest import clone_or_copy_repository
from patchsmith.patching import PatchSafetyError, apply_text_replacement


def test_apply_text_replacement_writes_unified_diff(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo")
    snapshot = clone_or_copy_repository(str(fixture), tmp_path / "repo")

    edit = apply_text_replacement(
        repo_path=snapshot.repo_path,
        relative_path="src/simple_calc.py",
        old="return left - right",
        new="return left + right",
    )

    assert "src/simple_calc.py" in edit.diff
    assert "+    return left + right" in edit.diff
    assert "return left + right" in (snapshot.repo_path / "src/simple_calc.py").read_text(
        encoding="utf-8"
    )


def test_apply_text_replacement_rejects_path_escape(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo")
    snapshot = clone_or_copy_repository(str(fixture), tmp_path / "repo")

    with pytest.raises(PatchSafetyError):
        apply_text_replacement(
            repo_path=snapshot.repo_path,
            relative_path="../outside.py",
            old="x",
            new="y",
        )

