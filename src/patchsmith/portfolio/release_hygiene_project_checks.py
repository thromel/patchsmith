"""Project-local release hygiene checks."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from patchsmith.portfolio.models import ReleaseHygieneCheck
from patchsmith.portfolio.release_hygiene_support import _release_check


def _git_repository_check(project_root: Path) -> ReleaseHygieneCheck:
    if not (project_root / ".git").exists():
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="No .git directory found at project root.",
            next_action="Initialize or restore the Git repository before claiming a stable tagged release.",
        )

    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="Git repository exists but has no commit yet.",
            next_action="Create a verified baseline commit before claiming a stable tagged release.",
        )

    branch = _run_git(project_root, "branch", "--show-current")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=(
                f"Could not inspect Git worktree: {status.stderr.strip() or status.stdout.strip()}"
            ),
            next_action="Fix Git metadata before claiming release readiness.",
        )
    if status.stdout.strip():
        changed_count = len([line for line in status.stdout.splitlines() if line.strip()])
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Git commit {head.stdout.strip()} has {changed_count} uncommitted file changes.",
            next_action="Commit, stash, or intentionally remove worktree changes before tagging a release.",
        )

    branch_name = branch.stdout.strip() or "detached HEAD"
    return _release_check(
        name="Git Repository",
        status="passed",
        evidence=f"Git commit {head.stdout.strip()} on {branch_name}; worktree clean.",
        next_action="Create a tag only after final verification.",
    )


def _packaging_config_check(project_root: Path) -> ReleaseHygieneCheck:
    pyproject_path = project_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence="pyproject.toml is missing.",
            next_action="Restore project package metadata before release.",
        )
    except tomllib.TOMLDecodeError as error:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"pyproject.toml could not be parsed: {error}",
            next_action="Fix package metadata before release.",
        )

    project = pyproject.get("project", {})
    optional_deps = project.get("optional-dependencies", {})
    dev_extra = optional_deps.get("dev", [])
    wheel = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
    )
    wheel_packages = wheel.get("packages", [])
    project_name = project.get("name")
    project_version = project.get("version")
    missing: list[str] = []
    if not project_name:
        missing.append("project.name")
    if not project_version:
        missing.append("project.version")
    if "src/patchsmith" not in wheel_packages:
        missing.append("tool.hatch.build.targets.wheel.packages includes src/patchsmith")
    if not _dependency_present(dev_extra, "pytest"):
        missing.append("project.optional-dependencies.dev includes pytest")
    if not _dependency_present(dev_extra, "build"):
        missing.append("project.optional-dependencies.dev includes build")

    if missing:
        return _release_check(
            name="Packaging Config",
            status="blocked",
            evidence=f"Missing package metadata: {', '.join(missing)}.",
            next_action="Fix pyproject package metadata before claiming release readiness.",
        )

    return _release_check(
        name="Packaging Config",
        status="passed",
        evidence=(
            f"{project_name} {project_version}; wheel packages {', '.join(wheel_packages)}; "
            "dev extra includes pytest and build."
        ),
        next_action="Keep package build validation in CI.",
    )


def _dependency_present(dependencies: list[Any], package_name: str) -> bool:
    prefix = package_name.lower()
    for dependency in dependencies:
        if isinstance(dependency, str) and dependency.lower().startswith(prefix):
            return True
    return False


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _has_demo_media(project_root: Path) -> bool:
    search_roots = [
        project_root / "docs",
        project_root / "artifacts",
        project_root / "assets",
    ]
    suffixes = {".gif", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}
    for root in search_roots:
        if not root.exists():
            continue
        if any(path.suffix.lower() in suffixes for path in root.rglob("*")):
            return True
    return False


def _has_architecture_diagram(project_root: Path) -> bool:
    architecture_path = project_root / "docs" / "03_architecture.md"
    try:
        architecture_text = architecture_path.read_text(encoding="utf-8")
    except OSError:
        architecture_text = ""
    if "```mermaid" in architecture_text:
        return True
    diagram_roots = [project_root / "docs", project_root / "assets"]
    suffixes = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
    for root in diagram_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if "arch" in path.name.lower() and path.suffix.lower() in suffixes:
                return True
    return False


__all__ = [
    "_git_repository_check",
    "_has_architecture_diagram",
    "_has_demo_media",
    "_packaging_config_check",
    "_run_git",
]
