"""Manifest registry and virtual-file records for DeepAgents runs."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

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

STABLE_TIMESTAMP = "1970-01-01T00:00:00+00:00"
RequiredReadPolicy = Literal["always", "skip_budget_critical"]


@dataclass(frozen=True)
class VirtualFile:
    path: str
    content: str
    kind: str
    encoding: str = "utf-8"
    created_at: str = STABLE_TIMESTAMP
    modified_at: str = STABLE_TIMESTAMP

    def to_agent_record(self) -> dict[str, str]:
        return {
            "content": self.content,
            "encoding": self.encoding,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }


@dataclass(frozen=True)
class ManifestDefinition:
    key: str
    path: str
    kind: str
    metadata_key: str
    required_read_policy: RequiredReadPolicy = "always"

    def to_spec(self, content: str | None) -> ManifestSpec | None:
        if content is None or not content.strip():
            return None
        return ManifestSpec(definition=self, content=content)

    def should_be_required(self, *, budget_critical: bool) -> bool:
        return self.required_read_policy == "always" or not budget_critical


@dataclass(frozen=True)
class ManifestSpec:
    definition: ManifestDefinition
    content: str

    @property
    def key(self) -> str:
        return self.definition.key

    @property
    def path(self) -> str:
        return self.definition.path

    @property
    def metadata_key(self) -> str:
        return self.definition.metadata_key

    def to_virtual_file(self) -> VirtualFile:
        return VirtualFile(
            path=self.path,
            content=self.content,
            kind=self.definition.kind,
        )


CORE_DEFINITIONS: tuple[ManifestDefinition, ...] = (
    ManifestDefinition(
        key="memory",
        path=PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
        kind="memory",
        metadata_key="memory_path",
        required_read_policy="skip_budget_critical",
    ),
    ManifestDefinition(
        key="repair_skill",
        path=PATCHSMITH_DEEPAGENTS_REPAIR_SKILL_PATH,
        kind="skill",
        metadata_key="repair_skill_path",
        required_read_policy="skip_budget_critical",
    ),
)

MANIFEST_DEFINITIONS: tuple[ManifestDefinition, ...] = (
    ManifestDefinition(
        key="repair_interface",
        path=PATCHSMITH_DEEPAGENTS_REPAIR_INTERFACE_PATH,
        kind="manifest",
        metadata_key="repair_interface_manifest_path",
    ),
    ManifestDefinition(
        key="source_hint",
        path=PATCHSMITH_DEEPAGENTS_SOURCE_HINTS_PATH,
        kind="manifest",
        metadata_key="source_hint_manifest_path",
        required_read_policy="skip_budget_critical",
    ),
    ManifestDefinition(
        key="repo_map",
        path=PATCHSMITH_DEEPAGENTS_REPO_MAP_PATH,
        kind="manifest",
        metadata_key="repo_map_manifest_path",
    ),
    ManifestDefinition(
        key="repo_instructions",
        path=PATCHSMITH_DEEPAGENTS_REPO_INSTRUCTIONS_PATH,
        kind="manifest",
        metadata_key="repo_instructions_manifest_path",
        required_read_policy="skip_budget_critical",
    ),
    ManifestDefinition(
        key="acceptance_rubric",
        path=PATCHSMITH_DEEPAGENTS_ACCEPTANCE_RUBRIC_PATH,
        kind="manifest",
        metadata_key="acceptance_rubric_manifest_path",
    ),
    ManifestDefinition(
        key="retry_feedback",
        path=PATCHSMITH_DEEPAGENTS_RETRY_FEEDBACK_PATH,
        kind="manifest",
        metadata_key="retry_feedback_manifest_path",
    ),
    ManifestDefinition(
        key="target_history",
        path=PATCHSMITH_DEEPAGENTS_TARGET_HISTORY_PATH,
        kind="manifest",
        metadata_key="target_history_manifest_path",
    ),
    ManifestDefinition(
        key="context_budget",
        path=PATCHSMITH_DEEPAGENTS_CONTEXT_BUDGET_PATH,
        kind="manifest",
        metadata_key="context_budget_manifest_path",
    ),
)

_DEFINITIONS_BY_KEY = {
    definition.key: definition
    for definition in (*CORE_DEFINITIONS, *MANIFEST_DEFINITIONS)
}


def manifest_specs_from_contents(
    contents: Mapping[str, str | None],
) -> list[ManifestSpec]:
    specs: list[ManifestSpec] = []
    for definition in MANIFEST_DEFINITIONS:
        spec = definition.to_spec(contents.get(definition.key))
        if spec is not None:
            specs.append(spec)
    return specs


def core_virtual_files(
    *,
    subagents_enabled: bool,
    memory_content: Callable[[bool], str],
    repair_skill_content: Callable[[bool], str],
) -> list[VirtualFile]:
    content_by_key = {
        "memory": memory_content(subagents_enabled),
        "repair_skill": repair_skill_content(subagents_enabled),
    }
    return [
        VirtualFile(
            path=definition.path,
            content=content_by_key[definition.key],
            kind=definition.kind,
        )
        for definition in CORE_DEFINITIONS
    ]


def add_virtual_files(
    files: dict[str, dict[str, str]],
    virtual_files: Iterable[VirtualFile],
) -> dict[str, dict[str, str]]:
    agent_file_map = dict(files)
    for virtual_file in virtual_files:
        agent_file_map[virtual_file.path] = virtual_file.to_agent_record()
    return agent_file_map


def required_read_paths(
    enabled_keys: Iterable[str],
    *,
    budget_critical: bool,
) -> list[str]:
    enabled = set(enabled_keys)
    paths: list[str] = []
    for definition in (*CORE_DEFINITIONS, *MANIFEST_DEFINITIONS):
        if definition.key not in enabled:
            continue
        if definition.should_be_required(budget_critical=budget_critical):
            paths.append(definition.path)
    return paths


def manifest_enabled_keys(
    *,
    source_hint_manifest: bool = False,
    retry_feedback_manifest: bool = False,
    target_history_manifest: bool = False,
    context_budget_manifest: bool = False,
    repo_map_manifest: bool = False,
    repo_instructions_manifest: bool = False,
    acceptance_rubric_manifest: bool = False,
) -> list[str]:
    enabled = ["memory", "repair_skill"]
    for key, is_enabled in (
        ("source_hint", source_hint_manifest),
        ("repo_map", repo_map_manifest),
        ("repo_instructions", repo_instructions_manifest),
        ("acceptance_rubric", acceptance_rubric_manifest),
        ("retry_feedback", retry_feedback_manifest),
        ("target_history", target_history_manifest),
        ("context_budget", context_budget_manifest),
    ):
        if is_enabled:
            enabled.append(key)
    return enabled


def manifest_path(key: str) -> str:
    return _DEFINITIONS_BY_KEY[key].path
