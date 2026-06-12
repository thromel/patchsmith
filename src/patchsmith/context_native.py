from __future__ import annotations

import time
from pathlib import Path

from patchsmith.context_models import (
    ContextBrokerRequest,
    ContextBundle,
    ContextTarget,
    SupportsRetrieve,
)
from patchsmith.models import RepositoryIndex
from patchsmith.retrieval import KeywordRetriever


class PatchSmithNativeBroker:
    def __init__(
        self,
        retriever: SupportsRetrieve | None = None,
        *,
        provider_name: str = "patchsmith_native",
    ) -> None:
        self.retriever: SupportsRetrieve = retriever or KeywordRetriever()
        self.provider_name = provider_name

    def prepare(
        self,
        request: ContextBrokerRequest,
        *,
        repo_index: RepositoryIndex,
        artifact_dir: Path | None = None,
    ) -> ContextBundle:
        started = time.perf_counter()
        contexts = self.retriever.retrieve(
            repo_path=request.repo_path,
            repo_index=repo_index,
            issue_text=request.task,
            top_k=5,
        )
        return ContextBundle(
            provider=self.provider_name,
            provider_version=None,
            targets=[
                ContextTarget(
                    path=context.path,
                    role="source",
                    rank=context.rank,
                    confidence=context.score,
                    reason=", ".join(context.matched_terms),
                    source=context.method,
                )
                for context in contexts
            ],
            related_tests=[],
            validation_commands=[],
            diagnostics=[],
            warnings=[],
            pack_uri=None,
            source_text_logged=False,
            raw_artifact_path=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


__all__ = ["PatchSmithNativeBroker"]
