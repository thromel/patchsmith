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


def test_clone_or_copy_ignores_local_environment_dirs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / ".cache" / "pip").mkdir(parents=True)
    (source / ".local" / "lib").mkdir(parents=True)
    (source / ".venv" / "lib").mkdir(parents=True)
    (source / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / ".cache" / "pip" / "metadata.txt").write_text("noise\n", encoding="utf-8")
    (source / ".local" / "lib" / "vendor.py").write_text("VALUE = 2\n", encoding="utf-8")
    (source / ".venv" / "lib" / "vendor.py").write_text("VALUE = 3\n", encoding="utf-8")

    snapshot = clone_or_copy_repository(str(source), tmp_path / "copied")
    paths = {file.path for file in index_repository(snapshot.repo_path).files}

    assert "src/app.py" in paths
    assert ".cache/pip/metadata.txt" not in paths
    assert ".local/lib/vendor.py" not in paths
    assert ".venv/lib/vendor.py" not in paths
    assert not (snapshot.repo_path / ".cache").exists()
    assert not (snapshot.repo_path / ".local").exists()
    assert not (snapshot.repo_path / ".venv").exists()


def test_clone_or_copy_preserves_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "target.txt").write_text("target\n", encoding="utf-8")
    (source / "link.txt").symlink_to("target.txt")

    snapshot = clone_or_copy_repository(str(source), tmp_path / "copied")

    copied_link = snapshot.repo_path / "link.txt"
    assert copied_link.is_symlink()
    assert copied_link.read_text(encoding="utf-8") == "target\n"
