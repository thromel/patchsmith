from pathlib import Path

from patchsmith.planning import RepairPlan
from patchsmith.runtime.plan_diagnostics import repair_plan_diagnostics


def test_repair_plan_diagnostics_records_bounded_text_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "src" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_text("alpha\nneedle\nneedle\nomega\n", encoding="utf-8")
    plan = RepairPlan(
        name="replace_needle",
        path="src/module.py",
        old="needle",
        new="replacement",
        summary="Replace one needle.",
    )

    diagnostics = repair_plan_diagnostics(plan, repo_path=repo)

    assert diagnostics["name"] == "replace_needle"
    assert diagnostics["path"] == "src/module.py"
    assert diagnostics["old_found"] is True
    assert diagnostics["old_occurrences"] == 2
    assert diagnostics["target_char_count"] == len("alpha\nneedle\nneedle\nomega\n")
    assert diagnostics["old"] == {
        "line_count": 1,
        "char_count": 6,
        "sha256_12": "09881f6ed933",
        "first_line_preview": "needle",
        "last_line_preview": "needle",
    }
    assert diagnostics["new"]["first_line_preview"] == "replacement"


def test_repair_plan_diagnostics_records_missing_old_span(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "src" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_text("alpha\nomega\n", encoding="utf-8")
    plan = RepairPlan(
        name="missing_span",
        path="src/module.py",
        old="needle",
        new="replacement",
        summary="Replace one needle.",
    )

    diagnostics = repair_plan_diagnostics(plan, repo_path=repo)

    assert diagnostics["old_found"] is False
    assert diagnostics["old_occurrences"] == 0
    assert "target_read_error" not in diagnostics


def test_repair_plan_diagnostics_records_target_read_errors(tmp_path: Path) -> None:
    plan = RepairPlan(
        name="unsafe_path",
        path="../outside.py",
        old="needle",
        new="replacement",
        summary="Invalid target.",
    )

    diagnostics = repair_plan_diagnostics(plan, repo_path=tmp_path / "repo")

    assert diagnostics["path"] == "../outside.py"
    assert "target_read_error" in diagnostics
    assert "unsafe relative path" in diagnostics["target_read_error"]
