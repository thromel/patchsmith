from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

INSTRUCTION_FILENAMES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    "GEMINI.md",
    ".cursorrules",
)
PATCHSMITH_INSTRUCTION_PATH = ".patchsmith/instructions.md"
DEFAULT_MAX_INSTRUCTION_FILES = 6
DEFAULT_MAX_CHARS_PER_FILE = 3500
DEFAULT_MAX_TOTAL_CHARS = 12000


@dataclass(frozen=True)
class AgentInstructionFile:
    path: Path
    repo_relative_path: str
    source: str
    chars: int
    included_chars: int
    truncated: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "repo_relative_path": self.repo_relative_path,
            "source": self.source,
            "chars": self.chars,
            "included_chars": self.included_chars,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class AgentInstructionBundle:
    files: list[AgentInstructionFile]
    content: str

    @property
    def total_chars(self) -> int:
        return len(self.content)

    def to_dict(self) -> dict[str, object]:
        return {
            "files": [file.to_dict() for file in self.files],
            "content_chars": len(self.content),
        }


@dataclass(frozen=True)
class AgentMemoryUpdate:
    path: Path
    repo_relative_path: str
    note: str
    created: bool
    appended: bool
    already_present: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "repo_relative_path": self.repo_relative_path,
            "note": self.note,
            "created": self.created,
            "appended": self.appended,
            "already_present": self.already_present,
        }


