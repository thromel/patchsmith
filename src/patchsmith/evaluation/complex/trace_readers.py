"""Trace readers for complex benchmark artifact extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import (
    _model_usage_from_trace,
    _patch_quality_from_trace,
    _trace_metrics_from_trace,
)
from patchsmith.patch_quality import assess_diff_quality


def trace_metrics(trace_path: str | None) -> dict[str, Any]:
    if not trace_path:
        return _empty_trace_metrics()
    path = Path(trace_path)
    if not path.is_file():
        return _empty_trace_metrics()
    return _trace_metrics_from_trace(path)


def model_usage(trace_path: str | None) -> dict[str, Any]:
    if not trace_path:
        return _empty_model_usage()
    path = Path(trace_path)
    if not path.is_file():
        return _empty_model_usage()
    return _model_usage_from_trace(path)


def deepagents_context_budget(trace_path: str | None) -> dict[str, Any]:
    if not trace_path:
        return _empty_deepagents_context_budget()
    path = Path(trace_path)
    if not path.is_file():
        return _empty_deepagents_context_budget()
    virtual_file_counts: list[int] = []
    max_context_files_values: list[int] = []
    context_budget_manifest_path: str | None = None
    context_budget_manifest_read_first = False
    repo_map_manifest_path: str | None = None
    repo_map_manifest_read_first = False
    repo_instructions_manifest_path: str | None = None
    repo_instructions_manifest_read_first = False
    acceptance_rubric_manifest_path: str | None = None
    acceptance_rubric_manifest_read_first = False
    repair_interface_manifest_path: str | None = None
    repair_interface_manifest_read_first = False
    resource_budgeted = False
    resource_budget_read_first = False
    resource_budget_max_model_responses: list[int] = []
    resource_budget_max_model_tokens: list[int] = []
    omitted_file_counts: list[int] = []
    omitted_paths: list[str] = []
    virtual_file_paths: list[str] = []
    for event in _trace_events(path):
        for metadata in _trace_metadata_values(event):
            contract = metadata.get("deepagents_contract")
            if not isinstance(contract, dict):
                continue
            _append_virtual_file_paths(
                virtual_file_paths,
                contract.get("virtual_file_paths"),
            )
            _append_optional_int(
                virtual_file_counts,
                contract.get("virtual_file_count"),
            )
            _append_optional_int(
                max_context_files_values,
                contract.get("max_context_files"),
            )
            manifest_path = _optional_str(contract.get("context_budget_manifest_path"))
            if manifest_path:
                context_budget_manifest_path = manifest_path
            repo_map_path = _optional_str(contract.get("repo_map_manifest_path"))
            if repo_map_path:
                repo_map_manifest_path = repo_map_path
            repo_instructions_path = _optional_str(contract.get("repo_instructions_manifest_path"))
            if repo_instructions_path:
                repo_instructions_manifest_path = repo_instructions_path
            acceptance_rubric_path = _optional_str(contract.get("acceptance_rubric_manifest_path"))
            if acceptance_rubric_path:
                acceptance_rubric_manifest_path = acceptance_rubric_path
            repair_interface_path = _optional_str(contract.get("repair_interface_manifest_path"))
            if repair_interface_path:
                repair_interface_manifest_path = repair_interface_path
            planning_policy = contract.get("planning_policy")
            if isinstance(planning_policy, dict):
                context_budget_manifest_read_first = context_budget_manifest_read_first or bool(
                    planning_policy.get("context_budget_manifest_read_first")
                )
                repo_map_manifest_read_first = repo_map_manifest_read_first or bool(
                    planning_policy.get("repo_map_manifest_read_first")
                )
                repo_instructions_manifest_read_first = (
                    repo_instructions_manifest_read_first
                    or bool(planning_policy.get("repo_instructions_manifest_read_first"))
                )
                acceptance_rubric_manifest_read_first = (
                    acceptance_rubric_manifest_read_first
                    or bool(planning_policy.get("acceptance_rubric_manifest_read_first"))
                )
                repair_interface_manifest_read_first = repair_interface_manifest_read_first or bool(
                    planning_policy.get("repair_interface_manifest_read_first")
                )
                resource_budget_read_first = resource_budget_read_first or bool(
                    planning_policy.get("resource_budget_read_first")
                )
            context_budget = contract.get("context_budget")
            if isinstance(context_budget, dict):
                _append_virtual_file_paths(
                    virtual_file_paths,
                    context_budget.get("mounted_paths"),
                )
                _append_optional_int(
                    omitted_file_counts,
                    context_budget.get("omitted_file_count"),
                )
                omitted_paths.extend(_string_tuple(context_budget.get("omitted_paths")))
            filesystem_policy = contract.get("filesystem_policy")
            if isinstance(filesystem_policy, dict):
                _append_virtual_context_paths_from_policy(
                    virtual_file_paths,
                    filesystem_policy.get("allowed_read_paths"),
                )
            resource_budget = contract.get("resource_budget")
            if isinstance(resource_budget, dict):
                resource_budgeted = resource_budgeted or bool(resource_budget)
                _append_optional_int(
                    resource_budget_max_model_responses,
                    resource_budget.get("max_model_responses"),
                )
                _append_optional_int(
                    resource_budget_max_model_tokens,
                    resource_budget.get("max_model_tokens"),
                )
    max_context_files = max(max_context_files_values) if max_context_files_values else None
    return {
        "deepagents_virtual_file_count": (
            max(virtual_file_counts) if virtual_file_counts else None
        ),
        "deepagents_virtual_file_paths": tuple(dict.fromkeys(virtual_file_paths)),
        "deepagents_max_context_files": max_context_files,
        "deepagents_context_budgeted": (max_context_files is not None and max_context_files > 0),
        "deepagents_context_budget_manifest_path": context_budget_manifest_path,
        "deepagents_context_budget_manifest_read_first": context_budget_manifest_read_first,
        "deepagents_context_budget_omitted_file_count": (
            max(omitted_file_counts) if omitted_file_counts else None
        ),
        "deepagents_context_budget_omitted_paths": tuple(dict.fromkeys(omitted_paths)),
        "deepagents_repo_map_manifest_path": repo_map_manifest_path,
        "deepagents_repo_map_manifest_read_first": repo_map_manifest_read_first,
        "deepagents_repo_instructions_manifest_path": (repo_instructions_manifest_path),
        "deepagents_repo_instructions_manifest_read_first": (repo_instructions_manifest_read_first),
        "deepagents_acceptance_rubric_manifest_path": (acceptance_rubric_manifest_path),
        "deepagents_acceptance_rubric_manifest_read_first": (acceptance_rubric_manifest_read_first),
        "deepagents_repair_interface_manifest_path": repair_interface_manifest_path,
        "deepagents_repair_interface_manifest_read_first": (repair_interface_manifest_read_first),
        "deepagents_resource_budgeted": resource_budgeted,
        "deepagents_resource_budget_read_first": resource_budget_read_first,
        "deepagents_resource_budget_max_model_responses": (
            max(resource_budget_max_model_responses)
            if resource_budget_max_model_responses
            else None
        ),
        "deepagents_resource_budget_max_model_tokens": (
            max(resource_budget_max_model_tokens) if resource_budget_max_model_tokens else None
        ),
    }


def patch_quality(trace_path: str | None, *, final_diff_path: str | None) -> dict[str, Any]:
    diff_quality = _diff_patch_quality(final_diff_path)
    if not trace_path:
        return diff_quality or _empty_patch_quality()
    path = Path(trace_path)
    if not path.is_file():
        return diff_quality or _empty_patch_quality()
    trace_quality = _patch_quality_from_trace(path)
    if diff_quality is None:
        return _normalized_patch_quality(trace_quality)
    return _merged_patch_quality(trace_quality, diff_quality)


def patch_target_alignment(
    *,
    trace_path: str | None,
    final_diff_path: str | None,
) -> dict[str, Any]:
    patch_targets = _final_diff_paths(final_diff_path)
    localized_targets = _localized_target_paths(trace_path)
    if not patch_targets or not localized_targets:
        return {
            "patch_target_paths": patch_targets,
            "localized_target_paths": localized_targets,
            "target_alignment_status": "unavailable",
            "patch_target_aligned": None,
        }
    localized_set = set(localized_targets)
    aligned = all(path in localized_set for path in patch_targets)
    return {
        "patch_target_paths": patch_targets,
        "localized_target_paths": localized_targets,
        "target_alignment_status": "aligned" if aligned else "misaligned",
        "patch_target_aligned": aligned,
    }


def _final_diff_paths(final_diff_path: str | None) -> tuple[str, ...]:
    if not final_diff_path:
        return ()
    path = Path(final_diff_path)
    if not path.is_file():
        return ()
    paths: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    for line in lines:
        if line.startswith("+++ b/"):
            _append_normalized_path(paths, line.removeprefix("+++ b/"))
        elif line.startswith("--- a/"):
            _append_normalized_path(paths, line.removeprefix("--- a/"))
    return tuple(paths)


def _localized_target_paths(trace_path: str | None) -> tuple[str, ...]:
    if not trace_path:
        return ()
    path = Path(trace_path)
    if not path.is_file():
        return ()
    paths: list[str] = []
    for event in _trace_events(path):
        for metadata in _trace_metadata_values(event):
            _append_contract_patchable_paths(paths, metadata.get("deepagents_contract"))
            _append_target_localization_paths(paths, metadata.get("target_localization"))
            _append_failure_localized_patch_plan_path(paths, event, metadata)
    return tuple(paths)


def _trace_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return events
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _trace_metadata_values(event: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        values.append(metadata)
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload_metadata = payload.get("metadata")
        if isinstance(payload_metadata, dict):
            values.append(payload_metadata)
    return values


def _append_contract_patchable_paths(paths: list[str], value: Any) -> None:
    if not isinstance(value, dict):
        return
    policy = value.get("patch_selection_policy")
    if not isinstance(policy, dict):
        return
    patchable_paths = policy.get("patchable_paths")
    if not isinstance(patchable_paths, list):
        return
    for path in patchable_paths:
        _append_normalized_path(paths, path)


def _append_virtual_file_paths(paths: list[str], value: Any) -> None:
    if not isinstance(value, list):
        return
    for path in value:
        _append_virtual_context_path(paths, path)


def _append_virtual_context_paths_from_policy(paths: list[str], value: Any) -> None:
    if not isinstance(value, list):
        return
    for path in value:
        _append_virtual_context_path(paths, path)


def _append_virtual_context_path(paths: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    normalized = value.strip().lstrip("/")
    if normalized in {"", "dev/null", "/dev/null"}:
        return
    if normalized.startswith(".patchsmith/"):
        return
    if normalized not in paths:
        paths.append(normalized)


def _append_target_localization_paths(paths: list[str], value: Any) -> None:
    if not isinstance(value, list):
        return
    for candidate in value:
        if not isinstance(candidate, dict):
            continue
        _append_normalized_path(paths, candidate.get("path"))


def _append_failure_localized_patch_plan_path(
    paths: list[str],
    event: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    if not _has_failure_localization_rationale(metadata.get("failure_localization")):
        return
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return
    patch_plan = payload.get("patch_plan")
    if not isinstance(patch_plan, dict):
        return
    _append_normalized_path(paths, patch_plan.get("path"))


def _has_failure_localization_rationale(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(_optional_str(value.get("failure_mechanism"))) and bool(
        _optional_str(value.get("target_rationale"))
    )


def _append_normalized_path(paths: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    normalized = value.strip().lstrip("/")
    if normalized in {"", "dev/null", "/dev/null"}:
        return
    if normalized not in paths:
        paths.append(normalized)


def _diff_patch_quality(final_diff_path: str | None) -> dict[str, Any] | None:
    if not final_diff_path:
        return None
    path = Path(final_diff_path)
    if not path.is_file():
        return None
    assessment = assess_diff_quality(path.read_text(encoding="utf-8"))
    if assessment.severity == "low" and not assessment.findings:
        return None
    return {
        "patch_quality_severity": assessment.severity,
        "patch_quality_warning": assessment.severity == "high",
        "patch_quality_codes": tuple(finding.code for finding in assessment.findings),
    }


def retry_feedback_artifacts(trace_path: str | None) -> tuple[str, ...]:
    if not trace_path:
        return ()
    path = Path(trace_path)
    if not path.is_file():
        return ()
    artifacts: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        retry_feedback_path = payload.get("retry_feedback_path")
        if not isinstance(retry_feedback_path, str) or not retry_feedback_path:
            continue
        if Path(retry_feedback_path).is_file():
            artifacts.append(retry_feedback_path)
    return tuple(dict.fromkeys(artifacts))


def _empty_trace_metrics() -> dict[str, Any]:
    return {
        "trace_event_count": 0,
        "runtime_node_count": 0,
        "failed_trace_event_count": 0,
        "retry_event_count": 0,
        "retry_labels": (),
        "retry_label_counts": {},
        "retry_failure_classes": (),
        "retry_failure_class_counts": {},
        "debuggability_score": 0.0,
        "agent_trajectory_score": 0.0,
        "todo_planning": False,
        "constrained_filesystem": False,
        "specialist_review": False,
        "guardrails": False,
        "structured_output": False,
        "retry_feedback": False,
        "patch_diagnostics": False,
        "contextual_verifier": False,
        "process_quality_label": "unscored",
        "process_quality_score": 0.0,
        "process_quality_flags": (),
    }


def _empty_model_usage() -> dict[str, Any]:
    return {
        "model_provider": None,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "response_count": None,
        "estimated_cost_usd": None,
    }


def _empty_deepagents_context_budget() -> dict[str, Any]:
    return {
        "deepagents_virtual_file_count": None,
        "deepagents_virtual_file_paths": (),
        "deepagents_max_context_files": None,
        "deepagents_context_budgeted": False,
        "deepagents_context_budget_manifest_path": None,
        "deepagents_context_budget_manifest_read_first": False,
        "deepagents_context_budget_omitted_file_count": None,
        "deepagents_context_budget_omitted_paths": (),
        "deepagents_repo_map_manifest_path": None,
        "deepagents_repo_map_manifest_read_first": False,
        "deepagents_repo_instructions_manifest_path": None,
        "deepagents_repo_instructions_manifest_read_first": False,
        "deepagents_acceptance_rubric_manifest_path": None,
        "deepagents_acceptance_rubric_manifest_read_first": False,
        "deepagents_repair_interface_manifest_path": None,
        "deepagents_repair_interface_manifest_read_first": False,
        "deepagents_resource_budgeted": False,
        "deepagents_resource_budget_read_first": False,
        "deepagents_resource_budget_max_model_responses": None,
        "deepagents_resource_budget_max_model_tokens": None,
    }


def _empty_patch_quality() -> dict[str, Any]:
    return {
        "patch_quality_severity": None,
        "patch_quality_warning": False,
        "patch_quality_codes": (),
    }


def _normalized_patch_quality(quality: dict[str, Any]) -> dict[str, Any]:
    return {
        "patch_quality_severity": _optional_str(quality.get("patch_quality_severity")),
        "patch_quality_warning": bool(quality.get("patch_quality_warning")),
        "patch_quality_codes": _quality_codes(quality.get("patch_quality_codes")),
    }


def _merged_patch_quality(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    left_severity = _optional_str(left.get("patch_quality_severity"))
    right_severity = _optional_str(right.get("patch_quality_severity"))
    return {
        "patch_quality_severity": _higher_severity(left_severity, right_severity),
        "patch_quality_warning": bool(left.get("patch_quality_warning"))
        or bool(right.get("patch_quality_warning")),
        "patch_quality_codes": _quality_codes(
            [
                *_quality_codes(left.get("patch_quality_codes")),
                *_quality_codes(right.get("patch_quality_codes")),
            ]
        ),
    }


def _higher_severity(left: str | None, right: str | None) -> str | None:
    return right if _severity_rank(right) > _severity_rank(left) else left


def _severity_rank(severity: str | None) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(severity or "", 0)


def _quality_codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    codes: list[str] = []
    for item in value:
        code = str(item) if item else ""
        if code and code not in codes:
            codes.append(code)
    return tuple(codes)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    strings: list[str] = []
    for item in value:
        text = _optional_str(item)
        if text and text not in strings:
            strings.append(text)
    return tuple(strings)


def _append_optional_int(values: list[int], value: Any) -> None:
    parsed = _optional_int(value)
    if parsed is not None:
        values.append(parsed)
