"""Deterministic target localization for retry-time repair planning."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from patchsmith.models import RetrievedContext


@dataclass(frozen=True)
class TargetLocalizationCandidate:
    path: str
    score: float
    reasons: tuple[str, ...]
    historical: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def target_localization_candidates(
    *,
    issue_text: str,
    retrieved_context: list[RetrievedContext],
    historical_paths: Iterable[str] = (),
    limit: int = 5,
    include_historical: bool = False,
) -> list[TargetLocalizationCandidate]:
    historical = {
        path.strip().lstrip("/")
        for path in historical_paths
        if isinstance(path, str) and path.strip()
    }
    issue_tokens = _tokens(issue_text)
    import_cache_issue = _looks_like_python_import_cache_issue(issue_text, issue_tokens)
    stale_path_retry = _looks_like_stale_path_retry(issue_text)
    candidates: dict[str, TargetLocalizationCandidate] = {}
    for context in retrieved_context:
        path = context.path.strip().lstrip("/")
        if not path or not is_likely_source_target(path):
            continue
        is_historical = path in historical
        if is_historical and not include_historical:
            continue

        score, reasons = _score_context(
            issue_text=issue_text,
            issue_tokens=issue_tokens,
            import_cache_issue=import_cache_issue,
            stale_path_retry=stale_path_retry,
            context=context,
            path=path,
            historical=is_historical,
        )
        if score <= 0:
            continue
        candidate = TargetLocalizationCandidate(
            path=path,
            score=round(score, 3),
            reasons=tuple(reasons),
            historical=is_historical,
        )
        previous = candidates.get(path)
        if previous is None or candidate.score > previous.score:
            candidates[path] = candidate

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: (
            _candidate_rank_group(candidate),
            -candidate.score,
            candidate.path,
        ),
    )
    return ranked[: max(limit, 0)]


def is_likely_source_target(path: str) -> bool:
    lowered = path.lower()
    if lowered.startswith(
        (
            "doc/",
            "docs/",
            "test/",
            "tests/",
            "testing/",
            "examples/",
            "example/",
            "fixtures/",
            "evals/",
        )
    ):
        return False
    source_suffixes = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".kt",
        ".swift",
    )
    return lowered.endswith(source_suffixes)


def _score_context(
    *,
    issue_text: str,
    issue_tokens: set[str],
    import_cache_issue: bool,
    stale_path_retry: bool,
    context: RetrievedContext,
    path: str,
    historical: bool,
) -> tuple[float, list[str]]:
    score = min(max(context.score, 0.0), 40.0) * 0.15
    reasons: list[str] = []
    if score:
        reasons.append("retrieval_score")

    path_tokens = _tokens(path)
    path_matches = sorted(issue_tokens & path_tokens)
    if path_matches:
        score += 3.0 * len(path_matches)
        reasons.append("path_terms:" + ",".join(path_matches[:4]))

    matched_terms = {
        _normalize_token(term.removeprefix("symbol:"))
        for term in context.matched_terms
        if term.strip()
    }
    reviewed_source_hint = "reviewed_source_hint" in context.matched_terms
    reviewed_symbols = _symbol_terms(context.matched_terms)
    matched_terms.discard("")
    if reviewed_source_hint:
        score += 12.0
        reasons.append("reviewed_source_hint")
    if reviewed_source_hint and reviewed_symbols:
        score += 8.0 * min(len(reviewed_symbols), 3)
        reasons.append("reviewed_symbols:" + ",".join(reviewed_symbols[:4]))
    matched_issue_terms = sorted(issue_tokens & matched_terms)
    if matched_issue_terms:
        score += 2.0 * min(len(matched_issue_terms), 8)
        reasons.append("matched_terms:" + ",".join(matched_issue_terms[:4]))

    symbol_matches = _symbol_identifier_matches(issue_text, context.matched_terms)
    if symbol_matches:
        score += 18.0 * len(symbol_matches)
        reasons.append("symbol_identifiers:" + ",".join(symbol_matches[:4]))

    excerpt = context.excerpt
    exact_identifier_matches = _exact_identifier_matches(issue_text, excerpt)
    if exact_identifier_matches:
        score += 5.0 * min(len(exact_identifier_matches), 6)
        reasons.append("exact_identifiers:" + ",".join(exact_identifier_matches[:4]))

    if path.startswith(("src/", "lib/")):
        score += 4.0
        reasons.append("source_path")

    if import_cache_issue:
        cue_score, cue_reasons = _python_import_cache_score(path, excerpt)
        if cue_score:
            score += cue_score
            reasons.extend(cue_reasons)

    if stale_path_retry:
        cue_score, cue_reasons = _stale_path_control_point_score(path, excerpt)
        if cue_score:
            score += cue_score
            reasons.extend(cue_reasons)

    if historical:
        score -= 25.0
        reasons.append("historical_retry_penalty")

    return score, _dedupe_reasons(reasons)


def _looks_like_python_import_cache_issue(issue_text: str, issue_tokens: set[str]) -> bool:
    lowered = issue_text.lower()
    exact_cues = (
        "co_filename",
        "sys.modules",
        "__file__",
        "f_code",
        "importlib",
        "import_path",
        "module_name",
        "pyc",
    )
    if any(cue in lowered for cue in exact_cues):
        return True
    semantic_cues = {
        "cache",
        "cached",
        "compile",
        "filename",
        "import",
        "module",
        "moved",
        "path",
        "rename",
        "renamed",
        "stale",
    }
    return len(issue_tokens & semantic_cues) >= 2


def _looks_like_stale_path_retry(issue_text: str) -> bool:
    lowered = issue_text.lower()
    strong_cues = (
        "stale path mismatch",
        "reported the stale path mismatch",
        "directly returns the old path",
        "old and new filesystem paths",
        "only invalidated importlib caches",
        "do not keep adding cache side effects",
    )
    if any(cue in lowered for cue in strong_cues):
        return True
    stale_filename_cues = (
        "stale co_filename",
        "old co_filename",
        "stale path",
        "old path",
        "renamed path",
        "moved file",
        "moved test",
    )
    code_cache_cues = (
        "co_filename",
        "f_code",
        "pyc",
        "bytecode",
        "cache",
        "cached",
        "reuses",
    )
    if any(cue in lowered for cue in stale_filename_cues) and any(
        cue in lowered for cue in code_cache_cues
    ):
        return True
    return "co_filename" in lowered and "path:" in lowered and "retry" in lowered


def _python_import_cache_score(path: str, excerpt: str) -> tuple[float, list[str]]:
    haystack = f"{path}\n{excerpt}".lower()
    score = 0.0
    matched: list[str] = []
    for cue, weight in _PYTHON_IMPORT_CACHE_CUES:
        if cue.lower() in haystack:
            score += weight
            matched.append(cue)
    if not matched:
        return 0.0, []
    reason = "python_import_cache_cues:" + ",".join(matched[:6])
    return score, [reason]


def _stale_path_control_point_score(path: str, excerpt: str) -> tuple[float, list[str]]:
    haystack = f"{path}\n{excerpt}".lower()
    score = 0.0
    matched: list[str] = []
    if _looks_like_stale_code_object_control_point(path, excerpt):
        score += 36.0
        matched.append("stale_code_object_control_point")
    for cue, weight in _STALE_PATH_CONTROL_POINT_CUES:
        if cue.lower() in haystack:
            score += weight
            matched.append(cue)
    if _looks_like_generic_import_cache_branch(path, excerpt):
        score -= 20.0
        matched.append("generic_import_cache_branch_penalty")
    if _looks_like_late_cache_side_effect(path, excerpt):
        score -= 18.0
        matched.append("late_cache_side_effect_penalty")
    if not matched:
        return 0.0, []
    reason = "stale_path_control_point_cues:" + ",".join(matched[:6])
    return score, [reason]


def _looks_like_stale_code_object_control_point(path: str, excerpt: str) -> bool:
    haystack = f"{path}\n{excerpt}".lower()
    code_object_cues = (
        "_read_pyc",
        "marshal.load",
        "types.codetype",
        "co.co_filename",
        "compile(",
        "exec(",
    )
    return any(cue in haystack for cue in code_object_cues)


def _looks_like_generic_import_cache_branch(path: str, excerpt: str) -> bool:
    haystack = f"{path}\n{excerpt}".lower()
    generic_import_cues = (
        "import_path",
        "sys.modules",
        "module_name_from_path",
        "importlib.import_module",
    )
    if not any(cue in haystack for cue in generic_import_cues):
        return False
    control_cues = (
        "_read_pyc",
        "marshal.load",
        "types.codetype",
        "co.co_filename",
        "compile(",
        "exec(",
    )
    return not any(cue in haystack for cue in control_cues)


def _looks_like_late_cache_side_effect(path: str, excerpt: str) -> bool:
    haystack = f"{path}\n{excerpt}".lower()
    late_cues = (
        "invalidate_caches",
        "copy_example",
        "shutil.copy",
        "rename(",
    )
    control_cues = (
        "_read_pyc",
        "co_filename",
        "marshal.load",
        "compile(",
        "exec(",
        "sys.modules",
    )
    return any(cue in haystack for cue in late_cues) and not any(
        cue in haystack for cue in control_cues
    )


def _exact_identifier_matches(issue_text: str, excerpt: str) -> list[str]:
    excerpt_lowered = excerpt.lower()
    matches: list[str] = []
    for identifier in _identifiers(issue_text):
        if len(identifier) < 4:
            continue
        if identifier.lower() in excerpt_lowered:
            matches.append(identifier.lower())
    return sorted(dict.fromkeys(matches))


def _symbol_identifier_matches(issue_text: str, matched_terms: Iterable[str]) -> list[str]:
    issue_identifiers = {
        identifier.lower()
        for identifier in _identifiers(issue_text)
        if len(identifier) >= 4
    }
    matches: list[str] = []
    for term in matched_terms:
        if not term.startswith("symbol:"):
            continue
        symbol = term.removeprefix("symbol:").strip().lower()
        if symbol and symbol in issue_identifiers:
            matches.append(symbol)
    return sorted(dict.fromkeys(matches))


def _symbol_terms(matched_terms: Iterable[str]) -> list[str]:
    symbols: list[str] = []
    for term in matched_terms:
        if not term.startswith("symbol:"):
            continue
        symbol = term.removeprefix("symbol:").strip()
        if symbol:
            symbols.append(symbol)
    return sorted(dict.fromkeys(symbols))


def _tokens(text: str) -> set[str]:
    return {
        _normalize_token(token)
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+", text.lower())
        if _normalize_token(token)
    }


def _identifiers(text: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", text)


def _normalize_token(token: str) -> str:
    return token.strip().strip("`'\"").lower().replace("-", "_")


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    return list(dict.fromkeys(reason for reason in reasons if reason))


def _candidate_rank_group(candidate: TargetLocalizationCandidate) -> int:
    if is_revived_historical_control_point(candidate):
        return 0
    if not candidate.historical:
        return 1
    return 2


def is_revived_historical_control_point(candidate: TargetLocalizationCandidate) -> bool:
    if not candidate.historical:
        return False
    reasons = ";".join(candidate.reasons)
    if "stale_code_object_control_point" in reasons:
        return candidate.score >= 10.0
    if "reviewed_source_hint" in reasons and (
        "exact_identifiers" in reasons or "symbol_identifiers" in reasons
    ):
        return candidate.score > 0.0
    if "stale_path_control_point_cues" in reasons:
        if "generic_import_cache_branch_penalty" in reasons:
            return False
        return candidate.score >= 10.0
    return False


_PYTHON_IMPORT_CACHE_CUES: tuple[tuple[str, float], ...] = (
    ("sys.modules", 16.0),
    ("module_name_from_path", 14.0),
    ("module_name", 10.0),
    ("import_path", 10.0),
    ("importlib", 8.0),
    ("__file__", 8.0),
    ("co_filename", 8.0),
    ("_read_pyc", 6.0),
    ("_write_pyc", 5.0),
    ("compile", 5.0),
    ("cached", 4.0),
    ("cache", 4.0),
    ("exec", 3.0),
    ("f_code", 3.0),
)


_STALE_PATH_CONTROL_POINT_CUES: tuple[tuple[str, float], ...] = (
    ("_read_pyc", 28.0),
    ("co.co_filename", 22.0),
    ("co_filename", 18.0),
    ("marshal.load", 14.0),
    ("source_stat", 12.0),
    ("compile(", 12.0),
    ("exec(", 10.0),
    ("_write_pyc", 8.0),
    ("sys.modules", 8.0),
    ("pyc", 6.0),
)
