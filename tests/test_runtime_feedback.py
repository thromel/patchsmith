from patchsmith.analysis import RepairOutcomeAnalysis
from patchsmith.models import CommandPolicyDecision, CommandResult
from patchsmith.runtime.attempts import (
    attempt_history_summary,
    attempted_target_old_span_hashes,
    attempted_target_paths,
    feedback_attempt_record,
    ineffective_target_paths,
    mounted_context_paths,
    retry_failure_class,
    retry_feedback_brief,
    retry_feedback_labels,
)
from patchsmith.runtime.feedback import (
    assertion_progress_summary,
    failure_localization_summary,
    patch_plan_feedback_summary,
    safety_gate_rejection_summary,
    sandbox_failure_signature,
    sandbox_feedback_summary,
)


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
    assert "Failure localization cues" in summary
    assert "Assertion actual: test1/test_a.py" in summary
    assert "Assertion expected: test2/test_a.py" in summary
    assert "Path-like assertion mismatch" in summary
    assert "Stale path cache hypothesis" in summary
    assert "`test1` vs `test2`" in summary
    assert "post-import __file__ checks are usually too late" in summary
    assert "Retry source search terms" in summary
    assert "AssertionRewritingHook" in summary
    assert "co_filename" in summary
    assert "AssertionError" in summary
    assert "test1/test_a.py" in summary
    assert "Previous changed hunks" in summary
    assert "-return stale_value" in summary


def test_sandbox_feedback_summary_flags_import_only_diff() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout="E   AssertionError: behavior still wrong\n",
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
            "diff --git a/src/python.py b/src/python.py",
            "@@ -1,2 +1,3 @@",
            "+from _pytest.pathlib import ImportPathMismatchError",
            " from _pytest.pathlib import import_path",
        ]
    )

    summary = sandbox_feedback_summary(test_result=result, final_diff=diff)

    assert "Patch effect warning" in summary
    assert "changed only Python import statements" in summary
    assert "ImportError, ModuleNotFoundError, or NameError" in summary


def test_sandbox_feedback_summary_warns_about_basename_only_path_guard() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/private/tmp/session/test1/test_a.py' == "
            "'/private/tmp/session/test2/test_a.py'\n"
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
            "diff --git a/src/_pytest/assertion/rewrite.py b/src/_pytest/assertion/rewrite.py",
            "@@ -389,6 +389,8 @@ def _read_pyc(",
            "+        if Path(co_filename := source).name != source.name:",
            "+            return None",
        ]
    )

    summary = sandbox_feedback_summary(test_result=result, final_diff=diff)

    assert "Patch effect warning" in summary
    assert "compared only a path basename" in summary
    assert "different parent directory" in summary
    assert "Compare the full cached filename/path" in summary


def test_failure_localization_summary_handles_exception_without_assert_comparison() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout="",
        stderr="AttributeError: 'bytes' object has no attribute 'exists'\n",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    summary = failure_localization_summary(result)

    assert "Exception class: AttributeError" in summary
    assert "Assertion actual" not in summary


def test_failure_localization_summary_distinguishes_path_from_source_text() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout=(
            "E   assert \"b'\\\\nfrom inspect import currentframe\\\\n'\" == "
            "'/private/tmp/test1/test_a.py'\n"
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

    summary = failure_localization_summary(result)

    assert "one side is not path-like" in summary
    assert "Actual is path-like: false" in summary
    assert "expected is path-like: true" in summary


def test_failure_localization_summary_identifies_same_file_different_parent_cache() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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

    summary = failure_localization_summary(result)

    assert "Assertion actual: /tmp/pytest-1/test_name0/test1/test_a.py" in summary
    assert "Assertion expected: /tmp/pytest-1/test_name0/test2/test_a.py" in summary
    assert "same file `test_a.py`" in summary
    assert "`test1` vs `test2`" in summary
    assert "module, function, or code object created before the move" in summary
    assert "cache read, bytecode validation, compile, or exec site" in summary
    assert "_read_pyc" in summary
    assert "exec(co, module.__dict__)" in summary
    assert "sys.modules" in summary
    assert "__pycache__" in summary


def test_sandbox_failure_signature_compacts_path_assertion() -> None:
    result = CommandResult(
        command="python3 -m pytest",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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

    signature = sandbox_failure_signature(result)

    assert "AssertionError" in signature
    assert "path:test_name0/test1/test_a.py!=test_name0/test2/test_a.py" in signature
    assert "at:pytest-1/test_name0/test1/test_a.py:5: AssertionError" in signature


def test_patch_plan_feedback_summary_highlights_span_match_diagnostics() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "edit",
                "status": "failed",
                "patch_plan": {
                    "path": "src/example.py",
                    "target_char_count": 1200,
                    "old_found": False,
                    "old_occurrences": 0,
                    "old": {
                        "line_count": 2,
                        "char_count": 42,
                        "sha256_12": "abc123def456",
                        "first_line_preview": "def broken():",
                        "last_line_preview": "return stale",
                    },
                    "new": {
                        "line_count": 2,
                        "char_count": 44,
                        "sha256_12": "def456abc123",
                        "first_line_preview": "def broken():",
                        "last_line_preview": "return fixed",
                    },
                },
            }
        ]
    )

    assert "Previous patch plan diagnostics" in summary
    assert "Path: src/example.py" in summary
    assert "Old span found in clean target: False" in summary
    assert "Old span occurrences: 0" in summary
    assert "sha256_12=abc123def456" in summary
    assert "return fixed" in summary


