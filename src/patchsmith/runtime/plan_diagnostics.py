from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from patchsmith.patching import PatchSafetyError, validate_repo_relative_path
from patchsmith.planning import RepairPlan
from patchsmith.text_spans import nearest_source_span

_PREVIEW_CHARS = 160


def repair_plan_diagnostics(
    plan: RepairPlan,
    *,
    repo_path: Path | None = None,
) -> dict[str, Any]:
    """Return bounded diagnostics for a repair plan without dumping full source text."""

    diagnostics: dict[str, Any] = {
        "name": plan.name,
        "path": plan.path,
        "old": _text_diagnostics(plan.old),
        "new": _text_diagnostics(plan.new),
    }
    if repo_path is None:
        return diagnostics

    try:
        target = validate_repo_relative_path(repo_path=repo_path, relative_path=plan.path)
        before = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, PatchSafetyError) as error:
        diagnostics["target_read_error"] = str(error)
        return diagnostics

    diagnostics["target_char_count"] = len(before)
    old_occurrences = before.count(plan.old) if plan.old else 0
    diagnostics["old_found"] = old_occurrences > 0
    diagnostics["old_occurrences"] = old_occurrences
    if old_occurrences == 0 and plan.old.strip():
        nearest_span = nearest_source_span(before, plan.old)
        if nearest_span:
            diagnostics["nearest_source_excerpt"] = nearest_span.to_diagnostics()
    return diagnostics


def _text_diagnostics(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    return {
        "line_count": len(lines),
        "char_count": len(text),
        "sha256_12": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
        "first_line_preview": _preview(lines[0] if lines else ""),
        "last_line_preview": _preview(lines[-1] if lines else ""),
    }


def _preview(text: str) -> str:
    compact = " ".join(text.replace("\t", " ").split())
    if len(compact) <= _PREVIEW_CHARS:
        return compact
    return f"{compact[: _PREVIEW_CHARS - 1]}..."
