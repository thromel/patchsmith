"""Result construction for public issue repair attempts."""

from __future__ import annotations

from patchsmith.evaluation._helpers import _dedupe_preserve_order
from patchsmith.evaluation_models import IssueCorpusPublicRepairAttemptResult


def public_issue_repair_attempt_result(
    *,
    task_id: str | None,
    repository: str | None,
    issue_url: str | None,
    status: str,
    readiness_status: str,
    repo_path: str | None,
    repo_exists: bool,
    repair_command: str | None,
    validation_command: str | None,
    validation_fixture_paths: list[str],
    reproduction_execution_status: str | None,
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    dry_run: bool,
    run_id: str | None,
    run_status: str | None,
    report_path: str | None,
    trace_path: str | None,
    final_diff_path: str | None,
    test_exit_code: int | None,
    patch_generated: bool,
    errors: list[str],
    warnings: list[str],
    evidence: list[str],
    next_actions: list[str],
) -> IssueCorpusPublicRepairAttemptResult:
    return IssueCorpusPublicRepairAttemptResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        readiness_status=readiness_status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        repair_command=repair_command,
        validation_command=validation_command,
        validation_fixture_paths=validation_fixture_paths,
        reproduction_execution_status=reproduction_execution_status,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        dry_run=dry_run,
        run_id=run_id,
        run_status=run_status,
        report_path=report_path,
        trace_path=trace_path,
        final_diff_path=final_diff_path,
        test_exit_code=test_exit_code,
        patch_generated=patch_generated,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )


__all__ = ["public_issue_repair_attempt_result"]
