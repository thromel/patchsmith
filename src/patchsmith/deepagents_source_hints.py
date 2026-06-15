"""Reviewed source-hint manifest rendering for DeepAgents runs."""

from __future__ import annotations

from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
    context_symbols,
)
from patchsmith.models import RetrievedContext


def source_hint_manifest(
    retrieved_context: list[RetrievedContext],
    virtual_to_repo: dict[str, str],
    *,
    max_excerpt_chars: int = 4000,
) -> str | None:
    sections: list[str] = []
    for context in retrieved_context:
        symbols = context_symbols(context)
        if "reviewed_source_hint" not in context.matched_terms and not symbols:
            continue
        virtual_path = "/" + context.path.lstrip("/")
        repo_path = virtual_to_repo.get(virtual_path, context.path)
        excerpt = clean_context_excerpt(context.excerpt).strip()
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[: max_excerpt_chars - 15] + "...[truncated]"
        sections.extend(
            [
                f"## `{repo_path}`",
                f"- Virtual path: `{virtual_path}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Priority: reviewed reproduction source hint",
            ]
        )
        if excerpt:
            sections.extend(
                [
                    "",
                    "Focused excerpt:",
                    "```text",
                    excerpt,
                    "```",
                ]
            )
        sections.append("")
    if not sections:
        return None
    return "\n".join(
        [
            "# PatchSmith Source Hint Manifest",
            "",
            "Read this manifest before broad source exploration. These hints came from "
            "reviewed reproduction evidence, and symbol-qualified hints identify code "
            "paths that should be inspected before selecting a different edit target.",
            "",
            *sections,
        ]
    ).rstrip()
