"""Structured output helpers for the native DeepAgents planner."""

from __future__ import annotations

import re
from typing import Any

from patchsmith.deepagents_files import clean_context_excerpt


def last_ai_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        if type(message).__name__ != "AIMessage":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content
    return ""


def structured_payload(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    structured = result.get("structured_response")
    if structured is None:
        return None
    if isinstance(structured, dict):
        return structured
    model_dump = getattr(structured, "model_dump", None)
    if callable(model_dump):
        payload = model_dump()
        return payload if isinstance(payload, dict) else None
    return None


def normalize_patch_payload(
    payload: dict[str, Any],
    files: dict[str, dict[str, str]],
) -> dict[str, Any]:
    path = payload.get("path")
    old = payload.get("old")
    new = payload.get("new")
    if not isinstance(path, str) or not isinstance(old, str) or not isinstance(new, str):
        return payload
    content = files.get(path, {}).get("content")
    if not isinstance(content, str):
        return payload
    fallback: dict[str, Any] | None = None
    for old_candidate in [old, *old_span_candidates(old)]:
        if old_candidate not in content:
            continue
        for new_candidate in [new, *new_span_candidates(new)]:
            candidate_payload = {**payload, "old": old_candidate, "new": new_candidate}
            if not requires_python_compile(path):
                return candidate_payload
            candidate_content = content.replace(old_candidate, new_candidate, 1)
            if python_compiles(candidate_content, path):
                return candidate_payload
            if fallback is None:
                fallback = candidate_payload
    return fallback or payload


def old_span_candidates(old: str) -> list[str]:
    candidates = [
        "\n".join(line.lstrip("\t") for line in old.splitlines()),
        "\n".join(re.sub(r"^\s*\d+\t", "", line) for line in old.splitlines()),
        clean_context_excerpt(old),
    ]
    expanded = list(candidates)
    for candidate in candidates:
        expanded.append("\n".join(line.lstrip("\t") for line in candidate.splitlines()))
    return [candidate for candidate in dict.fromkeys(expanded) if candidate != old]


def new_span_candidates(new: str) -> list[str]:
    candidates = [
        clean_context_excerpt(new),
        "\n".join(re.sub(r"^\s*\d+\t", "", line) for line in new.splitlines()),
        "\n".join(line.lstrip("\t") for line in new.splitlines()),
        strip_common_leading_tab(new),
    ]
    expanded = list(candidates)
    for candidate in candidates:
        expanded.append("\n".join(line.lstrip("\t") for line in candidate.splitlines()))
    return [candidate for candidate in dict.fromkeys(expanded) if candidate != new]


def strip_common_leading_tab(text: str) -> str:
    lines = text.splitlines()
    nonblank = [line for line in lines if line.strip()]
    if not nonblank or not all(line.startswith("\t") for line in nonblank):
        return text
    return "\n".join(line[1:] if line.startswith("\t") else line for line in lines)


def requires_python_compile(path: str) -> bool:
    return path.endswith(".py")


def python_compiles(content: str, path: str) -> bool:
    try:
        compile(content, path, "exec")
    except SyntaxError:
        return False
    return True


_last_ai_text = last_ai_text
_normalize_patch_payload = normalize_patch_payload
_structured_payload = structured_payload
