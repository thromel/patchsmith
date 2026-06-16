"""Follow-up candidate policy for complex benchmark summaries."""

from __future__ import annotations

from patchsmith.evaluation.complex.models import ComplexBenchmarkSuiteThresholds
from patchsmith.evaluation.complex.selection import selected_results as _selected_results
from patchsmith.evaluation_models import (
    ComplexBenchmarkFollowupCandidate,
    ComplexBenchmarkResult,
    ComplexBenchmarkSelection,
    ComplexBenchmarkSummary,
)

__all__ = [
    "complex_followup_candidates",
    "complex_suite_followup_candidates",
]


def complex_followup_candidates(
    results: list[ComplexBenchmarkResult],
    *,
    limit: int = 10,
) -> list[ComplexBenchmarkFollowupCandidate]:
    candidates: list[ComplexBenchmarkFollowupCandidate] = []
    for result in results:
        priority, reasons = _followup_priority(result)
        if priority <= 0:
            continue
        action = _followup_action(result)
        profile = _followup_profile(result)
        candidates.append(
            _candidate(
                result,
                action=action,
                profile=profile,
                priority=priority,
                reasons=reasons,
            )
        )
    return sorted(candidates, key=_followup_sort_key)[:limit]


def complex_suite_followup_candidates(
    *,
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection],
    summary: ComplexBenchmarkSummary,
    thresholds: ComplexBenchmarkSuiteThresholds | None,
    limit: int = 10,
) -> list[ComplexBenchmarkFollowupCandidate]:
    candidates = complex_followup_candidates(results, limit=limit)
    if thresholds is None:
        return candidates
    verifier_candidates = _suite_verifier_followup_candidates(
        results=results,
        selections=selections,
        summary=summary,
        thresholds=thresholds,
        existing_candidates=candidates,
    )
    if not verifier_candidates:
        return candidates
    return _merge_followup_candidates(candidates, verifier_candidates, limit=limit)


def _suite_verifier_followup_candidates(
    *,
    results: list[ComplexBenchmarkResult],
    selections: list[ComplexBenchmarkSelection],
    summary: ComplexBenchmarkSummary,
    thresholds: ComplexBenchmarkSuiteThresholds,
    existing_candidates: list[ComplexBenchmarkFollowupCandidate],
) -> list[ComplexBenchmarkFollowupCandidate]:
    if not _suite_verifier_gate_requested(thresholds):
        return []
    selected = _selected_results(results, selections)
    existing_verifier_keys = {
        (candidate.task_id, candidate.attempt_index)
        for candidate in existing_candidates
        if candidate.suggested_profile == "acceptance_rubric_verifier"
    }
    candidates: list[ComplexBenchmarkFollowupCandidate] = []
    for result in selected:
        attempt = result.repair_attempt
        if (attempt.task_id, attempt.attempt_index) in existing_verifier_keys:
            continue
        reasons = _suite_verifier_missing_reasons(
            result,
            summary=summary,
            thresholds=thresholds,
        )
        if not reasons:
            continue
        action = "verifier_contract_rerun"
        profile = "acceptance_rubric_verifier"
        candidates.append(
            _candidate(
                result,
                action=action,
                profile=profile,
                priority=360 + len(reasons) * 10,
                reasons=reasons,
            )
        )
    return candidates


def _candidate(
    result: ComplexBenchmarkResult,
    *,
    action: str,
    profile: str,
    priority: int,
    reasons: list[str],
) -> ComplexBenchmarkFollowupCandidate:
    attempt = result.repair_attempt
    outcome = result.patch_outcome
    trace = result.trace_evidence
    process = result.process_quality
    usage = result.model_usage
    return ComplexBenchmarkFollowupCandidate(
        task_id=attempt.task_id,
        attempt_index=attempt.attempt_index,
        attempt_count=attempt.attempt_count,
        action=action,
        suggested_profile=profile,
        recommended_command=_followup_command(
            result,
            action=action,
            profile=profile,
        ),
        recommended_env=_followup_env(result, action=action, profile=profile),
        validation_command=_followup_validation_command(
            result,
            action=action,
            profile=profile,
        ),
        success_criteria=_followup_success_criteria(
            action=action,
            profile=profile,
        ),
        status=outcome.status,
        strict_status=outcome.strict_status,
        failure_class=outcome.failure_class,
        harness_layer=outcome.harness_layer,
        process_quality_label=process.label,
        priority=priority,
        reasons=tuple(reasons),
        retry_failure_classes=trace.retry_failure_classes,
        response_count=usage.response_count,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
        report_path=trace.report_path,
        trace_path=trace.trace_path,
    )


