from pathlib import Path

from patchsmith.code_graph import build_code_context_graph
from patchsmith.ingest import clone_or_copy_repository, index_repository


def test_code_context_graph_connects_source_symbols_imports_and_tests(tmp_path: Path) -> None:
    fixture = Path("evals/tasks/seeded_bugs_v1/task_002_import_bug")
    snapshot = clone_or_copy_repository(str(fixture / "repo"), tmp_path / "repo")
    repo_index = index_repository(snapshot.repo_path)

    graph = build_code_context_graph(repo_path=snapshot.repo_path, repo_index=repo_index)

    assert "slugify" in graph.terms_for_path("src/string_tools.py")
    assert "tests/test_string_tools.py" in graph.neighbors_for_path("src/string_tools.py")
    assert "src/string_tools.py" in graph.neighbors_for_path("tests/test_string_tools.py")
    edge_relations = {edge.relation for edge in graph.edges}
    assert "defines" in edge_relations
    assert "imports" in edge_relations
    assert "tests" in edge_relations


def test_code_context_graph_rebuilds_when_sources_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = repo / "src" / "widget.py"
    source.write_text("def original():\n    return 1\n", encoding="utf-8")
    repo_index = index_repository(repo)

    first = build_code_context_graph(repo_path=repo, repo_index=repo_index)
    assert "original" in {node.name for node in first.nodes.values() if node.kind == "symbol"}

    # Rewrite the file with a different symbol and size; the mtime/size-keyed
    # fingerprint must invalidate the memoized graph.
    source.write_text("def replacement_symbol():\n    return 2\n", encoding="utf-8")
    repo_index = index_repository(repo)
    second = build_code_context_graph(repo_path=repo, repo_index=repo_index)
    symbol_names = {node.name for node in second.nodes.values() if node.kind == "symbol"}
    assert "replacement_symbol" in symbol_names
    assert "original" not in symbol_names
