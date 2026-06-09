from patchsmith.analysis import analyze_repair_outcome
from patchsmith.models import CommandPolicyDecision, CommandResult


def test_analyze_repair_outcome_validates_generated_patch() -> None:
    analysis = analyze_repair_outcome(
        patch_status="patch_generated",
        final_diff="--- a/src/a.py\n+++ b/src/a.py\n",
        test_result=_command_result(exit_code=0),
    )

    assert analysis.status == "validated"
    assert analysis.verdict == "patch_validated"
    assert analysis.patch_generated is True
    assert analysis.tests_passed is True


def test_analyze_repair_outcome_classifies_failed_unpatched_run() -> None:
    analysis = analyze_repair_outcome(
        patch_status="no_patch_generated",
        final_diff="",
        test_result=_command_result(exit_code=1),
    )

    assert analysis.status == "unresolved"
    assert analysis.verdict == "no_patch_tests_failed"
    assert analysis.failure_category == "no_patch_generated"


def _command_result(*, exit_code: int) -> CommandResult:
    return CommandResult(
        command="python3 -m pytest",
        exit_code=exit_code,
        stdout="",
        stderr="",
        duration_ms=1,
        timed_out=False,
        policy_decision=CommandPolicyDecision(allowed=True, reason="allowed"),
    )
