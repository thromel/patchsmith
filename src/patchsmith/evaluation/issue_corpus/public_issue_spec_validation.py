"""Reviewed reproduction-spec validation for public issue corpus tasks."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json
from patchsmith.evaluation._helpers import (
    _dedupe_preserve_order,
    _load_json_record_list,
    _optional_string,
    _records_by_task_id,
    _string_list,
)
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_reproduction_spec_validation,
)
from patchsmith.evaluation.issue_corpus.public_issues import (
    _plan_public_issue_reproduction_record,
)
from patchsmith.evaluation.issue_corpus.reproduction_specs import (
    load_public_issue_reproduction_specs as _load_public_issue_reproduction_specs,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicReproductionSpecValidationResult,
    IssueCorpusPublicReproductionSpecValidationSummary,
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
    render_public_issue_reproduction_spec_validation_report,
)
from patchsmith.security import CommandPolicy


def validate_public_issue_reproduction_specs(
    *,
    specs_path: Path,
    tasks_dir: Path,
    output_dir: Path,
    focused_plan_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicReproductionSpecValidationResult],
    IssueCorpusPublicReproductionSpecValidationSummary,
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
    specs_by_task = _load_public_issue_reproduction_specs(specs_path)
    policy = CommandPolicy()
    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir())
    task_ids = {task_dir.name for task_dir in task_dirs}
    results = [
        _validate_public_issue_reproduction_spec_record(
            task_dir=task_dir,
            focused_record=focused_by_task.get(task_dir.name),
            reproduction_spec=specs_by_task.get(task_dir.name),
            policy=policy,
        )
        for task_dir in task_dirs
    ]
    for extra_task_id in sorted(set(specs_by_task) - task_ids):
        results.append(
            IssueCorpusPublicReproductionSpecValidationResult(
                task_id=extra_task_id,
                repository=_optional_string(specs_by_task[extra_task_id].get("repository")),
                issue_url=_optional_string(specs_by_task[extra_task_id].get("issue_url")),
                status="blocked",
                spec_present=True,
                repo_path=None,
                repo_exists=False,
                reproduction_command=_optional_string(specs_by_task[extra_task_id].get("command")),
                command_source="reproduction_spec",
                policy_allowed=False,
                policy_reason=None,
                fixture_files=_normalize_public_issue_fixture_files(
                    specs_by_task[extra_task_id].get("fixture_files")
                )[0],
                source_hints=_normalize_public_issue_source_hints(
                    specs_by_task[extra_task_id].get("source_hints")
                )[0],
                expected_failure_signals=_string_list(
                    specs_by_task[extra_task_id].get("expected_failure_signals")
                ),
                errors=["reproduction spec task_id has no materialized task"],
                warnings=[],
                evidence=["reviewed reproduction spec found"],
                next_actions=[
                    "remove the extra spec or materialize the matching public issue task"
                ],
            )
        )
    summary = summarize_public_issue_reproduction_spec_validation(
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        spec_count=len(specs_by_task),
        results=results,
    )
    write_public_issue_reproduction_spec_validation_outputs(
        output_dir=output_dir,
        specs_path=specs_path,
        tasks_dir=tasks_dir,
        focused_plan_path=focused_plan_path,
        results=results,
        summary=summary,
    )
    return results, summary


def write_public_issue_reproduction_spec_validation_outputs(
    *,
    output_dir: Path,
    specs_path: Path,
    tasks_dir: Path,
    focused_plan_path: Path | None,
    results: list[IssueCorpusPublicReproductionSpecValidationResult],
    summary: IssueCorpusPublicReproductionSpecValidationSummary,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "public_issue_reproduction_spec_validation_results.json",
        [result.to_dict() for result in results],
        trailing_newline=True,
    )
    write_json(
        output_dir / "public_issue_reproduction_spec_validation_summary.json",
        summary.to_dict(),
        trailing_newline=True,
    )
    with (output_dir / "public_issue_reproduction_spec_validation_results.csv").open(
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
                "spec_present",
                "repo_path",
                "repo_exists",
                "reproduction_command",
                "command_source",
                "policy_allowed",
                "policy_reason",
                "fixture_paths",
                "expected_failure_signals",
                "errors",
                "warnings",
                "evidence",
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
                    "spec_present": result.spec_present,
                    "repo_path": result.repo_path,
                    "repo_exists": result.repo_exists,
                    "reproduction_command": result.reproduction_command,
                    "command_source": result.command_source,
                    "policy_allowed": result.policy_allowed,
                    "policy_reason": result.policy_reason,
                    "fixture_paths": ";".join(_public_issue_fixture_paths(result.fixture_files)),
                    "expected_failure_signals": ";".join(result.expected_failure_signals),
                    "errors": ";".join(result.errors),
                    "warnings": ";".join(result.warnings),
                    "evidence": ";".join(result.evidence),
                    "next_actions": ";".join(result.next_actions),
                }
            )
    (output_dir / "public_issue_reproduction_spec_validation_report.md").write_text(
        render_public_issue_reproduction_spec_validation_report(
            specs_path=specs_path,
            tasks_dir=tasks_dir,
            focused_plan_path=focused_plan_path,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def _validate_public_issue_reproduction_spec_record(
    *,
    task_dir: Path,
    focused_record: dict[str, Any] | None,
    reproduction_spec: dict[str, Any] | None,
    policy: CommandPolicy,
) -> IssueCorpusPublicReproductionSpecValidationResult:
    planned = _plan_public_issue_reproduction_record(
        task_dir=task_dir,
        focused_record=focused_record,
        reproduction_spec=reproduction_spec,
        policy=policy,
    )
    errors = list(planned.blockers)
    warnings = list(planned.warnings)
    evidence = list(planned.evidence)
    next_actions = list(planned.next_actions)
    spec_present = reproduction_spec is not None

    if spec_present:
        evidence.append("reviewed reproduction spec found")
    else:
        errors.append("reviewed reproduction spec is missing")
        next_actions.append(
            "fill public_issue_reproduction_specs_template.json and rerun validation"
        )

    if not planned.expected_failure_signals:
        errors.append("expected_failure_signals is empty")
        next_actions.append(
            "encode at least one exact failing assertion, traceback, or behavior signal"
        )

    if not planned.reproduction_command:
        errors.append("reproduction command is missing")
    elif not planned.policy_allowed:
        errors.append(
            f"reproduction command rejected by policy: {planned.policy_reason or 'unknown'}"
        )

    if planned.command_source != "reproduction_spec":
        warnings.append(
            "reproduction spec does not override the command; using planned fallback command"
        )

    status = "blocked" if errors else "warning" if warnings else "ready"
    return IssueCorpusPublicReproductionSpecValidationResult(
        task_id=planned.task_id,
        repository=planned.repository,
        issue_url=planned.issue_url,
        status=status,
        spec_present=spec_present,
        repo_path=planned.repo_path,
        repo_exists=planned.repo_exists,
        reproduction_command=planned.reproduction_command,
        command_source=planned.command_source,
        policy_allowed=planned.policy_allowed,
        policy_reason=planned.policy_reason,
        fixture_files=planned.fixture_files,
        source_hints=planned.source_hints,
        expected_failure_signals=planned.expected_failure_signals,
        errors=_dedupe_preserve_order(errors),
        warnings=_dedupe_preserve_order(warnings),
        evidence=_dedupe_preserve_order(evidence),
        next_actions=_dedupe_preserve_order(next_actions),
    )
