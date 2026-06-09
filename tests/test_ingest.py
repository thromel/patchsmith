from pathlib import Path

from patchsmith.ingest import clone_or_copy_repository, index_repository


def test_clone_or_copy_local_repository_indexes_files(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug/repo")
    snapshot = clone_or_copy_repository(str(fixture), tmp_path / "repo")

    assert snapshot.file_count >= 3
    assert snapshot.commit_hash.startswith("content:")
    assert snapshot.package_manager == "python/pyproject"
    assert "python3 -m pytest" in snapshot.test_commands

    repo_index = index_repository(snapshot.repo_path)
    paths = {file.path for file in repo_index.files}
    assert "src/simple_calc.py" in paths
    assert "tests/test_simple_calc.py" in paths
