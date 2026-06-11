"""Shared helpers for writing and loading artifact files.

These helpers centralize the JSON/CSV/Markdown artifact conventions used by the
evaluation, portfolio, and observability report writers.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def safe_artifact_name(value: str, *, lowercase: bool = False, fallback: str = "unknown") -> str:
    """Sanitize a value into a filesystem-safe artifact name."""
    if lowercase:
        value = value.lower()
    sanitized = "".join(character if character.isalnum() else "_" for character in value)
    sanitized = "_".join(part for part in sanitized.split("_") if part)
    return sanitized or fallback


def load_json(path: Path | None) -> Any:
    """Load a JSON artifact, returning None when missing or invalid."""
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def dict_or_empty(value: Any) -> dict[str, Any]:
    """Narrow an untyped JSON value to a dict, defaulting to empty."""
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: Any, *, trailing_newline: bool = False) -> None:
    """Write an indented JSON artifact."""
    text = json.dumps(payload, indent=2)
    if trailing_newline:
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    """Write a Markdown (or other text) artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(
    path: Path,
    *,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    """Write a CSV artifact; the header is omitted when fieldnames is empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


def format_cost(value: float | None) -> str:
    """Format a model-cost value for reports."""
    if value is None:
        return "n/a"
    if value == 0:
        return "$0.00"
    return f"${value:.6f}"
