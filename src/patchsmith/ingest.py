from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from patchsmith.models import FileRecord, RepositoryIndex, RepositorySnapshot

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".env",
    ".cache",
    ".local",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
IGNORED_FILES = {".DS_Store"}
MAX_INDEXED_FILE_BYTES = 256_000
# Network clone/checkout can be slow; local metadata queries should be quick.
GIT_CLONE_TIMEOUT_SECONDS = 600.0
GIT_QUERY_TIMEOUT_SECONDS = 120.0

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".md": "Markdown",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".sh": "Shell",
    ".txt": "Text",
}


def clone_or_copy_repository(
    repo: str,
    target_dir: Path,
    *,
    commit: str | None = None,
    branch: str | None = None,
) -> RepositorySnapshot:
    """Clone a public Git repo or copy a local path into a per-run workspace."""

    target_dir = target_dir.resolve()
    if target_dir.exists():
        raise FileExistsError(f"target directory already exists: {target_dir}")
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    source_path = Path(repo).expanduser()
    if source_path.exists():
        shutil.copytree(source_path, target_dir, ignore=_copy_ignore, symlinks=True)
        commit_hash = _resolve_git_commit(target_dir) or _content_hash(target_dir)
        branch_name = branch or _resolve_git_branch(target_dir)
    elif _looks_like_git_url(repo):
        command = ["git", "clone"]
        if branch:
            command.extend(["--branch", branch])
        if not commit:
            command.extend(["--depth", "1"])
        command.extend([repo, str(target_dir)])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_CLONE_TIMEOUT_SECONDS,
        )
        if commit:
            subprocess.run(
                ["git", "checkout", commit],
                cwd=target_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=GIT_CLONE_TIMEOUT_SECONDS,
            )
        commit_hash = _resolve_git_commit(target_dir) or _content_hash(target_dir)
        branch_name = branch or _resolve_git_branch(target_dir)
    else:
        raise ValueError(f"repo is neither a local path nor a supported Git URL: {repo}")

    repo_index = index_repository(target_dir)
    return RepositorySnapshot(
        repo_url=repo,
        repo_path=target_dir,
        commit_hash=commit_hash,
        branch=branch_name,
        file_count=len(repo_index.files),
        language_summary=repo_index.language_summary,
        package_manager=detect_package_manager(target_dir),
        test_commands=detect_test_commands(target_dir),
    )


def index_repository(repo_path: Path) -> RepositoryIndex:
    repo_path = repo_path.resolve()
    files: list[FileRecord] = []

    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if not _should_index_file(repo_path, path):
            continue
        relative_path = path.relative_to(repo_path).as_posix()
        files.append(
            FileRecord(
                path=relative_path,
                size_bytes=path.stat().st_size,
                language=detect_language(path),
                sha256=_hash_file(path),
            )
        )

    language_summary = dict(Counter(file.language for file in files))
    return RepositoryIndex(files=files, language_summary=language_summary)


def detect_language(path: Path) -> str:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "Unknown")


def detect_package_manager(repo_path: Path) -> str | None:
    if (repo_path / "pyproject.toml").exists():
        return "python/pyproject"
    if (repo_path / "requirements.txt").exists():
        return "python/requirements"
    if (repo_path / "package.json").exists():
        return "node/npm"
    return None


def detect_test_commands(repo_path: Path) -> list[str]:
    commands: list[str] = []
    has_python_tests = any(
        path.name.startswith("test_") and path.suffix == ".py" for path in repo_path.rglob("*.py")
    )
    has_package_json = (repo_path / "package.json").exists()

    if has_python_tests:
        commands.append("python3 -m pytest")
    if has_package_json:
        package_json = _read_json(repo_path / "package.json")
        scripts = package_json.get("scripts", {}) if isinstance(package_json, dict) else {}
        if isinstance(scripts, dict) and "test" in scripts:
            commands.append("npm test")
    return commands


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in (IGNORED_DIRS - {".git"}) or name in IGNORED_FILES:
            ignored.add(name)
    return ignored


def _should_index_file(repo_path: Path, path: Path) -> bool:
    relative_parts = path.relative_to(repo_path).parts
    if any(part in IGNORED_DIRS for part in relative_parts):
        return False
    if path.name in IGNORED_FILES:
        return False
    if path.stat().st_size > MAX_INDEXED_FILE_BYTES:
        return False
    return not _is_binary(path)


def _is_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\0" in sample


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_hash(repo_path: Path) -> str:
    digest = hashlib.sha256()
    for file in index_repository(repo_path).files:
        digest.update(file.path.encode("utf-8"))
        digest.update(file.sha256.encode("utf-8"))
    return f"content:{digest.hexdigest()}"


def _resolve_git_commit(repo_path: Path) -> str | None:
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_QUERY_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip()


def _resolve_git_branch(repo_path: Path) -> str | None:
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_QUERY_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def _looks_like_git_url(repo: str) -> bool:
    return repo.startswith(("https://", "http://", "git@")) or repo.endswith(".git")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
