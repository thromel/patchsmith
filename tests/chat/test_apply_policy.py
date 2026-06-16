from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from patchsmith.agent_apply import (
    apply_agent_run_diff,
    check_agent_run_diff,
    preflight_agent_apply_target,
)

pytestmark = pytest.mark.unit


def test_apply_agent_run_diff_applies_clean_local_repo(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    diff_path = tmp_path / "final.diff"
    diff_path.write_text(
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n",
        encoding="utf-8",
    )

    result = apply_agent_run_diff(repo=str(repo), diff_path=diff_path)

    assert result.status == "applied"
    assert result.applied is True
    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 2\n"


def test_check_agent_run_diff_verifies_without_mutating_repo(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    diff_path = tmp_path / "final.diff"
    diff_path.write_text(
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n",
        encoding="utf-8",
    )

    result = check_agent_run_diff(repo=str(repo), diff_path=diff_path)

    assert result.status == "ready"
    assert result.applied is False
    assert result.message == "diff can be applied to working tree"
    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 1\n"


def test_preflight_agent_apply_target_rejects_dirty_repo(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "repo")
    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")

    result = preflight_agent_apply_target(repo=str(repo))

    assert result.status == "dirty_worktree"
    assert result.applied is False
    assert "uncommitted changes" in result.message


def test_apply_agent_run_diff_rejects_remote_repo() -> None:
    result = apply_agent_run_diff(
        repo="https://github.com/example/repo.git",
        diff_path=Path("final.diff"),
    )

    assert result.status == "unsupported_repo"
    assert result.applied is False
    assert "local Git repository" in result.message


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _run_git(path, "init")
    _run_git(path, "config", "user.email", "patchsmith@example.invalid")
    _run_git(path, "config", "user.name", "PatchSmith Test")
    (path / "app.py").write_text("value = 1\n", encoding="utf-8")
    _run_git(path, "add", "app.py")
    _run_git(path, "commit", "-m", "init")
    return path


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
