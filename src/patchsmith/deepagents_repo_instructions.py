"""Scoped repository-instruction manifest rendering for DeepAgents runs."""

from __future__ import annotations

from pathlib import Path

from patchsmith.models import RetrievedContext

REPO_INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules")


def repo_instructions_manifest(
    repo_path: Path | None,
    selected_context: list[RetrievedContext],
    *,
    max_instruction_files: int = 5,
    max_chars_per_file: int = 3500,
    max_total_chars: int = 12_000,
) -> str | None:
    if repo_path is None or not selected_context or max_instruction_files <= 0:
        return None
    root = _resolved_repo_root(repo_path)
    if root is None:
        return None
    sections: list[str] = []
    emitted = 0
    emitted_chars = 0
    seen_paths: set[Path] = set()
    for scope_dir in _repo_instruction_scope_dirs(selected_context):
        for filename in REPO_INSTRUCTION_FILENAMES:
            if emitted >= max_instruction_files or emitted_chars >= max_total_chars:
                break
            candidate = _repo_instruction_candidate(root, scope_dir, filename)
            if candidate is None or candidate in seen_paths:
                continue
            content = _read_repo_instruction_file(candidate)
            if content is None:
                continue
            remaining_chars = max_total_chars - emitted_chars
            clipped = content[: min(max_chars_per_file, remaining_chars)].rstrip()
            if len(content) > len(clipped):
                clipped += "\n...[truncated]"
            instruction_path = candidate.relative_to(root).as_posix()
            scoped_paths = _scoped_instruction_paths(scope_dir, selected_context)
            sections.extend(
                [
                    f"## `{instruction_path}`",
                    f"- Scope directory: `{scope_dir or '.'}`",
                    "- Applies to mounted paths: "
                    + ", ".join(f"`{path}`" for path in scoped_paths),
                    "",
                    "```markdown",
                    clipped,
                    "```",
                    "",
                ]
            )
            emitted += 1
            emitted_chars += len(clipped)
            seen_paths.add(candidate)
        if emitted >= max_instruction_files or emitted_chars >= max_total_chars:
            break
    if not sections:
        return None
    return "\n".join(
        [
            "# PatchSmith Scoped Repository Instructions",
            "",
            "PatchSmith found AGENTS.md-style repository instruction files that apply "
            "to the mounted repair context. Treat them as scoped constraints, not as "
            "permission for broad repository exploration.",
            "",
            "Use only concrete coding, style, safety, and validation requirements that "
            "match the mounted paths below. If an instruction is generic or unrelated "
            "to the selected patch target, keep the repair bounded to the issue evidence.",
            "",
            *sections,
        ]
    ).rstrip()


def _resolved_repo_root(repo_path: Path) -> Path | None:
    try:
        root = repo_path.resolve()
    except OSError:
        return None
    return root if root.is_dir() else None


def _repo_instruction_scope_dirs(contexts: list[RetrievedContext]) -> list[str]:
    scope_dirs = [""]
    for context in contexts:
        normalized = context.path.replace("\\", "/").strip().lstrip("/")
        if not normalized or normalized.startswith("../"):
            continue
        parts = [part for part in normalized.split("/")[:-1] if part and part != "."]
        for index in range(1, len(parts) + 1):
            scope = "/".join(parts[:index])
            if scope not in scope_dirs:
                scope_dirs.append(scope)
    return scope_dirs


def _repo_instruction_candidate(
    root: Path,
    scope_dir: str,
    filename: str,
) -> Path | None:
    try:
        candidate = (root / scope_dir / filename).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _read_repo_instruction_file(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return content or None


def _scoped_instruction_paths(
    scope_dir: str,
    contexts: list[RetrievedContext],
) -> list[str]:
    normalized_scope = scope_dir.strip().strip("/")
    scoped_paths = []
    for context in contexts:
        normalized_path = context.path.replace("\\", "/").strip().lstrip("/")
        if not normalized_path:
            continue
        if not normalized_scope or normalized_path.startswith(f"{normalized_scope}/"):
            scoped_paths.append(normalized_path)
    return scoped_paths or ["all mounted paths"]