def _suite_verifier_gate_requested(
    thresholds: ComplexBenchmarkSuiteThresholds,
) -> bool:
    return any(
        threshold is not None
        for threshold in (
            thresholds.min_contextual_verifier_rate,
            thresholds.min_acceptance_rubric_manifest_rate,
            thresholds.min_acceptance_rubric_read_first_rate,
            thresholds.min_acceptance_rubric_alignment_rate,
        )
    )


def _suite_verifier_missing_reasons(
    result: ComplexBenchmarkResult,
    *,
    summary: ComplexBenchmarkSummary,
    thresholds: ComplexBenchmarkSuiteThresholds,
) -> list[str]:
    process = result.process_quality
    rubric = result.rubric_evidence
    reasons: list[str] = []
    if (
        thresholds.min_contextual_verifier_rate is not None
        and summary.contextual_verifier_rate < thresholds.min_contextual_verifier_rate
        and not process.contextual_verifier
    ):
        reasons.append("contextual_verifier_missing")
    manifest_rate = _rate(
        summary.acceptance_rubric_manifest_tasks,
        summary.attempted_tasks,
    )
    if (
        thresholds.min_acceptance_rubric_manifest_rate is not None
        and manifest_rate < thresholds.min_acceptance_rubric_manifest_rate
        and rubric.manifest_path is None
    ):
        reasons.append("acceptance_rubric_manifest_missing")
    if (
        thresholds.min_acceptance_rubric_read_first_rate is not None
        and summary.acceptance_rubric_read_first_rate
        < thresholds.min_acceptance_rubric_read_first_rate
        and not rubric.manifest_read_first
    ):
        reasons.append("acceptance_rubric_read_first_missing")
    if (
        thresholds.min_acceptance_rubric_alignment_rate is not None
        and summary.acceptance_rubric_alignment_rate
        < thresholds.min_acceptance_rubric_alignment_rate
        and rubric.aligned is not True
    ):
        reasons.append("acceptance_rubric_alignment_missing")
    return reasons


def _merge_followup_candidates(
    primary: list[ComplexBenchmarkFollowupCandidate],
    secondary: list[ComplexBenchmarkFollowupCandidate],
    *,
    limit: int,
) -> list[ComplexBenchmarkFollowupCandidate]:
    return sorted([*primary, *secondary], key=_followup_sort_key)[:limit]


def _followup_command(
    result: ComplexBenchmarkResult,
    *,
    action: str,
    profile: str,
) -> tuple[str, ...]:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "patchsmith.cli",
        "execute-public-issue-repairs",
        "--task-id",
        result.task_id,
        "--runtime",
        "deepagents",
        "--planner",
        "deepagents",
        "--context-provider",
        "native_hybrid",
        "--sandbox-mode",
        "docker",
        "--deepagents-subagents",
        _followup_subagent_mode(action, profile),
        "--deepagents-max-context-files",
        str(_followup_context_file_cap(action, profile)),
        "--max-retries",
        str(_followup_max_retries(action, profile)),
        "--max-actual-model-responses",
        str(_followup_response_cap(action, profile)),
        "--max-actual-model-tokens",
        str(_followup_token_cap(action, profile)),
        "--max-live-cost-usd",
        _followup_cost_cap(action, profile),
        "--estimated-cost-per-attempt-usd",
        _followup_estimated_cost(action, profile),
        "--output",
        _followup_attempt_output_dir(result, profile),
        "--execute",
        "--json",
    ]
    return tuple(command)


def _followup_validation_command(
    result: ComplexBenchmarkResult,
    *,
    action: str,
    profile: str,
) -> tuple[str, ...]:
    response_cap = str(_followup_response_cap(action, profile))
    token_cap = str(_followup_token_cap(action, profile))
    cost_cap = _followup_cost_cap(action, profile)
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "patchsmith.cli",
        "eval-complex-suite",
        "--attempt-dir",
        _followup_attempt_output_dir(result, profile),
        "--output",
        _followup_complex_output_dir(result, profile),
        "--min-validation-rate",
        "1.0",
        "--min-live-provider-tasks",
        "1",
        "--min-unique-tasks",
        "1",
        "--max-attempted-cost-per-validated-task-usd",
        cost_cap,
        "--max-attempted-tokens-per-validated-task",
        token_cap,
        "--max-attempted-responses-per-validated-task",
        response_cap,
        "--max-attempted-task-cost-usd",
        cost_cap,
        "--max-attempted-task-tokens",
        token_cap,
        "--max-attempted-task-responses",
        response_cap,
        "--max-selected-cost-per-validated-task-usd",
        cost_cap,
        "--max-selected-tokens-per-validated-task",
        token_cap,
        "--max-selected-responses-per-validated-task",
        response_cap,
        "--max-selected-task-cost-usd",
        cost_cap,
        "--max-selected-task-tokens",
        token_cap,
        "--max-selected-task-responses",
        response_cap,
        "--min-process-quality-score",
        "1.0",
        "--max-process-risky-validated-tasks",
        "0",
        "--min-target-alignment-rate",
        "1.0",
        "--json",
    ]
    if profile == "acceptance_rubric_verifier":
        command.extend(
            [
                "--min-contextual-verifier-rate",
                "1.0",
                "--min-acceptance-rubric-manifest-rate",
                "1.0",
                "--min-acceptance-rubric-read-first-rate",
                "1.0",
                "--min-acceptance-rubric-alignment-rate",
                "1.0",
            ]
        )
    return tuple(command)


