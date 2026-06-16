from __future__ import annotations

import pytest

from patchsmith.deepagents_files import _repair_interface_manifest
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
    PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
    PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
)
from patchsmith.deepagents_repair_interface import repair_interface_manifest

pytestmark = pytest.mark.unit


def test_repair_interface_manifest_routes_full_context_and_required_reads() -> None:
    manifest = repair_interface_manifest(
        virtual_to_repo={
            "/src/calc.py": "src/calc.py",
            "/tests/test_calc.py": "tests/test_calc.py",
        },
        files={
            "/src/calc.py": {
                "content": "def add(a, b):\n    return a - b\n",
                "encoding": "utf-8",
            }
        },
        subagent_mode="auto",
        subagents_enabled=True,
        subagent_routing_reasons=["source_hint_multi_symbol", ""],
        resource_budget={
            "max_model_responses": 12,
            "max_model_tokens": 200_000,
            "used_model_responses": 2,
            "used_model_tokens": 500,
        },
        source_hint_manifest=True,
        retry_feedback_manifest=True,
        target_history_manifest=True,
        context_budget_manifest=True,
        repo_map_manifest=True,
        repo_instructions_manifest=True,
        acceptance_rubric_manifest=True,
        context_mode="span",
        context_window_lines=32,
        preferred_target_paths=[
            "/src/calc.py",
            "src/calc.py",
            "tests/test_calc.py",
        ],
        preferred_target_symbols={"src/calc.py": ["add", "add"]},
    )

    assert "Subagent mode: `auto`" in manifest
    assert "Subagents enabled: `true`" in manifest
    assert "Routing reasons: `source_hint_multi_symbol`" in manifest
    assert "Context mode: `span`" in manifest
    assert "Context window lines: `32`" in manifest
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH in manifest
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in manifest
    assert "`src/calc.py` via `/src/calc.py`" in manifest
    assert "`tests/test_calc.py` via `/tests/test_calc.py`" in manifest
    assert [line for line in manifest.splitlines() if line == "- `src/calc.py`"] == [
        "- `src/calc.py`"
    ]
    assert "- `src/calc.py`: `add`" in manifest
    assert "Max model responses: `12`" in manifest
    assert "Used model responses before this attempt: `2`" in manifest
    assert "## Output Contract" in manifest


def test_budget_critical_interface_skips_generic_required_reads() -> None:
    manifest = repair_interface_manifest(
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        files={
            "/src/calc.py": {
                "content": "def add(a, b):\n    return a - b\n",
                "encoding": "utf-8",
            }
        },
        subagent_mode="inline",
        subagents_enabled=False,
        subagent_routing_reasons=["budget_pressure"],
        resource_budget={"remaining_model_responses": 3},
        source_hint_manifest=True,
        retry_feedback_manifest=True,
        target_history_manifest=True,
        context_budget_manifest=True,
        repo_map_manifest=True,
        repo_instructions_manifest=True,
        acceptance_rubric_manifest=True,
        preferred_target_paths=["src/calc.py"],
        preferred_target_symbols={"src/calc.py": ["add"]},
    )

    required_reads = manifest.split("## Required Reads", maxsplit=1)[1].split(
        "## Budget-Critical Mode",
        maxsplit=1,
    )[0]
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH not in required_reads
    assert PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH not in required_reads
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH not in required_reads
    assert PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH not in required_reads
    assert PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH in required_reads
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in required_reads
    assert PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH in required_reads
    assert PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH in required_reads
    assert PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH in required_reads
    assert "## Budget-Critical Mode" in manifest
    assert "Response ceiling: `3`" in manifest
    assert "## Fast Patch Packet" in manifest
    assert "### `src/calc.py` via `/src/calc.py`" in manifest
    assert "Preferred symbols: `add`" in manifest
    assert "def add(a, b):" in manifest


def test_budget_critical_fast_patch_packet_requires_mounted_source() -> None:
    manifest = repair_interface_manifest(
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        files={"/src/calc.py": {"content": "def add(): pass\n"}},
        subagent_mode="inline",
        subagents_enabled=False,
        subagent_routing_reasons=[],
        resource_budget={"max_model_responses": 6},
        preferred_target_paths=["src/missing.py"],
        preferred_target_symbols={"src/missing.py": ["missing"]},
    )

    assert "## Budget-Critical Mode" in manifest
    assert "## Fast Patch Packet" not in manifest


def test_deepagents_files_keeps_legacy_repair_interface_alias() -> None:
    assert _repair_interface_manifest is repair_interface_manifest
