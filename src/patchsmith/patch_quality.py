"""Patch maintainability and overfit-risk assessment."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from patchsmith.planning import RepairPlan


@dataclass(frozen=True)
class PatchQualityFinding:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PatchQualityAssessment:
    severity: str
    score: int
    findings: tuple[PatchQualityFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    @property
    def risk_notes(self) -> list[str]:
        if not self.findings:
            return ["Patch quality risk: low."]
        return [
            f"Patch quality risk: {self.severity} ({finding.code}: {finding.message})"
            for finding in self.findings
        ]


def assess_patch_quality(plan: RepairPlan) -> PatchQualityAssessment:
    findings: list[PatchQualityFinding] = []
    findings.extend(_patch_size_findings(plan))
    findings.extend(_path_findings(plan.path))
    findings.extend(_python_findings(plan))
    return _quality_assessment(findings)


def assess_diff_quality(diff: str) -> PatchQualityAssessment:
    removed_text = "\n".join(_diff_removed_lines(diff))
    added_text = "\n".join(_diff_added_lines(diff))
    paths = _diff_paths(diff)
    findings: list[PatchQualityFinding] = []
    findings.extend(_patch_size_text_findings(old=removed_text, new=added_text))
    for path in paths:
        findings.extend(_path_findings(path))
    if any(path.endswith(".py") for path in paths):
        findings.extend(_python_text_findings(old=removed_text, new=added_text))
    return _quality_assessment(findings)


def _quality_assessment(
    findings: list[PatchQualityFinding],
) -> PatchQualityAssessment:
    score = sum(_severity_weight(finding.severity) for finding in findings)
    return PatchQualityAssessment(
        severity=_overall_severity(findings),
        score=score,
        findings=tuple(findings),
    )


def patch_quality_severity_from_runtime_trace(
    runtime_trace: Iterable[Mapping[str, Any]],
) -> str | None:
    events = list(runtime_trace)
    for event in reversed(events):
        quality = event.get("quality")
        if not isinstance(quality, Mapping):
            continue
        severity = quality.get("severity")
        if isinstance(severity, str) and severity:
            return severity
    return None


def _patch_size_findings(plan: RepairPlan) -> list[PatchQualityFinding]:
    return _patch_size_text_findings(old=plan.old, new=plan.new)


def _patch_size_text_findings(*, old: str, new: str) -> list[PatchQualityFinding]:
    old_lines = _nonempty_line_count(old)
    new_lines = _nonempty_line_count(new)
    added_lines = max(0, new_lines - old_lines)
    if added_lines >= 35:
        return [
            PatchQualityFinding(
                code="large_replacement",
                severity="high",
                message=(
                    f"replacement adds {added_lines} non-empty lines; focused validation "
                    "may not cover the expanded behavior"
                ),
            )
        ]
    if added_lines >= 15:
        return [
            PatchQualityFinding(
                code="moderate_replacement",
                severity="medium",
                message=f"replacement adds {added_lines} non-empty lines",
            )
        ]
    if old_lines and new_lines >= old_lines * 5 and added_lines >= 8:
        return [
            PatchQualityFinding(
                code="expanding_small_span",
                severity="medium",
                message="small old span expands into a much larger implementation block",
            )
        ]
    return []


def _path_findings(path: str) -> list[PatchQualityFinding]:
    normalized = path.strip().lstrip("/").lower()
    if normalized.startswith(("test/", "tests/", "testing/")):
        return [
            PatchQualityFinding(
                code="test_target_patch",
                severity="high",
                message="patch edits a test or fixture path instead of production source",
            )
        ]
    if normalized.startswith(("doc/", "docs/", "examples/", "example/")):
        return [
            PatchQualityFinding(
                code="non_source_patch",
                severity="medium",
                message="patch edits documentation or example content",
            )
        ]
    return []


def _python_findings(plan: RepairPlan) -> list[PatchQualityFinding]:
    if not plan.path.endswith(".py"):
        return []
    return _python_text_findings(old=plan.old, new=plan.new)


def _python_text_findings(*, old: str, new: str) -> list[PatchQualityFinding]:
    findings: list[PatchQualityFinding] = []
    implementation_changed = _python_implementation_changed(old=old, new=new)
    findings.extend(
        _documentation_semantic_regression_findings(
            old=old,
            new=new,
            implementation_changed=implementation_changed,
        )
    )
    if _broad_exception_swallow_count(new) > _broad_exception_swallow_count(old):
        findings.append(
            PatchQualityFinding(
                code="broad_exception_swallow",
                severity="high",
                message="patch catches broad exceptions and suppresses them",
            )
        )
    if "__code__" in new:
        findings.append(
            PatchQualityFinding(
                code="code_object_mutation",
                severity="high",
                message="patch mutates Python function code objects at runtime",
            )
        )
    if _manually_rebuilds_code_type(new):
        findings.append(
            PatchQualityFinding(
                code="manual_code_type_rebuild",
                severity="high",
                message="patch manually rebuilds Python CodeType objects",
            )
        )
    if _rewrites_filename_metadata(new):
        findings.append(
            PatchQualityFinding(
                code="filename_metadata_rewrite",
                severity="medium",
                message="patch rewrites code-object filename metadata",
            )
        )
    if _rewrites_module_file_metadata(new):
        findings.append(
            PatchQualityFinding(
                code="module_file_metadata_rewrite",
                severity="medium",
                message="patch rewrites module __file__ metadata",
            )
        )
    if _adds_naked_import_cache_invalidation(old=old, new=new):
        findings.append(
            PatchQualityFinding(
                code="naked_import_cache_invalidation",
                severity="medium",
                message="patch only invalidates importlib caches without fixing the controlling read path",
            )
        )
    if _contains_constant_boolean_branch(new):
        findings.append(
            PatchQualityFinding(
                code="constant_boolean_branch",
                severity="high",
                message="patch introduces an always-true or always-false branch marker",
            )
        )
    if _adds_source_text_recompile(old=old, new=new):
        findings.append(
            PatchQualityFinding(
                code="source_text_recompile",
                severity="high",
                message="patch recompiles source text directly instead of repairing the cache decision",
            )
        )
    if _contains_best_effort_language(new):
        findings.append(
            PatchQualityFinding(
                code="best_effort_fallback",
                severity="medium",
                message="patch includes best-effort fallback behavior",
            )
        )
    return findings


def _documentation_semantic_regression_findings(
    *,
    old: str,
    new: str,
    implementation_changed: bool,
) -> list[PatchQualityFinding]:
    old_terms = _documentation_terms(old)
    if not old_terms:
        return []
    new_terms = _documentation_terms(new)
    if not new_terms:
        return []
    missing_terms = sorted(term for term in old_terms if term not in new_terms)
    if len(missing_terms) < 2:
        return []
    if len(missing_terms) / len(old_terms) < 0.3:
        return []
    severity = "medium" if implementation_changed else "high"
    scope = (
        "implementation replacement" if implementation_changed else "documentation-only replacement"
    )
    return [
        PatchQualityFinding(
            code="documentation_semantic_regression",
            severity=severity,
            message=(
                f"{scope} drops existing distinctive documentation terms: "
                + ", ".join(missing_terms[:5])
            ),
        )
    ]


def _python_implementation_changed(*, old: str, new: str) -> bool:
    old_lines = _python_implementation_lines(old)
    new_lines = _python_implementation_lines(new)
    return bool(old_lines or new_lines) and old_lines != new_lines


def _python_implementation_lines(text: str) -> list[str]:
    lines: list[str] = []
    active_quote: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if active_quote is not None:
            if active_quote in stripped:
                active_quote = None
            continue
        if stripped.startswith("#"):
            continue
        quote = _opening_triple_string_quote(stripped)
        if quote is not None:
            if stripped.count(quote) == 1:
                active_quote = quote
            continue
        lines.append(_strip_inline_comment(stripped))
    return lines


def _opening_triple_string_quote(line: str) -> str | None:
    match = re.match(r"^[rRuUbBfF]*(?P<quote>\"\"\"|''')", line)
    if match is None:
        return None
    return match.group("quote")


def _strip_inline_comment(line: str) -> str:
    code, _separator, _comment = line.partition("#")
    return code.rstrip()


def _documentation_terms(text: str) -> set[str]:
    fragments = _documentation_fragments(text)
    if not fragments:
        return set()
    terms: set[str] = set()
    for fragment in fragments:
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]+", fragment.lower()):
            if len(term) < 5 or term in _DOCUMENTATION_TERM_STOPWORDS:
                continue
            terms.add(term)
    return terms


def _documentation_fragments(text: str) -> list[str]:
    fragments = [
        match.group("body")
        for match in re.finditer(
            r'(?:"""|\'\'\')(?P<body>.*?)(?:"""|\'\'\')',
            text,
            flags=re.DOTALL,
        )
    ]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            fragments.append(stripped.lstrip("#").strip())
    return [fragment for fragment in fragments if fragment.strip()]