def _followup_success_criteria(
    *,
    action: str,
    profile: str,
) -> tuple[str, ...]:
    criteria = [
        "validation_rate >= 1.0",
        "live_provider_tasks >= 1",
        f"max_attempted_task_responses <= {_followup_response_cap(action, profile)}",
        f"max_attempted_task_tokens <= {_followup_token_cap(action, profile)}",
        f"max_attempted_task_cost_usd <= {_followup_cost_cap(action, profile)}",
        "avg_process_quality_score >= 1.0",
        "process_risky_validated_tasks == 0",
        "target_alignment_rate >= 1.0",
    ]
    if profile == "acceptance_rubric_verifier":
        criteria.extend(
            [
                "contextual_verifier_rate >= 1.0",
                "acceptance_rubric_manifest_rate >= 1.0",
                "acceptance_rubric_read_first_rate >= 1.0",
                "acceptance_rubric_alignment_rate >= 1.0",
            ]
        )
    return tuple(criteria)


def _followup_attempt_output_dir(
    result: ComplexBenchmarkResult,
    profile: str,
) -> str:
    return (
        f"artifacts/experiments/public_issue_corpus_v1/followup_{_slug(result.task_id)}_{profile}"
    )


def _followup_complex_output_dir(
    result: ComplexBenchmarkResult,
    profile: str,
) -> str:
    return f"artifacts/experiments/complex_followup_{_slug(result.task_id)}_{profile}"


def _followup_env(
    result: ComplexBenchmarkResult,
    *,
    action: str,
    profile: str,
) -> dict[str, str]:
    del result, action, profile
    return {"OPENAI_API_KEY": "<required>"}


def _followup_subagent_mode(action: str, profile: str) -> str:
    if profile in {"budget_critical_context_cap", "fast_patch_packet"}:
        return "auto"
    if action == "quality_gate_rerun":
        return "auto"
    return "auto"


def _followup_context_file_cap(action: str, profile: str) -> int:
    if profile == "budget_critical_context_cap":
        return 4
    if profile == "fast_patch_packet":
        return 3
    if action == "context_policy_ablation":
        return 3
    return 5


def _followup_max_retries(action: str, profile: str) -> int:
    if profile == "budget_critical_context_cap":
        return 0
    if action in {"quality_gate_rerun", "retry_policy_ablation"}:
        return 1
    return 0


def _followup_response_cap(action: str, profile: str) -> int:
    if profile == "budget_critical_context_cap":
        return 6
    if action in {"quality_gate_rerun", "retry_policy_ablation"}:
        return 10
    return 8


def _followup_token_cap(action: str, profile: str) -> int:
    if profile == "budget_critical_context_cap":
        return 90_000
    if action in {"quality_gate_rerun", "retry_policy_ablation"}:
        return 150_000
    return 120_000


def _followup_cost_cap(action: str, profile: str) -> str:
    if profile == "budget_critical_context_cap":
        return "0.07"
    if action in {"quality_gate_rerun", "retry_policy_ablation"}:
        return "0.12"
    return "0.10"


def _followup_estimated_cost(action: str, profile: str) -> str:
    return _followup_cost_cap(action, profile)


