from pathlib import Path

import pytest

from patchsmith.workspace_restore import WorkspaceRestorer


def test_workspace_restorer_restores_captured_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    baseline = tmp_path / "baseline"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")

    restorer = WorkspaceRestorer.create(
        repo_path=repo,
        baseline_path=baseline,
        enabled=True,
    )

    (repo / "src" / "module.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "generated.txt").write_text("temporary\n", encoding="utf-8")
    restorer.restore()

    assert (repo / "src" / "module.py").read_text(encoding="utf-8") == "value = 1\n"
    assert not (repo / "generated.txt").exists()


def test_workspace_restorer_rejects_baseline_inside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="baseline path"):
        WorkspaceRestorer.create(
            repo_path=repo,
            baseline_path=repo / ".baseline",
            enabled=True,
        )


def test_disabled_workspace_restorer_is_noop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    baseline = tmp_path / "baseline"
    repo.mkdir()
    (repo / "module.py").write_text("value = 1\n", encoding="utf-8")

    restorer = WorkspaceRestorer.create(
        repo_path=repo,
        baseline_path=baseline,
        enabled=False,
    )
    (repo / "module.py").write_text("value = 2\n", encoding="utf-8")
    restorer.restore()

    assert (repo / "module.py").read_text(encoding="utf-8") == "value = 2\n"
    assert not baseline.exists()
