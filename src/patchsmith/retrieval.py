from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from patchsmith.code_graph import build_code_context_graph
from patchsmith.models import RepositoryIndex, RetrievedContext
from patchsmith.retrieval_features import (
    _add_graph_score,
    _excerpt,
    _excerpt_terms,
    _graph_neighbor_boost,
    _path_hint_score,
    _path_hints,
    _path_prior,
    _runtime_cache_retry_query,
    _runtime_cache_source_score,
    _safe_read,
    _stack_symbols,
    _symbols,
    _token_counts,
    _tokens,
    is_test_path,
    path_terms,
    repo_file_path_set,
)


class KeywordRetriever:
    """Interpretable lexical retrieval baseline for Milestone 1."""

    def retrieve(
        self,
        *,
        repo_path: Path,
        repo_index: RepositoryIndex,
        issue_text: str,
        top_k: int = 5,
    ) -> list[RetrievedContext]:
        query_terms = _tokens(issue_text)
        if not query_terms:
            return []

        scored: list[tuple[float, str, list[str], str]] = []
        for file in repo_index.files:
            path = repo_path / file.path
            text = _safe_read(path)
            text_terms = Counter(_tokens(text))
            matched_terms = sorted(
                term for term in query_terms if term in text_terms or term in file.path.lower()
            )
            if not matched_terms:
                continue

            score = 0.0
            for term in matched_terms:
                score += text_terms.get(term, 0) * (1.0 + math.log1p(len(term)))
                if term in file.path.lower():
                    score += 3.0

            score += _path_prior(file.path)
            excerpt = _excerpt(text, matched_terms)
            scored.append((score, file.path, matched_terms, excerpt))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            RetrievedContext(
                path=path,
                rank=index + 1,
                score=score,
                method="keyword",
                matched_terms=matched_terms,
                excerpt=excerpt,
            )
            for index, (score, path, matched_terms, excerpt) in enumerate(scored[:top_k])
        ]


class HybridRetriever:
    """Symbol and path-aware native retrieval lane for early ablations."""

    def retrieve(
        self,
        *,
        repo_path: Path,
        repo_index: RepositoryIndex,
        issue_text: str,
        top_k: int = 5,
    ) -> list[RetrievedContext]:
        query_terms = _tokens(issue_text)
        path_hints = _path_hints(issue_text)
        stack_symbols = _stack_symbols(issue_text)
        runtime_cache_retry = _runtime_cache_retry_query(issue_text)
        if not query_terms and not path_hints and not stack_symbols:
            return []

        scored: list[tuple[float, str, list[str], str]] = []
        for file in repo_index.files:
            path = repo_path / file.path
            text = _safe_read(path)
            text_terms = _token_counts(text)
            file_path_terms = path_terms(file.path)
            symbols = _symbols(text, file.language)

            matched_terms = sorted(
                term
                for term in query_terms
                if term in text_terms or term in file_path_terms or term in symbols
            )
            matched_features = list(matched_terms)
            path_hint_score = _path_hint_score(file.path, path_hints)
            stack_symbol_matches = sorted(symbol for symbol in stack_symbols if symbol in symbols)
            if path_hint_score:
                matched_features.append("path_hint")
            if stack_symbol_matches:
                matched_features.extend(f"stack_symbol:{symbol}" for symbol in stack_symbol_matches)
            runtime_cache_score, runtime_cache_features = _runtime_cache_source_score(
                path=file.path,
                text=text,
                enabled=runtime_cache_retry,
            )
            if runtime_cache_features:
                matched_features.extend(runtime_cache_features)
            if not matched_features:
                continue

            is_test = is_test_path(file.path)
            score = 0.0
            for term in matched_terms:
                score += text_terms.get(term, 0) * (1.0 + math.log1p(len(term)))
                if term in file_path_terms:
                    score += 4.0
                if term in symbols:
                    score += 16.0 if not is_test else 2.0

            score += path_hint_score
            if stack_symbol_matches:
                score += sum(20.0 if not is_test else 4.0 for _ in stack_symbol_matches)
            score += _path_prior(file.path)
            if file.path.startswith(("src/", "lib/")):
                score += 4.0
            if is_test:
                score -= 3.0
            score += runtime_cache_score

            excerpt = _excerpt(
                text,
                matched_terms or stack_symbol_matches or runtime_cache_features,
            )
            scored.append((score, file.path, sorted(set(matched_features)), excerpt))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            RetrievedContext(
                path=path,
                rank=index + 1,
                score=score,
                method="native_hybrid",
                matched_terms=matched_terms,
                excerpt=excerpt,
            )
            for index, (score, path, matched_terms, excerpt) in enumerate(scored[:top_k])
        ]


class GraphRetriever:
    """Graph-augmented native retrieval lane for Sprint 6 experiments."""

    def __init__(self, base_retriever: HybridRetriever | None = None) -> None:
        self.base_retriever = base_retriever or HybridRetriever()

    def retrieve(
        self,
        *,
        repo_path: Path,
        repo_index: RepositoryIndex,
        issue_text: str,
        top_k: int = 5,
    ) -> list[RetrievedContext]:
        query_terms = _tokens(issue_text)
        graph = build_code_context_graph(repo_path=repo_path, repo_index=repo_index)
        seed_contexts = self.base_retriever.retrieve(
            repo_path=repo_path,
            repo_index=repo_index,
            issue_text=issue_text,
            top_k=max(top_k, 10),
        )
        if not query_terms and not seed_contexts:
            return []

        scored: dict[str, tuple[float, set[str]]] = {}
        repo_paths = repo_file_path_set(repo_index)
        for context in seed_contexts:
            _add_graph_score(
                scored,
                path=context.path,
                score=context.score + 4.0,
                features=set(context.matched_terms) | {"graph_seed"},
            )
            for neighbor in sorted(graph.neighbors_for_path(context.path)):
                if neighbor not in repo_paths:
                    continue
                neighbor_boost = _graph_neighbor_boost(seed_context=context, neighbor_path=neighbor)
                _add_graph_score(
                    scored,
                    path=neighbor,
                    score=neighbor_boost,
                    features={f"graph_neighbor:{context.path}"},
                )

        for file in repo_index.files:
            if file.language != "Python":
                continue
            graph_matches = query_terms & graph.terms_for_path(file.path)
            if not graph_matches:
                continue
            match_score = sum(8.0 + math.log1p(len(term)) for term in graph_matches)
            if is_test_path(file.path):
                match_score *= 0.35
            _add_graph_score(
                scored,
                path=file.path,
                score=match_score + _path_prior(file.path),
                features={f"graph_term:{term}" for term in graph_matches},
            )

        ranked: list[tuple[float, str, list[str], str]] = []
        for path, (score, features) in scored.items():
            text = _safe_read(repo_path / path)
            excerpt_terms = _excerpt_terms(features)
            ranked.append((score, path, sorted(features), _excerpt(text, excerpt_terms)))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            RetrievedContext(
                path=path,
                rank=index + 1,
                score=score,
                method="native_graph",
                matched_terms=features,
                excerpt=excerpt,
            )
            for index, (score, path, features, excerpt) in enumerate(ranked[:top_k])
        ]
