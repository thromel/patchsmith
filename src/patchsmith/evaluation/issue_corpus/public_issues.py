"""Evaluation issue corpus public issues (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty, write_json
from patchsmith.artifacts import safe_artifact_name as _safe_artifact_name
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _load_json_record_list,
    _optional_string,
    _records_by_task_id,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.log_signals import (
    candidate_failure_signals_from_logs as _candidate_failure_signals_from_logs,
)
from patchsmith.evaluation.issue_corpus.log_signals import (
    matched_expected_failure_signals as _matched_expected_failure_signals,
)
from patchsmith.evaluation.issue_corpus.materialize import _is_materialized_test_candidate_path
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_failure_signal_discovery,
    summarize_public_issue_reproduction_execution,
    summarize_public_issue_reproduction_plan,
)
from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    load_public_issue_reproduction_specs as _load_public_issue_reproduction_specs,
)
from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    public_issue_reproduction_specs_template as _public_issue_reproduction_specs_template,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
    IssueCorpusPublicReproductionPlanResult,
    IssueCorpusPublicReproductionPlanSummary,
)
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
from patchsmith.public_issue_reports import (
    render_public_issue_failure_signal_discovery_report,
    render_public_issue_reproduction_execution_report,
    render_public_issue_reproduction_plan_report,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy


def plan_public_issue_reproductions(
    *,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
    reproduction_specs_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionPlanResult],
    IssueCorpusPublicReproductionPlanSummary,
]:
    if not tasks_dir.exists():
        raise FileNotFoundError(f"materialized tasks directory does not exist: {tasks_dir}")
    if not tasks_dir.is_dir():
        raise ValueError(f"materialized tasks path is not a directory: {tasks_dir}")
    focused_records = (
        _load_json_record_list(focused_plan_path, label="focused test plan results")
        if focused_plan_path is not None and focused_plan_path.exists()
        else []
    )
    focused_by_task = _records_by_task_id(focused_records)
    reproduction_specs_by_task = (
        _load_public_issue_reproduction_specs(reproduction_specs_path)
        if reproduction_specs_path is not None
        else {}
    )
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    results = [
        _plan_public_issue_reproduction_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=reproduction_specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    summary = summarize_public_issue_reproduction_plan(
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
    )
    write_public_issue_reproduction_plan_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def write_public_issue_reproduction_plan_outputs(
    *,
    output_dir: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionPlanResult],
    summary: IssueCorpusPublicReproductionPlanSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_plan_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_plan_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_specs_template.json",
        _public_issue_reproduction_specs_template(results),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_plan_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "focused_files",
                "fixture_paths",
                "expected_failure_signals",
                "manual_spec_required",
                "evidence",
                "blockers",
                "warnings",
                "next_actions",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "focused_files": ";".join(result.focused_files),
                    "fixture_paths": ";".join(_public_issue_fixture_paths(result.fixture_files)),
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "evidence": ";".join(result.evidence),
                    "blockers": ";".join(result.blockers),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_plan_report.md").write_text(
        render_public_issue_reproduction_plan_report(
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def discover_public_issue_failure_signals(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicFailureSignalDiscoveryResult],
    IssueCorpusPublicFailureSignalDiscoverySummary,
]:
    records = _load_json_record_list(path=plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            network=sandbox_network,
        )
    )
    policy = CommandPolicy()
    run_logs_dir = output_dir / "public_issue_failure_signal_discovery_logs"
    results = [
        _discover_public_issue_failure_signal_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )
        for record in selected_records
    ]
    summary = summarize_public_issue_failure_signal_discovery(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_failure_signal_discovery_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def write_public_issue_failure_signal_discovery_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicFailureSignalDiscoveryResult],
    summary: IssueCorpusPublicFailureSignalDiscoverySummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_failure_signal_discovery_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_failure_signal_discovery_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_failure_signal_discovery_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "candidate_failure_signals",
                "errors",
                "warnings",
                "next_actions",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "candidate_failure_signals": ";".join(result.candidate_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_failure_signal_discovery_report.md").write_text(
        render_public_issue_failure_signal_discovery_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def execute_public_issue_reproductions(
    *,
    plan_path: Path,
    output_dir: Path,
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    sandbox_network: str = "none",
    timeout_seconds: int = 300,
    max_tasks: int | None = None,
    dry_run: bool = True,
) -> tuple[
    list[IssueCorpusPublicReproductionExecutionResult],
    IssueCorpusPublicReproductionExecutionSummary,
]:
    records = _load_json_record_list(plan_path, label="public issue reproduction plan")
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir = output_dir / "public_issue_reproductions"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    policy = CommandPolicy()
    runner = (
        None
        if dry_run
        else create_sandbox_runner(
            mode=sandbox_mode,
            image=sandbox_image,
            policy=policy,
            network=sandbox_network,
        )
    )
    results = [
        _execute_public_issue_reproduction_record(
            record=record,
            run_logs_dir=run_logs_dir,
            runner=runner,
            policy=policy,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )
        for record in selected_records
    ]
    summary = summarize_public_issue_reproduction_execution(
        plan_path=plan_path,
        results=results,
        dry_run=dry_run,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        timeout_seconds=timeout_seconds,
    )
    write_public_issue_reproduction_execution_outputs(
        output_dir=output_dir,
        plan_path=plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def write_public_issue_reproduction_execution_outputs(
    *,
    output_dir: Path,
    plan_path: Path,
    results: list[IssueCorpusPublicReproductionExecutionResult],
    summary: IssueCorpusPublicReproductionExecutionSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_execution_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_execution_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_execution_results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "repository",
                "issue_url",
                "status",
                "reproduction_plan_status",
                "repo_path",
                "reproduction_command",
                "expected_failure_signals",
                "manual_spec_required",
                "sandbox_mode",
                "sandbox_image",
                "sandbox_network",
                "dry_run",
                "exit_code",
                "timed_out",
                "duration_ms",
                "policy_allowed",
                "policy_reason",
                "stdout_path",
                "stderr_path",
                "fixture_paths",
                "matched_failure_signals",
                "missing_failure_signals",
                "errors",
                "warnings",
                "next_actions",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "repository": result.repository,
                    "issue_url": result.issue_url,
                    "status": result.status,
                    "reproduction_plan_status": result.reproduction_plan_status,
                    "repo_path": result.repo_path,
                    "reproduction_command": result.reproduction_command,
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "manual_spec_required": result.manual_spec_required,
                    "sandbox_mode": result.sandbox_mode,
                    "sandbox_image": result.sandbox_image,
                    "sandbox_network": result.sandbox_network,
                    "dry_run": result.dry_run,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "stdout_path": result.stdout_path,
                    "stderr_path": result.stderr_path,
                    "fixture_paths": ";".join(result.fixture_paths),
                    "matched_failure_signals": ";".join(result.matched_failure_signals),
                    "missing_failure_signals": ";".join(result.missing_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_execution_report.md").write_text(
        render_public_issue_reproduction_execution_report(
            plan_path=plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _plan_public_issue_reproduction_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionPlanResult:
    manifest_path = task_dir / "task_manifest.json"
    manifest: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []
    next_actions: list[str] = []

    if not manifest_path.exists():
        blockers.append("missing task_manifest.json")
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            blockers.append(f"task_manifest.json is invalid JSON: {error.msg}")
        else:
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                blockers.append("task_manifest.json must contain a JSON object")

    task_id = _optional_string(manifest.get("task_id")) or task_dir.name
    issue = dict_or_empty(manifest.get("issue"))
    snapshot = dict_or_empty(manifest.get("repository_snapshot"))
    retrieval = dict_or_empty(manifest.get("retrieval_preview"))
    reproduction = dict_or_empty(manifest.get("reproduction"))
    spec_reproduction = reproduction_spec if isinstance(reproduction_spec, dict) else {}
    repository = _optional_string(issue.get("repository"))
    issue_url = _optional_string(issue.get("issue_url"))
    repo_path = _optional_string(snapshot.get("repo_path")) or (
        _optional_string(focused_record.get("repo_path")) if focused_record else None
    )
    focused_files = _string_list(focused_record.get("focused_files")) if focused_record else []
    if not focused_files:
        focused_files = [
            path
            for path in _string_list(retrieval.get("retrieved_files"))
            if _is_materialized_test_candidate_path(path)
        ][:2]
    spec_command = _optional_string(spec_reproduction.get("command"))
    explicit_command = _optional_string(reproduction.get("command"))
    focused_command = _optional_string(focused_record.get("command")) if focused_record else None
    test_commands = _string_list(snapshot.get("test_commands"))
    if spec_command:
        command = spec_command
        command_source = "reproduction_spec"
        evidence.append("reproduction spec provides an explicit command")
    elif explicit_command:
        command = explicit_command
        command_source = "manifest_reproduction"
        evidence.append("manifest contains an explicit reproduction command")
    elif focused_command:
        command = focused_command
        command_source = "focused_test_plan"
        evidence.append("focused test plan provides the reproduction candidate command")
    elif test_commands:
        command = test_commands[0]
        command_source = "repository_test_command"
        warnings.append("using broad repository test command as reproduction candidate")
    else:
        command = None
        command_source = "missing"
        blockers.append("no reproduction or focused test command is available")

    spec_failure_signals = _string_list(spec_reproduction.get("expected_failure_signals"))
    manifest_failure_signals = _string_list(reproduction.get("expected_failure_signals"))
    expected_failure_signals = spec_failure_signals or manifest_failure_signals
    if "fixture_files" in spec_reproduction:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            spec_reproduction.get("fixture_files")
        )
        fixture_source = "reproduction spec"
    else:
        fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
            reproduction.get("fixture_files")
        )
        fixture_source = "task manifest"
    if fixture_errors:
        blockers.extend(fixture_errors)
    elif fixture_files:
        evidence.append(f"{fixture_source} provides {len(fixture_files)} temporary fixture file(s)")
    source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        spec_reproduction.get("source_hints")
    )
    if source_hint_errors:
        blockers.extend(source_hint_errors)
    elif source_hints:
        evidence.append(f"reproduction spec provides {len(source_hints)} reviewed source hint(s)")
    manual_spec_required = not expected_failure_signals
    if expected_failure_signals:
        if spec_failure_signals:
            evidence.append("expected failing signal is encoded in the reproduction spec")
        else:
            evidence.append("expected failing signal is encoded in the task manifest")
    else:
        warnings.append("expected failing signal is not encoded")
        next_actions.append(
            "add issue-specific expected failure text, assertion, traceback, or exit criteria"
        )

    workspace = Path.cwd()
    repo_exists = False
    if repo_path:
        repo = Path(repo_path)
        repo_exists = repo.exists() and repo.is_dir()
        if repo_exists:
            workspace = repo
            evidence.append("repository snapshot exists")
        else:
            blockers.append(f"repository snapshot is missing: {repo_path}")
    else:
        blockers.append("repository_snapshot.repo_path is missing")

    policy_allowed = False
    policy_reason: str | None = None
    if command:
        decision = policy.evaluate(command, workspace=workspace)
        policy_allowed = decision.allowed
        policy_reason = decision.reason
        if decision.allowed:
            evidence.append("reproduction command is allowed by command policy")
        else:
            blockers.append(f"reproduction command rejected by policy: {decision.reason}")

    if focused_record is None and command_source not in {
        "manifest_reproduction",
        "reproduction_spec",
    }:
        warnings.append("focused test plan record is missing")
        next_actions.append("regenerate `plan-materialized-focused-tests` before execution")
    if command and not blockers and not manual_spec_required:
        next_actions.append("execute reproduction command and save failing stdout/stderr evidence")
    elif command and not blockers:
        next_actions.append("review and encode the expected failing signal before execution")

    status = "blocked" if blockers else "warning" if warnings else "planned"
    return IssueCorpusPublicReproductionPlanResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        repo_path=repo_path,
        repo_exists=repo_exists,
        reproduction_command=command,
        command_source=command_source,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        focused_files=focused_files,
        fixture_files=fixture_files,
        source_hints=source_hints,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        evidence=_dedupe_preserve_order(evidence),
        blockers=_dedupe_preserve_order(blockers),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )


def _discover_public_issue_failure_signal_record(
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


def _execute_public_issue_reproduction_record(
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
) -> IssueCorpusPublicReproductionExecutionResult:
    task_id = _optional_string(record.get("task_id"))
    repository = _optional_string(record.get("repository"))
    issue_url = _optional_string(record.get("issue_url"))
    plan_status = _optional_string(record.get("status")) or "unknown"
    repo_path_value = _optional_string(record.get("repo_path"))
    command = _optional_string(record.get("reproduction_command"))
    expected_failure_signals = _string_list(record.get("expected_failure_signals"))
    manual_spec_required = record.get("manual_spec_required") is True or not (
        expected_failure_signals
    )
    errors = _string_list(record.get("blockers"))
    warnings = _string_list(record.get("warnings"))
    next_actions = _string_list(record.get("next_actions"))
    fixture_files, fixture_errors = _normalize_public_issue_fixture_files(
        record.get("fixture_files")
    )
    fixture_paths = _public_issue_fixture_paths(fixture_files)
    source_hints, source_hint_errors = _normalize_public_issue_source_hints(
        record.get("source_hints")
    )
    errors.extend(fixture_errors)
    errors.extend(source_hint_errors)

    exit_code: int | None = None
    timed_out = False
    duration_ms = 0
    policy_allowed = False
    policy_reason: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    matched_failure_signals: list[str] = []
    missing_failure_signals = list(expected_failure_signals)

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

    if manual_spec_required:
        errors.append("expected failing signal is not encoded")
        next_actions.append(
            "encode an issue-specific expected failure signal before executing reproduction"
        )

    if errors:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=_dedupe_preserve_order(errors),
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "resolve reproduction blockers before execution"]
            ),
        )

    if dry_run:
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="dry_run",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
            errors=[],
            warnings=_dedupe_preserve_order(warnings),
            next_actions=_dedupe_preserve_order(
                [*next_actions, "rerun with --execute to save failing reproduction logs"]
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
        return IssueCorpusPublicReproductionExecutionResult(
            task_id=task_id,
            repository=repository,
            issue_url=issue_url,
            status="blocked",
            reproduction_plan_status=plan_status,
            repo_path=repo_path_value,
            reproduction_command=command,
            expected_failure_signals=expected_failure_signals,
            manual_spec_required=manual_spec_required,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
            dry_run=dry_run,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_files=fixture_files,
            fixture_paths=fixture_paths,
            source_hints=source_hints,
            matched_failure_signals=matched_failure_signals,
            missing_failure_signals=missing_failure_signals,
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

    exit_code = command_result.exit_code
    timed_out = command_result.timed_out
    duration_ms = command_result.duration_ms
    policy_allowed = command_result.policy_decision.allowed
    policy_reason = command_result.policy_decision.reason
    stdout_path = str(stdout_file)
    stderr_path = str(stderr_file)
    combined_logs = "\n".join([command_result.stdout, command_result.stderr])
    matched_failure_signals = _matched_expected_failure_signals(
        combined_logs,
        expected_failure_signals,
    )
    matched_set = set(matched_failure_signals)
    missing_failure_signals = [
        signal for signal in expected_failure_signals if signal not in matched_set
    ]

    if not policy_allowed:
        status = "blocked"
        errors.append(f"reproduction command rejected by policy: {policy_reason or 'unknown'}")
        next_actions.append("resolve command-policy blockers before execution")
    elif timed_out:
        status = "timed_out"
        warnings.append(f"reproduction command timed out after {timeout_seconds}s")
        next_actions.append("inspect saved logs and narrow or raise the timeout")
    elif exit_code == 0:
        status = "not_reproduced"
        warnings.append("reproduction command passed; expected pre-repair failure was absent")
        next_actions.append(
            "confirm whether the issue is already fixed or update the reproduction command"
        )
    elif missing_failure_signals:
        status = "failed"
        warnings.append("reproduction command failed without all expected failure signals")
        next_actions.append(
            "inspect saved stdout/stderr and update expected failure criteria if appropriate"
        )
    else:
        status = "reproduced"
        next_actions.append("use the saved failing logs as pre-repair reproduction evidence")

    return IssueCorpusPublicReproductionExecutionResult(
        task_id=task_id,
        repository=repository,
        issue_url=issue_url,
        status=status,
        reproduction_plan_status=plan_status,
        repo_path=repo_path_value,
        reproduction_command=command,
        expected_failure_signals=expected_failure_signals,
        manual_spec_required=manual_spec_required,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        sandbox_network=sandbox_network,
        dry_run=dry_run,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        policy_allowed=policy_allowed,
        policy_reason=policy_reason,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        fixture_files=fixture_files,
        fixture_paths=fixture_paths,
        source_hints=source_hints,
        matched_failure_signals=matched_failure_signals,
        missing_failure_signals=missing_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        next_actions=_dedupe_preserve_order(next_actions),
    )
