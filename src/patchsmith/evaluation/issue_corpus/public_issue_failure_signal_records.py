"""Per-record public issue failure-signal discovery execution."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _optional_string,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.log_signals import (
    candidate_failure_signals_from_logs as _candidate_failure_signals_from_logs,
)
from patchsmith.evaluation_models import IssueCorpusPublicFailureSignalDiscoveryResult
from patchsmith.ingest import clone_or_copy_repository
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files as _normalize_public_issue_fixture_files,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_source_hints as _normalize_public_issue_source_hints,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
)
from patchsmith.public_issue_fixtures import (
    write_public_issue_fixture_files as _write_public_issue_fixture_files,
)
from patchsmith.security import CommandPolicy


def discover_public_issue_failure_signal_record(
    *,
    record: dict[str, Any],
    run_logs_dir: Path,
    runner: Any | None,
    policy: CommandPolicy,
    sandbox_mode: str,
    sandbox_image: str,
    sandbox_network: str,
    timeout_seconds: int,
    dry_run: bool,
) -> IssueCorpusPublicFailureSignalDiscoveryResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    _source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        record.get("source_hints")
    )
    errors.extend(fixture_errors)
    errors.extend(source_hint_errors)
    policy_allowed = False
    policy_reason: str | None = None
    workspace: Path | None = None

    if plan_status == "blocked":
        errors.append("reproduction plan is blocked")
    elif plan_status not in {"planned", "warning"}:
        warnings.append(f"reproduction plan status is {plan_status}")

    if repo_path_value:
        repo_path = Path(repo_path_value)
        if repo_path.exists() and repo_path.is_dir():
            workspace = repo_path
        else:
            errors.append(f"repository snapshot is not available: {repo_path_value}")
    else:
        errors.append("reproduction plan record has no repo_path")

    if not command:
        errors.append("reproduction command is missing")
    elif workspace is not None:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if not decision.allowed:
            errors.append(f"reproduction command rejected by policy: {decision.reason}")

    if errors:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve discovery blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [
                    *next_actions,
                    "rerun with --execute to observe candidate failure logs",
                ]
            ),
        )

    assert runner is not None
    assert workspace is not None
    assert command is not None
    run_dir = run_logs_dir / _safe_artifact_name(task_id or repository or "task")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_files:
            with tempfile.TemporaryDirectory(prefix="patchsmith-public-repro-fixtures-") as tmp_dir:
                fixture_workspace = Path(tmp_dir) / "repo"
                snapshot = clone_or_copy_repository(str(workspace), fixture_workspace)
                _write_public_issue_fixture_files(
                    repo_path=snapshot.repo_path,
                    fixture_files=fixture_files,
                )
                command_result = runner.run(
                    command=command,
                    workspace=snapshot.repo_path,
                    timeout_seconds=timeout_seconds,
                )
        else:
            command_result = runner.run(
                command=command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
    except (OSError, ValueError) as error:
        return IssueCorpusPublicFailureSignalDiscoveryResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=None,
            timed_out=False,
            duration_ms=0,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=None,
            stderr_path=None,
            fixture_paths=fixture_paths,
            candidate_failure_signals=[],
            errors=_dedupe_preserve_order(
                [*errors, f"failed to prepare fixture workspace: {error}"]
            ),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve fixture workspace preparation before execution"]
            ),
        )
    stdout_file = run_dir / "stdout.txt"
    stderr_file = run_dir / "stderr.txt"
    stdout_file.write_text(command_result.stdout, encoding="utf-8")
    stderr_file.write_text(command_result.stderr, encoding="utf-8")
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    candidate_failure_signals = _candidate_failure_signals_from_logs(combined_logs)
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason

    if not policy_allowed:
        status = "blocked"
        errors.append(f"reproduction command rejected by policy: {policy_reason or 'unknown'}")
        next_actions.append("resolve command-policy blockers before discovery")
    elif command_result.timed_out:
        status = "timed_out"
        warnings.append(f"candidate command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif command_result.exit_code == 0:
        status = "passed"
        warnings.append("candidate command passed; no failure signal was observed")
        next_actions.append(
            "write or select a more specific issue reproduction before repair attempts"
        )
    elif candidate_failure_signals:
        status = "observed_failure"
        next_actions.append(
            "review candidate_failure_signals and copy exact issue-specific signals into reviewed specs"
        )
    else:
        status = "failed"
        warnings.append("candidate command failed but no concise failure signal was extracted")
        next_actions.append("inspect saved stdout/stderr and choose reviewed failure signals")

    return IssueCorpusPublicFailureSignalDiscoveryResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=command_result.exit_code,
        timed_out=command_result.timed_out,
        duration_ms=command_result.duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=str(stdout_file),
        stderr_path=str(stderr_file),
        fixture_paths=fixture_paths,
        candidate_failure_signals=candidate_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


__all__ = ["discover_public_issue_failure_signal_record"]
