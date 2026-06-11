from pathlib import Path

from patchsmith.context import (
    ContextBundle,
    ContextTarget,
    normalize_ctxhelm_export,
    promote_active_context_targets,
    retrieved_context_from_bundle,
)
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


def test_retrieved_context_from_bundle_preserves_matching_fallback_excerpt() -> None:
    bundle = normalize_ctxhelm_export(
        {"targetFiles": [{"path": "src/simple_calc.py", "confidence": 0.8}]},
        repo_path=Path("tests/fixtures/simple_calc_bug/repo"),
        provider_version=None,
        raw_artifact_path=None,
        latency_ms=0,
    )
    native = [
        RetrievedContext(
            path="src/simple_calc.py",
            rank=1,
            score=8.0,
            method="native_hybrid",
            matched_terms=["add"],
            excerpt="20: def add(left, right):\n21:     return left - right",
        )
    ]

    contexts = retrieved_context_from_bundle(
        bundle=bundle,
        repo_path=Path("tests/fixtures/simple_calc_bug/repo"),
        fallback_contexts=native,
        top_k=1,
    )

    assert contexts[0].path == "src/simple_calc.py"
    assert contexts[0].excerpt == native[0].excerpt
    assert "add" in contexts[0].matched_terms


def test_promote_active_context_targets_prepend_existing_reviewed_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "hinted.py").write_text("def target():\n    pass\n", encoding="utf-8")
    (repo / "src" / "other.py").write_text("def other():\n    pass\n", encoding="utf-8")
    bundle = ContextBundle(
        provider="patchsmith_native_hybrid",
        provider_version=None,
        targets=[
            ContextTarget(
                path="src/other.py",
                role="source",
                rank=1,
                confidence=0.5,
                reason="keyword",
                source="native_hybrid",
            )
        ],
        related_tests=[],
        validation_commands=[],
        diagnostics=[],
        warnings=[],
        pack_uri=None,
        source_text_logged=False,
        raw_artifact_path=None,
        latency_ms=0,
    )

    promoted = promote_active_context_targets(
        bundle=bundle,
        repo_path=repo,
        active_paths=("src/hinted.py#target", "missing.py", "../escape.py"),
    )

    assert [target.path for target in promoted.targets] == ["src/hinted.py", "src/other.py"]
    assert [target.rank for target in promoted.targets] == [1, 2]
    assert promoted.targets[0].role == "reviewed_source_hint"
    assert promoted.targets[0].source == "active_path"
