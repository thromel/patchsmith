from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextEditResult:
    path: str
    before: str
    after: str
    diff: str


class PatchSafetyError(RuntimeError):
    pass


def apply_text_replacement(
    *,
    repo_path: Path,
    relative_path: str,
    old: str,
    new: str,
) -> TextEditResult:
    target = validate_repo_relative_path(repo_path=repo_path, relative_path=relative_path)
    before = target.read_text(encoding="utf-8")
    if old not in before:
        raise PatchSafetyError(f"replacement text not found in {relative_path}")
    after = before.replace(old, new, 1)
    target.write_text(after, encoding="utf-8")
    return TextEditResult(
        path=relative_path,
        before=before,
        after=after,
        diff=unified_diff(relative_path=relative_path, before=before, after=after),
    )


def validate_repo_relative_path(*, repo_path: Path, relative_path: str) -> Path:
    if relative_path.startswith("/") or relative_path.startswith("../") or "/../" in relative_path:
        raise PatchSafetyError(f"unsafe relative path: {relative_path}")
    target = (repo_path / relative_path).resolve()
    try:
        target.relative_to(repo_path.resolve())
    except ValueError as error:
        raise PatchSafetyError(f"path escapes repository: {relative_path}") from error
    if not target.exists():
        raise PatchSafetyError(f"path does not exist: {relative_path}")
    if not target.is_file():
        raise PatchSafetyError(f"path is not a file: {relative_path}")
    return target


def unified_diff(*, relative_path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )
