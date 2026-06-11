from pathlib import Path
from types import SimpleNamespace

from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_repair_attempts,
    summarize_public_issue_reproduction_plan,
    summarize_public_issue_reproduction_spec_validation,
)


def test_public_issue_reproduction_plan_summary_counts_statuses_and_fixtures() -> None:
    summary = summarize_public_issue_reproduction_plan(
        tasks_dir=Path("tasks"),
        focused_plan_path=None,
        results=[
            SimpleNamespace(
                status="planned",
                manual_spec_required=True,
                reproduction_command="python3 -m pytest",
                policy_allowed=True,
                fixture_files=[{"path": "tests/test_bug.py"}],
            ),
            SimpleNamespace(
                status="blocked",
                manual_spec_required=False,
                reproduction_command=None,
                policy_allowed=False,
                fixture_files=[],
            ),
        ],
    )

    assert summary.generated_at.endswith("Z")
    assert summary.task_count == 2
    assert summary.planned_tasks == 1
    assert summary.blocked_tasks == 1
    assert summary.manual_spec_required_tasks == 1
    assert summary.fixture_file_count == 1


def test_public_issue_spec_validation_summary_counts_review_gaps() -> None:
    summary = summarize_public_issue_reproduction_spec_validation(
        specs_path=Path("specs.json"),
        tasks_dir=Path("tasks"),
        focused_plan_path=Path("focused.json"),
        spec_count=2,
        results=[
            SimpleNamespace(
                status="ready",
                spec_present=True,
                expected_failure_signals=["AssertionError"],
                reproduction_command="python3 -m pytest",
                policy_allowed=True,
                errors=[],
                fixture_files=[],
            ),
            SimpleNamespace(
                status="blocked",
                spec_present=False,
                expected_failure_signals=[],
                reproduction_command="python3 -m pytest",
                policy_allowed=False,
                errors=["reproduction spec task_id has no materialized task"],
                fixture_files=[{"path": "tests/test_bug.py"}],
            ),
        ],
    )

    assert summary.spec_count == 2
    assert summary.ready_tasks == 1
    assert summary.blocked_tasks == 1
    assert summary.missing_spec_tasks == 1
    assert summary.empty_signal_tasks == 1
    assert summary.policy_blocked_tasks == 1
    assert summary.extra_spec_tasks == 1
    assert summary.fixture_file_tasks == 1


def test_public_issue_repair_attempt_summary_counts_validated_failed_and_blocked() -> None:
    summary = summarize_public_issue_repair_attempts(
        readiness_path=Path("readiness.json"),
        tasks_dir=None,
        dry_run=False,
        allow_warnings=True,
        runtime="deepagents",
        planner="deepagents",
        context_provider="native_hybrid",
        sandbox_mode="local",
        sandbox_image="python:3.12-slim",
        max_retries=1,
        results=[
            SimpleNamespace(status="validated", reproduction_execution_status="reproduced"),
            SimpleNamespace(status="failed", reproduction_execution_status="reproduced"),
            SimpleNamespace(status="blocked", reproduction_execution_status="blocked"),
            SimpleNamespace(status="warning", reproduction_execution_status="reproduced"),
        ],
    )

    assert summary.task_count == 4
    assert summary.attempted_tasks == 2
    assert summary.validated_tasks == 1
    assert summary.failed_tasks == 1
    assert summary.blocked_tasks == 1
    assert summary.warning_tasks == 1
    assert summary.reproduced_input_tasks == 3
