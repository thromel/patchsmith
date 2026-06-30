from __future__ import annotations

import math
from collections import Counter

from patchsmith.models import ContextPackingMetadata, RetrievedContext
from patchsmith.retrieval_features import is_test_path


def summarize_context_pack(contexts: list[RetrievedContext]) -> ContextPackingMetadata:
    excerpt_char_count = sum(len(context.excerpt) for context in contexts)
    method_counts = Counter(context.method for context in contexts)
    return ContextPackingMetadata(
        context_count=len(contexts),
        source_context_count=sum(1 for context in contexts if _is_source_path(context.path)),
        test_context_count=sum(1 for context in contexts if is_test_path(context.path)),
        excerpt_char_count=excerpt_char_count,
        approx_token_count=_approx_token_count(excerpt_char_count),
        method_counts=dict(sorted(method_counts.items())),
    )


def _approx_token_count(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return math.ceil(char_count / 4)


def _is_source_path(path: str) -> bool:
    return path.startswith(("src/", "lib/", "patchsmith/"))
