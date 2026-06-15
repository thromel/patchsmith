from __future__ import annotations

import pytest

from patchsmith.deepagents_context_budget import (
    context_budget_manifest,
    context_budget_metadata,
)
from patchsmith.deepagents_context_utils import (
    clean_context_excerpt,
    context_symbols,
    display_terms,
    omitted_contexts,
)
from patchsmith.deepagents_files import (
    _clean_context_excerpt,
    _context_budget_manifest,
    _context_budget_metadata,
)
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


def test_context_budget_metadata_reports_identity_based_omissions() -> None:
    selected = _context("src/selected.py")
    omitted = _context("src/omitted.py")

    metadata = context_budget_metadata(
        [selected, omitted],
        [selected],
        max_context_files=1,
    )

    assert metadata == {
        "max_context_files": 1,
        "retrieved_file_count": 2,
        "mounted_file_count": 1,
        "omitted_file_count": 1,
        "mounted_paths": ["src/selected.py"],
        "omitted_paths": ["src/omitted.py"],
    }
    assert omitted_contexts([selected, omitted], [selected]) == [omitted]


def test_context_budget_manifest_renders_omitted_context_evidence() -> None:
    selected = _context("src/selected.py")
    omitted = _context(
        "src/omitted.py",
        rank=3,
        score=0.42,
        matched_terms=["symbol:omitted", "old", "old", "reviewed_source_hint"],
        excerpt="1: def omitted():\n2:     return 'old'",
    )

    manifest = context_budget_manifest(
        [selected, omitted],
        [selected],
        max_context_files=1,
    )

    assert manifest is not None
    assert "# PatchSmith Context Budget Manifest" in manifest
    assert "- `src/selected.py`" in manifest
    assert "### `src/omitted.py`" in manifest
    assert "- Rank: `3`" in manifest
    assert "- Score: `0.4200`" in manifest
    assert "- Symbols: `omitted`" in manifest
    assert "- Matched terms: `symbol:omitted`, `old`, `reviewed_source_hint`" in manifest
    assert "1: def omitted" not in manifest
    assert "def omitted():\n    return 'old'" in manifest


def test_context_budget_manifest_is_absent_when_context_is_not_capped() -> None:
    selected = _context("src/selected.py")

    assert (
        context_budget_manifest(
            [selected],
            [selected],
            max_context_files=5,
        )
        is None
    )


def test_context_utils_and_deepagents_files_legacy_aliases() -> None:
    context = _context(
        "src/selected.py",
        matched_terms=["symbol:add", "symbol:add", "old", "new"],
    )

    assert clean_context_excerpt("12: return old") == "return old"
    assert context_symbols(context) == ["add"]
    assert display_terms(["old", "old", "new"], limit=2) == ["old", "new"]
    assert _clean_context_excerpt is clean_context_excerpt
    assert _context_budget_manifest is context_budget_manifest
    assert _context_budget_metadata is context_budget_metadata


def _context(
    path: str,
    *,
    rank: int = 1,
    score: float = 1.0,
    matched_terms: list[str] | None = None,
    excerpt: str = "",
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=rank,
        score=score,
        method="keyword",
        matched_terms=matched_terms or [],
        excerpt=excerpt,
    )
