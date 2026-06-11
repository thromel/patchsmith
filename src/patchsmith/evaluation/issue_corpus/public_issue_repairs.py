"""Public issue repair readiness and attempt workflows."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation._helpers import (
    _load_json_record_list,
    _optional_string,
    _records_by_task_id,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_attempts import (
    execute_public_issue_repair_record,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_helpers import (
    load_public_issue_task_manifests,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_outputs import (
    write_public_issue_repair_attempt_outputs,
    write_public_issue_repair_readiness_outputs,
)
from patchsmith.evaluation.issue_corpus.public_issue_repair_readiness import (
    check_public_issue_repair_readiness_record,
)
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_repair_attempts,
    summarize_public_issue_repair_readiness,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicRepairAttemptResult,
    IssueCorpusPublicRepairAttemptSummary,
    IssueCorpusPublicRepairReadinessResult,
    IssueCorpusPublicRepairReadinessSummary,
)
from patchsmith.workflow import RepairRunner


def check_public_issue_repair_readiness(
    *,
    focused_run_path: Path,
    diagnosis_path: Path,
    setup_validation_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    reproduction_execution_path: Path | None = None,
) -> tuple[
    list[IssueCorpusPublicRepairReadinessResult],
    IssueCorpusPublicRepairReadinessSummary,
]:
    focused_records = _load_json_record_list(focused_run_path, label="focused test run results")
    diagnosis_records = _load_json_record_list(
        diagnosis_path, label="focused test diagnosis results"
    )
    setup_validation_records = _load_json_record_list(
        setup_validation_path, label="focused test setup validation results"
    )
    reproduction_execution_records = (
        _load_json_record_list(
            reproduction_execution_path,
            label="public issue reproduction execution results",
        )
        if reproduction_execution_path is not None and reproduction_execution_path.exists()
        else []
    )
    manifests = load_public_issue_task_manifests(tasks_dir)
    diagnosis_by_task = _records_by_task_id(diagnosis_records)
    setup_validation_by_task = _records_by_task_id(setup_validation_records)
    reproduction_execution_by_task = _records_by_task_id(reproduction_execution_records)
    results = [
        check_public_issue_repair_readiness_record(
            focused_record=record,
            diagnosis_record=diagnosis_by_task.get(_optional_string(record.get("task_id")) or ""),
            setup_validation_record=setup_validation_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            reproduction_execution_record=reproduction_execution_by_task.get(
                _optional_string(record.get("task_id")) or ""
            ),
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
        )
        for record in focused_records
    ]
    summary = summarize_public_issue_repair_readiness(
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path if reproduction_execution_records else None
        ),
        results=results,
    )
    write_public_issue_repair_readiness_outputs(
        output_dir=output_dir,
        tasks_dir=tasks_dir,
        focused_run_path=focused_run_path,
        diagnosis_path=diagnosis_path,
        setup_validation_path=setup_validation_path,
        reproduction_execution_path=(
            reproduction_execution_path if reproduction_execution_records else None
        ),
        results=results,
        summary=summary,
    )
    return results, summary


def execute_public_issue_repairs(
    *,
    readiness_path: Path,
    output_dir: Path,
    tasks_dir: Path | None = None,
    runtime: str = "langgraph",
    planner: str = "fake_model",
    context_provider: str = "native_hybrid",
    sandbox_mode: str = "docker",
    sandbox_image: str = "patchsmith-seeded-smoke:py312",
    max_retries: int = 0,
    max_tasks: int | None = None,
    dry_run: bool = True,
    allow_warnings: bool = False,
) -> tuple[
    list[IssueCorpusPublicRepairAttemptResult],
    IssueCorpusPublicRepairAttemptSummary,
]:
    records = _load_json_record_list(
        readiness_path,
        label="public issue repair readiness results",
    )
    selected_records = records
    if max_tasks is not None and max_tasks > 0:
        selected_records = records[:max_tasks]
    manifests = load_public_issue_task_manifests(tasks_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = (
        None if dry_run else RepairRunner(artifacts_dir=output_dir / "public_issue_repair_attempts")
    )
    results = [
        execute_public_issue_repair_record(
            record=record,
            manifest=manifests.get(_optional_string(record.get("task_id")) or ""),
            runner=runner,
            runtime=runtime,
            planner=planner,
            context_provider=context_provider,
            sandbox_mode=sandbox_mode,
            sandbox_image=sandbox_image,
            max_retries=max_retries,
            dry_run=dry_run,
            allow_warnings=allow_warnings,
        )
        for record in selected_records
    ]
    summary = summarize_public_issue_repair_attempts(
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        dry_run=dry_run,
        allow_warnings=allow_warnings,
        runtime=runtime,
        planner=planner,
        context_provider=context_provider,
        sandbox_mode=sandbox_mode,
        sandbox_image=sandbox_image,
        max_retries=max_retries,
    )
    write_public_issue_repair_attempt_outputs(
        output_dir=output_dir,
        readiness_path=readiness_path,
        tasks_dir=tasks_dir,
        results=results,
        summary=summary,
    )
    return results, summary


__all__ = [
    "RepairRunner",
    "check_public_issue_repair_readiness",
    "execute_public_issue_repairs",
]
