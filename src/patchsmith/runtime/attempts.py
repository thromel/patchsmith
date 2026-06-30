from __future__ import annotations

import hashlib
from pathlib import Path

from patchsmith.analysis import RepairOutcomeAnalysis
from patchsmith.models import CommandResult, RunRequest
from patchsmith.runtime.core import AgentResult
from patchsmith.runtime.feedback import (
    assertion_progress_summary,
    patch_plan_feedback_summary,
    safety_gate_rejection_summary,
    sandbox_failure_signature,
    sandbox_feedback_summary,
)
from patchsmith.sandbox import SandboxRunner
from patchsmith.tracing import RunTrace


def emit_agent_result_trace(
    *,
    trace: RunTrace,
    request: RunRequest,
    agent_result: AgentResult,
    attempt: int,
) -> None:
    trace.emit(
        node_name="runtime",
        event_type="agent_result",
        status=agent_result.status,
        output_summary=agent_result.summary,
        payload={
            "runtime": request.runtime,
            "planner": request.planner,
            "attempt": attempt,
            "patch_candidates": [
                candidate.to_dict() for candidate in agent_result.patch_candidates
            ],
        },
    )
    for runtime_event in agent_result.runtime_trace:
        trace.emit(
            node_name=f"runtime.{runtime_event.get('node', 'unknown')}",
            event_type="runtime_node",
            status=str(runtime_event.get("status", "completed")),
            output_summary=str(runtime_event.get("summary", "")),
            payload={
                "runtime": request.runtime,
                "planner": request.planner,
                "workflow_attempt": attempt,
                **runtime_event,
            },
        )


def run_sandbox_attempt(
    *,
    command: str | None,
    sandbox: SandboxRunner,
    repo_path: Path,
    logs_dir: Path,
    trace: RunTrace,
    request: RunRequest,
    attempt: int,
) -> CommandResult | None:
    if not command:
        trace.emit(
            node_name="test",
            event_type="sandbox_command",
            status="skipped",
            output_summary="no test command supplied or detected",
            payload={
                "attempt": attempt,
                "sandbox_mode": request.sandbox_mode,
            },
        )
        return None

    test_result = sandbox.run(
        command=command,
        workspace=repo_path,
        timeout_seconds=60,
    )
    (logs_dir / "stdout.txt").write_text(test_result.stdout, encoding="utf-8")
    (logs_dir / "stderr.txt").write_text(test_result.stderr, encoding="utf-8")
    (logs_dir / f"stdout_attempt_{attempt}.txt").write_text(
        test_result.stdout,
        encoding="utf-8",
    )
    (logs_dir / f"stderr_attempt_{attempt}.txt").write_text(
        test_result.stderr,
        encoding="utf-8",
    )
    trace.emit(
        node_name="test",
        event_type="sandbox_command",
        status="completed" if test_result.exit_code == 0 else "failed",
        input_summary=command,
        output_summary=f"exit_code={test_result.exit_code}",
        payload={
            **test_result.to_dict(),
            "attempt": attempt,
            "sandbox_mode": request.sandbox_mode,
            "sandbox_image": request.sandbox_image if request.sandbox_mode == "docker" else None,
        },
        latency_ms=test_result.duration_ms,
    )
    return test_result


def test_feedback_retry_budget(request: RunRequest) -> int:
    if request.runtime == "deepagents" and request.planner == "deepagents":
        return max(0, request.max_retries)
    return 0


def should_retry_with_test_feedback(
    *,
    request: RunRequest,
    agent_result: AgentResult,
    test_result: CommandResult | None,
    repair_analysis: RepairOutcomeAnalysis | None = None,
    attempt: int,
    max_feedback_retries: int,
) -> bool:
    if test_feedback_retry_budget(request) == 0:
        return False
    if attempt > max_feedback_retries:
        return False
    if (
        repair_analysis is not None
        and repair_analysis.failure_category is not None
        and repair_analysis.failure_category.startswith("test_environment_")
    ):
        return False
    if agent_result.status == "patch_generated":
        if test_result is None:
            return False
        if _high_risk_patch_quality(repair_analysis):
            return test_result.exit_code == 0
        return test_result.exit_code != 0
    if agent_result.status not in {"no_patch_generated", "failed"}:
        return False
    return test_result is None or test_result.exit_code != 0