def test_patch_plan_feedback_summary_includes_nearest_source_excerpt() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "edit",
                "status": "failed",
                "patch_plan": {
                    "path": "src/example.py",
                    "old_found": False,
                    "old_occurrences": 0,
                    "old": {"sha256_12": "abc123def456"},
                    "nearest_source_excerpt": {
                        "start_line": 10,
                        "end_line": 13,
                        "similarity": 0.82,
                        "text": "def target(value: str | Path) -> None:\n    return value",
                    },
                },
            }
        ]
    )

    assert "Nearest exact source excerpt for old-span repair" in summary
    assert "lines 10-13" in summary
    assert "similarity=0.82" in summary
    assert "Copy this exact source text" in summary
    assert "str | Path" in summary


def test_patch_plan_feedback_summary_includes_safety_gate_unbound_names() -> None:
    runtime_trace = [
        {
            "node": "edit",
            "status": "failed",
            "summary": (
                "replacement introduces potentially unbound Python name(s) in "
                "src/_pytest/pathlib.py: `_is_same`"
            ),
            "patch_plan": {
                "path": "src/_pytest/pathlib.py",
                "old_found": True,
                "old_occurrences": 1,
                "old": {
                    "line_count": 28,
                    "char_count": 1240,
                    "sha256_12": "c61e2290627e",
                    "first_line_preview": "if mode is ImportMode.importlib:",
                    "last_line_preview": "return mod",
                },
            },
        }
    ]

    safety = safety_gate_rejection_summary(runtime_trace)
    summary = patch_plan_feedback_summary(runtime_trace)

    assert "Patch safety gate rejection" in safety
    assert "replacement introduces potentially unbound Python name" in safety
    assert "Unbound name correction" in safety
    assert "`_is_same`" in safety
    assert "Patch safety gate rejection" in summary
    assert "Old span found in clean target: True" in summary


def test_safety_gate_rejection_summary_includes_span_boundary_guidance() -> None:
    runtime_trace = [
        {
            "node": "edit",
            "status": "failed",
            "summary": (
                "replacement old span for src/_pytest/assertion/rewrite.py ends "
                "on Python compound statement without its body: "
                "`if int.from_bytes(size_data, \"little\") != size & 0xFFFFFFFF:`"
            ),
        }
    ]

    safety = safety_gate_rejection_summary(runtime_trace)

    assert "Patch safety gate rejection" in safety
    assert "Span boundary correction" in safety
    assert "syntactically complete Python" in safety
    assert "include the complete block" in safety


def test_patch_plan_feedback_summary_includes_target_history_violation() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "target_history_violation": {
                        "path": "src/_pytest/pathlib.py",
                        "reason": (
                            "selected target path was deprioritized by prior failed "
                            "attempts without naming distinct branch or call-site evidence"
                        ),
                        "required_evidence": (
                            "target_rationale must explain the new branch, cache read, "
                            "dispatch site, or call path inside this file and cite an "
                            "exact identifier from the old span"
                        ),
                        "deprioritized_paths": [
                            "src/_pytest/assertion/rewrite.py",
                            "src/_pytest/pathlib.py",
                        ],
                        "preferred_target_paths": [
                            "src/_pytest/python.py",
                            "src/_pytest/config/__init__.py",
                        ],
                    }
                },
            }
        ]
    )

    assert "Repeated target rejected by target-history guard" in summary
    assert "src/_pytest/pathlib.py" in summary
    assert "distinct branch or call-site evidence" in summary
    assert "Required next-target evidence" in summary
    assert "old span" in summary
    assert "src/_pytest/assertion/rewrite.py" in summary
    assert "Preferred untried source targets" in summary
    assert "src/_pytest/python.py" in summary