def _manually_rebuilds_code_type(text: str) -> bool:
    return re.search(r"\btypes\.CodeType\s*\(", text) is not None


def _rewrites_filename_metadata(text: str) -> bool:
    return re.search(r"\bco_filename\s*=", text) is not None


def _rewrites_module_file_metadata(text: str) -> bool:
    return re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\.__file__\s*=", text) is not None


def _adds_naked_import_cache_invalidation(*, old: str, new: str) -> bool:
    if "invalidate_caches" not in new:
        return False
    if _import_cache_invalidation_count(new) <= _import_cache_invalidation_count(old):
        return False
    added_lines = _added_stripped_lines(old=old, new=new)
    return bool(added_lines) and all(
        _is_import_cache_invalidation_line(line) for line in added_lines
    )


def _import_cache_invalidation_count(text: str) -> int:
    return len(re.findall(r"\binvalidate_caches\s*\(", text))


def _added_stripped_lines(*, old: str, new: str) -> list[str]:
    old_lines = {line.strip() for line in old.splitlines() if line.strip()}
    return [
        line.strip() for line in new.splitlines() if line.strip() and line.strip() not in old_lines
    ]


def _is_import_cache_invalidation_line(line: str) -> bool:
    if line in {"import importlib", "from importlib import invalidate_caches"}:
        return True
    return line in {
        "importlib.invalidate_caches()",
        "invalidate_caches()",
    }