def issue_with_test_feedback(
    *,
    original_issue: str,
    agent_status: str,
    agent_summary: str,
    test_result: CommandResult | None,
    final_diff: str,
    attempt: int,
    runtime_trace: list[dict[str, object]] | None = None,
    attempt_history: list[dict[str, object]] | None = None,
    repair_analysis: RepairOutcomeAnalysis | None = None,
) -> str:
    plan_feedback = patch_plan_feedback_summary(runtime_trace or [])
    retry_guidance = _retry_guidance(
        agent_status=agent_status,
        test_result=test_result,
        final_diff=final_diff,
        repair_analysis=repair_analysis,
        runtime_trace=runtime_trace or [],
    )
    retry_classification = "\n".join(
        _retry_classification_lines(
            agent_status=agent_status,
            test_result=test_result,
            final_diff=final_diff,
            repair_analysis=repair_analysis,
            runtime_trace=runtime_trace or [],
            attempt_history=attempt_history or [],
        )
    )
    intro = _retry_intro(
        attempt=attempt,
        quality_retry=_high_risk_patch_quality(repair_analysis),
    )
    sections = [
        original_issue.strip(),
        intro,
        f"Retry classification:\n{retry_classification}",
        f"Previous agent status:\n{agent_status}",
        f"Previous agent summary:\n{_truncate_feedback(agent_summary)}",
        "Sandbox feedback summary:\n"
        + sandbox_feedback_summary(test_result=test_result, final_diff=final_diff),
    ]
    history = attempt_history_summary(attempt_history or [])
    if history:
        sections.insert(4, history)
    if retry_guidance:
        sections.insert(5 if history else 4, retry_guidance)
    if plan_feedback:
        insert_at = 4
        if history:
            insert_at += 1
        if retry_guidance:
            insert_at += 1
        sections.insert(insert_at, plan_feedback)
    if test_result is not None:
        sections.extend(
            [
                f"Sandbox command:\n{test_result.command}",
                f"Sandbox exit code:\n{test_result.exit_code}",
                f"Sandbox stdout:\n{_truncate_feedback(test_result.stdout)}",
                f"Sandbox stderr:\n{_truncate_feedback(test_result.stderr)}",
            ]
        )
    sections.append(f"Current diff after failed attempt:\n{_truncate_feedback(final_diff)}")
    return "\n\n".join(sections)


def retry_feedback_brief(
    *,
    agent_status: str,
    agent_summary: str,
    test_result: CommandResult | None,
    final_diff: str,
    attempt: int,
    runtime_trace: list[dict[str, object]] | None = None,
    attempt_history: list[dict[str, object]] | None = None,
    repair_analysis: RepairOutcomeAnalysis | None = None,
) -> str:
    retry_guidance = _retry_guidance(
        agent_status=agent_status,
        test_result=test_result,
        final_diff=final_diff,
        repair_analysis=repair_analysis,
        runtime_trace=runtime_trace or [],
    )
    plan_feedback = patch_plan_feedback_summary(runtime_trace or [])
    diff_hash = _feedback_hash(final_diff)
    quality_retry = _high_risk_patch_quality(repair_analysis)
    diff_label = "Risky diff" if quality_retry else "Failed diff"
    workspace_state = (
        "- Workspace state: clean retry workspace; the risky patch has been reverted."
        if quality_retry
        else "- Workspace state: clean retry workspace; the failed patch has been reverted."
    )
    assertion_progress = assertion_progress_summary(
        test_result=test_result,
        final_diff=final_diff,
    )
    retry_classification = _retry_classification_lines(
        agent_status=agent_status,
        test_result=test_result,
        final_diff=final_diff,
        repair_analysis=repair_analysis,
        runtime_trace=runtime_trace or [],
        attempt_history=attempt_history or [],
    )
    required_retry_behavior = _required_retry_behavior(
        diff_hash=diff_hash,
        quality_retry=quality_retry,
        partial_assertion_progress=bool(assertion_progress),
    )
    sections = [
        "# PatchSmith Retry Feedback",
        "",
        f"- Previous attempt: `{attempt}`",
        f"- Previous agent status: `{agent_status}`",
        f"- {diff_label} sha256_12: `{diff_hash}`",
        workspace_state,
        "",
        "## Required Retry Behavior",
        "",
        *required_retry_behavior,
    ]
    sections.extend(["", "## Retry Classification", "", *retry_classification])
    if retry_guidance:
        sections.extend(["", "## Retry Diagnosis", "", retry_guidance])
    sections.extend(
        [
            "",
            "## Previous Agent Summary",
            "",
            _truncate_feedback(agent_summary),
            "",
            "## Sandbox Feedback",
            "",
            sandbox_feedback_summary(test_result=test_result, final_diff=final_diff),
        ]
    )
    history = attempt_history_summary(attempt_history or [])
    if history:
        sections.extend(["", "## Attempt History", "", history])
    if plan_feedback:
        sections.extend(["", "## Patch Plan Diagnostics", "", plan_feedback])
    if test_result is not None:
        sections.extend(
            [
                "",
                "## Sandbox Command",
                "",
                test_result.command,
                "",
                "## Sandbox Output",
                "",
                f"Exit code: `{test_result.exit_code}`",
                "",
                "Stdout:",
                "```text",
                _truncate_feedback(test_result.stdout),
                "```",
                "",
                "Stderr:",
                "```text",
                _truncate_feedback(test_result.stderr),
                "```",
            ]
        )
    sections.extend(
        [
            "",
            "## Failed Diff",
            "",
            "```diff",
            _truncate_feedback(final_diff),
            "```",
        ]
    )
    return "\n".join(sections)


