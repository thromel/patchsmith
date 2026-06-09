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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_repair_outcome(
    *,
    patch_status: str,
    final_diff: str,
    test_result: CommandResult | None,
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
        )

    tests_passed = test_result.exit_code == 0
    if patch_generated and tests_passed:
        return RepairOutcomeAnalysis(
            status="validated",
            verdict="patch_validated",
            summary="Patch candidate generated and targeted sandbox tests passed.",
            patch_generated=True,
            tests_passed=True,
            test_exit_code=test_result.exit_code,
            failure_category=None,
            next_action="Review final diff and broaden validation if needed.",
        )

    if patch_generated and not tests_passed:
        return RepairOutcomeAnalysis(
            status="needs_followup",
            verdict="patch_failed_tests",
            summary="Patch candidate generated, but targeted sandbox tests failed.",
            patch_generated=True,
            tests_passed=False,
            test_exit_code=test_result.exit_code,
            failure_category="test_failure_after_patch",
            next_action="Use sandbox stdout/stderr to refine the repair plan or retry.",
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
    )
