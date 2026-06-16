from __future__ import annotations

import pytest

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_contract import deepagents_planning_contract
from patchsmith.deepagents_manifests import ManifestContents
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
    PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
    PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
    PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
    PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
)

pytestmark = pytest.mark.unit


def test_deepagents_contract_uses_manifest_contents_for_paths_and_policy() -> None:
    contract = deepagents_planning_contract(
        config=DeepAgentsPlannerConfig(model="gpt-test"),
        virtual_file_paths=["/src/calc.py"],
        subagents=[],
        custom_agent_factory=False,
        manifest_contents=ManifestContents.from_enabled_flags(
            repair_interface=True,
            source_hint=True,
            repo_instructions=True,
            acceptance_rubric=True,
            context_budget=True,
        ),
        context_budget_metadata={
            "max_context_files": 1,
            "retrieved_file_count": 2,
            "mounted_file_count": 1,
            "omitted_file_count": 1,
            "mounted_paths": ["src/calc.py"],
            "omitted_paths": ["src/other.py"],
        },
        resource_budget={"remaining_model_responses": 3},
    )

    assert contract["repair_interface_manifest_path"] == (
        PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH
    )
    assert contract["source_hint_manifest_path"] == (PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH)
    assert contract["repo_instructions_manifest_path"] == (
        PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH
    )
    assert contract["acceptance_rubric_manifest_path"] == (
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH
    )
    assert contract["context_budget_manifest_path"] == (PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH)
    assert contract["context_budget"]["omitted_paths"] == ["src/other.py"]
    assert contract["repository_instructions"]["required"] is False
    assert contract["planning_policy"]["source_hint_manifest_read_first"] is False
    assert contract["planning_policy"]["acceptance_rubric_manifest_read_first"] is True
    assert contract["budget_critical_mode"] is True
    assert contract["filesystem_policy"]["allowed_read_paths"] == [
        PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
        PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
        PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
        "/src/calc.py",
    ]
