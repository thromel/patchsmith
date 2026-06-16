from __future__ import annotations

import pytest

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_context_selection import (
    context_selection_max_files,
    first_attempt_preferred_target_paths,
    preferred_target_paths_for_plan,
    preferred_target_symbols,
    select_deepagents_context,
)
from patchsmith.models import RetrievedContext
from patchsmith.target_localization import TargetLocalizationCandidate

pytestmark = pytest.mark.unit


def test_target_context_selection_auto_caps_to_localized_control_point() -> None:
    selection = select_deepagents_context(
        issue_text=(
            "Moving a pytest file leaves a stale co_filename after _read_pyc "
            "loads rewritten pyc bytecode."
        ),
        retrieved_context=[
            _context(
                path="src/_pytest/python.py",
                score=100.0,
                matched_terms=["reviewed_source_hint", "python"],
                excerpt="def pytest_pycollect_makeitem():\n    return None",
            ),
            _context(
                path="src/_pytest/assertion/rewrite.py",
                score=1.0,
                matched_terms=[
                    "reviewed_source_hint",
                    "symbol:_read_pyc",
                    "co_filename",
                    "pyc",
                ],
                excerpt=(
                    "def _read_pyc(source, pyc):\n"
                    "    co = marshal.load(pyc)\n"
                    "    return co"
                ),
            ),
            _context(
                path="testing/test_issue_14552_repro.py",
                matched_terms=["reviewed_source_hint", "validation_fixture"],
                excerpt="def test_moved_test_file_updates_code_filename(pytester): pass",
            ),
        ],
        config=DeepAgentsPlannerConfig(
            model="gpt-test",
            context_selection_mode="target",
        ),
        retry_feedback_manifest=None,
        deprioritized_paths=[],
        context_selection_pinned_paths=None,
        resource_budget=None,
    )

    assert selection.config.max_context_files == 1
    assert selection.selected_max_context_files == 1
    assert [context.path for context in selection.selected_context] == [
        "src/_pytest/assertion/rewrite.py"
    ]
    assert selection.target_candidates[0].path == "src/_pytest/assertion/rewrite.py"
    assert selection.preferred_target_paths == ["src/_pytest/assertion/rewrite.py"]
    assert selection.preferred_target_symbols == {
        "src/_pytest/assertion/rewrite.py": ["_read_pyc"]
    }


def test_pinned_paths_are_merged_before_localized_context_paths() -> None:
    selection = select_deepagents_context(
        issue_text="Retry still fails after config dispatch.",
        retrieved_context=[
            _context(
                path="src/_pytest/config/__init__.py",
                score=100.0,
                matched_terms=["reviewed_source_hint", "symbol:Config"],
                excerpt="class Config:\n    pass",
            ),
            _context(path="src/a.py", score=1.0, excerpt="def a():\n    return 'old'"),
            _context(path="src/b.py", score=1.0, excerpt="def b():\n    return 'old'"),
            _context(
                path="testing/test_repro.py",
                score=1.0,
                matched_terms=["validation_fixture"],
                excerpt="def test_repro():\n    assert False",
            ),
        ],
        config=DeepAgentsPlannerConfig(model="gpt-test", max_context_files=3),
        retry_feedback_manifest=None,
        deprioritized_paths=[],
        context_selection_pinned_paths=["src/a.py", "src/b.py"],
        resource_budget=None,
    )

    assert [context.path for context in selection.selected_context] == [
        "src/a.py",
        "src/b.py",
        "testing/test_repro.py",
    ]


def test_preferred_target_paths_keep_revived_historical_targets_first() -> None:
    candidates = [
        TargetLocalizationCandidate(
            path="src/rewrite.py",
            score=20.0,
            reasons=("stale_code_object_control_point",),
            historical=True,
        ),
        TargetLocalizationCandidate(
            path="src/pathlib.py",
            score=18.0,
            reasons=("symbol_identifiers:import_path",),
        ),
    ]

    assert preferred_target_paths_for_plan(
        candidates,
        config=DeepAgentsPlannerConfig(model="gpt-test"),
        retry_feedback_manifest="Previous patch changed the wrong file.",
        deprioritized_paths=["src/rewrite.py"],
        resource_budget=None,
    ) == ["src/rewrite.py", "src/pathlib.py"]


def test_first_attempt_preferred_target_paths_filter_when_top_target_is_stale_code_object() -> None:
    stale = TargetLocalizationCandidate(
        path="src/rewrite.py",
        score=15.0,
        reasons=("stale_code_object_control_point", "symbol_identifiers:_read_pyc"),
    )
    import_path = TargetLocalizationCandidate(
        path="src/pathlib.py",
        score=40.0,
        reasons=("symbol_identifiers:import_path",),
    )

    assert first_attempt_preferred_target_paths([stale, import_path]) == [
        "src/rewrite.py"
    ]


def test_symbol_focus_deduplicates_reviewed_and_detected_symbols() -> None:
    assert preferred_target_symbols(
        [
            TargetLocalizationCandidate(
                path="src/calc.py",
                score=10.0,
                reasons=(
                    "reviewed_symbols:add, add , subtract",
                    "symbol_identifiers:add,multiply",
                ),
            )
        ],
        preferred_target_paths=["/src/calc.py"],
    ) == {"src/calc.py": ["add", "subtract", "multiply"]}


def test_context_selection_max_files_keeps_unbounded_mode_without_strong_target() -> None:
    assert context_selection_max_files(
        config=DeepAgentsPlannerConfig(
            model="gpt-test",
            context_selection_mode="target",
        ),
        candidates=[
            TargetLocalizationCandidate(
                path="src/calc.py",
                score=1.0,
                reasons=("retrieval_score",),
            )
        ],
        retrieved_context=[
            _context(path="src/calc.py"),
            _context(path="src/other.py"),
        ],
    ) == 0


def _context(
    *,
    path: str = "src/calc.py",
    score: float = 0.9,
    matched_terms: list[str] | None = None,
    excerpt: str = "def add(a, b):\n    return a - b\n",
) -> RetrievedContext:
    return RetrievedContext(
        path=path,
        rank=1,
        score=score,
        method="keyword",
        matched_terms=matched_terms or ["add"],
        excerpt=excerpt,
    )
