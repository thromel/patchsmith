from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from patchsmith.agent_frontmatter import frontmatter_body, frontmatter_metadata

CUSTOM_COMMAND_ROOT = ".patchsmith/commands"
_COMMAND_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_.-]*(?::[a-z0-9][a-z0-9_.-]*)*$"
)


@dataclass(frozen=True)
class AgentCustomCommand:
    name: str
    path: Path
    template: str
    metadata: dict[str, str]

    @property
    def description(self) -> str | None:
        return self.metadata.get("description")

    @property
    def argument_hint(self) -> str | None:
        return self.metadata.get("argument_hint") or self.metadata.get("argument-hint")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "argument_hint": self.argument_hint,
            "metadata": dict(self.metadata),
        }


def list_custom_commands(repo: str) -> list[AgentCustomCommand]:
    command_dir = _command_dir(repo)
    if command_dir is None:
        return []
    commands = [
        _load_command_from_path(
            name=_command_name_from_path(command_dir, path),
            path=path,
        )
        for path in sorted(command_dir.rglob("*.md"))
        if path.is_file()
    ]
    return [command for command in commands if _valid_command_name(command.name)]


def load_custom_command(repo: str, name: str) -> AgentCustomCommand | None:
    normalized_name = name.strip().lower()
    if not _valid_command_name(normalized_name):
        return None
    command_dir = _command_dir(repo)
    if command_dir is None:
        return None
    command_path = command_dir.joinpath(*normalized_name.split(":")).with_suffix(".md")
    if not command_path.is_file():
        return None
    return _load_command_from_path(name=normalized_name, path=command_path)


def render_custom_command_prompt(
    command: AgentCustomCommand,
    argument: str,
) -> str:
    template = frontmatter_body(command.template).strip()
    rendered = template.replace("$ARGUMENTS", argument)
    rendered = rendered.replace("{{arguments}}", argument)
    rendered = rendered.replace("{{ args }}", argument)
    if argument and rendered == template:
        rendered = f"{rendered}\n\nArguments:\n{argument}"
    return (
        f"PatchSmith custom command /{command.name}\n"
        f"Source: {command.path}\n\n"
        f"{rendered.strip()}"
    ).rstrip()


def format_custom_commands(commands: list[AgentCustomCommand]) -> str:
    if not commands:
        return "No project custom commands found."
    lines = ["Project custom commands:"]
    for command in commands:
        label = f"- /{command.name}"
        if command.description:
            label = f"{label} - {command.description}"
        if command.argument_hint:
            label = f"{label} [{command.argument_hint}]"
        lines.append(f"{label} ({command.path})")
    return "\n".join(lines)


def custom_commands_payload(commands: list[AgentCustomCommand]) -> list[dict[str, object]]:
    return [command.to_dict() for command in commands]


def _load_command_from_path(*, name: str, path: Path) -> AgentCustomCommand:
    template = path.read_text(encoding="utf-8")
    return AgentCustomCommand(
        name=name,
        path=path,
        template=template,
        metadata=frontmatter_metadata(template),
    )


def _command_dir(repo: str) -> Path | None:
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir():
        return None
    command_dir = repo_path / CUSTOM_COMMAND_ROOT
    if not command_dir.is_dir():
        return None
    return command_dir


def _command_name_from_path(command_dir: Path, path: Path) -> str:
    relative = path.relative_to(command_dir).with_suffix("")
    return ":".join(relative.parts)


def _valid_command_name(name: str) -> bool:
    return bool(_COMMAND_NAME_PATTERN.fullmatch(name))

