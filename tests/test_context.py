from pathlib import Path

from patchsmith.context import normalize_ctxhelm_export, retrieved_context_from_bundle
from patchsmith.models import RetrievedContext


def test_normalize_ctxhelm_export_validates_paths_and_privacy() -> None:
    payload = {
        "packId": "pack-1",
        "sourceTextLogged": False,
        "warnings": ["warning"],
        "diagnostics": [{"code": "diag"}],
        "targetFiles": [
            {"path": "src/simple_calc.py", "confidence": 0.9, "reason": "target"},
            {"path": "../escape.py", "confidence": 1.0, "reason": "bad"},
        ],
        "retrievalCandidates": [
            {"path": "tests/test_simple_calc.py", "role": "test", "confidence": 0.8}
        ],
        "relatedTests": [
            {"path": "tests/test_simple_calc.py", "confidence": 0.8},
            {"path": "/etc/passwd", "confidence": 1.0},
        ],
        "validationCommands": ["python3 -m pytest", ""],
    }

    bundle = normalize_ctxhelm_export(
        payload,
        repo_path=Path("tests/fixtures/simple_calc_bug/repo"),
        provider_version="ctxhelm 2.4.0",
        raw_artifact_path="context.json",
        latency_ms=12,
    )

    assert bundle.provider == "ctxhelm_cli"
    assert bundle.provider_version == "ctxhelm 2.4.0"
    assert bundle.source_text_logged is False
    assert [target.path for target in bundle.targets] == ["src/simple_calc.py"]
    assert len(bundle.related_tests) == 1
    assert bundle.validation_commands == ["python3 -m pytest"]


def test_retrieved_context_from_bundle_appends_native_fallback() -> None:
    bundle = normalize_ctxhelm_export(
        {"targetFiles": [{"path": "src/simple_calc.py", "confidence": 0.8}]},
        repo_path=Path("tests/fixtures/simple_calc_bug/repo"),
        provider_version=None,
        raw_artifact_path=None,
        latency_ms=0,
    )
    native = [
        RetrievedContext(
            path="tests/test_simple_calc.py",
            rank=1,
            score=3.0,
            method="keyword",
            matched_terms=["add"],
            excerpt="1: def add(...",
        )
    ]

    contexts = retrieved_context_from_bundle(
        bundle=bundle,
        repo_path=Path("tests/fixtures/simple_calc_bug/repo"),
        fallback_contexts=native,
        top_k=2,
    )

    assert [context.path for context in contexts] == [
        "src/simple_calc.py",
        "tests/test_simple_calc.py",
    ]
    assert contexts[1].method == "keyword_fallback"
