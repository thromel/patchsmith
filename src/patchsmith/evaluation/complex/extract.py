"""Extract complex benchmark results from saved repair-attempt artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from patchsmith.evaluation.complex.summary import preflight_gate_blocked_from_gates
from patchsmith.evaluation.complex.trace_readers import (
    deepagents_context_budget as _deepagents_context_budget,
)
from patchsmith.evaluation.complex.trace_readers import model_usage as _model_usage
from patchsmith.evaluation.complex.trace_readers import patch_quality as _patch_quality
from patchsmith.evaluation.complex.trace_readers import (
    patch_target_alignment as _patch_target_alignment,
)
from patchsmith.evaluation.complex.trace_readers import (
    retry_feedback_artifacts as _retry_feedback_artifacts,
)
from patchsmith.evaluation.complex.trace_readers import trace_metrics as _trace_metrics
from patchsmith.evaluation_models import ComplexBenchmarkResult

__all__ = [
    "complex_result",
    "complex_results_from_attempt_dir",
]


def complex_results_from_attempt_dir(
    attempt_dir: Path,
) -> list[ComplexBenchmarkResult]:
    results_path = attempt_dir / "public_issue_repair_attempt_results.json"
    if not results_path.is_file():
        raise FileNotFoundError(f"missing public issue attempt results: {results_path}")

    rows = _load_json_list(results_path)
    return [complex_result(row) for row in rows]


def complex_result(row: dict[str, Any]) -> ComplexBenchmarkResult:
    trace_path = _optional_str(row.get("trace_path"))
    metrics = _trace_metrics(trace_path)
    usage = _model_usage(trace_path)
    context_budget = _deepagents_context_budget(trace_path)
    patch_quality = _patch_quality(
        trace_path,
        final_diff_path=_optional_str(row.get("final_diff_path")),
    )
    target_alignment = _patch_target_alignment(
        trace_path=trace_path,
        final_diff_path=_optional_str(row.get("final_diff_path")),
    )
    retry_feedback_artifacts = _retry_feedback_artifacts(trace_path)
    status = str(row.get("status") or "unknown")
    test_exit_code = _optional_int(row.get("test_exit_code"))
    validation_passed = status == "validated" and not patch_quality["patch_quality_warning"]
    strict_status = _strict_status(
        status=status,
        patch_quality_warning=patch_quality["patch_quality_warning"],
    )
    preflight_gates = _preflight_gates(row.get("preflight_gates"))
    (
        live_cost_budget_usd,
        live_cost_budget_overage,
        live_cost_budget_overage_usd,
    ) = _live_cost_budget(
        preflight_gates=preflight_gates,
        estimated_cost_usd=usage["estimated_cost_usd"],
    )
    acceptance_rubric_aligned = _acceptance_rubric_aligned(
        manifest_path=context_budget["deepagents_acceptance_rubric_manifest_path"],
        read_first=context_budget["deepagents_acceptance_rubric_manifest_read_first"],
        contextual_verifier=metrics["contextual_verifier"],
        patch_generated=bool(row.get("patch_generated")),
        patch_quality_warning=patch_quality["patch_quality_warning"],
        patch_target_paths=target_alignment["patch_target_paths"],
        patch_target_aligned=target_alignment["patch_target_aligned"],
        mounted_paths=context_budget["deepagents_virtual_file_paths"],
    )
    progress_score, progress_stage = _complex_progress(
        status=status,
        reproduced=str(row.get("reproduction_execution_status") or "") == "reproduced",
        patch_generated=bool(row.get("patch_generated")),
        validation_passed=validation_passed,
        patch_quality_warning=patch_quality["patch_quality_warning"],
        patch_target_aligned=target_alignment["patch_target_aligned"],
    )
    failure_class = _complex_failure_class(
        status=status,
        preflight_status=_preflight_status(row.get("preflight_status")),
        preflight_gates=preflight_gates,
        reproduced=str(row.get("reproduction_execution_status") or "") == "reproduced",
        patch_generated=bool(row.get("patch_generated")),
        validation_passed=validation_passed,
        patch_quality_warning=patch_quality["patch_quality_warning"],
        patch_target_aligned=target_alignment["patch_target_aligned"],
        live_cost_budget_overage=live_cost_budget_overage,
        failed_trace_event_count=metrics["failed_trace_event_count"],
        retry_event_count=metrics["retry_event_count"],
    )
    harness_layer = _harness_layer(
        status=status,
        test_exit_code=test_exit_code,
        preflight_status=_preflight_status(row.get("preflight_status")),
        preflight_gates=preflight_gates,
        reproduced=str(row.get("reproduction_execution_status") or "") == "reproduced",
        patch_generated=bool(row.get("patch_generated")),
        validation_passed=validation_passed,
        patch_quality_warning=patch_quality["patch_quality_warning"],
        patch_target_aligned=target_alignment["patch_target_aligned"],
        live_cost_budget_overage=live_cost_budget_overage,
        failed_trace_event_count=metrics["failed_trace_event_count"],
        retry_event_count=metrics["retry_event_count"],
    )
    return ComplexBenchmarkResult(
        task_id=str(row.get("task_id") or "unknown"),
        repository=_optional_str(row.get("repository")),
        issue_url=_optional_str(row.get("issue_url")),
        status=status,
        strict_status=strict_status,
        runtime=str(row.get("runtime") or "unknown"),
        planner=str(row.get("planner") or "unknown"),
        context_provider=str(row.get("context_provider") or "unknown"),
        reproduced=str(row.get("reproduction_execution_status") or "") == "reproduced",
        patch_generated=bool(row.get("patch_generated")),
        validation_passed=validation_passed,
        test_exit_code=test_exit_code,
        trace_path=trace_path,
        report_path=_optional_str(row.get("report_path")),
        progress_score=progress_score,
        progress_stage=progress_stage,
        failure_class=failure_class,
        harness_layer=harness_layer,
        patch_quality_severity=patch_quality["patch_quality_severity"],
        patch_quality_warning=patch_quality["patch_quality_warning"],
        patch_quality_codes=patch_quality["patch_quality_codes"],
        patch_target_paths=target_alignment["patch_target_paths"],
        localized_target_paths=target_alignment["localized_target_paths"],
        target_alignment_status=target_alignment["target_alignment_status"],
        patch_target_aligned=target_alignment["patch_target_aligned"],
        retry_feedback_artifacts=retry_feedback_artifacts,
        retry_feedback_artifact_count=len(retry_feedback_artifacts),
        retry_labels=metrics["retry_labels"],
        retry_label_counts=metrics["retry_label_counts"],
        retry_failure_classes=metrics["retry_failure_classes"],
        retry_failure_class_counts=metrics["retry_failure_class_counts"],
        deepagents_virtual_file_count=context_budget["deepagents_virtual_file_count"],
        deepagents_virtual_file_paths=context_budget["deepagents_virtual_file_paths"],
        deepagents_max_context_files=context_budget["deepagents_max_context_files"],
        deepagents_context_budgeted=context_budget["deepagents_context_budgeted"],
        deepagents_context_budget_manifest_path=context_budget[
            "deepagents_context_budget_manifest_path"
        ],
        deepagents_context_budget_manifest_read_first=context_budget[
            "deepagents_context_budget_manifest_read_first"
        ],
        deepagents_context_budget_omitted_file_count=context_budget[
            "deepagents_context_budget_omitted_file_count"
        ],
        deepagents_context_budget_omitted_paths=context_budget[
            "deepagents_context_budget_omitted_paths"
        ],
        deepagents_repo_map_manifest_path=context_budget["deepagents_repo_map_manifest_path"],
        deepagents_repo_map_manifest_read_first=context_budget[
            "deepagents_repo_map_manifest_read_first"
        ],
        deepagents_repo_instructions_manifest_path=context_budget[
            "deepagents_repo_instructions_manifest_path"
        ],
        deepagents_repo_instructions_manifest_read_first=context_budget[
            "deepagents_repo_instructions_manifest_read_first"
        ],
        deepagents_acceptance_rubric_manifest_path=context_budget[
            "deepagents_acceptance_rubric_manifest_path"
        ],
        deepagents_acceptance_rubric_manifest_read_first=context_budget[
            "deepagents_acceptance_rubric_manifest_read_first"
        ],
        deepagents_acceptance_rubric_aligned=acceptance_rubric_aligned,
        deepagents_repair_interface_manifest_path=context_budget[
            "deepagents_repair_interface_manifest_path"
        ],
        deepagents_repair_interface_manifest_read_first=context_budget[
            "deepagents_repair_interface_manifest_read_first"
        ],
        deepagents_resource_budgeted=context_budget["deepagents_resource_budgeted"],
        deepagents_resource_budget_read_first=context_budget[
            "deepagents_resource_budget_read_first"
        ],
        deepagents_resource_budget_max_model_responses=context_budget[
            "deepagents_resource_budget_max_model_responses"
        ],
        deepagents_resource_budget_max_model_tokens=context_budget[
            "deepagents_resource_budget_max_model_tokens"
        ],
        trace_event_count=metrics["trace_event_count"],
        runtime_node_count=metrics["runtime_node_count"],
        failed_trace_event_count=metrics["failed_trace_event_count"],
        retry_event_count=metrics["retry_event_count"],
        debuggability_score=metrics["debuggability_score"],
        agent_trajectory_score=metrics["agent_trajectory_score"],
        todo_planning=metrics["todo_planning"],
        constrained_filesystem=metrics["constrained_filesystem"],
        specialist_review=metrics["specialist_review"],
        guardrails=metrics["guardrails"],
        structured_output=metrics["structured_output"],
        retry_feedback=metrics["retry_feedback"],
        patch_diagnostics=metrics["patch_diagnostics"],
        contextual_verifier=metrics["contextual_verifier"],
        process_quality_label=metrics["process_quality_label"],
        process_quality_score=metrics["process_quality_score"],
        process_quality_flags=metrics["process_quality_flags"],
        model_provider=usage["model_provider"],
        response_count=usage["response_count"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        estimated_cost_usd=usage["estimated_cost_usd"],
        live_cost_budget_usd=live_cost_budget_usd,
        live_cost_budget_overage=live_cost_budget_overage,
        live_cost_budget_overage_usd=live_cost_budget_overage_usd,
        attempt_index=max(1, _optional_int(row.get("attempt_index")) or 1),
        attempt_count=max(1, _optional_int(row.get("attempt_count")) or 1),
        preflight_status=_preflight_status(row.get("preflight_status")),
        preflight_gates=preflight_gates,
    )


def _complex_progress(
    *,
    status: str,
    reproduced: bool,
    patch_generated: bool,
    validation_passed: bool,
    patch_quality_warning: bool,
    patch_target_aligned: bool | None,
) -> tuple[float, str]:
    if validation_passed:
        return 1.0, "validated"
    if status == "validated" and patch_quality_warning:
        return 0.85, "validated_quality_warning"
    if patch_target_aligned is True:
        return 0.65, "target_aligned_patch"
    if patch_generated:
        if patch_target_aligned is False:
            return 0.45, "patch_generated_misaligned"
        return 0.50, "patch_generated"
    if reproduced:
        return 0.20, "reproduced"
    if status == "blocked":
        return 0.0, "blocked"
    return 0.0, status or "unknown"


def _complex_failure_class(
    *,
    status: str,
    preflight_status: str,
    preflight_gates: list[dict[str, str]],
    reproduced: bool,
    patch_generated: bool,
    validation_passed: bool,
    patch_quality_warning: bool,
    patch_target_aligned: bool | None,
    live_cost_budget_overage: bool,
    failed_trace_event_count: int,
    retry_event_count: int,
) -> str:
    if validation_passed:
        return "validated"
    if patch_quality_warning:
        return "quality_risk"
    if live_cost_budget_overage:
        return "budget_overage"
    if preflight_gate_blocked_from_gates(preflight_gates, "budget"):
        return "budget_preflight_blocked"
    if preflight_gate_blocked_from_gates(preflight_gates, "model"):
        return "model_preflight_blocked"
    if preflight_gate_blocked_from_gates(preflight_gates, "sandbox"):
        return "sandbox_preflight_blocked"
    if preflight_status == "blocked":
        return "preflight_blocked"
    if not reproduced:
        return "reproduction_failed"
    if not patch_generated:
        return "no_patch"
    if patch_target_aligned is False:
        return "target_misaligned"
    if failed_trace_event_count > 0:
        return "tool_or_runtime_failure"
    if retry_event_count > 0:
        return "retry_exhausted"
    if status == "failed":
        return "validation_failed"
    if status == "blocked":
        return "blocked"
    return status or "unknown"


def _harness_layer(
    *,
    status: str,
    test_exit_code: int | None,
    preflight_status: str,
    preflight_gates: list[dict[str, str]],
    reproduced: bool,
    patch_generated: bool,
    validation_passed: bool,
    patch_quality_warning: bool,
    patch_target_aligned: bool | None,
    live_cost_budget_overage: bool,
    failed_trace_event_count: int,
    retry_event_count: int,
) -> str:
    if validation_passed:
        return "none"
    if live_cost_budget_overage or preflight_gate_blocked_from_gates(
        preflight_gates,
        "budget",
    ):
        return "budget"
    if preflight_gate_blocked_from_gates(preflight_gates, "model"):
        return "model"
    if preflight_gate_blocked_from_gates(preflight_gates, "sandbox"):
        return "sandbox"
    if preflight_status == "blocked":
        return "preflight"
    if not reproduced:
        return "reproduction"
    if not patch_generated:
        return "planning"
    if patch_target_aligned is False:
        return "context"
    if patch_quality_warning:
        return "patch_quality"
    if retry_event_count > 0:
        return "retry"
    if failed_trace_event_count > 0:
        return "runtime"
    if status == "failed" or (test_exit_code is not None and test_exit_code != 0):
        return "validation"
    if status == "blocked":
        return "orchestration"
    return "unknown"


def _acceptance_rubric_aligned(
    *,
    manifest_path: str | None,
    read_first: bool,
    contextual_verifier: bool,
    patch_generated: bool,
    patch_quality_warning: bool,
    patch_target_paths: tuple[str, ...],
    patch_target_aligned: bool | None,
    mounted_paths: tuple[str, ...],
) -> bool | None:
    if manifest_path is None:
        return None
    if (
        not read_first
        or not contextual_verifier
        or not patch_generated
        or patch_quality_warning
        or patch_target_aligned is not True
        or not patch_target_paths
    ):
        return False
    mounted = {
        normalized for path in mounted_paths if (normalized := _normalized_path(path)) is not None
    }
    if not mounted:
        return False
    targets = {
        normalized
        for path in patch_target_paths
        if (normalized := _normalized_path(path)) is not None
    }
    return bool(targets) and targets.issubset(mounted)


def _normalized_path(value: str) -> str | None:
    normalized = value.strip().lstrip("/")
    if normalized in {"", "dev/null", "/dev/null"}:
        return None
    return normalized


def _strict_status(*, status: str, patch_quality_warning: bool) -> str:
    if status == "validated" and patch_quality_warning:
        return "failed_quality"
    if status == "validated":
        return "validated"
    return status


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON list in {path}")
    return [row for row in data if isinstance(row, dict)]


def _preflight_status(value: object) -> str:
    text = _optional_str(value)
    return text if text else "not_applicable"


def _preflight_gates(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    gates: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        gates.append(
            {
                str(key): str(gate_value)
                for key, gate_value in item.items()
                if gate_value is not None
            }
        )
    return gates


def _live_cost_budget(
    *,
    preflight_gates: list[dict[str, str]],
    estimated_cost_usd: float | None,
) -> tuple[float | None, bool, float | None]:
    budget_cap = _live_cost_budget_cap(preflight_gates)
    overage: float | None = None
    if budget_cap is not None and estimated_cost_usd is not None:
        actual_overage = estimated_cost_usd - budget_cap
        if actual_overage > 0:
            overage = actual_overage
    return budget_cap, overage is not None, overage


def _live_cost_budget_cap(preflight_gates: list[dict[str, str]]) -> float | None:
    for gate in preflight_gates:
        if gate.get("name") != "budget":
            continue
        budget_cap = _optional_float(gate.get("max_live_cost_usd"))
        if budget_cap is not None:
            return budget_cap
    return None


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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
