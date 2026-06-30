from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from patchsmith.models import RepositoryIndex
from patchsmith.retrieval_features import cached_read_text, is_test_path, path_terms

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")

# Memoize the most recently built graph per repo path. The fingerprint over the
# Python files' (path, mtime, size) invalidates the cache when sources change,
# so retries that modify the workspace rebuild correctly.
_GRAPH_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], CodeContextGraph]] = {}


@dataclass(frozen=True)
class CodeGraphNode:
    node_id: str
    kind: str
    name: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodeGraphEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodeContextGraph:
    nodes: dict[str, CodeGraphNode]
    edges: list[CodeGraphEdge]
    file_terms: dict[str, set[str]]
    related_paths: dict[str, set[str]]

    def terms_for_path(self, path: str) -> set[str]:
        return self.file_terms.get(path, set())

    def neighbors_for_path(self, path: str) -> set[str]:
        return self.related_paths.get(path, set())

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "file_terms": {path: sorted(terms) for path, terms in self.file_terms.items()},
            "related_paths": {path: sorted(paths) for path, paths in self.related_paths.items()},
        }


def build_code_context_graph(*, repo_path: Path, repo_index: RepositoryIndex) -> CodeContextGraph:
    fingerprint = _repo_python_fingerprint(repo_path, repo_index)
    cache_key = str(repo_path)
    cached = _GRAPH_CACHE.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    graph = _build_code_context_graph(repo_path=repo_path, repo_index=repo_index)
    _GRAPH_CACHE[cache_key] = (fingerprint, graph)
    return graph


def _repo_python_fingerprint(
    repo_path: Path, repo_index: RepositoryIndex
) -> tuple[tuple[str, int, int], ...]:
    entries: list[tuple[str, int, int]] = []
    for file in repo_index.files:
        if file.language != "Python":
            continue
        try:
            stat = (repo_path / file.path).stat()
        except OSError:
            entries.append((file.path, -1, -1))
            continue
        entries.append((file.path, stat.st_mtime_ns, stat.st_size))
    entries.sort()
    return tuple(entries)


def _build_code_context_graph(*, repo_path: Path, repo_index: RepositoryIndex) -> CodeContextGraph:
    module_to_path = {
        module: file.path
        for file in repo_index.files
        if file.language == "Python"
        for module in _module_names_for_path(file.path)
    }
    nodes: dict[str, CodeGraphNode] = {}
    edges: list[CodeGraphEdge] = []
    file_terms: dict[str, set[str]] = {}
    related_paths: dict[str, set[str]] = defaultdict(set)

    for file in repo_index.files:
        if file.language != "Python":
            continue
        file_node = _file_node_id(file.path)
        nodes[file_node] = CodeGraphNode(
            node_id=file_node,
            kind="file",
            name=file.path,
            path=file.path,
        )
        text = cached_read_text(repo_path / file.path)
        terms = set(path_terms(file.path, drop_stopwords=False))

        parsed = _parse_python(text)
        symbols = _symbols_from_ast(parsed) if parsed else _symbols_from_text(text)
        imports = _imports_from_ast(parsed) if parsed else _imports_from_text(text)
        for symbol in symbols:
            symbol_node = f"symbol:{file.path}:{symbol}"
            nodes[symbol_node] = CodeGraphNode(
                node_id=symbol_node,
                kind="symbol",
                name=symbol,
                path=file.path,
            )
            edges.append(CodeGraphEdge(file_node, symbol_node, "defines"))
            terms.update(_name_terms(symbol))

        for module in imports:
            target_path = module_to_path.get(module)
            if target_path and target_path != file.path:
                target_node = _file_node_id(target_path)
                edges.append(CodeGraphEdge(file_node, target_node, "imports"))
                related_paths[file.path].add(target_path)
                related_paths[target_path].add(file.path)
                if is_test_path(file.path) and not is_test_path(target_path):
                    edges.append(CodeGraphEdge(file_node, target_node, "tests"))
                    edges.append(CodeGraphEdge(target_node, file_node, "covered_by"))
            else:
                module_node = f"module:{module}"
                nodes[module_node] = CodeGraphNode(
                    node_id=module_node,
                    kind="import",
                    name=module,
                    path=None,
                )
                edges.append(CodeGraphEdge(file_node, module_node, "imports"))
            terms.update(_name_terms(module))

        file_terms[file.path] = terms

    _add_test_basename_edges(repo_index, edges, related_paths)
    return CodeContextGraph(
        nodes=dict(sorted(nodes.items())),
        edges=edges,
        file_terms=file_terms,
        related_paths={path: set(paths) for path, paths in related_paths.items()},
    )


def _add_test_basename_edges(
    repo_index: RepositoryIndex,
    edges: list[CodeGraphEdge],
    related_paths: dict[str, set[str]],
) -> None:
    sources = [
        file.path
        for file in repo_index.files
        if file.language == "Python" and not is_test_path(file.path)
    ]
    source_by_stem = {Path(path).stem: path for path in sources}
    for file in repo_index.files:
        if file.language != "Python" or not is_test_path(file.path):
            continue
        stem = Path(file.path).stem
        source_stem = stem.removeprefix("test_").removesuffix("_test")
        source_path = source_by_stem.get(source_stem)
        if not source_path:
            continue
        test_node = _file_node_id(file.path)
        source_node = _file_node_id(source_path)
        edges.append(CodeGraphEdge(test_node, source_node, "tests"))
        edges.append(CodeGraphEdge(source_node, test_node, "covered_by"))
        related_paths[file.path].add(source_path)
        related_paths[source_path].add(file.path)


def _file_node_id(path: str) -> str:
    return f"file:{path}"


def _module_names_for_path(path: str) -> set[str]:
    without_suffix = path[:-3] if path.endswith(".py") else path
    parts = without_suffix.split("/")
    names = {parts[-1]}
    if parts and parts[0] in {"src", "lib"}:
        names.add(".".join(parts[1:]))
    names.add(".".join(parts))
    return {name for name in names if name}


def _parse_python(text: str) -> ast.AST | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _symbols_from_ast(parsed: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            symbols.add(node.name)
    return symbols


def _imports_from_ast(parsed: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def _symbols_from_text(text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(
            r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
            text,
            re.MULTILINE,
        )
    }


def _imports_from_text(text: str) -> set[str]:
    modules: set[str] = set()
    for match in re.finditer(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_.]*)", text, re.MULTILINE):
        modules.add(match.group(1).split(".", 1)[0])
    for match in re.finditer(
        r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+",
        text,
        re.MULTILINE,
    ):
        modules.add(match.group(1).split(".", 1)[0])
    return modules


def _name_terms(name: str) -> set[str]:
    terms: set[str] = set()
    for raw_token in TOKEN_RE.findall(name.replace(".", "_")):
        terms.update(part.lower() for part in raw_token.split("_") if len(part) > 2)
    return terms
