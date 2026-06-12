"""Public context-broker API facade."""

from __future__ import annotations

from patchsmith.context_bundle import (
    fallback_bundle,
    promote_active_context_targets,
    retrieved_context_from_bundle,
)
from patchsmith.context_ctxhelm import CtxhelmCliBroker, normalize_ctxhelm_export
from patchsmith.context_models import (
    ContextBroker,
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBudget,
    ContextBundle,
    ContextMode,
    ContextTarget,
    SupportsRetrieve,
)
from patchsmith.context_native import PatchSmithNativeBroker

__all__ = [
    "ContextBroker",
    "ContextBrokerError",
    "ContextBrokerRequest",
    "ContextBudget",
    "ContextBundle",
    "ContextMode",
    "ContextTarget",
    "CtxhelmCliBroker",
    "PatchSmithNativeBroker",
    "SupportsRetrieve",
    "fallback_bundle",
    "normalize_ctxhelm_export",
    "promote_active_context_targets",
    "retrieved_context_from_bundle",
]
