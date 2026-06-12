"""PatchSmith runner invocation for public issue repair attempts."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from patchsmith.evaluation._helpers import _dedupe_preserve_order, _path_has_text
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    public_issue_repair_attempt_issue_text,
    source_hint_context_paths,
)
from patchsmith.ingest import clone_or_copy_repository
from patchsmith.models import RunRequest
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_source_hints as _public_issue_fixture_source_hints,
)
from patchsmith.public_issue_fixtures import (
    write_public_issue_fixture_files as _write_public_issue_fixture_files,
)


@dataclass(frozen=True)
class PublicIssueRepairRunOutcome:
    run_id: str
    run_status: str
    report_path: str
    trace_path: str
    final_diff_path: str
    test_exit_code: int | None
    patch_generated: bool


def run_public_issue_repair_attempt(
    *,
    runner: Any,
    repo_path: str,
    issue_text: str,
    issue_url: str | None,
    validation_command: str,
    validation_fixture_paths: list[str],
    validation_fixture_files: list[dict[str, str]],
    validation_source_hints: list[str],
    runtime: str,
    planner: str,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    max_retries: int,
) -> PublicIssueRepairRunOutcome:
    run_repo = repo_path
    source_hints = _dedupe_preserve_order(
        [
            *validation_source_hints,
            *_public_issue_fixture_source_hints(
                repo_path=Path(repo_path),
                fixture_files=validation_fixture_files,
            ),
        ]
    )
    run_issue_text = public_issue_repair_attempt_issue_text(
        issue_text=issue_text,
        validation_command=validation_command,
        validation_fixture_paths=validation_fixture_paths,
        validation_fixture_files=validation_fixture_files,
        source_hints=source_hints,
    )
    context_paths = tuple(source_hint_context_paths(source_hints))
    if validation_fixture_files:
        with tempfile.TemporaryDirectory(prefix="patchsmith-public-repair-fixtures-") as tmp_dir:
            fixture_workspace = Path(tmp_dir) / "repo"
            snapshot = clone_or_copy_repository(repo_path, fixture_workspace)
            _write_public_issue_fixture_files(
                repo_path=snapshot.repo_path,
                fixture_files=validation_fixture_files,
            )
            run_repo = str(snapshot.repo_path)
            return _run_repair(
                runner=runner,
                repo=run_repo,
                issue_text=run_issue_text,
                issue_url=issue_url,
                validation_command=validation_command,
                runtime=runtime,
                planner=planner,
                max_retries=max_retries,
                context_provider=context_provider,
                sandbox_mode=sandbox_mode,
                sandbox_image=sandbox_image,
                context_paths=context_paths,
            )
    return _run_repair(
        runner=runner,
        repo=run_repo,
        issue_text=run_issue_text,
        issue_url=issue_url,
        validation_command=validation_command,
        runtime=runtime,
        planner=planner,
        max_retries=max_retries,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        context_paths=context_paths,
    )


def _run_repair(
    *,
    runner: Any,
    repo: str,
    issue_text: str,
    issue_url: str | None,
    validation_command: str,
    runtime: str,
    planner: str,
    max_retries: int,
    context_provider: str,
    sandbox_mode: str,
    sandbox_image: str,
    context_paths: tuple[str, ...],
) -> PublicIssueRepairRunOutcome:
    run_result = runner.run(
        RunRequest(
            repo=repo,
            issue_text=issue_text,
            issue_url=issue_url,
            test_command=validation_command,
            runtime=runtime,
            planner=planner,
            max_retries=max_retries,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            context_paths=context_paths,
        )
    )
    test_exit_code = (
        run_result.test_result.exit_code if run_result.test_result is not None else None
    )
    return PublicIssueRepairRunOutcome(
        run_id=run_result.run_id,
        run_status=run_result.status,
        report_path=str(run_result.report_path),
        trace_path=str(run_result.trace_path),
        final_diff_path=str(run_result.final_diff_path),
        test_exit_code=test_exit_code,
        patch_generated=_path_has_text(run_result.final_diff_path),
    )


__all__ = ["PublicIssueRepairRunOutcome", "run_public_issue_repair_attempt"]
