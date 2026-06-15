"""Context-budget manifest rendering for DeepAgents runs."""

from __future__ import annotations

from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
    context_symbols,
    display_terms,
    omitted_contexts,
)
from patchsmith.models import RetrievedContext


def context_budget_manifest(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    *,
    max_context_files: int,
    max_excerpt_chars: int = 1200,
) -> str | None:
    metadata = context_budget_metadata(
        retrieved_context,
        selected_context,
        max_context_files=max_context_files,
    )
    if metadata is None:
        return None
    omitted_context = omitted_contexts(retrieved_context, selected_context)
    lines = [
        "# PatchSmith Context Budget Manifest",
        "",
        f"- Max mounted repository files: `{metadata['max_context_files']}`",
        f"- Retrieved context files: `{metadata['retrieved_file_count']}`",
        f"- Mounted repository files: `{metadata['mounted_file_count']}`",
        f"- Omitted retrieved files: `{metadata['omitted_file_count']}`",
        "",
        "PatchSmith mounted only the selected repository files in this DeepAgents "
        "filesystem to keep the run within the configured context budget. Omitted "
        "files below are retrieval evidence, not readable source files in this run.",
        "",
        "Use omitted-file summaries as routing evidence before final target selection. "
        "Do not return an omitted path unless it is also listed as a mounted provided "
        "file; choose a mounted control point that directly governs the omitted signal.",
        "",
        "## Mounted Repository Files",
        "",
    ]
    for context in selected_context:
        lines.append(f"- `{context.path}`")
    lines.extend(["", "## Omitted Retrieved Files", ""])
    for context in omitted_context:
        symbols = context_symbols(context)
        terms = display_terms(context.matched_terms)
        excerpt = clean_context_excerpt(context.excerpt).strip()
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[: max_excerpt_chars - 15] + "...[truncated]"
        lines.extend(
            [
                f"### `{context.path}`",
                f"- Rank: `{context.rank}`",
                f"- Score: `{context.score:.4f}`",
                f"- Method: `{context.method}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Matched terms: "
                + (", ".join(f"`{term}`" for term in terms) if terms else "none"),
            ]
        )
        if excerpt:
            lines.extend(["", "Excerpt:", "```text", excerpt, "```"])
        lines.append("")
    return "\n".join(lines).rstrip()


def context_budget_metadata(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    *,
    max_context_files: int,
) -> dict[str, object] | None:
    if max_context_files <= 0 or len(retrieved_context) <= len(selected_context):
        return None
    omitted_context = omitted_contexts(retrieved_context, selected_context)
    if not omitted_context:
        return None
    return {
        "max_context_files": max_context_files,
        "retrieved_file_count": len(retrieved_context),
        "mounted_file_count": len(selected_context),
        "omitted_file_count": len(omitted_context),
        "mounted_paths": [context.path for context in selected_context],
        "omitted_paths": [context.path for context in omitted_context],
    }
