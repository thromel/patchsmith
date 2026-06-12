from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceRestorer:
    repo_path: Path
    baseline_path: Path
    enabled: bool = True

    @classmethod
    def create(
        cls,
        *,
        repo_path: Path,
        baseline_path: Path,
        enabled: bool,
    ) -> WorkspaceRestorer:
        restorer = cls(
            repo_path=repo_path.resolve(),
            baseline_path=baseline_path.resolve(),
            enabled=enabled,
        )
        if restorer.enabled:
            restorer._capture()
        return restorer

    def restore(self) -> None:
        if not self.enabled:
            return
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)
        shutil.copytree(self.baseline_path, self.repo_path, symlinks=True)

    def cleanup(self) -> None:
        if self.baseline_path.exists():
            shutil.rmtree(self.baseline_path)

    def _capture(self) -> None:
        self._validate_paths()
        if self.baseline_path.exists():
            shutil.rmtree(self.baseline_path)
        shutil.copytree(self.repo_path, self.baseline_path, symlinks=True)

    def _validate_paths(self) -> None:
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise FileNotFoundError(f"workspace repository does not exist: {self.repo_path}")
        if _is_relative_to(self.baseline_path, self.repo_path):
            raise ValueError("baseline path must not live inside the workspace repository")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


__all__ = ["WorkspaceRestorer"]
