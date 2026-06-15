"""Shared context-rendering helpers for DeepAgents manifests."""

from __future__ import annotations

import re
from collections.abc import Iterable

from patchsmith.models import RetrievedContext


def clean_context_excerpt(excerpt: str) -> str:
    lines = []
    for line in excerpt.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line))
    return "\n".join(lines)


def context_symbols(context: RetrievedContext) -> list[str]:
    symbols = []
    for term in context.matched_terms:
        if term.startswith("symbol:"):
            symbol = term.removeprefix("symbol:").strip()
            if symbol:
                symbols.append(symbol)
    return sorted(dict.fromkeys(symbols))


def display_terms(terms: Iterable[str], *, limit: int = 12) -> list[str]:
    displayed: list[str] = []
    for term in terms:
        stripped = term.strip()
        if stripped and stripped not in displayed:
            displayed.append(stripped)
        if len(displayed) >= limit:
            break
    return displayed


def omitted_contexts(
    retrieved_context: list[RetrievedContext],
    selected_context: list[RetrievedContext],
) -> list[RetrievedContext]:
    selected_ids = {id(context) for context in selected_context}
    return [context for context in retrieved_context if id(context) not in selected_ids]