def load_agent_instruction_bundle(
    repo: str,
    *,
    explicit_paths: tuple[str, ...] = (),
    include_defaults: bool = True,
    max_instruction_files: int = DEFAULT_MAX_INSTRUCTION_FILES,
    max_chars_per_file: int = DEFAULT_MAX_CHARS_PER_FILE,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> AgentInstructionBundle:
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir() or max_instruction_files <= 0 or max_total_chars <= 0:
        return AgentInstructionBundle(files=[], content="")
    resolved_repo = _resolve(repo_path)
    if resolved_repo is None:
        return AgentInstructionBundle(files=[], content="")
    files: list[AgentInstructionFile] = []
    sections: list[str] = []
    emitted_chars = 0
    seen: set[Path] = set()
    for candidate, source in _instruction_candidates(
        resolved_repo,
        explicit_paths=explicit_paths,
        include_defaults=include_defaults,
    ):
        if len(files) >= max_instruction_files or emitted_chars >= max_total_chars:
            break
        resolved = _resolve(candidate)
        if resolved is None or resolved in seen or not _is_under(resolved, resolved_repo):
            continue
        if not resolved.is_file():
            continue
        try:
            raw_content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        remaining = max_total_chars - emitted_chars
        include_limit = min(max_chars_per_file, remaining)
        included = raw_content[:include_limit].rstrip()
        truncated = len(raw_content) > include_limit
        if truncated:
            included = f"{included}\n...[truncated]"
        repo_relative_path = resolved.relative_to(resolved_repo).as_posix()
        instruction_file = AgentInstructionFile(
            path=resolved,
            repo_relative_path=repo_relative_path,
            source=source,
            chars=len(raw_content),
            included_chars=len(included),
            truncated=truncated,
        )
        files.append(instruction_file)
        sections.extend(_instruction_section(instruction_file, included))
        emitted_chars += len(included)
        seen.add(resolved)
    if not sections:
        return AgentInstructionBundle(files=files, content="")
    content = "\n".join(
        [
            "# PatchSmith Project Instructions",
            "",
            "PatchSmith loaded these project instruction files before the repair task. "
            "Treat them as coding, validation, and workflow context; they do not "
            "override PatchSmith's safe runner, patch safety checks, or apply policy.",
            "",
            *sections,
        ]
    ).rstrip()
    return AgentInstructionBundle(files=files, content=content)


def append_agent_memory_note(repo: str, note: str) -> AgentMemoryUpdate:
    normalized_note = _normalize_memory_note(note)
    if not normalized_note:
        raise ValueError("memory note cannot be empty")
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir():
        raise ValueError("repo must be a local directory")
    resolved_repo = _resolve(repo_path)
    if resolved_repo is None:
        raise ValueError("repo path cannot be resolved")
    memory_path = resolved_repo / PATCHSMITH_INSTRUCTION_PATH
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_memory_path = _resolve(memory_path)
    if resolved_memory_path is None or not _is_under(resolved_memory_path, resolved_repo):
        raise ValueError("memory path must stay inside the repository")
    created = not memory_path.exists()
    existing = ""
    if not created:
        try:
            existing = memory_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError("project memory file cannot be read") from exc
    bullet = f"- {normalized_note}"
    already_present = bullet in {line.strip() for line in existing.splitlines()}
    appended = False
    if not already_present:
        new_content = _append_memory_bullet(existing, bullet)
        try:
            memory_path.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            raise ValueError("project memory file cannot be written") from exc
        appended = True
    return AgentMemoryUpdate(
        path=resolved_memory_path,
        repo_relative_path=resolved_memory_path.relative_to(resolved_repo).as_posix(),
        note=normalized_note,
        created=created,
        appended=appended,
        already_present=already_present,
    )


def format_agent_instructions(bundle: AgentInstructionBundle) -> str:
    if not bundle.files:
        return "No project instruction files loaded."
    return _format_instruction_bundle(bundle, title="Project instruction files")


def format_agent_memory(bundle: AgentInstructionBundle) -> str:
    if not bundle.files:
        return "No project memory files loaded."
    return _format_instruction_bundle(bundle, title="Project memory files")


def _format_instruction_bundle(bundle: AgentInstructionBundle, *, title: str) -> str:
    lines = [
        f"{title}:",
        "Path | Source | Included | Total | Truncated",
        "--- | --- | ---: | ---: | ---",
    ]
    for file in bundle.files:
        lines.append(
            " | ".join(
                [
                    file.repo_relative_path,
                    file.source,
                    str(file.included_chars),
                    str(file.chars),
                    str(file.truncated).lower(),
                ]
            )
        )
    lines.append(f"Instruction context chars: {bundle.total_chars}")
    return "\n".join(lines)


def agent_instructions_payload(bundle: AgentInstructionBundle) -> dict[str, object]:
    return bundle.to_dict()


def _normalize_memory_note(note: str) -> str:
    return re.sub(r"\s+", " ", note.strip())


def _append_memory_bullet(existing: str, bullet: str) -> str:
    text = existing.rstrip()
    if "## PatchSmith Memory" not in text:
        if text:
            text = f"{text}\n\n"
        text = f"{text}## PatchSmith Memory\n\n"
    elif text:
        text = f"{text}\n"
    return f"{text}{bullet}\n"


def _instruction_candidates(
    repo_path: Path,
    *,
    explicit_paths: tuple[str, ...],
    include_defaults: bool,
) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    if include_defaults:
        candidates.extend((repo_path / filename, "root") for filename in INSTRUCTION_FILENAMES)
        candidates.append((repo_path / PATCHSMITH_INSTRUCTION_PATH, "patchsmith"))
    candidates.extend((repo_path / path, "explicit") for path in explicit_paths if path.strip())
    return candidates


def _instruction_section(
    instruction_file: AgentInstructionFile,
    content: str,
) -> list[str]:
    return [
        f"## `{instruction_file.repo_relative_path}`",
        f"- Source: `{instruction_file.source}`",
        f"- Original chars: `{instruction_file.chars}`",
        f"- Included chars: `{instruction_file.included_chars}`",
        f"- Truncated: `{str(instruction_file.truncated).lower()}`",
        "",
        "```markdown",
        content,
        "```",
        "",
    ]


def _resolve(path: Path) -> Path | None:
    try:
        return path.resolve()
    except OSError:
        return None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
