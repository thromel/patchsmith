from patchsmith.evaluation.issue_corpus.log_signals import (
    candidate_failure_signals_from_logs,
    last_nonempty_lines,
    matched_expected_failure_signals,
    matching_lines,
)


def test_log_signal_helpers_match_and_trim_failure_lines() -> None:
    logs = "\n".join(
        [
            "",
            "setup started",
            "E   AssertionError: expected moved filename",
            "E   AssertionError: expected moved filename",
            "ERROR: collection failed",
            "last line",
        ]
    )

    assert matching_lines(logs, ["assertionerror", "missing"], limit=1) == [
        "E   AssertionError: expected moved filename"
    ]
    assert matched_expected_failure_signals(
        logs,
        ["AssertionError: expected moved filename", "ModuleNotFoundError"],
    ) == ["AssertionError: expected moved filename"]
    assert candidate_failure_signals_from_logs(logs) == [
        "E   AssertionError: expected moved filename",
        "ERROR: collection failed",
    ]
    assert last_nonempty_lines(logs, limit=2) == ["ERROR: collection failed", "last line"]
