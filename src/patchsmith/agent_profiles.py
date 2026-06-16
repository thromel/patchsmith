from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from patchsmith.agent_frontmatter import frontmatter_body, frontmatter_metadata

AGENT_PROFILE_ROOT = ".patchsmith/agents"
_PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*(?::[a-z0-9][a-z0-9_.-]*)*$")
_SUBAGENT_MODES = {"auto", "full", "inline"}


@dataclass(frozen=True)
class AgentProfile:
    name: str
    path: Path
    instructions: str
    metadata: dict[str, str]

    @property
    def description(self) -> str | None:
        return self.metadata.get("description")

    @property
    def model(self) -> str | None:
        return _metadata_first(self.metadata, "model", "deepagents_model")

    @property
    def subagents(self) -> str | None:
        value = _metadata_first(self.metadata, "subagents", "deepagents_subagents")
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized if normalized in _SUBAGENT_MODES else None

    @property
    def max_context_files(self) -> int | None:
        return _metadata_int(
            self.metadata,
            "max_context_files",
            "deepagents_max_context_files",
        )

    @property
    def max_model_responses(self) -> int | None:
        return _metadata_int(self.metadata, "max_model_responses")

    @property
    def max_model_tokens(self) -> int | None:
        return _metadata_int(self.metadata, "max_model_tokens")

    @property
    def top_k(self) -> int | None:
        value = _metadata_int(self.metadata, "top_k")
        return value if value is None or value >= 0 else None

    @property
    def test_command(self) -> str | None:
        return self.metadata.get("test_command")

    @property
    def context_paths(self) -> tuple[str, ...]:
        raw = _metadata_first(self.metadata, "context_paths", "context_path")
        return _metadata_list(raw)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "model": self.model,
            "subagents": self.subagents,
            "max_context_files": self.max_context_files,
            "max_model_responses": self.max_model_responses,
            "max_model_tokens": self.max_model_tokens,
            "top_k": self.top_k,
            "test_command": self.test_command,
            "context_paths": list(self.context_paths),
            "instruction_chars": len(self.instructions),
            "metadata": dict(self.metadata),
        }


def list_agent_profiles(repo: str) -> list[AgentProfile]:
    profile_dir = _profile_dir(repo)
    if profile_dir is None:
        return []
    profiles = [
        _load_profile_from_path(
            name=_profile_name_from_path(profile_dir, path),
            path=path,
        )
        for path in sorted(profile_dir.rglob("*.md"))
        if path.is_file()
    ]
    return [profile for profile in profiles if _valid_profile_name(profile.name)]


def load_agent_profile(repo: str, name: str) -> AgentProfile | None:
    normalized_name = name.strip().lower()
    if not _valid_profile_name(normalized_name):
        return None
    profile_dir = _profile_dir(repo)
    if profile_dir is None:
        return None
    profile_path = profile_dir.joinpath(*normalized_name.split(":")).with_suffix(".md")
    if not profile_path.is_file():
        return None
    return _load_profile_from_path(name=normalized_name, path=profile_path)


def format_agent_profiles(profiles: list[AgentProfile]) -> str:
    if not profiles:
        return "No project agent profiles found."
    lines = ["Project agent profiles:"]
    for profile in profiles:
        label = f"- /agent {profile.name}"
        if profile.description:
            label = f"{label} - {profile.description}"
        detail = _profile_detail(profile)
        if detail:
            label = f"{label} [{detail}]"
        lines.append(f"{label} ({profile.path})")
    return "\n".join(lines)


def agent_profiles_payload(profiles: list[AgentProfile]) -> list[dict[str, object]]:
    return [profile.to_dict() for profile in profiles]


def profile_instruction_prompt(profile: AgentProfile, task: str) -> str:
    if not profile.instructions.strip():
        return task
    return (
        f"PatchSmith agent profile /{profile.name}\n"
        f"Source: {profile.path}\n\n"
        "Profile instructions:\n"
        f"{profile.instructions.strip()}\n\n"
        "Task:\n"
        f"{task.strip()}"
    ).rstrip()


def _load_profile_from_path(*, name: str, path: Path) -> AgentProfile:
    template = path.read_text(encoding="utf-8")
    return AgentProfile(
        name=name,
        path=path,
        instructions=frontmatter_body(template).strip(),
        metadata=frontmatter_metadata(template),
    )


def _profile_dir(repo: str) -> Path | None:
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir():
        return None
    profile_dir = repo_path / AGENT_PROFILE_ROOT
    if not profile_dir.is_dir():
        return None
    return profile_dir


def _profile_name_from_path(profile_dir: Path, path: Path) -> str:
    relative = path.relative_to(profile_dir).with_suffix("")
    return ":".join(relative.parts)


def _valid_profile_name(name: str) -> bool:
    return bool(_PROFILE_NAME_PATTERN.fullmatch(name))


def _metadata_first(metadata: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value:
            return value
    return None


def _metadata_int(metadata: dict[str, str], *keys: str) -> int | None:
    raw = _metadata_first(metadata, *keys)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _metadata_list(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    values: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        value = line.strip()
        if value.startswith("- "):
            value = value[2:].strip()
        if value:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _profile_detail(profile: AgentProfile) -> str:
    parts: list[str] = []
    if profile.model:
        parts.append(f"model={profile.model}")
    if profile.max_model_responses is not None:
        parts.append(f"responses={profile.max_model_responses}")
    if profile.max_model_tokens is not None:
        parts.append(f"tokens={profile.max_model_tokens}")
    if profile.context_paths:
        parts.append(f"context={len(profile.context_paths)}")
    return ", ".join(parts)