def _contains_constant_boolean_branch(text: str) -> bool:
    return re.search(r"\bif\s+(?:True|False)\b", text) is not None


def _adds_source_text_recompile(*, old: str, new: str) -> bool:
    return _source_text_recompile_count(new) > _source_text_recompile_count(old)


def _source_text_recompile_count(text: str) -> int:
    return len(re.findall(r"\bcompile\s*\([\s\S]*?\.read_text\s*\(", text))


def _diff_added_lines(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++") or not line.startswith("+"):
            continue
        lines.append(line[1:])
    return lines


def _diff_removed_lines(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("---") or not line.startswith("-"):
            continue
        lines.append(line[1:])
    return lines


def _diff_paths(diff: str) -> list[str]:
    paths: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line.removeprefix("+++ b/").strip()
        if path:
            paths.append(path)
    return list(dict.fromkeys(paths))


def _broad_exception_swallow_count(text: str) -> int:
    count = 0
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not _is_broad_exception_handler(line):
            continue
        indent = len(line) - len(line.lstrip())
        if _handler_suppresses_exception(lines=lines, start_index=index, handler_indent=indent):
            count += 1
    return count


def _is_broad_exception_handler(line: str) -> bool:
    stripped = line.strip()
    if re.match(r"except\s*:", stripped):
        return True
    if re.match(
        r"except\s+(?:Exception|BaseException)(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?\s*:",
        stripped,
    ):
        return True
    return (
        re.match(
            r"except\s*\([^)]*\b(?:Exception|BaseException)\b[^)]*\)\s*:",
            stripped,
        )
        is not None
    )


def _handler_suppresses_exception(
    *,
    lines: list[str],
    start_index: int,
    handler_indent: int,
) -> bool:
    for body_line in lines[start_index + 1 : start_index + 10]:
        if not body_line.strip() or body_line.lstrip().startswith("#"):
            continue
        body_indent = len(body_line) - len(body_line.lstrip())
        if body_indent <= handler_indent:
            break
        stripped = body_line.strip()
        if stripped.startswith("raise"):
            return False
        if stripped == "pass" or stripped.startswith(("return", "continue", "break")):
            return True
    return False


def _contains_best_effort_language(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "best-effort",
            "best effort",
            "ignore any failure",
            "not critical",
            "fall back to",
        )
    )


def _nonempty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _severity_weight(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 4}.get(severity, 0)


def _overall_severity(findings: list[PatchQualityFinding]) -> str:
    severities = {finding.severity for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


_DOCUMENTATION_TERM_STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "before",
    "being",
    "could",
    "error",
    "errors",
    "exception",
    "raised",
    "raises",
    "return",
    "should",
    "their",
    "there",
    "these",
    "those",
    "while",
    "which",
    "would",
}
