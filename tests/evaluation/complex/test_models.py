from __future__ import annotations

import pytest

from patchsmith.evaluation_models import (
    ComplexBenchmarkResult,
    ContextEvidence,
    CostEvidence,
    ModelUsage,
    PatchOutcome,
    ProcessQuality,
    RubricEvidence,
    TraceEvidence,
)

pytestmark = pytest.mark.unit


def test_complex_result_exposes_domain_evidence_views() -> None:
    result = _result()

    assert result.model_usage == ModelUsage(
        provider="deepagents_openai_chat",
        response_count=3,
        input_tokens=1000,
        output_tokens=250,
        total_tokens=1250,
        estimated_cost_usd=0.04,
    )
    assert result.patch_outcome == PatchOutcome(
        status="validated",
        strict_status="validated",
        reproduced=True,
        patch_generated=True,
        validation_passed=True,
        test_exit_code=0,
        progress_score=1.0,
        progress_stage="validated",
        failure_class="validated",
        harness_layer="validation",
        quality_severity="low",
        quality_warning=True,
        quality_codes=("style",),
        target_paths=("src/example.py",),
        localized_target_paths=("src/example.py", "tests/test_example.py"),
        target_alignment_status="aligned",
        target_aligned=True,
    )
    assert result.trace_evidence == TraceEvidence(
        trace_path="artifacts/trace.jsonl",
        report_path="artifacts/report.md",
        trace_event_count=12,
        runtime_node_count=4,
        failed_trace_event_count=1,
        retry_event_count=2,
        retry_feedback_artifacts=("artifacts/retry.md",),
        retry_feedback_artifact_count=1,
        retry_labels=("repair",),
        retry_label_counts={"repair": 1},
        retry_failure_classes=("test_failure",),
        retry_failure_class_counts={"test_failure": 1},
    )
    assert result.context_evidence == ContextEvidence(
        virtual_file_count=2,
        virtual_file_paths=("src/example.py", "tests/test_example.py"),
        max_context_files=2,
        context_budgeted=True,
        context_budget_manifest_path="manifests/context-budget.json",
        context_budget_manifest_read_first=True,
        context_budget_omitted_file_count=1,
        context_budget_omitted_paths=("docs/example.md",),
        repo_map_manifest_path="manifests/repo-map.json",
        repo_map_manifest_read_first=True,
        repo_instructions_manifest_path="manifests/repo-instructions.md",
        repo_instructions_manifest_read_first=True,
        repair_interface_manifest_path="manifests/repair-interface.md",
        repair_interface_manifest_read_first=True,
    )
    assert result.rubric_evidence == RubricEvidence(
        manifest_path="manifests/acceptance-rubric.md",
        manifest_read_first=True,
        aligned=True,
    )
    assert result.process_quality == ProcessQuality(
        debuggability_score=0.8,
        agent_trajectory_score=0.9,
        todo_planning=True,
        constrained_filesystem=True,
        specialist_review=True,
        guardrails=True,
        structured_output=True,
        retry_feedback=True,
        patch_diagnostics=True,
        contextual_verifier=True,
        label="solid",
        score=0.95,
        flags=("used_tests",),
    )
    assert result.cost_evidence == CostEvidence(
        model_usage=result.model_usage,
        live_cost_budget_usd=0.05,
        live_cost_budget_overage=True,
        live_cost_budget_overage_usd=0.01,
        resource_budgeted=True,
        resource_budget_read_first=True,
        resource_budget_max_model_responses=6,
        resource_budget_max_model_tokens=90_000,
    )
    assert result.repair_attempt.patch_outcome is not result.patch_outcome
    assert result.repair_attempt.patch_outcome == result.patch_outcome
    assert result.repair_attempt.cost_evidence == result.cost_evidence


