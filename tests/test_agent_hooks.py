from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchsmith.agent_hooks import list_agent_hooks, run_agent_hooks

pytestmark = pytest.mark.unit


def _write_hooks(repo: Path, hooks: dict[str, object]) -> None:
    config_dir = repo / ".patchsmith"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_hook_command_runs_as_argv_without_shell(tmp_path: Path) -> None:
    sentinel = tmp_path / "pwned.txt"
    # If the command were run through a shell, the `;` and `>` would create the
    # sentinel file. With shell=False the metacharacters are passed as literal
    # arguments to `python -c`, so the file must never be created.
    command = f"python -c pass ; touch {sentinel}"
    _write_hooks(tmp_path, {"PreRun": [{"command": command, "name": "guard"}]})

    result = run_agent_hooks(repo=str(tmp_path), event="PreRun", payload={})

    assert not sentinel.exists()
    assert result.event == "PreRun"


def test_hook_with_unparseable_command_is_blocked(tmp_path: Path) -> None:
    _write_hooks(tmp_path, {"PreRun": [{"command": 'echo "unterminated', "name": "bad"}]})

    result = run_agent_hooks(repo=str(tmp_path), event="PreRun", payload={})

    assert result.blocked
    assert result.block_reason is not None
    assert "could not parse" in result.block_reason


def test_hook_with_missing_executable_is_blocked(tmp_path: Path) -> None:
    _write_hooks(
        tmp_path,
        {"PreRun": [{"command": "patchsmith-nonexistent-binary", "name": "missing"}]},
    )

    result = run_agent_hooks(repo=str(tmp_path), event="PreRun", payload={})

    assert result.blocked
    assert result.block_reason is not None
    assert "not found" in result.block_reason


def test_list_agent_hooks_parses_entries(tmp_path: Path) -> None:
    _write_hooks(tmp_path, {"PreRun": ["python -c pass"]})

    hooks = list_agent_hooks(str(tmp_path))

    assert len(hooks) == 1
    assert hooks[0].event == "PreRun"
    assert hooks[0].command == "python -c pass"