def retry_feedback_labels(
    *,
    test_result: CommandResult | None,
    agent_status: str = "patch_generated",
    final_diff: str = "",
    repair_analysis: RepairOutcomeAnalysis | None = None,
    runtime_trace: list[dict[str, object]] | None = None,
    attempt_history: list[dict[str, object]] | None = None,
) -> tuple[str, ...]:
    labels: list[str] = []
    quality_retry = _high_risk_patch_quality(repair_analysis)
    if quality_retry:
        _append_label(labels, "quality_retry")
    else:
        _append_label(labels, "test_failure_retry")
    if test_result is None:
        _append_label(labels, "missing_validation_retry")
    elif test_result.exit_code == 0 and not quality_retry:
        _append_label(labels, "passing_test_retry")
    failure_class = retry_failure_class(
        agent_status=agent_status,
        test_result=test_result,
        final_diff=final_diff,
        repair_analysis=repair_analysis,
        runtime_trace=runtime_trace or [],
        attempt_history=attempt_history or [],
    )
    if failure_class != "unknown":
        _append_label(labels, f"failure_class_{failure_class}")

    patch_target = _latest_patch_target(runtime_trace or [])
    history_records = list(attempt_history or [])
    target_history_records = _prior_attempt_records_for_target_label(
        history_records,
        patch_target,
    )
    previous_targets = attempted_target_paths(target_history_records)
    if patch_target and patch_target in previous_targets:
        _append_label(labels, "same_target_retry")
    elif patch_target and previous_targets:
        _append_label(labels, "moved_control_point")
    if _latest_patch_old_hash(runtime_trace or []):
        _append_label(labels, "old_span_repair")
    if _latest_target_history_violation(runtime_trace or []):
        _append_label(labels, "target_history_override")
    if any(_is_partial_assertion_progress(record) for record in history_records):
        _append_label(labels, "partial_assertion_progress")
    safety_rejection = safety_gate_rejection_summary(runtime_trace or [])
    if safety_rejection:
        _append_label(labels, "safety_gate_retry")
        if "unbound name" in safety_rejection.lower():
            _append_label(labels, "unbound_name_retry")

    finding_codes = _latest_patch_quality_finding_codes(runtime_trace or [])
    if "broad_exception_swallow" in finding_codes:
        _append_label(labels, "broad_exception_retry")
    if "source_text_recompile" in finding_codes:
        _append_label(labels, "source_recompile_retry")
    if (
        "filename_metadata_rewrite" in finding_codes
        or "module_file_metadata_rewrite" in finding_codes
    ):
        _append_label(labels, "metadata_rewrite_retry")
    if "naked_import_cache_invalidation" in finding_codes:
        _append_label(labels, "naked_cache_invalidation_retry")
    return tuple(labels)


def retry_failure_class(
    *,
    agent_status: str,
    test_result: CommandResult | None,
    final_diff: str = "",
    repair_analysis: RepairOutcomeAnalysis | None = None,
    runtime_trace: list[dict[str, object]] | None = None,
    attempt_history: list[dict[str, object]] | None = None,
) -> str:
    trace = runtime_trace or []
    if _high_risk_patch_quality(repair_analysis):
        return "quality_risk"
    if safety_gate_rejection_summary(trace):
        return "safety_gate_rejection"
    if _latest_target_history_violation(trace):
        return "target_policy_rejected"
    if agent_status == "no_patch_generated":
        return "no_patch"
    if agent_status == "failed" and test_result is None:
        return "no_patch"
    if test_result is None:
        return "missing_validation"
    if assertion_progress_summary(test_result=test_result, final_diff=final_diff):
        return "partial_progress"

    patch_target = _latest_patch_target(trace)
    previous_records = _prior_attempt_records_for_target_label(
        list(attempt_history or []),
        patch_target,
    )
    if patch_target and patch_target in attempted_target_paths(previous_records):
        return "repeated_target_failure"

    if test_result.exit_code == 0:
        return "passing_test_retry"
    if test_result.exit_code != 0:
        return "validation_failed"
    return "unknown"