def test_complex_result_to_dict_keeps_backward_compatible_flat_schema() -> None:
    result = _result()

    row = result.to_dict()

    assert row["model_provider"] == "deepagents_openai_chat"
    assert row["deepagents_context_budgeted"] is True
    assert row["patch_quality_codes"] == ("style",)
    assert row["preflight_gates"] == [{"name": "budget", "status": "passed"}]
    assert "model_usage" not in row
    assert "patch_outcome" not in row
    assert "trace_evidence" not in row
    assert "context_evidence" not in row
    assert "rubric_evidence" not in row
    assert "process_quality" not in row
    assert "cost_evidence" not in row
    assert "repair_attempt" not in row


def _result() -> ComplexBenchmarkResult:
    return ComplexBenchmarkResult(
        task_id="task-1",
        repository="example/repo",
        issue_url="https://github.com/example/repo/issues/1",
        status="validated",
        strict_status="validated",
        runtime="deepagents",
        planner="deepagents",
        context_provider="native_hybrid",
        reproduced=True,
        patch_generated=True,
        validation_passed=True,
        test_exit_code=0,
        trace_path="artifacts/trace.jsonl",
        report_path="artifacts/report.md",
        progress_score=1.0,
        progress_stage="validated",
        failure_class="validated",
        harness_layer="validation",
        patch_quality_severity="low",
        patch_quality_warning=True,
        patch_quality_codes=("style",),
        patch_target_paths=("src/example.py",),
        localized_target_paths=("src/example.py", "tests/test_example.py"),
        target_alignment_status="aligned",
        patch_target_aligned=True,
        retry_feedback_artifacts=("artifacts/retry.md",),
        retry_feedback_artifact_count=1,
        retry_labels=("repair",),
        retry_label_counts={"repair": 1},
        retry_failure_classes=("test_failure",),
        retry_failure_class_counts={"test_failure": 1},
        deepagents_virtual_file_count=2,
        deepagents_virtual_file_paths=("src/example.py", "tests/test_example.py"),
        deepagents_max_context_files=2,
        deepagents_context_budgeted=True,
        deepagents_context_budget_manifest_path="manifests/context-budget.json",
        deepagents_context_budget_manifest_read_first=True,
        deepagents_context_budget_omitted_file_count=1,
        deepagents_context_budget_omitted_paths=("docs/example.md",),
        deepagents_repo_map_manifest_path="manifests/repo-map.json",
        deepagents_repo_map_manifest_read_first=True,
        deepagents_repo_instructions_manifest_path=("manifests/repo-instructions.md"),
        deepagents_repo_instructions_manifest_read_first=True,
        deepagents_acceptance_rubric_manifest_path=("manifests/acceptance-rubric.md"),
        deepagents_acceptance_rubric_manifest_read_first=True,
        deepagents_acceptance_rubric_aligned=True,
        deepagents_repair_interface_manifest_path=("manifests/repair-interface.md"),
        deepagents_repair_interface_manifest_read_first=True,
        deepagents_resource_budgeted=True,
        deepagents_resource_budget_read_first=True,
        deepagents_resource_budget_max_model_responses=6,
        deepagents_resource_budget_max_model_tokens=90_000,
        trace_event_count=12,
        runtime_node_count=4,
        failed_trace_event_count=1,
        retry_event_count=2,
        debuggability_score=0.8,
        agent_trajectory_score=0.9,
        todo_planning=True,
        constrained_filesystem=True,
        specialist_review=True,
        guardrails=True,
        structured_output=True,
        retry_feedback=True,
        patch_diagnostics=True,
        contextual_verifier=True,
        process_quality_label="solid",
        process_quality_score=0.95,
        process_quality_flags=("used_tests",),
        model_provider="deepagents_openai_chat",
        response_count=3,
        input_tokens=1000,
        output_tokens=250,
        total_tokens=1250,
        estimated_cost_usd=0.04,
        live_cost_budget_usd=0.05,
        live_cost_budget_overage=True,
        live_cost_budget_overage_usd=0.01,
        attempt_index=2,
        attempt_count=3,
        preflight_status="passed",
        preflight_gates=[{"name": "budget", "status": "passed"}],
    )
