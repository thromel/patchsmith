"""Virtual file helpers for the native DeepAgents planner."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    deepagents_agents_md,
)
from patchsmith.models import RetrievedContext


def context_files(
    retrieved_context: list[RetrievedContext],
    *,
    repo_path: Path | None = None,
    max_file_chars: int = 40_000,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    files: dict[str, dict[str, str]] = {}
    virtual_to_repo: dict[str, str] = {}
    for context in retrieved_context:
        virtual_path = "/" + context.path.lstrip("/")
        virtual_to_repo[virtual_path] = context.path
        content, modified_at = context_file_content_and_timestamp(
            repo_path,
            context,
            max_file_chars=max_file_chars,
        )
        files[virtual_path] = {
            "content": content,
            "encoding": "utf-8",
            "created_at": modified_at,
            "modified_at": modified_at,
        }
    return files, virtual_to_repo


def agent_files(files: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        **files,
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH: {
            "content": deepagents_agents_md(),
            "encoding": "utf-8",
            "created_at": stable_timestamp(),
            "modified_at": stable_timestamp(),
        },
    }


def read_only_filesystem_permissions(
    paths: Iterable[str],
    *,
    permission_cls: Callable[..., Any],
) -> list[Any]:
    allowed_reads = sorted(
        {"/" + path.strip().lstrip("/") for path in paths if isinstance(path, str) and path.strip()}
    )
    return [
        permission_cls(operations=["read"], paths=allowed_reads, mode="allow"),
        permission_cls(operations=["read", "write"], paths=["/**"], mode="deny"),
    ]


def repo_path_from_agent_path(path: str, virtual_to_repo: dict[str, str]) -> str:
    normalized = "/" + path.strip().lstrip("/")
    return virtual_to_repo.get(normalized, normalized.lstrip("/"))


def context_file_content_and_timestamp(
    repo_path: Path | None,
    context: RetrievedContext,
    *,
    max_file_chars: int,
) -> tuple[str, str]:
    if repo_path is None:
        return clean_context_excerpt(context.excerpt), stable_timestamp()
    path = repo_path / context.path
    try:
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            return (
                focused_file_content(content, context.excerpt, max_file_chars=max_file_chars),
                path_modified_at(path),
            )
    except UnicodeDecodeError:
        pass
    return clean_context_excerpt(context.excerpt), stable_timestamp()


def focused_file_content(content: str, excerpt: str, *, max_file_chars: int) -> str:
    if max_file_chars <= 0 or len(content) <= max_file_chars:
        return content
    cleaned_excerpt = clean_context_excerpt(excerpt)
    if cleaned_excerpt.strip():
        return cleaned_excerpt[:max_file_chars]
    return content[:max_file_chars]


def clean_context_excerpt(excerpt: str) -> str:
    lines = []
    for line in excerpt.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line))
    return "\n".join(lines)


def path_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def stable_timestamp() -> str:
    return "1970-01-01T00:00:00+00:00"


_agent_files = agent_files
_clean_context_excerpt = clean_context_excerpt
_context_files = context_files
_read_only_filesystem_permissions = read_only_filesystem_permissions
_repo_path_from_agent_path = repo_path_from_agent_path