def test_patch_plan_feedback_summary_includes_target_selection_violation() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "target_selection_violation": {
                        "path": "tests/test_repro.py",
                        "reason": "selected target path is outside the retry patchable path policy",
                        "required_path_policy": (
                            "path must be one of the preferred untried source targets"
                        ),
                        "preferred_target_paths": ["src/_pytest/python.py"],
                        "deprioritized_paths": ["src/_pytest/pathlib.py"],
                    }
                },
            }
        ]
    )

    assert "Patchable target policy rejected path" in summary
    assert "tests/test_repro.py" in summary
    assert "Patchable source targets" in summary
    assert "src/_pytest/python.py" in summary
    assert "Historical target paths" in summary
    assert "src/_pytest/pathlib.py" in summary


def test_patch_plan_feedback_summary_includes_target_symbol_violation() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "target_symbol_violation": {
                        "path": "src/_pytest/assertion/rewrite.py",
                        "reason": (
                            "selected path matched the constrained patchable path policy, "
                            "but the exact old span did not enter a preferred symbol"
                        ),
                        "required_symbol_policy": (
                            "old must include one of the preferred symbols"
                        ),
                        "preferred_symbols": ["_read_pyc"],
                    }
                },
            }
        ]
    )

    assert "Preferred symbol policy rejected old span" in summary
    assert "src/_pytest/assertion/rewrite.py" in summary
    assert "did not enter a preferred symbol" in summary
    assert "Preferred symbols for next old span" in summary
    assert "_read_pyc" in summary


def test_patch_plan_feedback_summary_includes_no_op_patch_violation() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "no_op_patch_violation": {
                        "path": "src/_pytest/assertion/rewrite.py",
                        "reason": (
                            "old and new replacement spans are identical after normalization"
                        ),
                        "required_patch_policy": (
                            "new must make a concrete source-behavior change"
                        ),
                        "old_sha256_12": "abc123",
                        "new_sha256_12": "abc123",
                    }
                },
            }
        ]
    )

    assert "No-op patch policy rejected replacement" in summary
    assert "src/_pytest/assertion/rewrite.py" in summary
    assert "identical after normalization" in summary
    assert "real behavior-changing old/new span" in summary


def test_patch_plan_feedback_summary_marks_no_op_replacement() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "plan",
                "status": "completed",
                "patch_plan": {
                    "path": "src/_pytest/assertion/rewrite.py",
                    "old_found": True,
                    "old_occurrences": 1,
                    "old": {
                        "line_count": 47,
                        "char_count": 1778,
                        "sha256_12": "992865cf2a70",
                        "first_line_preview": "def _read_pyc(",
                        "last_line_preview": "return co",
                    },
                    "new": {
                        "line_count": 47,
                        "char_count": 1778,
                        "sha256_12": "992865cf2a70",
                        "first_line_preview": "def _read_pyc(",
                        "last_line_preview": "return co",
                    },
                },
            }
        ]
    )

    assert "No-op replacement rejected" in summary
    assert "old and new span hashes are identical" in summary
    assert "do not abandon this source control point" in summary
    assert "narrower exact old span" in summary


def test_patch_plan_feedback_summary_includes_patch_quality() -> None:
    summary = patch_plan_feedback_summary(
        [
            {
                "node": "patch_quality",
                "status": "high",
                "quality": {
                    "severity": "high",
                    "score": 8,
                    "findings": [
                        {
                            "code": "broad_exception_swallow",
                            "severity": "high",
                            "message": "patch catches broad exceptions and suppresses them",
                        }
                    ],
                },
            }
        ]
    )

    assert "Patch quality risk: high" in summary
    assert "broad_exception_swallow" in summary


