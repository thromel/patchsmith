"""Structured-output and target-policy validation for DeepAgents plans."""

from __future__ import annotations

import ast
import hashlib
import keyword
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from patchsmith.deepagents_files import _repo_path_from_agent_path
from patchsmith.deepagents_payloads import (
    _last_ai_text,
    _normalize_patch_payload,
    _structured_payload,
)
from patchsmith.models import RetrievedContext
from patchsmith.planning import (
    ModelCallMetadata,
    RepairPlan,
    _extract_json_object,
    _repair_plan_from_payload,
)


@dataclass(frozen=True)
class DeepAgentsPlanValidationResult:
    plan: RepairPlan | None
    metadata_update: dict[str, Any]


def validate_deepagents_plan_result(
    *,
    result: Any,
    files: dict[str, dict[str, str]],
    virtual_to_repo: dict[str, str],
    selected_context: list[RetrievedContext],
    deprioritized_paths: list[str],
    target_old_span_hashes: dict[str, list[str]],
    preferred_target_paths: list[str],
    preferred_target_symbols: Mapping[str, Iterable[str]],
    repo_path: Path | None,
    model_metadata: ModelCallMetadata,
    contract: dict[str, Any],
) -> DeepAgentsPlanValidationResult:
    payload = _structured_payload(result) or _extract_json_object(_last_ai_text(result))
    if payload is None:
        return DeepAgentsPlanValidationResult(plan=None, metadata_update={})
    path = payload.get("path")
    if isinstance(path, str):
        virtual_path = "/" + path.strip().lstrip("/")
        payload = _normalize_patch_payload({**payload, "path": virtual_path}, files)
        payload = {
            **payload,
            "path": _repo_path_from_agent_path(virtual_path, virtual_to_repo),
        }
    failure_localization = _failure_localization_metadata(payload)
    if failure_localization is None:
        return DeepAgentsPlanValidationResult(
            plan=None,
            metadata_update={
                "structured_output_error": {
                    "missing_required_fields": _missing_localization_fields(payload),
                },
            },
        )
    no_op_patch_violation = _no_op_patch_policy_violation(payload)
    if no_op_patch_violation is not None:
        return DeepAgentsPlanValidationResult(
            plan=None,
            metadata_update={"no_op_patch_violation": no_op_patch_violation},
        )
    target_history_violation = _target_history_violation(
        payload=payload,
        deprioritized_paths=deprioritized_paths,
        preferred_target_paths=preferred_target_paths,
        failure_localization=failure_localization,
        target_old_span_hashes=target_old_span_hashes,
    )
    if target_history_violation is not None:
        return DeepAgentsPlanValidationResult(
            plan=None,
            metadata_update={"target_history_violation": target_history_violation},
        )
    target_selection_violation = _target_selection_policy_violation(
        payload=payload,
        deprioritized_paths=deprioritized_paths,
        preferred_target_paths=preferred_target_paths,
        failure_localization=failure_localization,
    )
    if target_selection_violation is not None:
        return DeepAgentsPlanValidationResult(
            plan=None,
            metadata_update={"target_selection_violation": target_selection_violation},
        )
    target_symbol_violation = _target_symbol_policy_violation(
        payload=payload,
        repo_path=repo_path,
        preferred_target_symbols=preferred_target_symbols,
    )
    if target_symbol_violation is not None:
        return DeepAgentsPlanValidationResult(
            plan=None,
            metadata_update={"target_symbol_violation": target_symbol_violation},
        )
    return DeepAgentsPlanValidationResult(
        plan=_repair_plan_from_payload(
            payload=payload,
            allowed_paths={context.path for context in selected_context},
            default_name="deepagents_native_json_plan",
            model_metadata=model_metadata,
            extra_metadata={
                "deepagents_contract": contract,
                "failure_localization": failure_localization,
            },
        ),
        metadata_update={},
    )


def _failure_localization_metadata(payload: Mapping[str, Any]) -> dict[str, str] | None:
    failure_mechanism = _payload_string(payload, "failure_mechanism")
    target_rationale = _payload_string(payload, "target_rationale")
    if failure_mechanism is None or target_rationale is None:
        return None
    return {
        "failure_mechanism": failure_mechanism,
        "target_rationale": target_rationale,
    }


def _missing_localization_fields(payload: Mapping[str, Any]) -> list[str]:
    return [
        field
        for field in ("failure_mechanism", "target_rationale")
        if _payload_string(payload, field) is None
    ]


