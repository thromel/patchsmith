from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.deepagents_context_files import (
    context_files,
    focused_file_content,
    stable_timestamp,
)
from patchsmith.deepagents_files import (
    _context_files,
)
from patchsmith.deepagents_files import (
    context_files as legacy_context_files,
)
from patchsmith.deepagents_files import (
    focused_file_content as legacy_focused_file_content,
)
from patchsmith.models import RetrievedContext

pytestmark = pytest.mark.unit


def test_context_files_reads_repo_files_and_mounts_focused_spans(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = repo / "src" / "calc.py"
    source.write_text(
        "\n".join(
            [
                "def subtract(a, b):",
                "    return a - b",
                "",
                "def add(a, b):",
                "    return a - b",
                "",
                "def multiply(a, b):",
                "    return a * b",
                "",
            ]
        ),
        encoding="utf-8",
    )

    files, virtual_to_repo = context_files(
        [
            _context(
                "src/calc.py",
                matched_terms=["symbol:add"],
                excerpt="def add(a, b):\n    return a - b",
            )
        ],
        repo_path=repo,
        max_file_chars=80,
        context_mode="span",
        context_window_lines=8,
    )

    assert virtual_to_repo == {"/src/calc.py": "src/calc.py"}
    mounted = files["/src/calc.py"]
    assert mounted["encoding"] == "utf-8"
    assert mounted["created_at"] == mounted["modified_at"]
    assert mounted["created_at"] != stable_timestamp()
    assert "def add(a, b):" in mounted["content"]
    assert "return a - b" in mounted["content"]


def test_context_files_falls_back_to_clean_excerpt_without_repo_path() -> None:
    files, virtual_to_repo = context_files(
        [_context("src/missing.py", excerpt="12:     return old\n13:")],
        repo_path=None,
        max_file_chars=80,
    )

    assert virtual_to_repo == {"/src/missing.py": "src/missing.py"}
    assert files["/src/missing.py"]["content"] == "    return old\n"
    assert files["/src/missing.py"]["created_at"] == stable_timestamp()


def test_focused_file_content_uses_excerpt_when_full_content_exceeds_budget() -> None:
    assert (
        focused_file_content(
            "x" * 100,
            "27: return useful_value",
            max_file_chars=12,
        )
        == "return usefu"
    )


def test_deepagents_files_keeps_legacy_context_file_exports() -> None:
    assert _context_files is context_files
    assert legacy_context_files is context_files
    assert legacy_focused_file_content is focused_file_content


def _context(
    path: str,
    *,
    matched_terms: list[str] | None = None,
    excerpt: str = "",
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=1.0,
        method="keyword",
        matched_terms=matched_terms or [],
        excerpt=excerpt,
    )
