from __future__ import annotations

from pathlib import Path

from patchsmith.deepagents_files import (
    _acceptance_rubric_manifest,
    _repo_instructions_manifest,
)
from patchsmith.deepagents_repo_instructions import repo_instructions_manifest
from patchsmith.deepagents_rubric import acceptance_rubric_manifest
from patchsmith.models import RetrievedContext


def _context(
    path: str,
    *,
    matched_terms: list[str] | None = None,
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=0.9,
        method="keyword",
        matched_terms=matched_terms or [],
        excerpt="",
    )


def test_acceptance_rubric_manifest_is_task_local_and_targeted() -> None:
    rubric = acceptance_rubric_manifest(
        issue_text="1: failure happens after cached bytecode is reused",
        selected_context=[
            _context("src/_pytest/assertion/rewrite.py"),
            _context("tests/test_rewrite.py", matched_terms=["validation_fixture"]),
        ],
        preferred_target_paths=[
            "src/_pytest/assertion/rewrite.py",
            "/src/_pytest/assertion/rewrite.py",
        ],
        preferred_target_symbols={
            "src/_pytest/assertion/rewrite.py": [
                "_read_pyc",
                "_read_pyc",
            ]
        },
    )

    assert "1: failure happens" not in rubric
    assert "failure happens after cached bytecode is reused" in rubric
    assert rubric.count("src/_pytest/assertion/rewrite.py") >= 2
    assert (
        "Preferred target order:\n\n- `src/_pytest/assertion/rewrite.py`\n\nPreferred symbol focus:"
    ) in rubric
    assert "- `src/_pytest/assertion/rewrite.py`: `_read_pyc`" in rubric
    assert "Mounted validation or reproduction files:" in rubric
    assert "- `tests/test_rewrite.py`" in rubric
    assert "No naked `importlib.invalidate_caches()`" in rubric


def test_deepagents_files_keeps_legacy_rubric_alias() -> None:
    assert _acceptance_rubric_manifest is acceptance_rubric_manifest


def test_deepagents_files_keeps_legacy_repo_instructions_alias() -> None:
    assert _repo_instructions_manifest is repo_instructions_manifest


def test_repo_instructions_manifest_is_scoped_to_mounted_ancestors(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "other").mkdir()
    (repo / "AGENTS.md").write_text(
        "Root rule: keep patches minimal.",
        encoding="utf-8",
    )
    (repo / "src" / "pkg" / "AGENTS.md").write_text(
        "Package rule: preserve public API names.",
        encoding="utf-8",
    )
    (repo / "other" / "AGENTS.md").write_text(
        "Other rule should not apply.",
        encoding="utf-8",
    )

    manifest = repo_instructions_manifest(
        repo,
        [_context("src/pkg/module.py")],
    )

    assert manifest is not None
    assert "# PatchSmith Scoped Repository Instructions" in manifest
    assert "`AGENTS.md`" in manifest
    assert "`src/pkg/AGENTS.md`" in manifest
    assert "`src/pkg/module.py`" in manifest
    assert "Root rule: keep patches minimal." in manifest
    assert "Package rule: preserve public API names." in manifest
    assert "Other rule should not apply." not in manifest
