"""Shared helpers for public issue report rendering."""

from __future__ import annotations


def _markdown_table_text(value: object) -> str:
    text = str(value).replace("|", "/").replace("\n", " ")
    return text[:500]


__all__ = ["_markdown_table_text"]
