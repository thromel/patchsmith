from __future__ import annotations

import difflib
import re

IMPORT_FAILURE_MARKERS = (
    "ImportError",
    "ModuleNotFoundError",
    "NameError",
)


def replacement_changes_only_python_imports(*, old: str, new: str) -> bool:
    changed_lines = _replacement_changed_lines(old=old, new=new)
    return bool(changed_lines) and all(_is_python_import_line(line) for line in changed_lines)


def diff_changes_only_python_imports(diff: str) -> bool:
    changed_lines: list[str] = []
    for raw_line in diff.splitlines():
        if raw_line.startswith(("+++", "---", "diff --git ", "@@ ")):
            continue
        if not raw_line.startswith(("+", "-")):
            continue
        stripped = raw_line[1:].strip()
        if stripped:
            changed_lines.append(stripped)
    return bool(changed_lines) and all(_is_python_import_line(line) for line in changed_lines)


def text_mentions_import_resolution_failure(text: str) -> bool:
    if any(marker in text for marker in IMPORT_FAILURE_MARKERS):
        return True
    lowered = text.lower()
    return bool(
        re.search(r"\bno module named\b", lowered)
        or re.search(r"\bname ['\"][A-Za-z_][A-Za-z0-9_]*['\"] is not defined\b", lowered)
    )


def _replacement_changed_lines(*, old: str, new: str) -> list[str]:
    lines: list[str] = []
    for raw_line in difflib.ndiff(old.splitlines(), new.splitlines()):
        if not raw_line.startswith(("- ", "+ ")):
            continue
        stripped = raw_line[2:].strip()
        if stripped:
            lines.append(stripped)
    return lines


def _is_python_import_line(line: str) -> bool:
    return line.startswith(("import ", "from "))
