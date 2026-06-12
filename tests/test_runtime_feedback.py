from patchsmith.models import CommandPolicyDecision, CommandResult
from patchsmith.runtime.feedback import sandbox_feedback_summary


def test_sandbox_feedback_summary_highlights_failure_and_diff() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout="\n".join(
            [
                "test_a.py F",
                ">   ???",
                "E   AssertionError: assert 'test1/test_a.py' == 'test2/test_a.py'",
                "- test2/test_a.py",
                "+ test1/test_a.py",
            ]
        ),
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )
    diff = "\n".join(
        [
            "diff --git a/src/example.py b/src/example.py",
            "@@ -1,2 +1,2 @@",
            "-return stale_value",
            "+return checked_value",
        ]
    )

    summary = sandbox_feedback_summary(test_result=result, final_diff=diff)

    assert "Sandbox exit code: 1" in summary
    assert "AssertionError" in summary
    assert "test1/test_a.py" in summary
    assert "Previous changed hunks" in summary
    assert "-return stale_value" in summary