def test_retry_feedback_brief_packages_sandbox_and_patch_diagnostics() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_bug.py",
        exit_code=1,
        stdout="E   AssertionError: wrong filename\n",
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

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Applied a patch in the wrong branch.",
        test_result=result,
        final_diff=diff,
        attempt=1,
        runtime_trace=[
            {
                "patch_plan": {
                    "path": "src/example.py",
                    "old_found": True,
                    "old_occurrences": 1,
                    "old": {"sha256_12": "abc123def456", "first_line_preview": "return stale"},
                }
            }
        ],
    )

    assert "# PatchSmith Retry Feedback" in brief
    assert "Previous attempt: `1`" in brief
    assert "Failed diff sha256_12" in brief
    assert "Failure class: `validation_failed`" in brief
    assert "Next retry focus: localize the failing assertion or exception first" in brief
    assert "Do not return the same failed diff unchanged" in brief
    assert "Do not return a patch with the same failed diff hash" in brief
    assert "copy that excerpt verbatim" in brief
    assert "Do not return an import-only patch" in brief
    assert "ImportError, ModuleNotFoundError, or NameError" in brief
    assert "previous patch applied cleanly, but validation still failed" in brief
    assert "Failure localization cues" in brief
    assert "AssertionError: wrong filename" in brief
    assert "Previous patch plan diagnostics" in brief
    assert "sha256_12=abc123def456" in brief
    assert "```diff" in brief


def test_retry_feedback_labels_classify_test_failure_retry() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_bug.py",
        exit_code=1,
        stdout="E   AssertionError: wrong filename\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    labels = retry_feedback_labels(
        test_result=result,
        runtime_trace=[
            {
                "node": "plan",
                "patch_plan": {
                    "path": "src/example.py",
                    "old": {"sha256_12": "abc123def456"},
                },
            }
        ],
        attempt_history=[],
    )

    assert labels == (
        "test_failure_retry",
        "failure_class_validation_failed",
        "old_span_repair",
    )


def test_retry_feedback_labels_classify_safety_gate_unbound_retry() -> None:
    labels = retry_feedback_labels(
        test_result=None,
        runtime_trace=[
            {
                "node": "edit",
                "status": "failed",
                "summary": (
                    "replacement introduces potentially unbound Python name(s) in "
                    "src/_pytest/pathlib.py: `_is_same`"
                ),
                "patch_plan": {
                    "path": "src/_pytest/pathlib.py",
                    "old": {"sha256_12": "c61e2290627e"},
                },
            }
        ],
        attempt_history=[],
    )

    assert labels == (
        "test_failure_retry",
        "missing_validation_retry",
        "failure_class_safety_gate_rejection",
        "old_span_repair",
        "safety_gate_retry",
        "unbound_name_retry",
    )


def test_retry_feedback_labels_classify_quality_and_target_history_retry() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_bug.py",
        exit_code=0,
        stdout="1 passed\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    labels = retry_feedback_labels(
        test_result=result,
        repair_analysis=RepairOutcomeAnalysis(
            status="validated_with_warnings",
            verdict="patch_validated_quality_warning",
            summary="Tests passed, but patch quality risk is high.",
            patch_generated=True,
            tests_passed=True,
            test_exit_code=0,
            failure_category="high_risk_patch_quality",
            next_action="retry with lower-risk repair",
            patch_quality_severity="high",
        ),
        runtime_trace=[
            {
                "node": "plan",
                "metadata": {
                    "target_history_violation": {
                        "path": "src/example.py",
                    }
                },
                "patch_plan": {
                    "path": "src/example.py",
                    "old": {"sha256_12": "abc123def456"},
                },
            },
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "high",
                    "findings": [
                        {"code": "broad_exception_swallow"},
                        {"code": "source_text_recompile"},
                    ],
                },
            },
        ],
        attempt_history=[
            {
                "patch_target": "src/example.py",
            },
            {
                "patch_target": "src/example.py",
                "progress_classification": "partial_assertion_progress",
            }
        ],
    )

    assert labels == (
        "quality_retry",
        "failure_class_quality_risk",
        "same_target_retry",
        "old_span_repair",
        "target_history_override",
        "partial_assertion_progress",
        "broad_exception_retry",
        "source_recompile_retry",
    )


