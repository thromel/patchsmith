from __future__ import annotations

import pytest

from patchsmith.deepagents_manifests import (
    STABLE_TIMESTAMP,
    VirtualFile,
    add_virtual_files,
    manifest_enabled_keys,
    manifest_path,
    manifest_specs_from_contents,
    required_read_paths,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
    PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
    PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
)

pytestmark = pytest.mark.unit


def test_virtual_file_records_stable_agent_metadata() -> None:
    record = VirtualFile(
        path="/patchsmith/manifest.md",
        content="manifest",
        kind="manifest",
    ).to_agent_record()

    assert record == {
        "content": "manifest",
        "encoding": "utf-8",
        "created_at": STABLE_TIMESTAMP,
        "modified_at": STABLE_TIMESTAMP,
    }


def test_manifest_specs_use_registry_order_and_skip_blank_content() -> None:
    specs = manifest_specs_from_contents(
        {
            "context_budget": "budget",
            "source_hint": "   ",
            "repair_interface": "interface",
            "acceptance_rubric": "rubric",
        }
    )

    assert [(spec.key, spec.path, spec.content) for spec in specs] == [
        (
            "repair_interface",
            PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
            "interface",
        ),
        (
            "acceptance_rubric",
            PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
            "rubric",
        ),
        (
            "context_budget",
            PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
            "budget",
        ),
    ]
    assert specs[0].to_virtual_file().kind == "manifest"


def test_add_virtual_files_preserves_existing_files_and_mounts_manifest_specs() -> None:
    base_files = {
        "/src/calc.py": {
            "content": "def add(): pass\n",
            "encoding": "utf-8",
        }
    }
    specs = manifest_specs_from_contents({"repo_map": "map"})

    files = add_virtual_files(
        base_files,
        [spec.to_virtual_file() for spec in specs],
    )

    assert files["/src/calc.py"]["content"] == "def add(): pass\n"
    assert files[PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH] == {
        "content": "map",
        "encoding": "utf-8",
        "created_at": STABLE_TIMESTAMP,
        "modified_at": STABLE_TIMESTAMP,
    }


def test_required_read_paths_respect_budget_critical_policy() -> None:
    enabled = manifest_enabled_keys(
        source_hint_manifest=True,
        repo_map_manifest=True,
        repo_instructions_manifest=True,
        acceptance_rubric_manifest=True,
        retry_feedback_manifest=True,
        target_history_manifest=True,
        context_budget_manifest=True,
    )

    assert required_read_paths(enabled, budget_critical=False) == [
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
        PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
        PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
        PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
        PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    ]
    assert required_read_paths(enabled, budget_critical=True) == [
        PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
        PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
        PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    ]
    assert manifest_path("repo_map") == PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH
