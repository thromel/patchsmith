from __future__ import annotations

import difflib
import io
import token
import tokenize
from dataclasses import dataclass
from pathlib import Path

from patchsmith.python_patch_safety import (
    introduced_duplicate_python_import_names,
    introduced_unbound_python_names,
    introduced_unknown_private_self_attribute_loads,
    introduced_unknown_private_self_method_calls,
    removed_imported_python_names_still_used,
    removed_module_bound_python_names_still_used,
)
from patchsmith.text_spans import nearest_source_span


@dataclass(frozen=True)
class TextEditResult:
    path: str
    before: str
    after: str
    diff: str
    replacement_strategy: str = "exact"
    replacement_similarity: float | None = None


class PatchSafetyError(RuntimeError):
    pass


def apply_text_replacement(
    *,
    repo_path: Path,
    relative_path: str,
    old: str,
    new: str,
    reject_comment_only: bool = False,
    reject_python_syntax_errors: bool = False,
    reject_python_unbound_names: bool = False,
    allow_nearest_match: bool = False,
    nearest_match_min_similarity: float = 0.9,
) -> TextEditResult:
    target = validate_repo_relative_path(repo_path=repo_path, relative_path=relative_path)
    before = target.read_text(encoding="utf-8")
    replacement_offset = before.find(old)
    replacement_removed_length = len(old)
    replacement_strategy = "exact"
    replacement_similarity: float | None = None
    if replacement_offset < 0:
        nearest_match = (
            nearest_source_span(
                before,
                old,
                min_similarity=nearest_match_min_similarity,
            )
            if allow_nearest_match
            else None
        )
        if nearest_match is None:
            raise PatchSafetyError(f"replacement text not found in {relative_path}")
        replacement_offset = nearest_match.start_offset
        replacement_removed_length = nearest_match.end_offset - nearest_match.start_offset
        replacement_strategy = "nearest_source_span"
        replacement_similarity = nearest_match.similarity
    after = (
        before[:replacement_offset]
        + new
        + before[replacement_offset + replacement_removed_length :]
    )
    if reject_comment_only and is_comment_or_whitespace_only_edit(
        relative_path=relative_path,
        before=before,
        after=after,
    ):
        raise PatchSafetyError(
            f"replacement changes only comments or whitespace in {relative_path}"
        )
    if reject_python_syntax_errors and relative_path.endswith(".py"):
        _raise_for_dangling_python_compound_span(
            relative_path=relative_path,
            old=old,
            new=new,
        )
        _raise_for_python_syntax_error(relative_path=relative_path, content=after)
    if reject_python_unbound_names and relative_path.endswith(".py"):
        _raise_for_python_unbound_names(
            relative_path=relative_path,
            before=before,
            content=after,
            replacement_offset=replacement_offset,
            removed_length=replacement_removed_length,
            replacement_length=len(new),
        )
    target.write_text(after, encoding="utf-8")
    return TextEditResult(
        path=relative_path,
        before=before,
        after=after,
        diff=unified_diff(relative_path=relative_path, before=before, after=after),
        replacement_strategy=replacement_strategy,
        replacement_similarity=replacement_similarity,
    )


def validate_repo_relative_path(*, repo_path: Path, relative_path: str) -> Path:
    if relative_path.startswith(("/", "../")) or "/../" in relative_path:
        raise PatchSafetyError(f"unsafe relative path: {relative_path}")
    target = (repo_path / relative_path).resolve()
    try:
        target.relative_to(repo_path.resolve())
    except ValueError as error:
        raise PatchSafetyError(f"path escapes repository: {relative_path}") from error
    if not target.exists():
        raise PatchSafetyError(f"path does not exist: {relative_path}")
    if not target.is_file():
        raise PatchSafetyError(f"path is not a file: {relative_path}")
    return target


def is_comment_or_whitespace_only_edit(
    *,
    relative_path: str,
    before: str,
    after: str,
) -> bool:
    if before == after:
        return True
    if not relative_path.endswith(".py"):
        return False
    before_tokens = _python_semantic_tokens(before)
    after_tokens = _python_semantic_tokens(after)
    if before_tokens is None or after_tokens is None:
        return False
    return before_tokens == after_tokens


def unified_diff(*, relative_path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )


def _python_semantic_tokens(source: str) -> list[tuple[int, str]] | None:
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return [
            (item.type, item.string)
            for item in tokens
            if item.type
            not in {
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                token.ENDMARKER,
            }
        ]
    except (IndentationError, SyntaxError, tokenize.TokenError):
        return None


def _raise_for_python_syntax_error(*, relative_path: str, content: str) -> None:
    try:
        compile(content, relative_path, "exec")
    except SyntaxError as error:
        location = f"line {error.lineno}" if error.lineno is not None else "unknown line"
        raise PatchSafetyError(
            f"replacement makes {relative_path} fail Python compilation: "
            f"{type(error).__name__} at {location}: {error.msg}"
        ) from error


def _raise_for_dangling_python_compound_span(
    *,
    relative_path: str,
    old: str,
    new: str,
) -> None:
    old_last = _last_nonempty_line(old)
    new_last = _last_nonempty_line(new)
    if old_last is None or new_last is None:
        return
    if not old_last.rstrip().endswith(":"):
        return
    if new_last.rstrip().endswith(":"):
        return
    header = old_last.strip()
    if not _looks_like_python_compound_header(header):
        return
    raise PatchSafetyError(
        f"replacement old span for {relative_path} ends on Python compound "
        f"statement without its body: `{_shorten_for_error(header)}`. Include "
        "the complete block in old/new, or replace only the header with another "
        "header that keeps the existing body."
    )


def _last_nonempty_line(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line
    return None


def _looks_like_python_compound_header(line: str) -> bool:
    prefixes = (
        "if ",
        "elif ",
        "else:",
        "for ",
        "async for ",
        "while ",
        "try:",
        "except ",
        "finally:",
        "with ",
        "async with ",
        "def ",
        "async def ",
        "class ",
        "match ",
        "case ",
    )
    return line.startswith(prefixes)


def _shorten_for_error(text: str, *, limit: int = 100) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _raise_for_python_unbound_names(
    *,
    relative_path: str,
    before: str,
    content: str,
    replacement_offset: int,
    removed_length: int,
    replacement_length: int,
) -> None:
    introduced_names = introduced_unbound_python_names(
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        replacement_length=replacement_length,
    )
    removed_import_names = removed_imported_python_names_still_used(
        source_before_replacement=before,
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        removed_length=removed_length,
    )
    removed_module_names = removed_module_bound_python_names_still_used(
        source_before_replacement=before,
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        removed_length=removed_length,
    )
    duplicate_import_names = introduced_duplicate_python_import_names(
        source_before_replacement=before,
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        removed_length=removed_length,
        replacement_length=replacement_length,
    )
    unknown_private_methods = introduced_unknown_private_self_method_calls(
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        replacement_length=replacement_length,
    )
    unknown_private_attributes = introduced_unknown_private_self_attribute_loads(
        source_after_replacement=content,
        replacement_offset=replacement_offset,
        replacement_length=replacement_length,
    )
    names = tuple(
        sorted(
            {
                *introduced_names,
                *removed_import_names,
                *removed_module_names,
                *duplicate_import_names,
                *unknown_private_methods,
                *unknown_private_attributes,
            }
        )
    )
    if not names:
        return
    formatted = ", ".join(f"`{name}`" for name in names)
    raise PatchSafetyError(
        f"replacement introduces potentially unbound Python name(s) in "
        f"{relative_path}: {formatted}"
    )
