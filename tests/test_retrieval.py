from pathlib import Path

from patchsmith.ingest import clone_or_copy_repository, index_repository
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever


def test_keyword_retrieval_finds_likely_source_file(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/simple_calc_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    contexts = KeywordRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue,
        top_k=3,
    )

    assert contexts
    assert contexts[0].path == "src/simple_calc.py"
    assert "add" in contexts[0].matched_terms


def test_hybrid_retrieval_prioritizes_source_symbol_over_test_import(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_002_import_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue,
        top_k=3,
    )

    assert contexts
    assert contexts[0].path == "src/string_tools.py"
    assert contexts[0].method == "native_hybrid"


def test_hybrid_retrieval_uses_direct_path_hint(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_002_import_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue = "Failure appears isolated to src/string_tools.py."

    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue,
        top_k=3,
    )

    assert contexts
    assert contexts[0].path == "src/string_tools.py"
    assert "path_hint" in contexts[0].matched_terms


def test_hybrid_retrieval_exact_path_hint_beats_noisy_keyword_matches(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "src" / "requests" / "exceptions.py").write_text(
        "class ChunkedEncodingError(Exception):\n    pass\n",
        encoding="utf-8",
    )
    (repo / "docs" / "advanced.py").write_text(
        ("chunked encoding transient connection documentation issue " * 200),
        encoding="utf-8",
    )
    repo_index = index_repository(repo)
    issue = (
        "The fixture imports ChunkedEncodingError. "
        "Source files implied by fixture imports: `src/requests/exceptions.py`."
    )

    contexts = HybridRetriever().retrieve(
        repo_path=repo,
        repo_index=repo_index,
        issue_text=issue,
        top_k=2,
    )

    assert contexts[0].path == "src/requests/exceptions.py"
    assert "path_hint" in contexts[0].matched_terms


def test_hybrid_retrieval_excerpt_prefers_symbol_window_over_boilerplate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "pathlib.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from pathlib import Path",
                "",
                *[f"FILLER_{index} = {index}" for index in range(90)],
                "def import_path(path):",
                "    cached = sys.modules.get(path.stem)",
                "    return cached",
            ]
        ),
        encoding="utf-8",
    )
    repo_index = index_repository(repo)
    issue = (
        "Moved test files keep the old co_filename. "
        "Reviewed source files and fixture import hints: `src/pkg/pathlib.py`."
    )

    contexts = HybridRetriever().retrieve(
        repo_path=repo,
        repo_index=repo_index,
        issue_text=issue,
        top_k=1,
    )

    assert contexts[0].path == "src/pkg/pathlib.py"
    assert "def import_path" in contexts[0].excerpt
    assert "from __future__ import annotations" not in contexts[0].excerpt


def test_hybrid_retrieval_uses_traceback_path_and_symbol(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_002_import_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue = """Traceback (most recent call last):
  File "/tmp/work/repo/src/string_tools.py", line 2, in slugify
    return cleaned.strip("-")
NameError: name 're' is not defined
"""

    contexts = HybridRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue,
        top_k=3,
    )

    assert contexts
    assert contexts[0].path == "src/string_tools.py"
    assert "path_hint" in contexts[0].matched_terms
    assert "stack_symbol:slugify" in contexts[0].matched_terms


def test_graph_retrieval_expands_source_to_related_tests(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_002_import_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)
    issue = (fixture / "issue.md").read_text(encoding="utf-8")

    contexts = GraphRetriever().retrieve(
        repo_path=snapshot.repo_path,
        repo_index=repo_index,
        issue_text=issue,
        top_k=3,
    )

    assert contexts
    assert contexts[0].path == "src/string_tools.py"
    assert contexts[0].method == "native_graph"
    assert "tests/test_string_tools.py" in [context.path for context in contexts]
    assert any("graph_neighbor:src/string_tools.py" in context.matched_terms for context in contexts)