def _no_op_patch_policy_violation(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    old = _payload_string(payload, "old")
    new = _payload_string(payload, "new")
    if old is None or new is None:
        return None
    if _normalized_patch_payload_text(old) != _normalized_patch_payload_text(new):
        return None
    path = _payload_string(payload, "path") or ""
    return {
        "path": path.strip().lstrip("/"),
        "reason": "old and new replacement spans are identical after normalization",
        "required_patch_policy": (
            "new must make a concrete source-behavior change inside the selected "
            "control point; do not return an identical or comment-only replacement"
        ),
        "old_sha256_12": _sha256_12(old),
        "new_sha256_12": _sha256_12(new),
    }


def _normalized_patch_payload_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _target_history_violation(
    *,
    payload: Mapping[str, Any],
    deprioritized_paths: list[str],
    preferred_target_paths: list[str],
    failure_localization: Mapping[str, str],
    target_old_span_hashes: dict[str, list[str]],
) -> dict[str, Any] | None:
    path = _payload_string(payload, "path")
    if path is None:
        return None
    normalized_path = path.lstrip("/")
    normalized_deprioritized = {
        deprioritized_path.strip().lstrip("/")
        for deprioritized_path in deprioritized_paths
        if deprioritized_path.strip()
    }
    if normalized_path not in normalized_deprioritized:
        return None
    normalized_preferred = {
        preferred_path.strip().lstrip("/")
        for preferred_path in preferred_target_paths
        if preferred_path.strip()
    }
    target_rationale = failure_localization.get("target_rationale", "")
    old_span = _payload_string(payload, "old") or ""
    old_span_hash = _sha256_12(old_span)
    prior_old_span_hashes = target_old_span_hashes.get(normalized_path, [])
    if old_span_hash in prior_old_span_hashes:
        return {
            "path": normalized_path,
            "reason": (
                "selected historical target path reuses an old span already tried "
                "under the same unresolved failure"
            ),
            "required_evidence": (
                "choose a preferred untried source target, or use a different exact "
                "old span that controls a distinct branch, cache read, dispatch site, "
                "or call path"
            ),
            "deprioritized_paths": sorted(normalized_deprioritized),
            "preferred_target_paths": preferred_target_paths,
            "reused_old_span_sha256_12": old_span_hash,
        }
    if normalized_path in normalized_preferred:
        return None
    if _rationale_names_distinct_target_evidence(target_rationale, old_span):
        return None
    return {
        "path": normalized_path,
        "reason": (
            "selected target path was deprioritized by prior failed attempts without "
            "naming distinct branch or call-site evidence from the proposed old span"
        ),
        "required_evidence": (
            "target_rationale must explain the new branch, cache read, dispatch site, "
            "or call path inside this file and cite an exact identifier from the old span"
        ),
        "deprioritized_paths": sorted(normalized_deprioritized),
        "preferred_target_paths": preferred_target_paths,
    }


def _target_selection_policy_violation(
    *,
    payload: Mapping[str, Any],
    deprioritized_paths: list[str],
    preferred_target_paths: list[str],
    failure_localization: Mapping[str, str],
) -> dict[str, Any] | None:
    if not preferred_target_paths:
        return None
    path = _payload_string(payload, "path")
    if path is None:
        return None
    normalized_path = path.lstrip("/")
    normalized_preferred = {
        preferred_path.strip().lstrip("/")
        for preferred_path in preferred_target_paths
        if preferred_path.strip()
    }
    if normalized_path in normalized_preferred:
        return None
    normalized_deprioritized = {
        deprioritized_path.strip().lstrip("/")
        for deprioritized_path in deprioritized_paths
        if deprioritized_path.strip()
    }
    if normalized_path in normalized_deprioritized:
        target_rationale = failure_localization.get("target_rationale", "")
        old_span = _payload_string(payload, "old") or ""
        if _rationale_names_distinct_target_evidence(target_rationale, old_span):
            return None
    return {
        "path": normalized_path,
        "reason": "selected target path is outside the retry patchable path policy",
        "required_path_policy": (
            "path must be one of the preferred untried source targets unless a "
            "historical path cites explicit old-span evidence for a distinct control point"
        ),
        "preferred_target_paths": sorted(normalized_preferred),
        "deprioritized_paths": sorted(normalized_deprioritized),
    }


def _target_symbol_policy_violation(
    *,
    payload: Mapping[str, Any],
    repo_path: Path | None,
    preferred_target_symbols: Mapping[str, Iterable[str]],
) -> dict[str, Any] | None:
    path = _payload_string(payload, "path")
    if path is None:
        return None
    normalized_path = path.strip().lstrip("/")
    symbols = _ordered_unique_symbols(
        preferred_target_symbols.get(normalized_path, [])
    )
    if not symbols:
        return None
    old_span = _payload_string(payload, "old") or ""
    if any(_text_mentions_symbol(old_span, symbol) for symbol in symbols):
        return None
    if repo_path is None:
        return None
    if _old_span_is_inside_preferred_symbol(
        repo_path=repo_path,
        relative_path=normalized_path,
        old_span=old_span,
        preferred_symbols=symbols,
    ):
        return None
    return {
        "path": normalized_path,
        "reason": (
            "selected path matched the constrained patchable path policy, but the "
            "exact old span did not enter a preferred symbol for this run"
        ),
        "required_symbol_policy": (
            "old must include one of the preferred symbols unless PatchSmith is run "
            "without the constrained first-attempt symbol policy"
        ),
        "preferred_symbols": symbols,
    }


def _text_mentions_symbol(text: str, symbol: str) -> bool:
    base_symbol = symbol.rsplit(".", maxsplit=1)[-1].strip()
    if not base_symbol:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(base_symbol)}(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _old_span_is_inside_preferred_symbol(
    *,
    repo_path: Path,
    relative_path: str,
    old_span: str,
    preferred_symbols: Iterable[str],
) -> bool:
    if not old_span:
        return False
    try:
        target = (repo_path / relative_path).resolve()
        target.relative_to(repo_path.resolve())
        source = target.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    offset = source.find(old_span)
    if offset < 0:
        return False
    start_line = source.count("\n", 0, offset) + 1
    end_line = start_line + old_span.count("\n")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    preferred_bases = {
        symbol.rsplit(".", maxsplit=1)[-1].strip()
        for symbol in preferred_symbols
        if symbol.strip()
    }
    if not preferred_bases:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name not in preferred_bases:
            continue
        node_end = getattr(node, "end_lineno", None)
        if (
            node.lineno <= start_line
            and isinstance(node_end, int)
            and end_line <= node_end
        ):
            return True
    return False


def _rationale_names_distinct_target_evidence(rationale: str, old_span: str) -> bool:
    normalized = " ".join(rationale.lower().split())
    if not normalized:
        return False
    contrast_terms = (
        "different",
        "distinct",
        "new branch",
        "new call",
        "not exercised",
        "not previously",
        "previous attempt",
        "prior attempt",
        "previous edit",
        "prior edit",
        "untried",
    )
    control_terms = (
        "branch",
        "cache read",
        "cache write",
        "call path",
        "call site",
        "call-site",
        "dispatch site",
        "line ",
        "return path",
    )
    return (
        any(term in normalized for term in contrast_terms)
        and any(term in normalized for term in control_terms)
        and _rationale_cites_old_span_identifier(normalized, old_span)
    )


def _rationale_cites_old_span_identifier(
    normalized_rationale: str,
    old_span: str,
) -> bool:
    source_terms = _old_span_source_terms(old_span)
    if not source_terms:
        return _old_span_fragment_cited(normalized_rationale, old_span)
    return any(term in normalized_rationale for term in source_terms)


def _old_span_source_terms(old_span: str) -> list[str]:
    raw_terms = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?",
        old_span,
    )
    terms: list[str] = []
    for raw_term in raw_terms:
        term = raw_term.lower()
        if term in _SOURCE_EVIDENCE_STOPWORDS:
            continue
        if "." not in term and len(term) < 3:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _old_span_fragment_cited(normalized_rationale: str, old_span: str) -> bool:
    compact = " ".join(old_span.lower().split())
    if len(compact) < 8:
        return False
    return compact in normalized_rationale


_SOURCE_EVIDENCE_STOPWORDS = {
    *keyword.kwlist,
    "none",
    "true",
    "false",
    "self",
    "cls",
    "str",
    "int",
    "list",
    "dict",
    "set",
    "tuple",
    "return",
}


def _payload_string(payload: Mapping[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _sha256_12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _ordered_unique_symbols(symbols: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for symbol in symbols:
        stripped = symbol.strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)
    return ordered
