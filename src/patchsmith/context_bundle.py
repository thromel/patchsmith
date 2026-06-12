from __future__ import annotations

from pathlib import Path

from patchsmith.context_models import ContextBundle, ContextTarget
from patchsmith.models import RetrievedContext


def retrieved_context_from_bundle(
    *,
    bundle: ContextBundle,
    repo_path: Path,
    fallback_contexts: list[RetrievedContext],
    top_k: int,
) -> list[RetrievedContext]:
    contexts: list[RetrievedContext] = []
    seen: set[str] = set()
    fallback_by_path = {context.path: context for context in fallback_contexts}
    for target in bundle.targets:
        if target.path in seen:
            continue
        seen.add(target.path)
        fallback = fallback_by_path.get(target.path)
        contexts.append(
            RetrievedContext(
                path=target.path,
                rank=len(contexts) + 1,
                score=float(target.confidence or (fallback.score if fallback else 0.0)),
                method=bundle.provider,
                matched_terms=(
                    [target.role, target.source, *fallback.matched_terms]
                    if fallback
                    else [target.role, target.source]
                ),
                excerpt=(
                    fallback.excerpt
                    if fallback and fallback.excerpt.strip()
                    else _read_excerpt(repo_path / target.path)
                ),
            )
        )
        if len(contexts) >= top_k:
            return contexts

    for context in fallback_contexts:
        if context.path in seen:
            continue
        seen.add(context.path)
        contexts.append(
            RetrievedContext(
                path=context.path,
                rank=len(contexts) + 1,
                score=context.score,
                method=f"{context.method}_fallback",
                matched_terms=context.matched_terms,
                excerpt=context.excerpt,
            )
        )
        if len(contexts) >= top_k:
            break
    return contexts


def promote_active_context_targets(
    *,
    bundle: ContextBundle,
    repo_path: Path,
    active_paths: tuple[str, ...],
) -> ContextBundle:
    active_targets = _active_context_targets(repo_path=repo_path, active_paths=active_paths)
    if not active_targets:
        return bundle

    seen_paths = {target.path for target in active_targets}
    merged_targets = [
        *active_targets,
        *(target for target in bundle.targets if target.path not in seen_paths),
    ]
    return ContextBundle(
        provider=bundle.provider,
        provider_version=bundle.provider_version,
        targets=_renumber_context_targets(merged_targets),
        related_tests=bundle.related_tests,
        validation_commands=bundle.validation_commands,
        diagnostics=bundle.diagnostics,
        warnings=bundle.warnings,
        pack_uri=bundle.pack_uri,
        source_text_logged=bundle.source_text_logged,
        raw_artifact_path=bundle.raw_artifact_path,
        latency_ms=bundle.latency_ms,
        fallback_used=bundle.fallback_used,
    )


def fallback_bundle(
    *,
    provider: str,
    reason: str,
    native_bundle: ContextBundle,
) -> ContextBundle:
    return ContextBundle(
        provider=f"{provider}_fallback",
        provider_version=None,
        targets=native_bundle.targets,
        related_tests=[],
        validation_commands=[],
        diagnostics=[{"code": "context_broker_fallback", "message": reason, "severity": "warning"}],
        warnings=[reason],
        pack_uri=None,
        source_text_logged=False,
        raw_artifact_path=None,
        latency_ms=native_bundle.latency_ms,
        fallback_used=True,
    )


def _active_context_targets(
    *,
    repo_path: Path,
    active_paths: tuple[str, ...],
) -> list[ContextTarget]:
    targets: list[ContextTarget] = []
    seen_paths: set[str] = set()
    for raw_path in active_paths:
        path = _normalize_active_context_path(raw_path)
        if path is None or path in seen_paths:
            continue
        if not _is_repo_relative_path(repo_path, path):
            continue
        if not (repo_path / path).is_file():
            continue
        seen_paths.add(path)
        targets.append(
            ContextTarget(
                path=path,
                role="reviewed_source_hint",
                rank=len(targets) + 1,
                confidence=1.0,
                reason="reviewed source hint",
                source="active_path",
            )
        )
    return targets


def _normalize_active_context_path(path: str) -> str | None:
    if not isinstance(path, str):
        return None
    file_path = path.strip().strip("`").partition("#")[0]
    if not file_path:
        return None
    return Path(file_path).as_posix()


def _renumber_context_targets(targets: list[ContextTarget]) -> list[ContextTarget]:
    return [
        ContextTarget(
            path=target.path,
            role=target.role,
            rank=index,
            confidence=target.confidence,
            reason=target.reason,
            source=target.source,
        )
        for index, target in enumerate(targets, start=1)
    ]


def _is_repo_relative_path(repo_path: Path, path: str) -> bool:
    if path.startswith(("/", "../")) or "/../" in path:
        return False
    try:
        (repo_path / path).resolve().relative_to(repo_path.resolve())
    except ValueError:
        return False
    return True


def _read_excerpt(path: Path, max_lines: int = 8) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return "\n".join(f"{index + 1}: {line}" for index, line in enumerate(lines[:max_lines]))


__all__ = [
    "fallback_bundle",
    "promote_active_context_targets",
    "retrieved_context_from_bundle",
]
