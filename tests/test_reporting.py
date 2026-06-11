from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.models import (
    CommandResult,
    RepositorySnapshot,
    RetrievedContext,
    RunRequest,
    TraceEvent,
)
from patchsmith.reporting import render_run_report
from patchsmith.security import CommandPolicyDecision

pytestmark = pytest.mark.unit


def _snapshot(tmp_path: Path) -> RepositorySnapshot:
    return RepositorySnapshot(
        repo_url="https://example.com/repo.git",
        repo_path=tmp_path,
        commit_hash="abc1234",
        branch="main",
        file_count=3,
        language_summary={"python": 3},
        package_manager="pip",
        test_commands=["pytest"],
    )


def test_render_run_report_includes_core_sections(tmp_path: Path) -> None:
    request = RunRequest(repo="https://example.com/repo.git", issue_text="add() subtracts")
    context = RetrievedContext(
        path="src/calc.py",
        rank=1,
        score=0.9,
        method="keyword",
        matched_terms=["add"],
        excerpt="def add(a, b):",
    )
    test_result = CommandResult(
        command="pytest",
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_ms=10,
        timed_out=False,
        policy_decision=CommandPolicyDecision(True, "allowed", ("pytest",)),
    )
    report = render_run_report(
        run_id="run-123",
        request=request,
        snapshot=_snapshot(tmp_path),
        retrieved_context=[context],
        test_result=test_result,
        final_diff="--- a/src/calc.py\n+++ b/src/calc.py",
        trace_events=[
            TraceEvent(
                run_id="run-123",
                event_id="evt-1",
                node_name="ingest",
                event_type="node",
                status="completed",
                started_at="2026-01-01T00:00:00Z",
                completed_at="2026-01-01T00:00:01Z",
                latency_ms=1000,
            )
        ],
        status="completed",
    )
    assert "# PatchSmith Run Report" in report
    assert "run-123" in report
    assert "src/calc.py" in report
    assert "## Summary" in report


def test_render_run_report_handles_missing_test_result(tmp_path: Path) -> None:
    request = RunRequest(repo="local-repo", issue_text="bug")
    report = render_run_report(
        run_id="run-456",
        request=request,
        snapshot=_snapshot(tmp_path),
        retrieved_context=[],
        test_result=None,
        final_diff="",
        trace_events=[],
        status="failed",
    )
    assert "run-456" in report
    assert "`failed`" in report