def _followup_action(result: ComplexBenchmarkResult) -> str:
    outcome = result.patch_outcome
    trace = result.trace_evidence
    process = result.process_quality
    cost = result.cost_evidence
    if cost.live_cost_budget_overage or outcome.harness_layer == "budget":
        return "budget_contract_tightening"
    if outcome.validation_passed and (
        _high_response_count(result) or _high_token_count(result) or _high_cost(result)
    ):
        return "cost_optimization_rerun"
    if outcome.harness_layer == "patch_quality" or outcome.quality_warning:
        return "quality_gate_rerun"
    if outcome.harness_layer == "context" or outcome.target_aligned is False:
        return "context_policy_ablation"
    if outcome.harness_layer == "retry" or trace.retry_failure_classes:
        return "retry_policy_ablation"
    if process.label == "risky":
        return "process_quality_review"
    if outcome.harness_layer == "runtime" or trace.failed_trace_event_count >= 3:
        return "runtime_failure_triage"
    if outcome.harness_layer == "planning" or not outcome.patch_generated:
        return "planning_context_repair"
    if not outcome.validation_passed:
        return "validation_failure_rerun"
    return "manual_triage"


def _followup_profile(result: ComplexBenchmarkResult) -> str:
    outcome = result.patch_outcome
    trace = result.trace_evidence
    process = result.process_quality
    cost = result.cost_evidence
    if cost.live_cost_budget_overage or outcome.harness_layer == "budget":
        return "resource_budget_auto"
    if _followup_action(result) == "cost_optimization_rerun":
        return "budget_critical_context_cap"
    if outcome.harness_layer == "patch_quality" or outcome.quality_warning:
        return "acceptance_rubric_verifier"
    if outcome.harness_layer == "context" or outcome.target_aligned is False:
        return "targeted_context_ablation"
    if outcome.harness_layer == "retry" or trace.retry_failure_classes:
        return "structured_retry_feedback"
    if process.label == "risky":
        return "process_quality_gate"
    if outcome.harness_layer == "runtime" or trace.failed_trace_event_count >= 3:
        return "runtime_trace_triage"
    if outcome.harness_layer == "planning" or not outcome.patch_generated:
        return "fast_patch_packet"
    if not outcome.validation_passed:
        return "focused_validation_retry"
    return "manual_review"


def _followup_priority(result: ComplexBenchmarkResult) -> tuple[int, list[str]]:
    outcome = result.patch_outcome
    trace = result.trace_evidence
    process = result.process_quality
    cost = result.cost_evidence
    priority = 0
    reasons: list[str] = []
    if not outcome.validation_passed:
        priority += 120
        reasons.append("strict_not_validated")
    if outcome.strict_status == "failed_quality" or outcome.quality_warning:
        priority += 100
        reasons.append("quality_risk")
    if outcome.failure_class not in {"validated", "unknown"}:
        priority += 80
        reasons.append(f"failure_class:{outcome.failure_class}")
    if outcome.harness_layer not in {"none", "unknown"}:
        priority += 70
        reasons.append(f"harness_layer:{outcome.harness_layer}")
    if process.label == "risky":
        priority += 90
        reasons.append("process_risky")
    elif process.label == "watch":
        priority += 40
        reasons.append("process_watch")
    if trace.retry_failure_classes:
        priority += 60
        reasons.append("retry_failure:" + ",".join(trace.retry_failure_classes))
    if cost.live_cost_budget_overage:
        priority += 80
        reasons.append("live_cost_budget_overage")
    if outcome.target_aligned is False:
        priority += 70
        reasons.append("target_misaligned")
    if trace.failed_trace_event_count >= 3:
        priority += 35
        reasons.append("failed_event_churn")
    if _high_response_count(result):
        priority += 20
        reasons.append("high_response_count")
    if _high_token_count(result):
        priority += 20
        reasons.append("high_token_count")
    if _high_cost(result):
        priority += 20
        reasons.append("high_cost")
    return priority, reasons


def _high_response_count(result: ComplexBenchmarkResult) -> bool:
    response_count = result.model_usage.response_count
    return response_count is not None and response_count >= 7


def _high_token_count(result: ComplexBenchmarkResult) -> bool:
    total_tokens = result.model_usage.total_tokens
    return total_tokens is not None and total_tokens >= 120_000


def _high_cost(result: ComplexBenchmarkResult) -> bool:
    estimated_cost_usd = result.model_usage.estimated_cost_usd
    return estimated_cost_usd is not None and estimated_cost_usd >= 0.09


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value.strip()]
    slug = "_".join(part for part in "".join(chars).split("_") if part)
    return slug or "unknown"


def _followup_sort_key(
    candidate: ComplexBenchmarkFollowupCandidate,
) -> tuple[object, ...]:
    return (
        -candidate.priority,
        _optional_float_rank(candidate.estimated_cost_usd),
        _optional_int_rank(candidate.total_tokens),
        candidate.task_id,
        candidate.attempt_index,
    )


def _optional_float_rank(value: float | None) -> float:
    return value if value is not None else float("inf")


def _optional_int_rank(value: int | None) -> int:
    return value if value is not None else 10**18


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
