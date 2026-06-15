from __future__ import annotations

from patchsmith.evaluation.trajectory import agent_trajectory_metrics


def test_agent_trajectory_tracks_contextual_verifier_without_score_drift() -> None:
    metrics = agent_trajectory_metrics(
        [
            {
                "node_name": "runtime.todo",
                "event_type": "runtime_node",
                "payload": {"node": "todo"},
            },
            {
                "node_name": "runtime.plan",
                "event_type": "runtime_node",
                "payload": {
                    "node": "plan",
                    "metadata": {
                        "deepagents_contract": {
                            "filesystem_policy": {
                                "allowed_read_paths": [
                                    "/.patchsmith/acceptance-rubric.md",
                                    "/src/pkg.py",
                                ]
                            },
                            "contextual_verifier": {
                                "type": "acceptance_rubric",
                                "manifest_path": "/.patchsmith/acceptance-rubric.md",
                                "required": True,
                            },
                            "planning_policy": {
                                "todos_required": True,
                                "one_bounded_replacement": True,
                                "acceptance_rubric_manifest_read_first": True,
                            },
                            "response_format": "PatchPlan",
                            "subagents": [{"name": "patch-reviewer"}],
                        },
                    },
                    "patch_plan": {"path": "src/pkg.py"},
                },
            },
        ]
    )

    assert metrics.contextual_verifier is True
    assert metrics.todo_planning is True
    assert metrics.constrained_filesystem is True
    assert metrics.specialist_review is True
    assert metrics.guardrails is True
    assert metrics.structured_output is True
    assert metrics.patch_diagnostics is True
    assert metrics.retry_feedback is False
    assert metrics.process_quality_label == "risky"
    assert metrics.process_quality_flags == ("missing_verification",)
    assert metrics.score == 6 / 7


def test_agent_trajectory_process_quality_marks_verified_trace_solid() -> None:
    metrics = agent_trajectory_metrics(
        [
            {
                "node_name": "runtime.edit",
                "event_type": "runtime_node",
                "status": "completed",
                "payload": {"node": "edit"},
            },
            {
                "node_name": "test",
                "event_type": "sandbox_command",
                "status": "completed",
                "payload": {"exit_code": 0},
            },
            {
                "node_name": "analyze",
                "event_type": "repair_outcome",
                "status": "validated",
                "payload": {"tests_passed": True},
            },
        ]
    )

    assert metrics.process_quality_label == "solid"
    assert metrics.process_quality_score == 1.0
    assert metrics.process_quality_flags == ()


def test_agent_trajectory_process_quality_flags_blind_retry() -> None:
    metrics = agent_trajectory_metrics(
        [
            {
                "node_name": "feedback_retry",
                "event_type": "repair_retry",
                "status": "scheduled",
                "payload": {},
            },
            {
                "node_name": "test",
                "event_type": "sandbox_command",
                "status": "completed",
                "payload": {"exit_code": 0},
            },
        ]
    )

    assert metrics.process_quality_label == "risky"
    assert metrics.process_quality_score == 0.7
    assert metrics.process_quality_flags == ("blind_retry",)
