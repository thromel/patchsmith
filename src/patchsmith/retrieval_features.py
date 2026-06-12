"""Shared token, path, and excerpt helpers for native retrieval."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from patchsmith.models import RepositoryIndex, RetrievedContext

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])((?:src|lib|tests|test)/[A-Za-z0-9_./-]+\.py)")
TRACEBACK_FILE_RE = re.compile(r'File ["\']([^"\']+\.py)["\'], line \d+', re.IGNORECASE)
STACK_FRAME_RE = re.compile(
    r'File ["\'][^"\']+\.py["\'], line \d+(?:, in ([A-Za-z_][A-Za-z0-9_]*))?',
    re.IGNORECASE,
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "returns",
    "that",
    "the",
    "to",
    "when",
    "with",
}
LOW_SIGNAL_EXCERPT_TERMS = STOPWORDS | {
    "__future__",
    "added",
    "already",
    "annotations",
    "assert",
    "assert_outcomes",
    "captured",
    "com",
    "command",
    "contains",
    "context",
    "dedent",
    "def",
    "doc",
    "encoding",
    "expected",
    "file",
    "files",
    "first",
    "fixture",
    "fixtures",
    "github",
    "https",
    "issue",
    "issues",
    "mkdir",
    "none",
    "not",
    "open",
    "passed",
    "public",
    "pytest",
    "python",
    "python3",
    "reference",
    "run",
    "runpytest",
    "second",
    "source",
    "src",
    "str",
    "test",
    "testing",
    "tests",
    "text",
    "textwrap",
    "this",
    "traceback",
    "type",
    "used",
    "utf",
    "validation",
    "write_text",
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def _token_counts(text: str) -> Counter[str]:
    return Counter(
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    )


def _path_terms(path: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9_]+|_", path)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def _path_hints(issue_text: str) -> set[str]:
    hints: set[str] = set()
    for match in PATH_RE.finditer(issue_text):
        hint = _normalize_path_hint(match.group(1))
        if hint:
            hints.add(hint)
    for match in TRACEBACK_FILE_RE.finditer(issue_text):
        normalized = _normalize_path_hint(match.group(1))
        if normalized:
            hints.add(normalized)
    return hints


def _normalize_path_hint(path: str) -> str:
    normalized = path.replace("\\", "/").strip().strip("\"'")
    for prefix in ("./", "/"):
        while normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    for marker in ("/src/", "/lib/", "/tests/", "/test/"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[1]
            normalized = marker.strip("/") + "/" + normalized
            break
    if not normalized.endswith(".py"):
        return ""
    return normalized


def _stack_symbols(issue_text: str) -> set[str]:
    symbols: set[str] = set()
    for line in issue_text.splitlines():
        match = STACK_FRAME_RE.search(line)
        if not match or not match.group(1):
            continue
        name = match.group(1).lower()
        symbols.add(name)
        symbols.update(part for part in name.split("_") if len(part) > 2)
    return symbols


def _path_hint_score(path: str, path_hints: set[str]) -> float:
    if not path_hints:
        return 0.0
    if path in path_hints:
        return 10_000.0
    filename = path.rsplit("/", 1)[-1]
    if filename in {hint.rsplit("/", 1)[-1] for hint in path_hints}:
        return 500.0
    if any(path.endswith(f"/{hint}") or hint.endswith(f"/{path}") for hint in path_hints):
        return 250.0
    return 0.0


def _add_graph_score(
    scored: dict[str, tuple[float, set[str]]],
    *,
    path: str,
    score: float,
    features: set[str],
) -> None:
    current_score, current_features = scored.get(path, (0.0, set()))
    scored[path] = (current_score + score, current_features | features)


def _graph_neighbor_boost(*, seed_context: RetrievedContext, neighbor_path: str) -> float:
    if _is_test_path(seed_context.path) and not _is_test_path(neighbor_path):
        return seed_context.score + 30.0
    if _is_test_path(neighbor_path):
        return 4.0
    return 10.0


def _repo_file_exists(repo_index: RepositoryIndex, path: str) -> bool:
    return any(file.path == path for file in repo_index.files)


def _excerpt_terms(features: set[str]) -> list[str]:
    terms: list[str] = []
    for feature in features:
        raw = feature.rsplit(":", 1)[-1]
        for term in raw.split("_"):
            if len(term) > 2 and "/" not in term:
                terms.append(term)
    return sorted(set(terms))


def _symbols(text: str, language: str) -> set[str]:
    if language != "Python":
        return set()
    symbols: set[str] = set()
    for match in re.finditer(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE):
        name = match.group(1).lower()
        symbols.add(name)
        symbols.update(part for part in name.split("_") if len(part) > 2)
    return symbols


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _path_prior(path: str) -> float:
    if path.startswith(("src/", "lib/", "patchsmith/")):
        return 1.5
    if path.startswith(("tests/", "test/")):
        return 0.5
    return 0.0


def _is_test_path(path: str) -> bool:
    return path.startswith(("tests/", "test/")) or "/test_" in path or path.endswith("_test.py")


def _excerpt(text: str, matched_terms: list[str], radius: int = 90) -> str:
    lines = text.splitlines()
    if not lines:
        return ""

    lowered_terms = _excerpt_search_terms(matched_terms)
    first_match = _best_excerpt_center(lines, lowered_terms)

    start = max(0, first_match - radius)
    end = min(len(lines), first_match + radius + 1)
    return "\n".join(f"{line_no + 1}: {lines[line_no]}" for line_no in range(start, end))


def _excerpt_search_terms(matched_terms: list[str]) -> tuple[str, ...]:
    terms = []
    for term in matched_terms:
        normalized = term.lower().rsplit(":", 1)[-1]
        if len(normalized) <= 2 or normalized in LOW_SIGNAL_EXCERPT_TERMS:
            continue
        terms.append(normalized)
        if "_" in normalized:
            terms.extend(
                part
                for part in normalized.split("_")
                if len(part) > 2 and part not in LOW_SIGNAL_EXCERPT_TERMS
            )
    if not terms:
        terms = [
            term.lower()
            for term in matched_terms
            if len(term) > 2 and term.lower() not in STOPWORDS
        ]
    return tuple(dict.fromkeys(terms))


def _best_excerpt_center(lines: list[str], lowered_terms: tuple[str, ...]) -> int:
    best_index = 0
    best_score = 0.0
    for index, line in enumerate(lines):
        score = _line_match_score(line, lowered_terms)
        if score > best_score:
            best_index = index
            best_score = score
    if best_score > 0:
        return best_index

    for index, line in enumerate(lines):
        lower_line = line.lower()
        if any(term in lower_line for term in lowered_terms):
            return index
    return 0


def _line_match_score(line: str, lowered_terms: tuple[str, ...]) -> float:
    lower_line = line.lower()
    score = 0.0
    for term in lowered_terms:
        if term not in lower_line:
            continue
        weight = 1.0
        if "_" in term:
            weight += 2.0
        if len(term) >= 8:
            weight += 1.0
        score += lower_line.count(term) * weight
    if score and re.match(r"\s*(?:async\s+def|def|class)\s+", line):
        score += 6.0
    if score and line[:1].isspace():
        score += 0.25
    return score
