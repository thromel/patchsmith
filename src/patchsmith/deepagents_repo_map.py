"""Retrieved repo-map manifest rendering for DeepAgents runs."""

from __future__ import annotations

import re

from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
    context_symbols,
    display_terms,
    omitted_contexts,
)
from patchsmith.models import RetrievedContext


def repo_map_manifest(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
    virtual_to_repo: dict[str, str],
    files: dict[str, dict[str, str]],
    *,
    max_definitions_per_file: int = 8,
    max_terms_per_file: int = 10,
) -> str | None:
    if not retrieved_context:
        return None
    selected_ids = {id(context) for context in selected_context}
    omitted_context = omitted_contexts(retrieved_context, selected_context)
    lines = [
        "# PatchSmith Retrieved Repo Map",
        "",
        "This compact map summarizes the retrieved context before deep file reads. "
        "Use it to route target selection, then inspect the mounted source file before "
        "returning a patch. Omitted files are retrieval evidence only and may not be "
        "valid final patch paths under a context cap.",
        "",
        "## Mounted Files",
        "",
    ]
    mounted_sections = _repo_map_sections(
        [context for context in retrieved_context if id(context) in selected_ids],
        selected=True,
        virtual_to_repo=virtual_to_repo,
        files=files,
        max_definitions_per_file=max_definitions_per_file,
        max_terms_per_file=max_terms_per_file,
    )
    omitted_sections = _repo_map_sections(
        omitted_context,
        selected=False,
        virtual_to_repo=virtual_to_repo,
        files=files,
        max_definitions_per_file=max_definitions_per_file,
        max_terms_per_file=max_terms_per_file,
    )
    lines.extend(mounted_sections or ["- none"])
    if omitted_sections:
        lines.extend(["", "## Omitted Retrieved Files", "", *omitted_sections])
    return "\n".join(lines).rstrip()


def _repo_map_sections(
    contexts: list[RetrievedContext],
    *,
    selected: bool,
    virtual_to_repo: dict[str, str],
    files: dict[str, dict[str, str]],
    max_definitions_per_file: int,
    max_terms_per_file: int,
) -> list[str]:
    sections: list[str] = []
    for context in contexts:
        virtual_path = "/" + context.path.lstrip("/")
        repo_path = virtual_to_repo.get(virtual_path, context.path)
        source = (
            files.get(virtual_path, {}).get("content", "")
            if selected
            else clean_context_excerpt(context.excerpt)
        )
        definitions = _definition_signatures(source)
        symbols = context_symbols(context)
        terms = display_terms(context.matched_terms, limit=max_terms_per_file)
        sections.extend(
            [
                f"### `{repo_path}`",
                f"- Virtual path: `{virtual_path}`",
                f"- Status: `{'mounted' if selected else 'omitted'}`",
                f"- Rank: `{context.rank}`",
                f"- Score: `{context.score:.4f}`",
                f"- Method: `{context.method}`",
                "- Symbols: "
                + (", ".join(f"`{symbol}`" for symbol in symbols) if symbols else "none"),
                "- Matched terms: "
                + (", ".join(f"`{term}`" for term in terms) if terms else "none"),
            ]
        )
        if definitions:
            sections.extend(["- Definition signatures:"])
            sections.extend(
                f"  - `{signature}`"
                for signature in definitions[: max(max_definitions_per_file, 0)]
            )
        sections.append("")
    return sections


def _definition_signatures(source: str) -> list[str]:
    signatures: list[str] = []
    for line in clean_context_excerpt(source).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        if _looks_like_definition_signature(stripped):
            signatures.append(_truncate_signature(stripped))
    return list(dict.fromkeys(signatures))


def _looks_like_definition_signature(line: str) -> bool:
    return bool(
        re.match(
            r"^(?:async\s+def|def|class)\s+[A-Za-z_][A-Za-z0-9_]*",
            line,
        )
        or re.match(
            r"^(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][A-Za-z0-9_$]*",
            line,
        )
        or re.match(
            r"^(?:export\s+)?(?:class|interface|type)\s+[A-Za-z_$][A-Za-z0-9_$]*",
            line,
        )
        or re.match(
            r"^(?:pub\s+)?(?:async\s+)?fn\s+[A-Za-z_][A-Za-z0-9_]*",
            line,
        )
    )


def _truncate_signature(signature: str, *, limit: int = 160) -> str:
    compact = " ".join(signature.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 15] + "...[truncated]"
