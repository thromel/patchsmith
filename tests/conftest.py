"""Shared pytest fixtures for the PatchSmith test suite."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the project repository root."""
    return REPO_ROOT


@pytest.fixture
def simple_calc_fixture() -> Path:
    """Path to the seeded simple_calc_bug fixture (issue + mini repo)."""
    return FIXTURES_DIR / "simple_calc_bug"


@pytest.fixture
def simple_calc_repo_copy(tmp_path: Path, simple_calc_fixture: Path) -> Path:
    """Disposable copy of the simple_calc_bug fixture repository."""
    destination = tmp_path / "repo"
    shutil.copytree(simple_calc_fixture / "repo", destination)
    return destination


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    """Empty artifacts directory rooted in the test's tmp_path."""
    destination = tmp_path / "artifacts"
    destination.mkdir(parents=True, exist_ok=True)
    return destination
