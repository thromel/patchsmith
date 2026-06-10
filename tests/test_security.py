import subprocess
from pathlib import Path

from patchsmith.security import CommandPolicy, FocusedSetupCommandPolicy
from patchsmith.sandbox import DockerSandboxRunner


def test_command_policy_allows_pytest(workspace: Path | None = None) -> None:
    workspace = workspace or Path.cwd()
    decision = CommandPolicy().evaluate("python3 -m pytest tests", workspace=workspace)

    assert decision.allowed
    assert decision.tokens == ("python3", "-m", "pytest", "tests")


def test_command_policy_rejects_shell_chaining() -> None:
    decision = CommandPolicy().evaluate("python3 -m pytest && printenv", workspace=Path.cwd())

    assert not decision.allowed
    assert "blocked command fragment" in decision.reason


def test_command_policy_rejects_dependency_install_by_default() -> None:
    decision = CommandPolicy().evaluate("python3 -m pip install -e .", workspace=Path.cwd())

    assert not decision.allowed
    assert "not allowlisted" in decision.reason


def test_focused_setup_policy_allows_only_editable_project_installs() -> None:
    workspace = Path.cwd()
    policy = FocusedSetupCommandPolicy()

    project_install = policy.evaluate("python3 -m pip install -e .", workspace=workspace)
    test_extra_install = policy.evaluate(
        'python3 -m pip install -e ".[test]"',
        workspace=workspace,
    )
    test_group_install = policy.evaluate(
        "python3 -m pip install -e . --group test",
        workspace=workspace,
    )
    external_install = policy.evaluate("python3 -m pip install requests", workspace=workspace)
    external_group_install = policy.evaluate(
        "python3 -m pip install -e . --group dev",
        workspace=workspace,
    )

    assert project_install.allowed
    assert project_install.reason == "allowed focused setup editable install"
    assert test_extra_install.allowed
    assert test_group_install.allowed
    assert not external_install.allowed
    assert not external_group_install.allowed


def test_command_policy_rejects_absolute_host_path() -> None:
    decision = CommandPolicy().evaluate("python3 -m pytest /etc", workspace=Path.cwd())

    assert not decision.allowed
    assert "absolute path outside workspace" in decision.reason


def test_docker_sandbox_rejects_blocked_command_without_subprocess(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        raise AssertionError("docker should not run rejected commands")

    monkeypatch.setattr("patchsmith.sandbox.subprocess.run", fail_run)

    result = DockerSandboxRunner().run(
        command="python3 -m pytest && printenv",
        workspace=tmp_path,
    )

    assert result.exit_code is None
    assert "blocked command fragment" in result.stderr


def test_docker_sandbox_builds_isolated_command_and_sanitized_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/docker.sock")

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr("patchsmith.sandbox.subprocess.run", fake_run)

    result = DockerSandboxRunner(image="patchsmith-test:latest").run(
        command="python3 -m pytest",
        workspace=tmp_path,
    )

    assert result.exit_code == 0
    assert result.stdout == "ok\n"
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:2] == ["docker", "run"]
    assert "--rm" in command
    assert command[command.index("--pull") + 1] == "never"
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--security-opt") + 1] == "no-new-privileges"
    assert command[command.index("--workdir") + 1] == "/workspace"
    assert command[command.index("--volume") + 1] == f"{tmp_path.resolve()}:/workspace"
    assert "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYTEST=9.0.0" in command
    assert command[-4:] == ["patchsmith-test:latest", "python3", "-m", "pytest"]
    env = kwargs["env"]
    assert isinstance(env, dict)
    assert "PATH" in env
    assert env["DOCKER_HOST"] == "unix:///tmp/docker.sock"
    assert "OPENAI_API_KEY" not in env


def test_docker_sandbox_removes_container_on_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, timeout=1, output="partial")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("patchsmith.sandbox.subprocess.run", fake_run)

    result = DockerSandboxRunner().run(
        command="python3 -m pytest",
        workspace=tmp_path,
        timeout_seconds=1,
    )

    assert result.timed_out
    assert calls[0][:2] == ["docker", "run"]
    assert calls[1][:3] == ["docker", "rm", "-f"]
    assert calls[1][3].startswith("patchsmith-")
