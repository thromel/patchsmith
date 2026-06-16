from __future__ import annotations

import pytest

from patchsmith.deepagents_files import _repo_map_manifest
from patchsmith.deepagents_repo_map import repo_map_manifest
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


def test_repo_map_manifest_renders_mounted_and_omitted_context_sections() -> None:
    selected = _context(
        "src/selected.py",
        rank=1,
        score=0.98,
        matched_terms=["symbol:selected", "old", "old", "branch"],
        excerpt="def selected():\n    return 'excerpt'",
    )
    omitted = _context(
        "src/omitted.py",
        rank=2,
        score=0.42,
        matched_terms=["symbol:Omitted", "symbol:helper", "old"],
        excerpt="12: class Omitted:\n13:     def helper(self):\n14:         return 'old'",
    )

    manifest = repo_map_manifest(
        [selected, omitted],
        [selected],
        {"/src/selected.py": "src/selected.py", "/src/omitted.py": "src/omitted.py"},
        {
            "/src/selected.py": {
                "content": (
                    "def selected():\n    return 'old'\n\nclass SelectedHelper:\n    pass\n"
                )
            }
        },
    )

    assert manifest is not None
    assert "# PatchSmith Retrieved Repo Map" in manifest
    assert "## Mounted Files" in manifest
    assert "## Omitted Retrieved Files" in manifest
    assert "### `src/selected.py`" in manifest
    assert "- Status: `mounted`" in manifest
    assert "- Symbols: `selected`" in manifest
    assert "- Matched terms: `symbol:selected`, `old`, `branch`" in manifest
    assert "  - `def selected():`" in manifest
    assert "  - `class SelectedHelper:`" in manifest
    assert "### `src/omitted.py`" in manifest
    assert "- Status: `omitted`" in manifest
    assert "- Symbols: `Omitted`, `helper`" in manifest
    assert "  - `class Omitted:`" in manifest
    assert "12: class Omitted" not in manifest


def test_repo_map_manifest_limits_terms_and_definition_signatures() -> None:
    selected = _context(
        "src/app.ts",
        matched_terms=["one", "two", "three"],
    )

    manifest = repo_map_manifest(
        [selected],
        [selected],
        {"/src/app.ts": "src/app.ts"},
        {
            "/src/app.ts": {
                "content": (
                    "export function first() {}\nexport class Second {}\nfunction third() {}\n"
                )
            }
        },
        max_definitions_per_file=2,
        max_terms_per_file=2,
    )

    assert manifest is not None
    assert "- Matched terms: `one`, `two`" in manifest
    assert "`three`" not in manifest
    assert "  - `export function first() {}`" in manifest
    assert "  - `export class Second {}`" in manifest
    assert "function third" not in manifest


def test_repo_map_manifest_is_absent_without_retrieved_context() -> None:
    assert repo_map_manifest([], [], {}, {}) is None


def test_deepagents_files_keeps_legacy_repo_map_alias() -> None:
    assert _repo_map_manifest is repo_map_manifest


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
