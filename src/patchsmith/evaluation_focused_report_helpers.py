"""Shared helpers for focused public issue report rendering."""

from __future__ import annotations


def _markdown_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:500]


__all__ = ["_markdown_table_text"]
