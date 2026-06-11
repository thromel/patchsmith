from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES = 64_000
SOURCE_HINT_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def public_issue_fixture_source_hints(
    *,
    repo_path: Path,
    fixture_files: list[dict[str, str]],
    limit: int = 8,
) -> list[str]:
    root = repo_path.resolve()
    hints: list[str] = []
    for fixture in fixture_files:
        content = fixture.get("content", "")
        if not isinstance(content, str):
            continue
        for module in python_import_modules(content):
            module_path = module.replace(".", "/")
            candidates = _module_source_candidates(module_path)
            for candidate in candidates:
                if candidate in hints:
                    continue
                if (root / candidate).is_file():
                    hints.append(candidate)
                    break
            if len(hints) >= limit:
                return hints
    return hints


def _module_source_candidates(module_path: str) -> list[str]:
    return [
        f"{module_path}.py",
        f"src/{module_path}.py",
        f"{module_path}/__init__.py",
        f"src/{module_path}/__init__.py",
    ]


def python_import_modules(source: str) -> list[str]:
    modules: list[str] = []
    for match in re.finditer(
        r"(?m)^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+([A-Za-z_][\w.]*)(?:\s|,|$)",
        source,
    ):
        package = match.group(1)
        imported_name = match.group(2)
        modules.append(package)
        if imported_name not in {"*", ""}:
            modules.append(f"{package}.{imported_name}")
    for match in re.finditer(r"(?m)^\s*import\s+([A-Za-z_][\w.]*)", source):
        modules.append(match.group(1))
    return _dedupe_preserve_order(modules)


def normalize_public_issue_fixture_files(
    value: Any,
) -> tuple[list[dict[str, str]], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["fixture_files must be a list"]

    fixture_files: list[dict[str, str]] = []
    errors: list[str] = []
    seen_paths: set[str] = set()
    for index, raw_fixture in enumerate(value, start=1):
        if not isinstance(raw_fixture, dict):
            errors.append(f"fixture_files[{index}] must be an object")
            continue
        raw_path = _optional_string(raw_fixture.get("path"))
        if raw_path is None or not raw_path.strip():
            errors.append(f"fixture_files[{index}].path is missing")
            continue
        path = Path(raw_path)
        normalized_path = path.as_posix()
        if path.is_absolute():
            errors.append(
                f"fixture_files[{index}].path must be repository-relative: {raw_path}"
            )
            continue
        if raw_path.endswith(("/", "\\")) or normalized_path in {"", "."}:
            errors.append(f"fixture_files[{index}].path must name a file: {raw_path}")
            continue
        if any(part in {"..", ""} for part in path.parts):
            errors.append(
                f"fixture_files[{index}].path cannot contain traversal: {raw_path}"
            )
            continue
        if any(part == ".git" for part in path.parts):
            errors.append(
                f"fixture_files[{index}].path cannot target Git metadata: {raw_path}"
            )
            continue
        if normalized_path in seen_paths:
            errors.append(f"fixture_files[{index}].path is duplicated: {normalized_path}")
            continue
        content = raw_fixture.get("content")
        if not isinstance(content, str):
            errors.append(f"fixture_files[{index}].content must be a string")
            continue
        content_size = len(content.encode("utf-8"))
        if content_size > PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES:
            errors.append(
                f"fixture_files[{index}].content exceeds "
                f"{PUBLIC_ISSUE_FIXTURE_FILE_MAX_BYTES} bytes"
            )
            continue
        seen_paths.add(normalized_path)
        fixture_files.append({"path": normalized_path, "content": content})
    return fixture_files, errors


def public_issue_fixture_paths(fixture_files: list[dict[str, str]]) -> list[str]:
    return [
        fixture["path"]
        for fixture in fixture_files
        if isinstance(fixture.get("path"), str) and fixture["path"]
    ]


def normalize_public_issue_source_hints(value: Any) -> tuple[list[str], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["source_hints must be a list"]

    source_hints: list[str] = []
    errors: list[str] = []
    seen_hints: set[str] = set()
    for index, raw_hint in enumerate(value, start=1):
        if not isinstance(raw_hint, str) or not raw_hint.strip():
            errors.append(f"source_hints[{index}] must be a non-empty string")
            continue
        hint_path, hint_symbol = _split_source_hint(raw_hint.strip())
        if hint_symbol is not None and not SOURCE_HINT_SYMBOL_RE.match(hint_symbol):
            errors.append(
                f"source_hints[{index}] symbol must be identifier-like: {raw_hint}"
            )
            continue
        path = Path(hint_path)
        normalized_path = path.as_posix()
        if path.is_absolute():
            errors.append(
                f"source_hints[{index}] must be repository-relative: {raw_hint}"
            )
            continue
        if raw_hint.endswith(("/", "\\")) or normalized_path in {"", "."}:
            errors.append(f"source_hints[{index}] must name a file: {raw_hint}")
            continue
        if any(part in {"..", ""} for part in path.parts):
            errors.append(f"source_hints[{index}] cannot contain traversal: {raw_hint}")
            continue
        if any(part == ".git" for part in path.parts):
            errors.append(f"source_hints[{index}] cannot target Git metadata: {raw_hint}")
            continue
        normalized_hint = (
            f"{normalized_path}#{hint_symbol}" if hint_symbol else normalized_path
        )
        if normalized_hint in seen_hints:
            errors.append(f"source_hints[{index}] is duplicated: {normalized_hint}")
            continue
        seen_hints.add(normalized_hint)
        source_hints.append(normalized_hint)
    return source_hints, errors


def _split_source_hint(raw_hint: str) -> tuple[str, str | None]:
    path, separator, symbol = raw_hint.partition("#")
    return path, symbol if separator else None


def write_public_issue_fixture_files(
    *,
    repo_path: Path,
    fixture_files: list[dict[str, str]],
) -> None:
    root = repo_path.resolve()
    for fixture in fixture_files:
        relative_path = Path(fixture["path"])
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError(
                f"fixture file escapes repository workspace: {fixture['path']}"
            ) from error
        if target.exists() and target.is_dir():
            raise IsADirectoryError(
                f"fixture file target is an existing directory: {fixture['path']}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fixture["content"], encoding="utf-8")


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
