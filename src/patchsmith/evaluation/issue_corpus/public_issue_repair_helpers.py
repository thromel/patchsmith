"""Shared helpers for public issue repair workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)


def first_manifest_repair_command(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    commands = _string_list(manifest.get("suggested_commands"))
    return commands[0] if commands else None


def public_issue_repair_issue_text(manifest: dict[str, Any] | None) -> str | None:
    if manifest is None:
        return None
    issue_file = _optional_string(manifest.get("issue_file"))
    if issue_file:
        path = Path(issue_file)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    issue = dict_or_empty(manifest.get("issue"))
    parts = [
        _optional_string(issue.get("title")),
        _optional_string(issue.get("task_type")),
        _optional_string(issue.get("selection_reason")),
    ]
    workflow = _string_list(issue.get("expected_workflow"))
    text = "\n".join(part for part in [*parts, *workflow] if part)
    return text or None


def public_issue_repair_attempt_issue_text(
    *,
    issue_text: str,
    validation_command: str | None,
    validation_fixture_paths: list[str],
    validation_fixture_files: list[dict[str, str]],
    source_hints: list[str],
) -> str:
    sections = [issue_text.rstrip()]
    details: list[str] = []
    if validation_command:
        details.append(f"Validation command: `{validation_command}`")
    if validation_fixture_paths:
        details.append(
            "Fixture files already added to the disposable repair workspace: "
            + ", ".join(f"`{path}`" for path in validation_fixture_paths)
        )
    if source_hints:
        details.append(
            "Reviewed source files and fixture import hints: "
            + ", ".join(f"`{path}`" for path in source_hints)
        )
    if details:
        sections.extend(["", "## Reviewed Reproduction", "", *details])
    for fixture in validation_fixture_files[:3]:
        path = fixture.get("path", "fixture")
        content = fixture.get("content", "")
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        excerpt = content[:4000]
        sections.extend(
            [
                "",
                f"### Fixture `{path}`",
                "",
                "```python",
                excerpt,
                "```",
            ]
        )
    return "\n".join(sections)


def source_hint_context_paths(source_hints: list[str]) -> list[str]:
    context_paths: list[str] = []
    for hint in source_hints:
        if not isinstance(hint, str):
            continue
        context_path = _normalize_source_hint_context_path(hint)
        if context_path:
            context_paths.append(context_path)
    return _dedupe_preserve_order(context_paths)


def _normalize_source_hint_context_path(hint: str) -> str:
    path_text, separator, symbol = hint.strip().partition("#")
    if not path_text:
        return ""
    normalized_path = Path(path_text).as_posix()
    normalized_symbol = symbol.strip()
    if separator and normalized_symbol:
        return f"{normalized_path}#{normalized_symbol}"
    return normalized_path


def load_public_issue_task_manifests(tasks_dir: Path | None) -> dict[str, dict[str, Any]]:
    if tasks_dir is None or not tasks_dir.exists() or not tasks_dir.is_dir():
        return {}
    manifests: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(tasks_dir.glob("*/task_manifest.json")):
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        task_id = _optional_string(parsed.get("task_id")) or manifest_path.parent.name
        manifests[task_id] = parsed
    return manifests
