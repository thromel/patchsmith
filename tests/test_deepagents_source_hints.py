from __future__ import annotations

import pytest

from patchsmith.deepagents_files import _source_hint_manifest
from patchsmith.deepagents_source_hints import source_hint_manifest
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


def test_source_hint_manifest_renders_reviewed_and_symbol_hints() -> None:
    reviewed = _context(
        "src/hinted.py",
        matched_terms=["reviewed_source_hint", "symbol:target_symbol"],
        excerpt="1: def target_symbol():\n2:     return 'old'",
    )
    symbol_only = _context(
        "src/symbol.py",
        matched_terms=["symbol:helper"],
        excerpt="def helper():\n    return 'value'",
    )

    manifest = source_hint_manifest(
        [reviewed, symbol_only],
        {
            "/src/hinted.py": "src/hinted.py",
            "/src/symbol.py": "src/symbol.py",
        },
    )

    assert manifest is not None
    assert "# PatchSmith Source Hint Manifest" in manifest
    assert "## `src/hinted.py`" in manifest
    assert "- Virtual path: `/src/hinted.py`" in manifest
    assert "- Symbols: `target_symbol`" in manifest
    assert "1: def target_symbol" not in manifest
    assert "def target_symbol():\n    return 'old'" in manifest
    assert "## `src/symbol.py`" in manifest
    assert "- Symbols: `helper`" in manifest


def test_source_hint_manifest_truncates_long_excerpts() -> None:
    context = _context(
        "src/hinted.py",
        matched_terms=["reviewed_source_hint"],
        excerpt="x" * 40,
    )

    manifest = source_hint_manifest(
        [context],
        {"/src/hinted.py": "src/hinted.py"},
        max_excerpt_chars=20,
    )

    assert manifest is not None
    assert "xxxxx...[truncated]" in manifest
    assert "x" * 40 not in manifest


def test_source_hint_manifest_is_absent_without_reviewed_or_symbol_hints() -> None:
    assert (
        source_hint_manifest(
            [_context("src/plain.py", matched_terms=["plain"], excerpt="pass")],
            {"/src/plain.py": "src/plain.py"},
        )
        is None
    )


def test_deepagents_files_keeps_legacy_source_hint_alias() -> None:
    assert _source_hint_manifest is source_hint_manifest


def _context(
    path: str,
    *,
    matched_terms: list[str],
    excerpt: str,
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=1.0,
        method="keyword",
        matched_terms=matched_terms,
        excerpt=excerpt,
    )
