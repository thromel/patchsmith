from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.compatibility import load_complex_benchmark_results

pytestmark = pytest.mark.unit


def test_load_complex_benchmark_results_accepts_historical_flat_rows(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "complex_benchmark_results.json"
    results_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "task-1",
                    "repository": "example/repo",
                    "issue_url": "https://github.com/example/repo/issues/1",
                    "status": "validated",
                    "strict_status": "validated",
                    "runtime": "deepagents",
                    "planner": "deepagents",
                    "context_provider": "native_hybrid",
                    "reproduced": True,
                    "patch_generated": True,
                    "validation_passed": True,
                    "test_exit_code": 0,
                    "trace_path": "trace.jsonl",
                    "report_path": "report.md",
                    "patch_quality_codes": ["style", "tests"],
                    "patch_target_paths": ["src/example.py"],
                    "retry_label_counts": {"repair": 2},
                    "deepagents_virtual_file_paths": ["src/example.py"],
                    "process_quality_flags": ["used_tests"],
                    "preflight_gates": [{"name": "budget", "status": "passed"}],
                    "model_usage": {"provider": "nested future field"},
                },
                "ignored legacy corruption",
            ]
        ),
        encoding="utf-8",
    )

    results = load_complex_benchmark_results(results_path)

    assert len(results) == 1
    result = results[0]
    assert result.task_id == "task-1"
    assert result.patch_quality_codes == ("style", "tests")
    assert result.patch_target_paths == ("src/example.py",)
    assert result.retry_label_counts == {"repair": 2}
    assert result.context_evidence.virtual_file_paths == ("src/example.py",)
    assert result.process_quality.flags == ("used_tests",)
    assert result.preflight_gates == [{"name": "budget", "status": "passed"}]
    assert "model_usage" not in result.to_dict()


def test_load_complex_benchmark_results_returns_empty_for_missing_or_invalid_json(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.json"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not-json}", encoding="utf-8")

    assert load_complex_benchmark_results(missing_path) == []
    assert load_complex_benchmark_results(invalid_path) == []
