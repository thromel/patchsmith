from pathlib import Path

from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files,
    normalize_public_issue_source_hints,
    public_issue_fixture_paths,
    public_issue_fixture_source_hints,
    write_public_issue_fixture_files,
)


def test_public_issue_fixture_helpers_normalize_write_and_hint(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "src" / "requests" / "exceptions.py").write_text(
        "class ChunkedEncodingError(Exception):\n    pass\n",
        encoding="utf-8",
    )
    fixture_files, errors = normalize_public_issue_fixture_files(
        [
            {
                "path": "tests/test_issue_repro.py",
                "content": "from requests.exceptions import ChunkedEncodingError\n",
            }
        ]
    )

    assert errors == []
    assert public_issue_fixture_paths(fixture_files) == ["tests/test_issue_repro.py"]
    assert public_issue_fixture_source_hints(
        repo_path=repo,
        fixture_files=fixture_files,
    ) == ["src/requests/exceptions.py"]

    write_public_issue_fixture_files(repo_path=repo, fixture_files=fixture_files)

    assert (repo / "tests" / "test_issue_repro.py").read_text(encoding="utf-8") == (
        "from requests.exceptions import ChunkedEncodingError\n"
    )


def test_public_issue_fixture_hints_imported_submodule(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "src" / "requests" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "requests" / "compat.py").write_text("", encoding="utf-8")
    fixture_files, errors = normalize_public_issue_fixture_files(
        [
            {
                "path": "tests/test_issue_repro.py",
                "content": "from requests import compat\n",
            }
        ]
    )

    assert errors == []
    assert public_issue_fixture_source_hints(
        repo_path=repo,
        fixture_files=fixture_files,
    ) == ["src/requests/__init__.py", "src/requests/compat.py"]


def test_public_issue_fixture_helpers_reject_unsafe_paths() -> None:
    fixture_files, errors = normalize_public_issue_fixture_files(
        [{"path": "../escape.py", "content": ""}, {"path": ".git/config", "content": ""}]
    )

    assert fixture_files == []
    assert "fixture_files[1].path cannot contain traversal: ../escape.py" in errors
    assert "fixture_files[2].path cannot target Git metadata: .git/config" in errors


def test_public_issue_source_hints_normalize_and_reject_unsafe_paths() -> None:
    source_hints, errors = normalize_public_issue_source_hints(
        [
            "src/_pytest/pathlib.py#import_path",
            "../escape.py",
            ".git/config",
            "src/_pytest/pathlib.py#bad/symbol",
        ]
    )

    assert source_hints == ["src/_pytest/pathlib.py#import_path"]
    assert "source_hints[2] cannot contain traversal: ../escape.py" in errors
    assert "source_hints[3] cannot target Git metadata: .git/config" in errors
    assert (
        "source_hints[4] symbol must be identifier-like: "
        "src/_pytest/pathlib.py#bad/symbol"
    ) in errors