def test_retry_failure_class_prioritizes_actionable_retry_causes() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_bug.py",
        exit_code=1,
        stdout="E   AssertionError: wrong filename\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    assert (
        retry_failure_class(
            agent_status="patch_generated",
            test_result=result,
            final_diff="diff --git a/src/example.py b/src/example.py\n+return fixed\n",
        )
        == "validation_failed"
    )
    assert (
        retry_failure_class(
            agent_status="no_patch_generated",
            test_result=None,
            runtime_trace=[
                {
                    "node": "edit",
                    "status": "failed",
                    "summary": (
                        "replacement introduces potentially unbound Python name(s) in "
                        "src/example.py: `_missing`"
                    ),
                }
            ],
        )
        == "safety_gate_rejection"
    )
    assert (
        retry_failure_class(
            agent_status="patch_generated",
            test_result=result,
            runtime_trace=[
                {
                    "node": "plan",
                    "patch_plan": {"path": "src/example.py"},
                }
            ],
            attempt_history=[
                {"patch_target": "src/example.py"},
                {"patch_target": "src/example.py"},
            ],
        )
        == "repeated_target_failure"
    )
    assert (
        retry_failure_class(
            agent_status="patch_generated",
            test_result=CommandResult(
                command="python3 -m pytest",
                exit_code=0,
                stdout="1 passed\n",
                stderr="",
                duration_ms=12,
                timed_out=False,
                policy_decision=CommandPolicyDecision(
                    allowed=True,
                    reason="allowed",
                    tokens=("python3", "-m", "pytest"),
                ),
            ),
            repair_analysis=RepairOutcomeAnalysis(
                status="validated_with_warnings",
                verdict="patch_validated_quality_warning",
                summary="Tests passed, but patch quality risk is high.",
                patch_generated=True,
                tests_passed=True,
                test_exit_code=0,
                failure_category="high_risk_patch_quality",
                next_action="retry with lower-risk repair",
                patch_quality_severity="high",
            ),
        )
        == "quality_risk"
    )


def test_retry_feedback_brief_rejects_failed_filename_metadata_rewrite() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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
            "diff --git a/src/_pytest/assertion/rewrite.py b/src/_pytest/assertion/rewrite.py",
            "@@ -397,7 +397,7 @@",
            "-        return co",
            "+        return co.replace(co_filename=str(source))",
        ]
    )

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Rewrote co_filename on cached pyc code objects.",
        test_result=result,
        final_diff=diff,
        attempt=2,
        runtime_trace=[
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "medium",
                    "findings": [
                        {
                            "code": "filename_metadata_rewrite",
                            "severity": "medium",
                            "message": "patch rewrites code-object filename metadata",
                        }
                    ],
                },
            }
        ],
    )

    assert "Rejected repair hypothesis" in brief
    assert "rewrote code-object filename metadata" in brief
    assert "Do not keep setting or replacing `co_filename` directly" in brief
    assert "invalidating stale bytecode/module cache entries" in brief
    assert "`_read_pyc`, `compile`, or `exec`" in brief


def test_retry_feedback_brief_rejects_high_risk_source_text_recompile() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=0,
        stdout="1 passed\n",
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
            "diff --git a/src/_pytest/assertion/rewrite.py b/src/_pytest/assertion/rewrite.py",
            "@@ -397,6 +397,7 @@",
            "+        co = compile(source.read_text(encoding=\"utf-8\"), str(source), \"exec\")",
        ]
    )

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Recompiled current source text after reading a cached pyc.",
        test_result=result,
        final_diff=diff,
        attempt=4,
        runtime_trace=[
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "high",
                    "findings": [
                        {
                            "code": "source_text_recompile",
                            "severity": "high",
                            "message": "patch recompiles source text directly",
                        }
                    ],
                },
            }
        ],
        repair_analysis=RepairOutcomeAnalysis(
            status="validated_with_warnings",
            verdict="patch_validated_quality_warning",
            summary="Tests passed, but patch quality risk is high.",
            patch_generated=True,
            tests_passed=True,
            test_exit_code=0,
            failure_category="high_risk_patch_quality",
            next_action="retry with lower-risk repair",
            patch_quality_severity="high",
        ),
    )

    assert "Risky diff sha256_12" in brief
    assert "source_text_recompile" in brief
    assert "bypassed cache validation by recompiling source text directly" in brief
    assert "Do not keep recompiling source as the repair" in brief
    assert "returning `None` to trigger the existing compile path" in brief
    assert "basename-only `.name` check" in brief


