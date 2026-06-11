"""Shared materialized issue task helpers."""

from __future__ import annotations

from pathlib import Path


def is_materialized_test_candidate_path(path: str) -> bool:
    path_obj = Path(path)
    parts = path_obj.parts
    name = path_obj.name
    return (
        (bool(parts) and parts[0] in {"tests", "test", "testing"})
        or name.startswith("test_")
        or name.endswith("_test.py")
    )
