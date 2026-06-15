from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NearestSourceSpan:
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int
    similarity: float
    text: str

    def to_diagnostics(self, *, max_excerpt_chars: int = 1_200) -> dict[str, Any]:
        text = self.text
        if len(text) > max_excerpt_chars:
            text = text[: max_excerpt_chars - 15] + "...[truncated]"
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "similarity": round(self.similarity, 3),
            "text": text,
        }


def nearest_source_span(
    source: str,
    missing_old: str,
    *,
    min_similarity: float = 0.45,
) -> NearestSourceSpan | None:
    source_lines = source.splitlines(keepends=True)
    old_lines = missing_old.splitlines()
    if not source_lines or not old_lines:
        return None

    old_len = max(1, len(old_lines))
    window_lengths = [
        length for length in range(old_len - 2, old_len + 3) if 1 <= length <= len(source_lines)
    ]
    if not window_lengths:
        return None

    normalized_old = _normalize_for_similarity(missing_old)
    if not normalized_old:
        return None

    best_score = 0.0
    best_start = 0
    best_end = 0
    best_offset = 0
    line_offsets = _line_offsets(source_lines)
    for window_len in window_lengths:
        for start in range(len(source_lines) - window_len + 1):
            end = start + window_len
            candidate = "".join(source_lines[start:end])
            score = difflib.SequenceMatcher(
                None,
                normalized_old,
                _normalize_for_similarity(candidate),
            ).ratio()
            if score > best_score:
                best_score = score
                best_start = start
                best_end = end
                best_offset = line_offsets[start]

    if best_score < min_similarity:
        return None

    text = "".join(source_lines[best_start:best_end])
    end_offset = best_offset + len(text)
    text, end_offset = _without_final_line_ending(text, end_offset)
    return NearestSourceSpan(
        start_line=best_start + 1,
        end_line=best_end,
        start_offset=best_offset,
        end_offset=end_offset,
        similarity=best_score,
        text=text,
    )


def _line_offsets(lines: list[str]) -> list[int]:
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    return offsets


def _without_final_line_ending(text: str, end_offset: int) -> tuple[str, int]:
    if text.endswith("\r\n"):
        return text[:-2], end_offset - 2
    if text.endswith(("\n", "\r")):
        return text[:-1], end_offset - 1
    return text, end_offset


def _normalize_for_similarity(text: str) -> str:
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())
