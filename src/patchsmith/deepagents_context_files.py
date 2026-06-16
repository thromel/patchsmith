"""Mounted source-file shaping for DeepAgents runs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from patchsmith.deepagents_context_utils import clean_context_excerpt
from patchsmith.deepagents_manifests import STABLE_TIMESTAMP
from patchsmith.models import RetrievedContext


def context_files(
    retrieved_context: list[RetrievedContext],
    *,
    repo_path: Path | None = None,
    max_file_chars: int = 40_000,
    context_mode: str = "full",
    context_window_lines: int = 80,
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
            context_mode=context_mode,
            context_window_lines=context_window_lines,
        )
        files[virtual_path] = {
            "content": content,
            "encoding": "utf-8",
            "created_at": modified_at,
            "modified_at": modified_at,
        }
    return files, virtual_to_repo


def context_file_content_and_timestamp(
    repo_path: Path | None,
    context: RetrievedContext,
    *,
    max_file_chars: int,
    context_mode: str = "full",
    context_window_lines: int = 80,
) -> tuple[str, str]:
    if repo_path is None:
        return clean_context_excerpt(context.excerpt), stable_timestamp()
    path = repo_path / context.path
    try:
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            return (
                focused_file_content(
                    content,
                    context.excerpt,
                    max_file_chars=max_file_chars,
                    context=context,
                    context_mode=context_mode,
                    context_window_lines=context_window_lines,
                ),
                path_modified_at(path),
            )
    except UnicodeDecodeError:
        pass
    return clean_context_excerpt(context.excerpt), stable_timestamp()


def focused_file_content(
    content: str,
    excerpt: str,
    *,
    max_file_chars: int,
    context: RetrievedContext | None = None,
    context_mode: str = "full",
    context_window_lines: int = 80,
) -> str:
    if context_mode == "span" and context is not None:
        span = _focused_source_span(
            content,
            context,
            max_file_chars=max_file_chars,
            context_window_lines=context_window_lines,
        )
        if span is not None:
            return span
    if max_file_chars <= 0 or len(content) <= max_file_chars:
        return content
    cleaned_excerpt = clean_context_excerpt(excerpt)
    if cleaned_excerpt.strip():
        return cleaned_excerpt[:max_file_chars]
    return content[:max_file_chars]


def path_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def stable_timestamp() -> str:
    return STABLE_TIMESTAMP


def _focused_source_span(
    content: str,
    context: RetrievedContext,
    *,
    max_file_chars: int,
    context_window_lines: int,
) -> str | None:
    lines = content.splitlines(keepends=True)
    if not lines:
        return None
    anchors = _source_span_anchor_lines(content, lines, context)
    if not anchors:
        return None
    anchor = anchors[0]
    window = max(8, context_window_lines)
    before = window // 2
    after = window - before
    start = max(0, anchor - before)
    end = min(len(lines), anchor + after)
    text = "".join(lines[start:end])
    if max_file_chars > 0 and len(text) > max_file_chars:
        text = _trim_span_to_char_budget(
            lines,
            anchor=anchor,
            max_file_chars=max_file_chars,
        )
    return text if text.strip() else None


def _source_span_anchor_lines(
    content: str,
    lines: list[str],
    context: RetrievedContext,
) -> list[int]:
    terms = _source_span_anchor_terms(context)
    scored: list[tuple[int, int]] = []
    if terms:
        lowered_terms = [term.lower() for term in terms]
        for index, line in enumerate(lines):
            lowered = line.lower()
            score = sum(1 for term in lowered_terms if term and term in lowered)
            if score:
                scored.append((-score, index))
    excerpt_anchor = _excerpt_anchor_line(content, lines, context.excerpt)
    if excerpt_anchor is not None:
        scored.append((-100, excerpt_anchor))
    return [index for _score, index in sorted(dict.fromkeys(scored))]


def _source_span_anchor_terms(context: RetrievedContext) -> list[str]:
    terms: list[str] = []
    for term in context.matched_terms:
        for candidate in _term_candidates(term):
            if candidate and candidate not in terms:
                terms.append(candidate)
    return terms


def _term_candidates(term: str) -> list[str]:
    raw = term.strip()
    if not raw:
        return []
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1].strip()
    raw = raw.strip("`'\"")
    candidates = [raw] if len(raw) >= 4 else []
    candidates.extend(part for part in re.split(r"[^A-Za-z0-9_]+", raw) if len(part) >= 4)
    return [candidate for candidate in dict.fromkeys(candidates) if candidate]


def _excerpt_anchor_line(
    content: str,
    lines: list[str],
    excerpt: str,
) -> int | None:
    cleaned = clean_context_excerpt(excerpt)
    for excerpt_line in cleaned.splitlines():
        needle = excerpt_line.strip()
        if len(needle) < 12:
            continue
        offset = content.find(needle)
        if offset < 0:
            continue
        running = 0
        for index, line in enumerate(lines):
            running += len(line)
            if running > offset:
                return index
    return None


def _trim_span_to_char_budget(
    lines: list[str],
    *,
    anchor: int,
    max_file_chars: int,
) -> str:
    start = anchor
    end = anchor + 1
    text = "".join(lines[start:end])
    while len(text) < max_file_chars and (start > 0 or end < len(lines)):
        expanded = False
        if start > 0:
            candidate = lines[start - 1] + text
            if len(candidate) <= max_file_chars:
                start -= 1
                text = candidate
                expanded = True
        if end < len(lines):
            candidate = text + lines[end]
            if len(candidate) <= max_file_chars:
                end += 1
                text = candidate
                expanded = True
        if not expanded:
            break
    return text
