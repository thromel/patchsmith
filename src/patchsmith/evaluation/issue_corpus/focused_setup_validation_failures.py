"""Failure classification for focused-test setup validation."""

from __future__ import annotations


def classify_focused_test_setup_validation_failure(
    *,
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
) -> tuple[str | None, str | None, list[str], list[str]]:
    if status in {"passed", "dry_run", "skipped"}:
        return None, None, [], []
    if status == "timed_out":
        return (
            "validation_timeout",
            "validation command timed out before producing a stable setup signal",
            [],
            ["raise or split the timeout only after confirming the command scope is focused"],
        )
    if status == "blocked":
        return (
            "validation_policy_or_setup_blocker",
            "validation command could not run because setup or command policy blocked it",
            [],
            ["resolve setup and command-policy blockers before interpreting validation output"],
        )

    combined = "\n".join(part for part in [stderr, stdout] if part)
    combined_lower = combined.lower()
    if "minversion" in combined_lower and "actual pytest-" in combined_lower:
        return (
            "pytest_in_tree_version_metadata",
            "pytest validation imported the repository development version below pyproject minversion",
            _diagnostic_lines(
                combined,
                ["minversion", "actual pytest-"],
            ),
            [
                "refresh the pytest setup recipe to run through the repository's supported tox/nox workflow or generated version metadata",
            ],
        )
    if "recursive dependency involving fixture 'httpbin'" in combined_lower:
        return (
            "missing_httpbin_fixture_provider",
            "requests validation requires an external httpbin fixture provider instead of the recursive local fixture alias",
            _diagnostic_lines(
                combined,
                ["recursive dependency involving fixture 'httpbin'", "tests/conftest.py"],
            ),
            [
                "narrow requests validation to issue-specific tests that do not require httpbin or add a controlled httpbin fixture provider",
            ],
        )
    if "no module named" in combined_lower:
        return (
            "missing_python_dependency",
            "validation failed because a required Python dependency was not importable",
            _diagnostic_lines(combined, ["no module named"]),
            ["extend the disposable setup recipe with the missing dependency only after review"],
        )
    if "file or directory not found" in combined_lower or "not found:" in combined_lower:
        return (
            "invalid_validation_target",
            "validation command references a test path or selector that pytest cannot find",
            _diagnostic_lines(combined, ["file or directory not found", "not found:"]),
            ["regenerate the focused validation command from current repository paths"],
        )
    if exit_code is not None:
        return (
            "unknown_validation_failure",
            f"validation command exited {exit_code} without a recognized setup diagnostic",
            _diagnostic_lines(combined, ["error", "failed", "traceback"]),
            ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
        )
    return (
        "unknown_validation_failure",
        "validation command failed without an exit code or recognized setup diagnostic",
        _diagnostic_lines(combined, ["error", "failed", "traceback"]),
        ["inspect captured stdout/stderr and add a specific setup recipe or diagnostic"],
    )


def _diagnostic_lines(text: str, patterns: list[str], *, limit: int = 3) -> list[str]:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    evidence: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            evidence.append(stripped[:240])
        if len(evidence) >= limit:
            break
    return evidence


__all__ = ["classify_focused_test_setup_validation_failure"]
