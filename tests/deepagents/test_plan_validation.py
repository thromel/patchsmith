from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.deepagents_plan_validation import validate_deepagents_plan_result
from patchsmith.models import RetrievedContext
from patchsmith.planning import ModelCallMetadata

pytestmark = pytest.mark.unit


def test_validate_deepagents_plan_result_builds_repair_plan() -> None:
    source = "def add(a, b):\n    return a - b\n"

    result = validate_deepagents_plan_result(
        result={
            "messages": [],
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a + b",
                "summary": "Fix addition.",
                "failure_mechanism": "add subtracts instead of adding",
                "target_rationale": "src/calc.py contains add's return expression",
            },
        },
        files={"/src/calc.py": {"content": source}},
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        selected_context=[_context(source)],
        deprioritized_paths=[],
        target_old_span_hashes={},
        preferred_target_paths=[],
        preferred_target_symbols={},
        repo_path=None,
        model_metadata=ModelCallMetadata(provider="deepagents", model="gpt-test"),
        contract={"subagent_mode": "auto"},
    )

    assert result.metadata_update == {}
    assert result.plan is not None
    assert result.plan.path == "src/calc.py"
    assert result.plan.old == "return a - b"
    assert result.plan.new == "return a + b"
    assert result.plan.metadata is not None
    assert result.plan.metadata["failure_localization"] == {
        "failure_mechanism": "add subtracts instead of adding",
        "target_rationale": "src/calc.py contains add's return expression",
    }


def test_validate_deepagents_plan_result_reports_missing_localization() -> None:
    result = validate_deepagents_plan_result(
        result={
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a + b",
                "summary": "Fix addition.",
            }
        },
        files={"/src/calc.py": {"content": "def add(a, b):\n    return a - b\n"}},
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        selected_context=[_context("def add(a, b):\n    return a - b\n")],
        deprioritized_paths=[],
        target_old_span_hashes={},
        preferred_target_paths=[],
        preferred_target_symbols={},
        repo_path=None,
        model_metadata=ModelCallMetadata(provider="deepagents", model="gpt-test"),
        contract={},
    )

    assert result.plan is None
    assert result.metadata_update == {
        "structured_output_error": {
            "missing_required_fields": ["failure_mechanism", "target_rationale"],
        }
    }


def test_validate_deepagents_plan_result_rejects_no_op_patch() -> None:
    result = validate_deepagents_plan_result(
        result={
            "structured_response": {
                "path": "src/calc.py",
                "old": "return a - b",
                "new": "return a - b",
                "summary": "No-op.",
                "failure_mechanism": "add subtracts instead of adding",
                "target_rationale": "src/calc.py contains add's return expression",
            }
        },
        files={"/src/calc.py": {"content": "def add(a, b):\n    return a - b\n"}},
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        selected_context=[_context("def add(a, b):\n    return a - b\n")],
        deprioritized_paths=[],
        target_old_span_hashes={},
        preferred_target_paths=[],
        preferred_target_symbols={},
        repo_path=None,
        model_metadata=ModelCallMetadata(provider="deepagents", model="gpt-test"),
        contract={},
    )

    assert result.plan is None
    violation = result.metadata_update["no_op_patch_violation"]
    assert violation["path"] == "src/calc.py"
    assert "old and new replacement spans are identical" in violation["reason"]


def test_validate_deepagents_plan_result_rejects_span_outside_preferred_symbol(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = "def add(a, b):\n    return a - b\n\ndef unrelated():\n    return 0\n"
    (repo / "src" / "calc.py").write_text(source, encoding="utf-8")

    result = validate_deepagents_plan_result(
        result={
            "structured_response": {
                "path": "src/calc.py",
                "old": "    return 0",
                "new": "    return 1",
                "summary": "Change unrelated return.",
                "failure_mechanism": "add subtracts instead of adding",
                "target_rationale": "src/calc.py contains add's return expression",
            }
        },
        files={"/src/calc.py": {"content": source}},
        virtual_to_repo={"/src/calc.py": "src/calc.py"},
        selected_context=[_context(source)],
        deprioritized_paths=[],
        target_old_span_hashes={},
        preferred_target_paths=["src/calc.py"],
        preferred_target_symbols={"src/calc.py": ["add"]},
        repo_path=repo,
        model_metadata=ModelCallMetadata(provider="deepagents", model="gpt-test"),
        contract={},
    )

    assert result.plan is None
    violation = result.metadata_update["target_symbol_violation"]
    assert violation["path"] == "src/calc.py"
    assert violation["preferred_symbols"] == ["add"]


def _context(excerpt: str) -> RetrievedContext:
    return RetrievedContext(
        path="src/calc.py",
        rank=1,
        score=0.9,
        method="keyword",
        matched_terms=["add"],
        excerpt=excerpt,
    )