def test_retry_feedback_brief_rejects_broad_exception_swallowing() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
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
            "diff --git a/src/_pytest/assertion/rewrite.py b/src/_pytest/assertion/rewrite.py",
            "@@ -397,6 +397,12 @@",
            "+        try:",
            "+            co = co.replace(co_filename=str(source))",
            "+        except Exception:",
            "+            pass",
        ]
    )

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Wrapped code filename repair in broad exception handling.",
        test_result=result,
        final_diff=diff,
        attempt=4,
        runtime_trace=[
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "high",
                    "findings": [
                        {
                            "code": "broad_exception_swallow",
                            "severity": "high",
                            "message": "patch catches broad exceptions and suppresses them",
                        }
                    ],
                },
            }
        ],
    )

    assert "Rejected high-risk repair mechanism" in brief
    assert "broad exception swallowing" in brief
    assert "Do not keep a catch-and-fallback wrapper" in brief
    assert "explicit precondition check" in brief
    assert "catch the specific expected exception" in brief


def test_retry_feedback_brief_rejects_failed_module_file_metadata_rewrite() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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
            "diff --git a/src/_pytest/_py/path.py b/src/_pytest/_py/path.py",
            "@@ -1129,6 +1129,9 @@",
            "+            if modfile != str(self):",
            "+                mod.__file__ = str(self)",
            "+                modfile = mod.__file__",
        ]
    )

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Updated module __file__ metadata after moving a test file.",
        test_result=result,
        final_diff=diff,
        attempt=5,
        runtime_trace=[
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "medium",
                    "findings": [
                        {
                            "code": "module_file_metadata_rewrite",
                            "severity": "medium",
                            "message": "patch rewrites module __file__ metadata",
                        }
                    ],
                },
            }
        ],
    )

    assert "Rejected repair hypothesis" in brief
    assert "rewrote module `__file__` metadata" in brief
    assert "Do not keep assigning `__file__`" in brief
    assert "invalidating stale module or bytecode cache entries" in brief
    assert "import, `_read_pyc`, `compile`, or `exec`" in brief


def test_retry_feedback_brief_rejects_failed_naked_import_cache_invalidation() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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
            "diff --git a/src/_pytest/pytester.py b/src/_pytest/pytester.py",
            "@@ -984,6 +984,9 @@",
            "+            import importlib",
            "+",
            "+            importlib.invalidate_caches()",
        ]
    )

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Invalidated importlib caches after copying example files.",
        test_result=result,
        final_diff=diff,
        attempt=5,
        runtime_trace=[
            {
                "node": "patch_quality",
                "quality": {
                    "severity": "medium",
                    "findings": [
                        {
                            "code": "naked_import_cache_invalidation",
                            "severity": "medium",
                            "message": (
                                "patch only invalidates importlib caches without fixing "
                                "the controlling read path"
                            ),
                        }
                    ],
                },
            }
        ],
    )

    assert "Rejected repair hypothesis" in brief
    assert "only invalidated importlib caches" in brief
    assert "Do not keep adding cache side effects" in brief
    assert "directly returns the old path" in brief


def test_retry_feedback_brief_includes_stale_path_control_point_guidance() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
            "/tmp/pytest-1/test_name0/test1/test_a.py:5: AssertionError\n"
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

    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Moved to a different cache branch but tests still fail.",
        test_result=result,
        final_diff="diff --git a/src/pkg.py b/src/pkg.py\n",
        attempt=2,
        runtime_trace=[],
    )

    assert "Stale path mismatch control-point guidance" in brief
    assert "`_read_pyc`, bytecode cache validation, `compile`, `exec`" in brief
    assert "only calling `importlib.invalidate_caches()`" in brief


