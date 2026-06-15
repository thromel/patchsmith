from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.agent_instructions import load_agent_instruction_bundle

pytestmark = pytest.mark.unit


def test_instruction_file_with_trailing_newline_is_not_marked_truncated(
    tmp_path: Path,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "## Project memory\n- Keep edits focused.\n",
        encoding="utf-8",
    )

    bundle = load_agent_instruction_bundle(str(tmp_path))

    assert len(bundle.files) == 1
    assert bundle.files[0].truncated is False
    assert bundle.files[0].chars == len("## Project memory\n- Keep edits focused.\n")


def test_instruction_file_over_limit_is_marked_truncated(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("abcdef\n", encoding="utf-8")

    bundle = load_agent_instruction_bundle(str(tmp_path), max_chars_per_file=3)

    assert len(bundle.files) == 1
    assert bundle.files[0].truncated is True
    assert "...[truncated]" in bundle.content
