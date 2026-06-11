from __future__ import annotations

from pathlib import Path

import pytest

from patchsmith.sandbox import (
    DockerSandboxRunner,
    LocalSandboxRunner,
    _timeout_output,
    create_sandbox_runner,
)


def test_create_sandbox_runner_dispatches_modes() -> None:
    assert isinstance(create_sandbox_runner(mode="local"), LocalSandboxRunner)
    docker_runner = create_sandbox_runner(mode="docker", image="python:3.12-slim")
    assert isinstance(docker_runner, DockerSandboxRunner)
    with pytest.raises(ValueError, match="unsupported sandbox mode"):
        create_sandbox_runner(mode="cloud")


@pytest.mark.unit
def test_local_runner_blocks_non_allowlisted_command(tmp_path: Path) -> None:
    runner = LocalSandboxRunner()
    result = runner.run(command="rm -rf /", workspace=tmp_path)
    assert result.exit_code is None
    assert not result.policy_decision.allowed
    assert result.stdout == ""


@pytest.mark.integration
def test_local_runner_executes_allowlisted_command(tmp_path: Path) -> None:
    runner = LocalSandboxRunner()
    result = runner.run(command="pytest --version", workspace=tmp_path, timeout_seconds=60)
    assert result.policy_decision.allowed
    assert result.exit_code == 0
    assert "pytest" in result.stdout
    assert not result.timed_out


@pytest.mark.unit
def test_timeout_output_normalizes_bytes_and_none() -> None:
    assert _timeout_output(None) == ""
    assert _timeout_output(b"partial") == "partial"
    assert _timeout_output("text") == "text"
