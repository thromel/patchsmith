from patchsmith.context_packing import summarize_context_pack
from patchsmith.models import RetrievedContext


def test_summarize_context_pack_counts_sources_tests_and_tokens() -> None:
    packing = summarize_context_pack(
        [
            RetrievedContext(
                path="src/simple_calc.py",
                rank=1,
                score=10.0,
                method="native_hybrid",
                matched_terms=["add"],
                excerpt="1: def add(left, right):\n2:     return left + right\n",
            ),
            RetrievedContext(
                path="tests/test_simple_calc.py",
                rank=2,
                score=4.0,
                method="native_hybrid",
                matched_terms=["add"],
                excerpt="1: def test_add():\n2:     assert add(1, 2) == 3\n",
            ),
        ]
    )

    assert packing.context_count == 2
    assert packing.source_context_count == 1
    assert packing.test_context_count == 1
    assert packing.excerpt_char_count > 0
    assert packing.approx_token_count > 0
    assert packing.method_counts == {"native_hybrid": 2}
