from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.evaluation.complex.trace_readers import (
    deepagents_context_budget,
    patch_target_alignment,
    retry_feedback_artifacts,
    trace_metrics,
)

pytestmark = pytest.mark.unit


def test_trace_readers_extract_context_budget_and_target_alignment(
    tmp_path: Path,
) -> None:
    retry_feedback = tmp_path / "retry_feedback.md"
    retry_feedback.write_text("retry feedback\n", encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "metadata": {
                            "deepagents_contract": {
                                "virtual_file_paths": ["/src/calc.py"],
                                "virtual_file_count": 1,
                                "max_context_files": 1,
                                "context_budget_manifest_path": ("/.patchsmith/context-budget.md"),
                                "repo_map_manifest_path": "/.patchsmith/repo-map.md",
                                "repo_instructions_manifest_path": (
                                    "/.patchsmith/repo-instructions.md"
                                ),
                                "acceptance_rubric_manifest_path": (
                                    "/.patchsmith/acceptance-rubric.md"
                                ),
                                "repair_interface_manifest_path": (
                                    "/.patchsmith/repair-interface.md"
                                ),
                                "planning_policy": {
                                    "context_budget_manifest_read_first": True,
                                    "repo_map_manifest_read_first": True,
                                    "repo_instructions_manifest_read_first": True,
                                    "acceptance_rubric_manifest_read_first": True,
                                    "repair_interface_manifest_read_first": True,
                                    "resource_budget_read_first": True,
                                },
                                "context_budget": {
                                    "mounted_paths": ["src/calc.py"],
                                    "omitted_file_count": 2,
                                    "omitted_paths": ["src/other.py"],
                                },
                                "filesystem_policy": {
                                    "allowed_read_paths": [
                                        "/src/calc.py",
                                        "/.patchsmith/repair-interface.md",
                                    ]
                                },
                                "resource_budget": {
                                    "max_model_responses": 6,
                                    "max_model_tokens": 120000,
                                },
                                "patch_selection_policy": {
                                    "patchable_paths": ["src/calc.py"],
                                },
                            },
                            "target_localization": [{"path": "src/calc.py"}],
                        },
                        "payload": {
                            "retry_feedback_path": str(retry_feedback),
                        },
                    }
                ),
                json.dumps(
                    {
                        "metadata": {
                            "failure_localization": {
                                "failure_mechanism": "add subtracts",
                                "target_rationale": "add controls arithmetic",
                            }
                        },
                        "payload": {
                            "patch_plan": {"path": "src/calc.py"},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    diff_path = tmp_path / "final.diff"
    diff_path.write_text(
        "--- a/src/calc.py\n+++ b/src/calc.py\n@@\n-    return a - b\n+    return a + b\n",
        encoding="utf-8",
    )

    context_budget = deepagents_context_budget(str(trace_path))
    alignment = patch_target_alignment(
        trace_path=str(trace_path),
        final_diff_path=str(diff_path),
    )

    assert context_budget["deepagents_virtual_file_count"] == 1
    assert context_budget["deepagents_virtual_file_paths"] == ("src/calc.py",)
    assert context_budget["deepagents_context_budgeted"] is True
    assert context_budget["deepagents_context_budget_manifest_read_first"] is True
    assert context_budget["deepagents_context_budget_omitted_file_count"] == 2
    assert context_budget["deepagents_context_budget_omitted_paths"] == ("src/other.py",)
    assert context_budget["deepagents_resource_budgeted"] is True
    assert context_budget["deepagents_resource_budget_read_first"] is True
    assert context_budget["deepagents_resource_budget_max_model_responses"] == 6
    assert context_budget["deepagents_resource_budget_max_model_tokens"] == 120000
    assert alignment["target_alignment_status"] == "aligned"
    assert alignment["patch_target_aligned"] is True
    assert alignment["patch_target_paths"] == ("src/calc.py",)
    assert alignment["localized_target_paths"] == ("src/calc.py",)
    assert retry_feedback_artifacts(str(trace_path)) == (str(retry_feedback),)


def test_trace_readers_return_empty_fallbacks_for_missing_paths(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing.jsonl")

    assert trace_metrics(missing)["trace_event_count"] == 0
    assert deepagents_context_budget(missing)["deepagents_context_budgeted"] is False
    assert (
        patch_target_alignment(trace_path=missing, final_diff_path=None)["target_alignment_status"]
        == "unavailable"
    )
    assert retry_feedback_artifacts(missing) == ()
