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


def test_analyze_repair_outcome_warns_on_high_risk_validated_patch() -> None:
    analysis = analyze_repair_outcome(
        patch_status="patch_generated",
        final_diff="--- a/src/a.py\n+++ b/src/a.py\n",
        test_result=_command_result(exit_code=0),
        patch_quality_severity="high",
    )

    assert analysis.status == "validated_with_warnings"
    assert analysis.verdict == "patch_validated_quality_warning"
    assert analysis.patch_generated is True
    assert analysis.tests_passed is True
    assert analysis.failure_category == "high_risk_patch_quality"
    assert analysis.patch_quality_severity == "high"


def test_analyze_repair_outcome_classifies_failed_unpatched_run() -> None:
    analysis = analyze_repair_outcome(
        patch_status="no_patch_generated",
        final_diff="",
        test_result=_command_result(exit_code=1),
    )

    assert analysis.status == "unresolved"
    assert analysis.verdict == "no_patch_tests_failed"
    assert analysis.failure_category == "no_patch_generated"


def test_analyze_repair_outcome_classifies_missing_pytest_as_environment_blocker() -> None:
    analysis = analyze_repair_outcome(
        patch_status="patch_generated",
        final_diff="--- a/src/a.py\n+++ b/src/a.py\n",
        test_result=_command_result(
            exit_code=1,
            stderr="/usr/bin/python3: No module named pytest\n",
        ),
    )

    assert analysis.status == "unvalidated"
    assert analysis.verdict == "patch_validation_blocked"
    assert analysis.failure_category == "test_environment_missing_pytest"
    assert "before retrying the model" in analysis.next_action


def _command_result(*, exit_code: int, stderr: str = "") -> CommandResult:
    return CommandResult(
        command="python3 -m pytest",
        exit_code=exit_code,
        stdout="",
        stderr=stderr,
        duration_ms=1,
        timed_out=False,
        policy_decision=CommandPolicyDecision(allowed=True, reason="allowed"),
    )
