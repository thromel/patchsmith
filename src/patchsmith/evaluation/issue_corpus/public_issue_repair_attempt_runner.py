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
    model_call_count: int | None
    model_response_count: int | None
    model_input_tokens: int | None
    model_output_tokens: int | None
    model_total_tokens: int | None
    estimated_model_cost_usd: float | None


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
    deepagents_max_context_files: int | None = None,
    max_actual_model_responses: int | None = None,
    max_actual_model_tokens: int | None = None,
    deepagents_subagent_mode: str | None = None,
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
    context_paths = tuple(
        _dedupe_preserve_order(
            [
                *source_hint_context_paths(source_hints),
                *validation_fixture_paths,
            ]
        )
    )
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
                deepagents_max_context_files=deepagents_max_context_files,
                max_actual_model_responses=max_actual_model_responses,
                max_actual_model_tokens=max_actual_model_tokens,
                deepagents_subagent_mode=deepagents_subagent_mode,
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
        deepagents_max_context_files=deepagents_max_context_files,
        max_actual_model_responses=max_actual_model_responses,
        max_actual_model_tokens=max_actual_model_tokens,
        deepagents_subagent_mode=deepagents_subagent_mode,
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
    deepagents_max_context_files: int | None,
    max_actual_model_responses: int | None = None,
    max_actual_model_tokens: int | None = None,
    deepagents_subagent_mode: str | None = None,
) -> PublicIssueRepairRunOutcome:
    runtime_config = _deepagents_runtime_config(
        runtime=runtime,
        planner=planner,
        max_context_files=deepagents_max_context_files,
        max_actual_model_responses=max_actual_model_responses,
        max_actual_model_tokens=max_actual_model_tokens,
        subagent_mode=deepagents_subagent_mode,
    )
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
            runtime_config=runtime_config,
        )
    )
    test_exit_code = (
        run_result.test_result.exit_code if run_result.test_result is not None else None
    )
    model_usage = getattr(run_result, "model_usage", {})
    return PublicIssueRepairRunOutcome(
        run_id=run_result.run_id,
        run_status=run_result.status,
        report_path=str(run_result.report_path),
        trace_path=str(run_result.trace_path),
        final_diff_path=str(run_result.final_diff_path),
        test_exit_code=test_exit_code,
        patch_generated=_path_has_text(run_result.final_diff_path),
        model_call_count=_usage_int(model_usage, "call_count"),
        model_response_count=_usage_int(model_usage, "response_count"),
        model_input_tokens=_usage_int(model_usage, "input_tokens"),
        model_output_tokens=_usage_int(model_usage, "output_tokens"),
        model_total_tokens=_usage_int(model_usage, "total_tokens"),
        estimated_model_cost_usd=_usage_float(
            model_usage,
            "estimated_cost_usd",
        ),
    )


def _deepagents_runtime_config(
    *,
    runtime: str,
    planner: str,
    max_context_files: int | None,
    max_actual_model_responses: int | None,
    max_actual_model_tokens: int | None,
    subagent_mode: str | None,
) -> dict[str, object]:
    if runtime != "deepagents" or planner != "deepagents":
        return {}
    runtime_config: dict[str, object] = {}
    if max_context_files is not None and max_context_files > 0:
        runtime_config["max_context_files"] = max_context_files
    resource_budget: dict[str, int] = {}
    if max_actual_model_responses is not None and max_actual_model_responses >= 0:
        resource_budget["max_model_responses"] = max_actual_model_responses
    if max_actual_model_tokens is not None and max_actual_model_tokens >= 0:
        resource_budget["max_model_tokens"] = max_actual_model_tokens
    if resource_budget:
        runtime_config["resource_budget"] = resource_budget
    if subagent_mode in {"full", "auto", "inline"}:
        runtime_config["subagent_mode"] = subagent_mode
    return runtime_config


def _usage_int(model_usage: dict[str, Any], key: str) -> int | None:
    value = model_usage.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _usage_float(model_usage: dict[str, Any], key: str) -> float | None:
    value = model_usage.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


__all__ = ["PublicIssueRepairRunOutcome", "run_public_issue_repair_attempt"]