def test_retry_feedback_brief_includes_attempt_history_with_same_signature() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_bug.py",
        exit_code=1,
        stdout=(
            "E   AssertionError: assert "
            "'/tmp/pytest-1/test_name0/test1/test_a.py' == "
            "'/tmp/pytest-1/test_name0/test2/test_a.py'\n"
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
    first_diff = "\n".join(
        [
            "diff --git a/src/pathlib.py b/src/pathlib.py",
            "@@ -1 +1 @@",
            "-return sys.modules[module_name]",
            "+return fresh_module",
        ]
    )
    second_diff = "\n".join(
        [
            "diff --git a/src/rewrite.py b/src/rewrite.py",
            "@@ -1 +1 @@",
            "-exec(co, module.__dict__)",
            "+exec(co, module.__dict__)",
        ]
    )
    first_record = feedback_attempt_record(
        attempt=1,
        agent_status="patch_generated",
        agent_summary="Edited import cache path.",
        test_result=result,
        final_diff=first_diff,
        runtime_trace=[{"patch_plan": {"path": "src/pathlib.py"}}],
    )
    second_record = feedback_attempt_record(
        attempt=2,
        agent_status="patch_generated",
        agent_summary="Edited rewrite path.",
        test_result=result,
        final_diff=second_diff,
        runtime_trace=[{"patch_plan": {"path": "src/rewrite.py"}}],
    )

    history = attempt_history_summary([first_record, second_record])
    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Edited rewrite path.",
        test_result=result,
        final_diff=second_diff,
        attempt=2,
        runtime_trace=[{"patch_plan": {"path": "src/rewrite.py"}}],
        attempt_history=[first_record, second_record],
    )

    assert "Prior attempts are negative evidence" in history
    assert "target=src/pathlib.py" in history
    assert "files=src/pathlib.py" in history
    assert "target=src/rewrite.py" in history
    assert "class=validation_failed" in history
    assert "same failure signature as previous attempt" in history
    assert "Deprioritized target paths" in history
    assert ineffective_target_paths([first_record, second_record]) == [
        "src/pathlib.py",
        "src/rewrite.py",
    ]
    assert attempted_target_paths([first_record, second_record]) == [
        "src/pathlib.py",
        "src/rewrite.py",
    ]
    assert "## Attempt History" in brief
    assert "Do not keep editing the same target family" in brief


def test_retry_feedback_allows_same_target_after_partial_assertion_progress() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue_7341_repro.py",
        exit_code=1,
        stdout="\n".join(
            [
                "tests/test_issue_7341_repro.py F",
                "E       AssertionError: ChunkedEncodingError docs should mention transient connection resets",
                "E       assert ('transient' in 'the server declared chunked encoding but the connection was reset or sent an invalid chunk.')",
                "tests/test_issue_7341_repro.py:9: AssertionError",
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
            "diff --git a/src/requests/exceptions.py b/src/requests/exceptions.py",
            "@@ -130,7 +130,7 @@",
            "-    \"\"\"The server declared chunked encoding but sent an invalid chunk.\"\"\"",
            "+    \"\"\"The server declared chunked encoding but the connection was reset or sent an invalid chunk.\"\"\"",
        ]
    )
    old_hash = "c62150ea2492"
    runtime_trace = [
        {
            "patch_plan": {
                "path": "src/requests/exceptions.py",
                "old": {"sha256_12": old_hash},
            }
        }
    ]

    assert "Partial assertion progress" in assertion_progress_summary(
        test_result=result,
        final_diff=diff,
    )

    record = feedback_attempt_record(
        attempt=1,
        agent_status="patch_generated",
        agent_summary="Edited ChunkedEncodingError docstring.",
        test_result=result,
        final_diff=diff,
        runtime_trace=runtime_trace,
    )
    history = attempt_history_summary([record])
    brief = retry_feedback_brief(
        agent_status="patch_generated",
        agent_summary="Edited ChunkedEncodingError docstring.",
        test_result=result,
        final_diff=diff,
        attempt=1,
        runtime_trace=runtime_trace,
        attempt_history=[record],
    )

    assert record["progress_classification"] == "partial_assertion_progress"
    assert "partial_assertion_progress" in history
    assert "the same target can still be the right control point" in history
    assert "refine the same target span" in brief
    assert "target history" in brief
    assert attempted_target_paths([record]) == ["src/requests/exceptions.py"]
    assert attempted_target_old_span_hashes([record]) == {}


def test_ineffective_target_paths_ignores_changed_failure_signature() -> None:
    records = [
        {
            "attempt": 1,
            "agent_status": "patch_generated",
            "patch_target": "src/pathlib.py",
            "changed_files": ["src/pathlib.py"],
            "failure_signature": "AssertionError | path:a!=b",
        },
        {
            "attempt": 2,
            "agent_status": "patch_generated",
            "patch_target": "src/rewrite.py",
            "changed_files": ["src/rewrite.py"],
            "failure_signature": "TypeError | at:src/new_site.py:10",
        },
    ]

    assert ineffective_target_paths(records) == []


