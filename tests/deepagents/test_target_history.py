from __future__ import annotations

import pytest

from patchsmith.deepagents_files import _target_history_manifest
from patchsmith.deepagents_target_history import target_history_manifest

pytestmark = pytest.mark.unit


def test_target_history_manifest_renders_preferred_and_historical_paths() -> None:
    manifest = target_history_manifest(
        ["src/old_target.py", "src/another_failed_target.py"],
        preferred_target_paths=["src/new_target.py", "src/old_target.py"],
        preferred_target_reasons={
            "src/new_target.py": [
                "matched_terms:old",
                "reviewed_source_hint",
                "path_terms:new",
                "exact_identifiers:add",
                "python_import_cache_cues",
            ],
            "src/old_target.py": [
                "stale_path_control_point_cues",
                "path_terms:old",
            ],
        },
    )

    assert manifest is not None
    assert "# PatchSmith Target History Manifest" in manifest
    assert "## Preferred Untried Source Targets" in manifest
    assert (
        "- `src/new_target.py` - reviewed_source_hint, python_import_cache_cues, "
        "exact_identifiers:add, matched_terms:old"
    ) in manifest
    assert "## Revived Historical Control Points" in manifest
    assert "- `src/old_target.py` - stale_path_control_point_cues, path_terms:old" in manifest
    assert "## Historical Target Paths" in manifest
    assert "- `src/another_failed_target.py`" in manifest


def test_target_history_manifest_renders_only_preferred_untried_paths() -> None:
    manifest = target_history_manifest(
        [],
        preferred_target_paths=["src/first.py", "src/second.py"],
    )

    assert manifest is not None
    assert "Preferred Untried Source Targets" in manifest
    assert "Historical Target Paths" not in manifest
    assert "- `src/first.py`" in manifest
    assert "- `src/second.py`" in manifest


def test_target_history_manifest_is_absent_without_targets() -> None:
    assert target_history_manifest([]) is None
    assert (
        target_history_manifest(
            [],
            preferred_target_paths=["", "   "],
        )
        is None
    )


def test_deepagents_files_keeps_legacy_target_history_alias() -> None:
    assert _target_history_manifest is target_history_manifest
