from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.artifacts import (
    format_cost,
    load_json,
    safe_artifact_name,
    write_csv,
    write_json,
    write_markdown,
)

pytestmark = pytest.mark.unit


def test_safe_artifact_name_sanitizes_and_collapses() -> None:
    assert safe_artifact_name("task 001/logic-bug") == "task_001_logic_bug"
    assert safe_artifact_name("") == "unknown"
    assert safe_artifact_name("///", fallback="artifact") == "artifact"
    assert safe_artifact_name("Build SDist", lowercase=True) == "build_sdist"


def test_load_json_handles_missing_and_invalid(tmp_path: Path) -> None:
    assert load_json(None) is None
    assert load_json(tmp_path / "missing.json") is None
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    assert load_json(invalid) is None
    valid = tmp_path / "valid.json"
    valid.write_text('{"key": 1}', encoding="utf-8")
    assert load_json(valid) == {"key": 1}


def test_write_json_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"
    write_json(path, {"a": [1, 2]})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": [1, 2]}
    assert not path.read_text(encoding="utf-8").endswith("\n")
    write_json(path, {"a": 1}, trailing_newline=True)
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_markdown_creates_parents(tmp_path: Path) -> None:
    path = tmp_path / "reports" / "report.md"
    write_markdown(path, "# Title\n")
    assert path.read_text(encoding="utf-8") == "# Title\n"


def test_write_csv_writes_header_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    write_csv(path, fieldnames=["a", "b"], rows=[{"a": 1, "b": 2}])
    assert path.read_text(encoding="utf-8").splitlines() == ["a,b", "1,2"]
    empty = tmp_path / "empty.csv"
    write_csv(empty, fieldnames=[], rows=[])
    assert empty.read_text(encoding="utf-8") == ""


def test_format_cost() -> None:
    assert format_cost(None) == "n/a"
    assert format_cost(0) == "$0.00"
    assert format_cost(0.1234567) == "$0.123457"