def feedback_attempt_record(
    *,
    attempt: int,
    agent_status: str,
    agent_summary: str,
    test_result: CommandResult | None,
    final_diff: str,
    runtime_trace: list[dict[str, object]] | None = None,
    repair_analysis: RepairOutcomeAnalysis | None = None,
    attempt_history: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    assertion_progress = assertion_progress_summary(
        test_result=test_result,
        final_diff=final_diff,
    )
    patch_target = _latest_patch_target(runtime_trace or [])
    history_for_class = list(attempt_history or [])
    if patch_target:
        history_for_class.append({"patch_target": patch_target})
    record: dict[str, object] = {
        "attempt": attempt,
        "agent_status": agent_status,
        "agent_summary": _truncate_feedback(agent_summary, limit=180),
        "test_exit_code": test_result.exit_code if test_result is not None else None,
        "diff_sha256_12": _feedback_hash(final_diff),
        "changed_files": _diff_changed_files(final_diff),
        "failure_signature": sandbox_failure_signature(test_result),
        "patch_target": patch_target,
        "patch_old_sha256_12": _latest_patch_old_hash(runtime_trace or []),
        "patch_quality_severity": _latest_patch_quality_severity(runtime_trace or []),
        "patch_quality_findings": _latest_patch_quality_finding_codes(runtime_trace or []),
        "safety_gate_rejection": safety_gate_rejection_summary(runtime_trace or []),
        "failure_class": retry_failure_class(
            agent_status=agent_status,
            test_result=test_result,
            final_diff=final_diff,
            repair_analysis=repair_analysis,
            runtime_trace=runtime_trace or [],
            attempt_history=history_for_class,
        ),
    }
    mounted_paths = _latest_mounted_context_paths(runtime_trace or [])
    if mounted_paths:
        record["mounted_context_paths"] = mounted_paths
    if assertion_progress:
        record["progress_classification"] = "partial_assertion_progress"
        record["progress_summary"] = assertion_progress
    return record


def attempt_history_summary(history: list[dict[str, object]]) -> str:
    if not history:
        return ""
    ineffective_paths = ineffective_target_paths(history)
    lines = [
        "Prior attempts are negative evidence when the failure signature does not change. "
        "Do not keep editing the same target family after an applied patch leaves the "
        "same failure signature unless the new target_rationale explains the new control point."
    ]
    if any(_is_partial_assertion_progress(record) for record in history):
        lines.append(
            "Attempts marked partial_assertion_progress changed a value observed by "
            "the failing assertion. In that case, the same target can still be the "
            "right control point when the next edit addresses the missing asserted "
            "literal or condition instead of repeating the failed diff."
        )
    if ineffective_paths:
        lines.append(
            "Deprioritized target paths for the next retry: "
            + ", ".join(ineffective_paths)
            + ". Prefer an untried control point unless you can state why one of these "
            "paths still contains the exact untested branch."
        )
    previous_signature = ""
    for record in history:
        signature = str(record.get("failure_signature", ""))
        same_marker = (
            " (same failure signature as previous attempt)"
            if signature and signature == previous_signature
            else ""
        )
        changed_files = record.get("changed_files")
        if isinstance(changed_files, list) and changed_files:
            files = ", ".join(str(path) for path in changed_files)
        else:
            files = "none"
        target = str(record.get("patch_target") or "unknown")
        quality = str(record.get("patch_quality_severity") or "")
        quality_suffix = f", quality={quality}" if quality else ""
        safety = "yes" if str(record.get("safety_gate_rejection") or "") else ""
        safety_suffix = f", safety_gate={safety}" if safety else ""
        progress = str(record.get("progress_classification") or "")
        progress_suffix = f", progress={progress}" if progress else ""
        failure_class = str(record.get("failure_class") or "")
        failure_class_suffix = f", class={failure_class}" if failure_class else ""
        lines.append(
            "- Attempt "
            f"{record.get('attempt')}: status={record.get('agent_status')}, "
            f"target={target}, files={files}, test_exit={record.get('test_exit_code')}, "
            f"diff={record.get('diff_sha256_12')}, failure={signature or 'n/a'}"
            f"{quality_suffix}{safety_suffix}{progress_suffix}{failure_class_suffix}"
            f"{same_marker}"
        )
        if signature:
            previous_signature = signature
    return "\n".join(lines)


def ineffective_target_paths(history: list[dict[str, object]]) -> list[str]:
    """Return paths to deprioritize because the same failure signature recurred.

    When a failure signature is seen more than once, every path touched under
    that signature (previously and now) is considered ineffective. Order is
    preserved while membership tests use sets to stay linear in the history
    size.
    """
    paths: list[str] = []
    paths_seen: set[str] = set()
    paths_by_signature: dict[str, list[str]] = {}
    seen_by_signature: dict[str, set[str]] = {}

    def _mark_ineffective(candidate: str) -> None:
        if candidate not in paths_seen:
            paths_seen.add(candidate)
            paths.append(candidate)

    for record in history:
        signature = str(record.get("failure_signature", ""))
        if not signature:
            continue
        record_paths = _record_paths(record)
        if signature in paths_by_signature:
            for path in paths_by_signature[signature]:
                _mark_ineffective(path)
            for path in record_paths:
                _mark_ineffective(path)
        else:
            paths_by_signature[signature] = []
            seen_by_signature[signature] = set()
        signature_seen = seen_by_signature[signature]
        for path in record_paths:
            if path not in signature_seen:
                signature_seen.add(path)
                paths_by_signature[signature].append(path)
    return paths


def attempted_target_paths(history: list[dict[str, object]]) -> list[str]:
    paths: list[str] = []
    for record in history:
        for path in _record_paths(record):
            if path not in paths:
                paths.append(path)
    return paths


def attempted_target_old_span_hashes(
    history: list[dict[str, object]],
) -> dict[str, list[str]]:
    hashes_by_path: dict[str, list[str]] = {}
    for record in history:
        if _is_partial_assertion_progress(record):
            continue
        target = record.get("patch_target")
        old_hash = record.get("patch_old_sha256_12")
        if not isinstance(target, str) or not target:
            continue
        if not isinstance(old_hash, str) or not old_hash:
            continue
        hashes = hashes_by_path.setdefault(target, [])
        if old_hash not in hashes:
            hashes.append(old_hash)
    return hashes_by_path


def mounted_context_paths(history: list[dict[str, object]]) -> list[str]:
    for record in reversed(history):
        value = record.get("mounted_context_paths")
        if not isinstance(value, list):
            continue
        paths: list[str] = []
        for path in value:
            if not isinstance(path, str):
                continue
            normalized = path.strip().lstrip("/")
            if normalized and normalized not in paths:
                paths.append(normalized)
        if paths:
            return paths
    return []


def _is_partial_assertion_progress(record: dict[str, object]) -> bool:
    return record.get("progress_classification") == "partial_assertion_progress"


def _retry_classification_lines(
    *,
    agent_status: str,
    test_result: CommandResult | None,
    final_diff: str,
    repair_analysis: RepairOutcomeAnalysis | None = None,
    runtime_trace: list[dict[str, object]] | None = None,
    attempt_history: list[dict[str, object]] | None = None,
) -> list[str]:
    failure_class = retry_failure_class(
        agent_status=agent_status,
        test_result=test_result,
        final_diff=final_diff,
        repair_analysis=repair_analysis,
        runtime_trace=runtime_trace or [],
        attempt_history=attempt_history or [],
    )
    return [
        f"- Failure class: `{failure_class}`",
        f"- Next retry focus: {_retry_failure_focus(failure_class)}",
        "- Process guard: use the sandbox output, patch diagnostics, and attempt history "
        "before editing; do not spend the retry on a blind variation of the previous diff.",
    ]


def _retry_failure_focus(failure_class: str) -> str:
    focus_by_class = {
        "quality_risk": (
            "replace the high-risk repair mechanism with a lower-risk source control point; "
            "passing focused tests is not enough."
        ),
        "safety_gate_rejection": (
            "repair the rejected target path or exact old/new span before changing behavior."
        ),
        "target_policy_rejected": (
            "choose an allowed, untried source control point or justify the distinct branch "
            "inside a previously rejected target."
        ),
        "no_patch": ("produce one bounded patch plan with a valid target path and exact old span."),
        "missing_validation": (
            "produce a patch and make the validation assumption explicit; there was no "
            "sandbox result to confirm behavior."
        ),
        "partial_progress": (
            "refine the same observed behavior only if the next old span adds the missing "
            "asserted requirement instead of repeating the failed diff."
        ),
        "repeated_target_failure": (
            "avoid the same ineffective target family unless the new rationale names a "
            "different branch, cache read, or dispatch site."
        ),
        "passing_test_retry": (
            "explain why a retry is still required despite exit code zero, then keep the "
            "next patch smaller and evidence-backed."
        ),
        "validation_failed": (
            "localize the failing assertion or exception first, then move the edit to the "
            "branch, cache, registry, or dispatch site that still controls the failure."
        ),
    }
    return focus_by_class.get(
        failure_class,
        "classify the previous failure from saved evidence before choosing the next edit.",
    )


def _retry_guidance(
    *,
    agent_status: str,
    test_result: CommandResult | None,
    final_diff: str,
    repair_analysis: RepairOutcomeAnalysis | None = None,
    runtime_trace: list[dict[str, object]] | None = None,
) -> str:
    if _high_risk_patch_quality(repair_analysis):
        lines = [
            "Retry diagnosis:\n"
            "The previous patch passed the targeted sandbox command, but PatchSmith "
            "classified it as high-risk patch quality. Treat this as a maintainability "
            "and overfit failure, not as a clean validation. Do not reuse the same "
            "high-risk mechanism unchanged; avoid the Patch Plan Diagnostics quality "
            "findings and move the repair to a lower-risk source control point."
        ]
        source_recompile_guidance = _high_risk_source_text_recompile_guidance(runtime_trace or [])
        if source_recompile_guidance:
            lines.append(source_recompile_guidance)
        broad_exception_guidance = _broad_exception_swallow_guidance(runtime_trace or [])
        if broad_exception_guidance:
            lines.append(broad_exception_guidance)
        return "\n".join(lines)
    if agent_status == "patch_generated" and test_result is not None and test_result.exit_code != 0:
        assertion_progress = assertion_progress_summary(
            test_result=test_result,
            final_diff=final_diff,
        )
        lines = [
            "Retry diagnosis:",
        ]
        if assertion_progress:
            lines.append(assertion_progress)
            lines.append(
                "The previous patch reached the failing assertion but was incomplete. "
                "It is acceptable to refine the same target and clean-workspace old "
                "span when the new replacement adds the missing asserted requirement; "
                "do not move away solely because target history lists that path."
            )
        else:
            lines.append(
                "The previous patch applied cleanly, but validation still failed. Treat the "
                "chosen edit location or behavior as insufficient, not as an exact-span problem. "
                "Do not reuse the same old-span hash or return a cosmetic variation of the "
                "previous diff; inspect a different controlling branch, cache, module registry, "
                "or dispatch site if the failure signature is unchanged."
            )
        stale_path_guidance = _stale_path_mismatch_control_point_guidance(test_result)
        if stale_path_guidance:
            lines.append(stale_path_guidance)
        metadata_guidance = _failed_filename_metadata_rewrite_guidance(
            test_result=test_result,
            runtime_trace=runtime_trace or [],
        )
        if metadata_guidance:
            lines.append(metadata_guidance)
        broad_exception_guidance = _broad_exception_swallow_guidance(runtime_trace or [])
        if broad_exception_guidance:
            lines.append(broad_exception_guidance)
        cache_guidance = _failed_naked_import_cache_invalidation_guidance(
            test_result=test_result,
            runtime_trace=runtime_trace or [],
        )
        if cache_guidance:
            lines.append(cache_guidance)
        return "\n".join(lines)
    if agent_status == "no_patch_generated":
        safety_rejection = safety_gate_rejection_summary(runtime_trace or [])
        if safety_rejection:
            lines = [
                "Retry diagnosis:",
                "PatchSmith's safety gate rejected the previous bounded edit before it "
                "could become a patch. Treat this as a plan-repair problem, not as a "
                "sandbox validation result. Do not repeat the rejected replacement; "
                "repair the exact safety finding below while keeping the same issue "
                "mechanism in view.",
                safety_rejection,
            ]
            if "unbound name" in safety_rejection.lower():
                lines.append(
                    "For unbound-name rejections, do not call a new helper unless the "
                    "returned replacement also defines it. Prefer using existing local "
                    "names from the old span or choosing a slightly larger exact span "
                    "that includes the helper definition."
                )
            return "\n".join(lines)
        return (
            "Retry diagnosis:\n"
            "The previous edit was rejected or no patch was generated. First repair the "
            "target path and exact old span before changing behavior."
        )
    return ""


def _retry_intro(*, attempt: int, quality_retry: bool) -> str:
    if quality_retry:
        return (
            f"Previous DeepAgents repair attempt {attempt} passed the targeted sandbox "
            "command, but PatchSmith marked the patch quality as high-risk. The risky "
            "patch has been reverted before this retry; repair the clean workspace state "
            "with one bounded replacement. Do not return the same high-risk diff "
            "unchanged. Prefer a lower-risk source control point over runtime code-object "
            "mutation, direct source-text recompilation, broad exception swallowing, "
            "metadata rewriting, or broad fallback logic."
        )
    return (
        f"Previous DeepAgents repair attempt {attempt} did not validate. "
        "The failed patch has been reverted before this retry; repair the "
        "clean workspace state with one bounded replacement. "
        "Do not return the same failed diff unchanged; use the sandbox "
        "failure to move the edit to the branch or cache site that still "
        "controls the observed behavior. "
        "You may fix a prior bad patch or provide a different exact old span "
        "if the previous edit was rejected. Before choosing the next edit, "
        "check whether the previous patch is on the code path reached by the "
        "unchanged failure; if not, move the fix to the earlier branch, cache "
        "return, or dispatch point that controls the failing behavior."
    )


def _required_retry_behavior(
    *,
    diff_hash: str,
    quality_retry: bool,
    partial_assertion_progress: bool = False,
) -> list[str]:
    shared = [
        "- If the previous edit was rejected, fix the target path and exact old span before "
        "changing behavior.",
        "- If Patch Plan Diagnostics includes a nearest exact source excerpt, copy that "
        "excerpt verbatim into the next `old` field when it is the intended target.",
        "- Do not return an import-only patch for a behavioral failure unless the sandbox "
        "failure is ImportError, ModuleNotFoundError, or NameError and the imported name "
        "directly fixes that failure; do not add duplicate imports.",
    ]
    if quality_retry:
        return [
            "- Do not return the same high-risk diff unchanged.",
            f"- Do not return a patch with the same risky diff hash `{diff_hash}`.",
            "- Avoid the high-risk quality findings listed in Patch Plan Diagnostics.",
            "- Prefer the earlier import, cache, compile, dispatch, or collection control "
            "point over mutating runtime code objects, directly recompiling source text, "
            "or rewriting code-object metadata.",
            *shared,
        ]
    return [
        "- Do not return the same failed diff unchanged.",
        f"- Do not return a patch with the same failed diff hash `{diff_hash}`.",
        (
            "- If the previous patch changed the value shown by the failing assertion "
            "but still missed a required literal or condition, refine the same target "
            "span with the missing requirement; do not abandon it solely because it "
            "appears in target history."
            if partial_assertion_progress
            else "- If the previous patch applied but tests still failed, move to the "
            "earlier branch, cache, dispatch point, or runtime mechanism that still "
            "controls the failure."
        ),
        *shared,
    ]


def _high_risk_patch_quality(repair_analysis: RepairOutcomeAnalysis | None) -> bool:
    return (
        repair_analysis is not None
        and repair_analysis.failure_category == "high_risk_patch_quality"
        and repair_analysis.tests_passed is True
    )


def _failed_filename_metadata_rewrite_guidance(
    *,
    test_result: CommandResult,
    runtime_trace: list[dict[str, object]],
) -> str:
    finding_codes = _latest_patch_quality_finding_codes(runtime_trace)
    code_object_rewrite = "filename_metadata_rewrite" in finding_codes
    module_file_rewrite = "module_file_metadata_rewrite" in finding_codes
    if not code_object_rewrite and not module_file_rewrite:
        return ""
    signature = sandbox_failure_signature(test_result)
    if "path:" not in signature:
        return ""
    if module_file_rewrite and not code_object_rewrite:
        return (
            "Rejected repair hypothesis:\n"
            "The previous patch rewrote module `__file__` metadata, but the sandbox "
            "still reported the stale path mismatch. Do not keep assigning `__file__` "
            "on cached modules as a proxy for recompilation. Prefer invalidating stale "
            "module or bytecode cache entries, or recompiling from the current source "
            "path at the import, `_read_pyc`, `compile`, or `exec` control point."
        )
    return (
        "Rejected repair hypothesis:\n"
        "The previous patch rewrote code-object filename metadata, but the sandbox still "
        "reported the stale path mismatch. Do not keep setting or replacing `co_filename` "
        "directly, and do not switch to assigning module `__file__` as a metadata-only "
        "proxy. Prefer invalidating stale bytecode/module cache entries or recompiling "
        "from the current source path at the import, `_read_pyc`, `compile`, or `exec` "
        "control point."
    )


def _high_risk_source_text_recompile_guidance(
    runtime_trace: list[dict[str, object]],
) -> str:
    if "source_text_recompile" not in _latest_patch_quality_finding_codes(runtime_trace):
        return ""
    return (
        "Rejected high-risk repair mechanism:\n"
        "The previous patch bypassed cache validation by recompiling source text directly "
        "with `compile(...read_text(...), ...)`. Do not keep recompiling source as the "
        "repair. For stale bytecode/module cache failures, prefer a bounded check that "
        "rejects or invalidates the stale cached object before it is returned, such as "
        "comparing the cached code object's full `co_filename` to the current source path "
        "and returning `None` to trigger the existing compile path. Do not use a "
        "basename-only `.name` check when the observed failure differs by parent path."
    )


def _broad_exception_swallow_guidance(runtime_trace: list[dict[str, object]]) -> str:
    if "broad_exception_swallow" not in _latest_patch_quality_finding_codes(runtime_trace):
        return ""
    return (
        "Rejected high-risk repair mechanism:\n"
        "The previous patch introduced broad exception swallowing such as "
        "`except Exception`, `BaseException`, or bare `except:` around the repair. "
        "Do not keep a catch-and-fallback wrapper as the fix. Prefer an explicit "
        "precondition check at the branch that returns stale or invalid data, or move "
        "the edit to the earlier read, cache, compile, dispatch, or validation site "
        "that controls the bad value. If a defensive boundary is genuinely required, "
        "catch the specific expected exception and make the fallback behavior explicit "
        "instead of silently returning the original value."
    )


def _stale_path_mismatch_control_point_guidance(test_result: CommandResult) -> str:
    signature = sandbox_failure_signature(test_result)
    if "path:" not in signature:
        return ""
    return (
        "Stale path mismatch control-point guidance:\n"
        "The unchanged sandbox failure compares old and new filesystem paths. Prefer the "
        "source branch that returns, reads, or compiles the stale filename, such as "
        "`_read_pyc`, bytecode cache validation, `compile`, `exec`, or a `sys.modules` "
        "cache-return guard. Avoid late call-site side effects like only calling "
        "`importlib.invalidate_caches()` after a copy or rename unless that branch "
        "directly controls the stale value."
    )


def _failed_naked_import_cache_invalidation_guidance(
    *,
    test_result: CommandResult,
    runtime_trace: list[dict[str, object]],
) -> str:
    if "naked_import_cache_invalidation" not in _latest_patch_quality_finding_codes(runtime_trace):
        return ""
    signature = sandbox_failure_signature(test_result)
    if "path:" not in signature:
        return ""
    return (
        "Rejected repair hypothesis:\n"
        "The previous patch only invalidated importlib caches, but the sandbox still "
        "reported the stale path mismatch. Do not keep adding cache side effects at "
        "call sites that do not read or compile the stale value. Move the repair to "
        "the stale module, bytecode, import, `_read_pyc`, `compile`, or `exec` branch "
        "that directly returns the old path."
    )


def _latest_patch_quality_severity(runtime_trace: list[dict[str, object]]) -> str:
    quality = _latest_patch_quality(runtime_trace)
    severity = quality.get("severity")
    return str(severity) if severity else ""


def _latest_patch_quality_finding_codes(runtime_trace: list[dict[str, object]]) -> list[str]:
    quality = _latest_patch_quality(runtime_trace)
    findings = quality.get("findings")
    if not isinstance(findings, list):
        return []
    codes: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        code = finding.get("code")
        if isinstance(code, str) and code and code not in codes:
            codes.append(code)
    return codes


def _latest_patch_quality(runtime_trace: list[dict[str, object]]) -> dict[str, object]:
    for event in reversed(runtime_trace):
        quality = event.get("quality")
        if isinstance(quality, dict):
            return quality
    return {}


def _diff_changed_files(diff: str) -> list[str]:
    paths: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        parts = line.split()
        if len(parts) < 4 or not parts[2].startswith("a/"):
            continue
        path = parts[2][2:]
        if path not in paths:
            paths.append(path)
    return paths


def _latest_patch_target(runtime_trace: list[dict[str, object]]) -> str:
    for event in reversed(runtime_trace):
        patch_plan = event.get("patch_plan")
        if isinstance(patch_plan, dict):
            path = patch_plan.get("path")
            if path:
                return str(path)
        metadata = event.get("metadata")
        if isinstance(metadata, dict):
            for key in ("target_history_violation", "target_selection_violation"):
                violation = metadata.get(key)
                if isinstance(violation, dict):
                    path = violation.get("path")
                    if path:
                        return str(path)
    return ""


def _latest_patch_old_hash(runtime_trace: list[dict[str, object]]) -> str:
    for event in reversed(runtime_trace):
        patch_plan = event.get("patch_plan")
        if not isinstance(patch_plan, dict):
            continue
        old = patch_plan.get("old")
        if not isinstance(old, dict):
            continue
        old_hash = old.get("sha256_12")
        if old_hash:
            return str(old_hash)
    return ""


def _latest_mounted_context_paths(runtime_trace: list[dict[str, object]]) -> list[str]:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        contract = metadata.get("deepagents_contract")
        if not isinstance(contract, dict):
            continue
        context_budget = contract.get("context_budget")
        if not isinstance(context_budget, dict):
            continue
        mounted_paths = context_budget.get("mounted_paths")
        if not isinstance(mounted_paths, list):
            continue
        paths: list[str] = []
        for path in mounted_paths:
            if not isinstance(path, str):
                continue
            normalized = path.strip().lstrip("/")
            if normalized and normalized not in paths:
                paths.append(normalized)
        if paths:
            return paths
    return []


def _latest_target_history_violation(runtime_trace: list[dict[str, object]]) -> bool:
    for event in reversed(runtime_trace):
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if isinstance(metadata.get("target_history_violation"), dict):
            return True
        if isinstance(metadata.get("target_selection_violation"), dict):
            return True
    return False


def _prior_attempt_records_for_target_label(
    records: list[dict[str, object]],
    current_target: str,
) -> list[dict[str, object]]:
    if not records or not current_target:
        return records
    last_target = records[-1].get("patch_target")
    if isinstance(last_target, str) and last_target == current_target:
        return records[:-1]
    return records


def _append_label(labels: list[str], label: str) -> None:
    if label not in labels:
        labels.append(label)


def _record_paths(record: dict[str, object]) -> list[str]:
    paths: list[str] = []
    target = record.get("patch_target")
    if isinstance(target, str) and target:
        paths.append(target)
    changed_files = record.get("changed_files")
    if isinstance(changed_files, list):
        for path in changed_files:
            if isinstance(path, str) and path and path not in paths:
                paths.append(path)
    return paths


def _truncate_feedback(text: str, limit: int = 4_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _feedback_hash(text: str) -> str:
    if not text:
        return "empty"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
