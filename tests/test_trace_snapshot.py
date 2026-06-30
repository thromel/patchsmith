from __future__ import annotations

import pytest

from patchsmith.runtime.trace_snapshot import build_runtime_trace_snapshot

pytestmark = pytest.mark.unit


def test_empty_trace_yields_empty_snapshot() -> None:
    snapshot = build_runtime_trace_snapshot([])

    assert snapshot.patch_plan is None
    assert snapshot.quality is None
    assert snapshot.patch_target == ""
    assert snapshot.patch_old_hash == ""
    assert snapshot.mounted_context_paths == []
    assert snapshot.has_target_history_or_selection_violation is False
    assert snapshot.patch_quality_severity == ""
    assert snapshot.patch_quality_finding_codes == []


def test_snapshot_resolves_latest_signals_in_single_pass() -> None:
    trace = [
        {"patch_plan": {"path": "src/old.py", "old": {"sha256_12": "aaa"}}},
        {"quality": {"severity": "low", "findings": [{"code": "x"}]}},
        {
            "patch_plan": {"path": "src/new.py"},
            "metadata": {"target_history_violation": {"path": "src/new.py"}},
        },
        {"quality": {"severity": "high", "findings": [{"code": "naked_import"}, {"code": "x"}]}},
        {
            "node": "edit",
            "status": "failed",
            "summary": "rejected: unbound `helper`",
            "metadata": {
                "deepagents_contract": {
                    "context_budget": {"mounted_paths": ["/src/a.py", "src/b.py", "src/a.py"]}
                }
            },
        },
    ]

    snapshot = build_runtime_trace_snapshot(trace)

    # Latest patch_plan is the most recent one.
    assert snapshot.patch_plan == {"path": "src/new.py"}
    # patch_target resolves from the latest event that yields a path.
    assert snapshot.patch_target == "src/new.py"
    # old hash falls back to the most recent patch_plan that carries one.
    assert snapshot.patch_old_hash == "aaa"
    assert snapshot.quality == {
        "severity": "high",
        "findings": [{"code": "naked_import"}, {"code": "x"}],
    }
    assert snapshot.patch_quality_severity == "high"
    assert snapshot.patch_quality_finding_codes == ["naked_import", "x"]
    assert snapshot.has_target_history_or_selection_violation is True
    assert snapshot.safety_gate_rejection is not None
    assert snapshot.mounted_context_paths == ["src/a.py", "src/b.py"]
