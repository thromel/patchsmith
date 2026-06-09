from pathlib import Path

from patchsmith.security import CommandPolicy


def test_command_policy_allows_pytest(workspace: Path | None = None) -> None:
    workspace = workspace or Path.cwd()
    decision = CommandPolicy().evaluate("python3 -m pytest tests", workspace=workspace)

    assert decision.allowed
    assert decision.tokens == ("python3", "-m", "pytest", "tests")


def test_command_policy_rejects_shell_chaining() -> None:
    decision = CommandPolicy().evaluate("python3 -m pytest && printenv", workspace=Path.cwd())

    assert not decision.allowed
    assert "blocked command fragment" in decision.reason


def test_command_policy_rejects_absolute_host_path() -> None:
    decision = CommandPolicy().evaluate("python3 -m pytest /etc", workspace=Path.cwd())

    assert not decision.allowed
    assert "absolute path outside workspace" in decision.reason

