from __future__ import annotations

import pytest

from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
)
from patchsmith.deepagents_run_interface import build_deepagents_run_interface

pytestmark = pytest.mark.unit


def test_build_deepagents_run_interface_mounts_manifest_and_virtual_files() -> None:
    run_interface = build_deepagents_run_interface(
        files={
            "/src/calc.py": {
                "content": "def add(a, b):\n    return a - b\n",
                "encoding": "utf-8",
            }
        },
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        subagent_mode="auto",
        subagents_enabled=False,
        subagent_routing_reasons=["auto_simple_single_control_point"],
        resource_budget={"max_model_responses": 12, "max_model_tokens": 200_000},
        source_hint_manifest="source hints",
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest=None,
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest="acceptance rubric",
        context_mode="full",
        context_window_lines=80,
        preferred_target_paths=["src/calc.py"],
        preferred_target_symbols={"src/calc.py": ["add"]},
    )

    assert run_interface.repair_interface_manifest_path == (
        PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH
    )
    assert "PatchSmith Repair Interface" in run_interface.repair_interface_manifest
    assert "Subagent mode: `auto`" in run_interface.repair_interface_manifest
    assert "Subagents enabled: `false`" in run_interface.repair_interface_manifest
    assert "Max model responses: `12`" in run_interface.repair_interface_manifest
    assert "`src/calc.py` via `/src/calc.py`" in run_interface.repair_interface_manifest

    files = run_interface.agent_files
    assert "/src/calc.py" in files
    assert PATCHSMITH_DEEPAGENTS_MEMORY_PATH in files
    assert PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH in files
    assert PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH in files
    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH in files
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH in files
    assert files[PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH]["content"] == (
        run_interface.repair_interface_manifest
    )


def test_build_deepagents_run_interface_omits_absent_optional_manifests() -> None:
    run_interface = build_deepagents_run_interface(
        files={"/src/calc.py": {"content": "x = 1\n", "encoding": "utf-8"}},
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        subagent_mode="inline",
        subagents_enabled=False,
        subagent_routing_reasons=["configured_inline"],
        resource_budget=None,
        source_hint_manifest=None,
        retry_feedback_manifest=None,
        target_history_manifest=None,
        context_budget_manifest=None,
        repo_map_manifest=None,
        repo_instructions_manifest=None,
        acceptance_rubric_manifest=None,
        context_mode="span",
        context_window_lines=24,
        preferred_target_paths=[],
        preferred_target_symbols={},
    )

    assert PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH not in run_interface.agent_files
    assert PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH not in run_interface.agent_files
    assert "Context mode: `span`" in run_interface.repair_interface_manifest
    assert "Routing reasons: `configured_inline`" in run_interface.repair_interface_manifest
