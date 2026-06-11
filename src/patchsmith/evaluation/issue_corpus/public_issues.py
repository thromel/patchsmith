"""Evaluation issue corpus public issues (split from evaluation.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty, write_json
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _load_json_record_list,
    _optional_string,
    _records_by_task_id,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.materialize import _is_materialized_test_candidate_path
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_reproduction_plan,
)
from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    load_public_issue_reproduction_specs as _load_public_issue_reproduction_specs,
)
from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    public_issue_reproduction_specs_template as _public_issue_reproduction_specs_template,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicReproductionPlanResult,
    IssueCorpusPublicReproductionPlanSummary,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_fixture_files as _normalize_public_issue_fixture_files,
)
from patchsmith.public_issue_fixtures import (
    normalize_public_issue_source_hints as _normalize_public_issue_source_hints,
)
from patchsmith.public_issue_fixtures import (
    public_issue_fixture_paths as _public_issue_fixture_paths,
)
from patchsmith.public_issue_reports import (
    render_public_issue_reproduction_plan_report,
)
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
