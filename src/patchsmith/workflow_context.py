from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from patchsmith.context import (
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBundle,
    CtxhelmCliBroker,
    PatchSmithNativeBroker,
    fallback_bundle,
    promote_active_context_targets,
    retrieved_context_from_bundle,
)
from patchsmith.models import RepositoryIndex, RetrievedContext, RunRequest
from patchsmith.retrieval import GraphRetriever, HybridRetriever, KeywordRetriever
from patchsmith.tracing import RunTrace


@dataclass(frozen=True)
class WorkflowContextSelection:
    context_bundle: ContextBundle
    retrieved_context: list[RetrievedContext]


class WorkflowContextSelector:
    def __init__(self) -> None:
        self.retriever = KeywordRetriever()
        self.native_broker = PatchSmithNativeBroker(self.retriever)
        self.hybrid_retriever = HybridRetriever()
        self.hybrid_broker = PatchSmithNativeBroker(
            self.hybrid_retriever, provider_name="patchsmith_native_hybrid"
        )
        self.graph_retriever = GraphRetriever()
        self.graph_broker = PatchSmithNativeBroker(
            self.graph_retriever, provider_name="patchsmith_native_graph"
        )
        self.ctxhelm_broker = CtxhelmCliBroker()

    def select(
        self,
        *,
        request: RunRequest,
        repo_path: Path,
        repo_index: RepositoryIndex,
        artifact_dir: Path,
        trace: RunTrace,
    ) -> WorkflowContextSelection:
        started = time.perf_counter()
        native_context = self.retriever.retrieve(
            repo_path=repo_path,
            repo_index=repo_index,
            issue_text=request.issue_text,
            top_k=request.top_k,
        )
        hybrid_context = self.hybrid_retriever.retrieve(
            repo_path=repo_path,
            repo_index=repo_index,
            issue_text=request.issue_text,
            top_k=request.top_k,
        )
        graph_context = self.graph_retriever.retrieve(
            repo_path=repo_path,
            repo_index=repo_index,
            issue_text=request.issue_text,
            top_k=request.top_k,
        )
        trace.time_event(
            node_name="retrieve",
            event_type="keyword_search",
            status="completed",
            input_summary=request.issue_text[:160],
            output_summary=", ".join(context.path for context in native_context) or "no matches",
            payload={"contexts": [context.to_dict() for context in native_context]},
            started=started,
        )

        broker_request = ContextBrokerRequest(
            repo_path=repo_path,
            task=request.issue_text,
            active_paths=request.context_paths,
        )
        native_bundle = self.native_broker.prepare(
            broker_request,
            repo_index=repo_index,
            artifact_dir=artifact_dir,
        )
        context_bundle = native_bundle
        fallback_contexts = native_context
        if request.context_provider == "native_hybrid":
            context_bundle = self.hybrid_broker.prepare(
                broker_request,
                repo_index=repo_index,
                artifact_dir=artifact_dir,
            )
            fallback_contexts = hybrid_context
        if request.context_provider == "native_graph":
            context_bundle = self.graph_broker.prepare(
                broker_request,
                repo_index=repo_index,
                artifact_dir=artifact_dir,
            )
            fallback_contexts = graph_context
        if request.context_provider in {"ctxhelm_cli", "auto"}:
            context_bundle = self._ctxhelm_or_fallback(
                broker_request=broker_request,
                repo_index=repo_index,
                artifact_dir=artifact_dir,
                native_bundle=native_bundle,
            )
        context_bundle = promote_active_context_targets(
            bundle=context_bundle,
            repo_path=repo_path,
            active_paths=request.context_paths,
        )

        trace.emit(
            node_name="context_broker",
            event_type="context_broker_call",
            status="fallback" if context_bundle.fallback_used else "completed",
            input_summary=request.context_provider,
            output_summary=(
                f"{context_bundle.provider} targets={len(context_bundle.targets)} "
                f"tests={len(context_bundle.related_tests)}"
            ),
            payload=context_bundle.to_dict(),
            latency_ms=context_bundle.latency_ms,
        )

        return WorkflowContextSelection(
            context_bundle=context_bundle,
            retrieved_context=retrieved_context_from_bundle(
                bundle=context_bundle,
                repo_path=repo_path,
                fallback_contexts=fallback_contexts,
                top_k=request.top_k,
            ),
        )

    def _ctxhelm_or_fallback(
        self,
        *,
        broker_request: ContextBrokerRequest,
        repo_index: RepositoryIndex,
        artifact_dir: Path,
        native_bundle: ContextBundle,
    ) -> ContextBundle:
        try:
            context_bundle = self.ctxhelm_broker.prepare(
                broker_request,
                repo_index=repo_index,
                artifact_dir=artifact_dir,
            )
        except ContextBrokerError as error:
            return fallback_bundle(
                provider="ctxhelm_cli",
                reason=str(error),
                native_bundle=native_bundle,
            )
        if context_bundle.targets:
            return context_bundle
        return fallback_bundle(
            provider="ctxhelm_cli",
            reason="ctxhelm returned no target files; using native keyword contexts",
            native_bundle=native_bundle,
        )


__all__ = ["WorkflowContextSelection", "WorkflowContextSelector"]
