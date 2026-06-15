from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from patchsmith.models import CommandResult


@dataclass(frozen=True)
class RepairOutcomeAnalysis:
    status: str
    verdict: str
    summary: str
    patch_generated: bool
    tests_passed: bool | None
    test_exit_code: int | None
    failure_category: str | None
    next_action: str
    patch_quality_severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_repair_outcome(
    *,
    patch_status: str,
    final_diff: str,
    test_result: CommandResult | None,
    patch_quality_severity: str | None = None,
) -> RepairOutcomeAnalysis:
    patch_generated = bool(final_diff.strip()) and patch_status == "patch_generated"
    if test_result is None:
        return RepairOutcomeAnalysis(
            status="unvalidated" if patch_generated else "unresolved",
            verdict="patch_unvalidated" if patch_generated else "no_patch_generated",
            summary=(
                "Patch candidate generated, but no sandbox command was available."
                if patch_generated
                else "No patch candidate was generated and no sandbox command was available."
            ),
            patch_generated=patch_generated,
            tests_passed=None,
            test_exit_code=None,
            failure_category="missing_test_command",
            next_action="Provide or detect a targeted test command before judging repair quality.",
            patch_quality_severity=patch_quality_severity,
        )

    tests_passed = test_result.exit_code == 0
    infrastructure_failure = _infrastructure_failure_category(test_result)
    if patch_generated and tests_passed:
        if patch_quality_severity == "high":
            return RepairOutcomeAnalysis(
                status="validated_with_warnings",
                verdict="patch_validated_quality_warning",
                summary=(
                    "Patch candidate generated and targeted sandbox tests passed, "
                    "but patch quality risk is high."
                ),
                patch_generated=True,
                tests_passed=True,
                test_exit_code=test_result.exit_code,
                failure_category="high_risk_patch_quality",
                next_action=(
                    "Review maintainability risk and broaden validation before treating "
                    "this as a clean repair."
                ),
                patch_quality_severity=patch_quality_severity,
            )
        return RepairOutcomeAnalysis(
            status="validated",
            verdict="patch_validated",
            summary="Patch candidate generated and targeted sandbox tests passed.",
            patch_generated=True,
            tests_passed=True,
            test_exit_code=test_result.exit_code,
            failure_category=None,
            next_action="Review final diff and broaden validation if needed.",
            patch_quality_severity=patch_quality_severity,
        )

    if patch_generated and not tests_passed:
        if infrastructure_failure is not None:
            return RepairOutcomeAnalysis(
                status="unvalidated",
                verdict="patch_validation_blocked",
                summary=(
                    "Patch candidate generated, but the sandbox command failed before "
                    "it could validate repair quality."
                ),
                patch_generated=True,
                tests_passed=False,
                test_exit_code=test_result.exit_code,
                failure_category=infrastructure_failure,
                next_action=(
                    "Fix the validation environment or test command before retrying the model."
                ),
                patch_quality_severity=patch_quality_severity,
            )
        return RepairOutcomeAnalysis(
            status="needs_followup",
            verdict="patch_failed_tests",
            summary="Patch candidate generated, but targeted sandbox tests failed.",
            patch_generated=True,
            tests_passed=False,
            test_exit_code=test_result.exit_code,
            failure_category="test_failure_after_patch",
            next_action="Use sandbox stdout/stderr to refine the repair plan or retry.",
            patch_quality_severity=patch_quality_severity,
        )

    if tests_passed:
        return RepairOutcomeAnalysis(
            status="ambiguous",
            verdict="tests_passed_without_patch",
            summary="No patch candidate was generated, but targeted sandbox tests passed.",
            patch_generated=False,
            tests_passed=True,
            test_exit_code=test_result.exit_code,
            failure_category="tests_do_not_reproduce_issue",
            next_action="Check whether the issue reproduces under the selected test command.",
            patch_quality_severity=patch_quality_severity,
        )

    if infrastructure_failure is not None:
        return RepairOutcomeAnalysis(
            status="unvalidated",
            verdict="validation_blocked",
            summary=(
                "No patch candidate was generated and the sandbox command failed before "
                "repair quality could be evaluated."
            ),
            patch_generated=False,
            tests_passed=False,
            test_exit_code=test_result.exit_code,
            failure_category=infrastructure_failure,
            next_action="Fix the validation environment or test command before retrying the model.",
            patch_quality_severity=patch_quality_severity,
        )

    return RepairOutcomeAnalysis(
        status="unresolved",
        verdict="no_patch_tests_failed",
        summary="No patch candidate was generated and targeted sandbox tests failed.",
        patch_generated=False,
        tests_passed=False,
        test_exit_code=test_result.exit_code,
        failure_category="no_patch_generated",
        next_action="Improve retrieval or planning before rerunning the sandbox command.",
        patch_quality_severity=patch_quality_severity,
    )


def _infrastructure_failure_category(test_result: CommandResult) -> str | None:
    combined_output = f"{test_result.stdout}\n{test_result.stderr}".lower()
    if test_result.policy_decision and not test_result.policy_decision.allowed:
        return "test_environment_policy_blocked"
    if test_result.timed_out:
        return "test_environment_timeout"
    if "no module named pytest" in combined_output:
        return "test_environment_missing_pytest"
    if "pytest: command not found" in combined_output:
        return "test_environment_missing_pytest"
    if "no such file or directory" in combined_output and "pytest" in combined_output:
        return "test_environment_missing_pytest"
    return None