def test_ineffective_target_paths_handles_non_adjacent_signature_recurrence() -> None:
    records = [
        {
            "attempt": 1,
            "agent_status": "no_patch_generated",
            "patch_target": "src/pathlib.py",
            "changed_files": [],
            "failure_signature": "AssertionError | path:a!=b",
        },
        {
            "attempt": 2,
            "agent_status": "patch_generated",
            "patch_target": "src/rewrite.py",
            "changed_files": ["src/rewrite.py"],
            "failure_signature": "AttributeError",
        },
        {
            "attempt": 3,
            "agent_status": "patch_generated",
            "patch_target": "src/pathlib.py",
            "changed_files": ["src/pathlib.py"],
            "failure_signature": "AssertionError | path:a!=b",
        },
    ]

    assert ineffective_target_paths(records) == ["src/pathlib.py"]


def test_feedback_attempt_record_captures_target_history_violation_path() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout="E   AssertionError: assert 'test1/test_a.py' == 'test2/test_a.py'\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    record = feedback_attempt_record(
        attempt=3,
        agent_status="no_patch_generated",
        agent_summary="DeepAgents adapter produced no bounded repair plan.",
        test_result=result,
        final_diff="",
        runtime_trace=[
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "target_history_violation": {
                        "path": "src/_pytest/assertion/rewrite.py",
                        "reason": "selected target path was deprioritized",
                    }
                },
            }
        ],
    )

    assert record["patch_target"] == "src/_pytest/assertion/rewrite.py"
    assert record["patch_old_sha256_12"] == ""
    assert attempted_target_paths([record]) == ["src/_pytest/assertion/rewrite.py"]


def test_feedback_attempt_record_captures_mounted_context_paths() -> None:
    record = feedback_attempt_record(
        attempt=1,
        agent_status="patch_generated",
        agent_summary="generated patch",
        test_result=None,
        final_diff="",
        runtime_trace=[
            {
                "metadata": {
                    "deepagents_contract": {
                        "context_budget": {
                            "mounted_paths": [
                                "/src/a.py",
                                "src/b.py",
                                "src/a.py",
                                123,
                            ]
                        }
                    }
                }
            }
        ],
    )

    assert record["mounted_context_paths"] == ["src/a.py", "src/b.py"]
    assert mounted_context_paths([record]) == ["src/a.py", "src/b.py"]


def test_feedback_attempt_record_captures_target_selection_violation_path() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout="E   AssertionError: behavior still wrong\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    record = feedback_attempt_record(
        attempt=3,
        agent_status="no_patch_generated",
        agent_summary="DeepAgents adapter produced no bounded repair plan.",
        test_result=result,
        final_diff="",
        runtime_trace=[
            {
                "node": "plan",
                "status": "no_match",
                "metadata": {
                    "target_selection_violation": {
                        "path": "tests/test_repro.py",
                        "reason": "selected target path is outside patch policy",
                    }
                },
            }
        ],
    )

    assert record["patch_target"] == "tests/test_repro.py"
    assert attempted_target_paths([record]) == ["tests/test_repro.py"]


def test_feedback_attempt_record_captures_patch_old_span_hashes() -> None:
    result = CommandResult(
        command="python3 -m pytest tests/test_issue.py",
        exit_code=1,
        stdout="E   AssertionError: behavior still wrong\n",
        stderr="",
        duration_ms=12,
        timed_out=False,
        policy_decision=CommandPolicyDecision(
            allowed=True,
            reason="allowed",
            tokens=("python3", "-m", "pytest"),
        ),
    )

    record = feedback_attempt_record(
        attempt=1,
        agent_status="patch_generated",
        agent_summary="Edited rewrite pyc branch.",
        test_result=result,
        final_diff="",
        runtime_trace=[
            {
                "node": "plan",
                "status": "completed",
                "patch_plan": {
                    "path": "src/_pytest/assertion/rewrite.py",
                    "old": {"sha256_12": "edc740415ac5"},
                },
            }
        ],
    )

    assert record["patch_old_sha256_12"] == "edc740415ac5"
    assert attempted_target_old_span_hashes([record]) == {
        "src/_pytest/assertion/rewrite.py": ["edc740415ac5"]
    }
