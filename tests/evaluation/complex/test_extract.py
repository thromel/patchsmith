from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.extract import (
    complex_result,
    complex_results_from_attempt_dir,
)
from patchsmith.evaluation.runners import complex as runner_complex

pytestmark = pytest.mark.unit


def test_complex_results_from_attempt_dir_loads_saved_rows_and_filters_noise(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    (attempt_dir / "public_issue_repair_attempt_results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "budget-task",
                    "status": "failed",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduction_execution_status": "reproduced",
                    "patch_generated": True,
                    "test_exit_code": 1,
                    "report_path": "reports/budget-task.md",
                    "preflight_status": "blocked",
                    "preflight_gates": [
                        {
                            "name": "budget",
                            "status": "blocked",
                            "max_live_cost_usd": "0.01",
                            "ignored": None,
                        }
                    ],
                    "attempt_index": "0",
                    "attempt_count": "2",
                },
                "ignored",
            ]
        ),
        encoding="utf-8",
    )

    results = complex_results_from_attempt_dir(attempt_dir)

    assert len(results) == 1
    result = results[0]
    assert result.task_id == "budget-task"
    assert result.status == "failed"
    assert result.strict_status == "failed"
    assert result.validation_passed is False
    assert result.reproduced is True
    assert result.patch_generated is True
    assert result.progress_stage == "patch_generated"
    assert result.failure_class == "budget_preflight_blocked"
    assert result.harness_layer == "budget"
    assert result.live_cost_budget_usd == 0.01
    assert result.live_cost_budget_overage is False
    assert result.preflight_gates == [
        {"name": "budget", "status": "blocked", "max_live_cost_usd": "0.01"}
    ]
    assert result.attempt_index == 1
    assert result.attempt_count == 2


def test_complex_results_from_attempt_dir_requires_attempt_results_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="missing public issue attempt results"):
        complex_results_from_attempt_dir(tmp_path)


def test_complex_result_defaults_unknown_fields_without_trace() -> None:
    result = complex_result({"task_id": "minimal", "status": "blocked"})

    assert result.task_id == "minimal"
    assert result.runtime == "unknown"
    assert result.planner == "unknown"
    assert result.context_provider == "unknown"
    assert result.progress_stage == "blocked"
    assert result.failure_class == "reproduction_failed"
    assert result.harness_layer == "reproduction"
    assert result.model_provider is None
    assert result.response_count is None


def test_runner_delegates_extraction_to_complex_package() -> None:
    assert runner_complex._complex_results_from_attempt_dir is complex_results_from_attempt_dir
