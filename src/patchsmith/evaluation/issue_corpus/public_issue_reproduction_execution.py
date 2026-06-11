"""Public issue failure-signal discovery and reproduction execution."""

from __future__ import annotations

from pathlib import Path

from patchsmith.evaluation._helpers import _load_json_record_list
from patchsmith.evaluation.issue_corpus.public_issue_failure_signal_records import (
    discover_public_issue_failure_signal_record as _discover_public_issue_failure_signal_record,
)
from patchsmith.evaluation.issue_corpus.public_issue_reproduction_outputs import (
    write_public_issue_failure_signal_discovery_outputs,
    write_public_issue_reproduction_execution_outputs,
)
from patchsmith.evaluation.issue_corpus.public_issue_reproduction_records import (
    execute_public_issue_reproduction_record as _execute_public_issue_reproduction_record,
)
from patchsmith.evaluation.issue_corpus.public_issue_summaries import (
    summarize_public_issue_failure_signal_discovery,
    summarize_public_issue_reproduction_execution,
)
from patchsmith.evaluation_models import (
    IssueCorpusPublicFailureSignalDiscoveryResult,
    IssueCorpusPublicFailureSignalDiscoverySummary,
    IssueCorpusPublicReproductionExecutionResult,
    IssueCorpusPublicReproductionExecutionSummary,
)
from patchsmith.sandbox import create_sandbox_runner
from patchsmith.security import CommandPolicy


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


__all__ = [
    "discover_public_issue_failure_signals",
    "execute_public_issue_reproductions",
]
