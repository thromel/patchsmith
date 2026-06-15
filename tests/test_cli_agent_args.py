from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from patchsmith.cli.agent_args import (
    add_agent_options,
    add_agent_prompt_arg,
    agent_config_from_args,
    load_agent_initial_prompt,
    load_agent_issue_text,
)

pytestmark = pytest.mark.unit


def test_agent_config_from_args_preserves_shared_cli_defaults(tmp_path: Path) -> None:
    parser = _agent_parser()
    args = parser.parse_args(
        [
            "Fix parser",
            "--repo",
            str(tmp_path),
            "--context-path",
            "src/parser.py#parse",
            "--deepagents-max-context-files",
            "4",
            "--max-model-responses",
            "5",
            "--max-model-tokens",
            "90000",
            "--no-agent-instructions",
        ]
    )

    config, error = agent_config_from_args(args)

    assert error is None
    assert config.repo == str(tmp_path)
    assert config.context_provider == "native_hybrid"
    assert config.context_paths == ("src/parser.py#parse",)
    assert config.deepagents_subagents == "auto"
    assert config.deepagents_max_context_files == 4
    assert config.max_model_responses == 5
    assert config.max_model_tokens == 90000
    assert config.load_agent_instructions is False
    assert load_agent_initial_prompt(args) == "Fix parser"
    assert load_agent_issue_text(args) == "Fix parser"


def test_agent_config_from_args_merges_project_profile(tmp_path: Path) -> None:
    profile_dir = tmp_path / ".patchsmith" / "agents"
    profile_dir.mkdir(parents=True)
    profile_instructions = "Check failure evidence before editing."
    (profile_dir / "verifier.md").write_text(
        "---\n"
        "description: Verification-focused mode\n"
        "model: gpt-5-mini\n"
        "subagents: inline\n"
        "max_context_files: 2\n"
        "max_model_responses: 4\n"
        "max_model_tokens: 80000\n"
        "test_command: pytest tests/test_target.py -q\n"
        "context_paths: src/profile_target.py#fix\n"
        "---\n"
        f"{profile_instructions}\n",
        encoding="utf-8",
    )
    parser = _agent_parser()
    args = parser.parse_args(
        [
            "Fix target",
            "--repo",
            str(tmp_path),
            "--context-path",
            "src/requested.py#entry",
            "--agent-profile",
            "verifier",
            "--no-agent-instructions",
        ]
    )

    config, error = agent_config_from_args(args)

    assert error is None
    assert config.agent_profile == "verifier"
    assert config.agent_profile_path == str(profile_dir / "verifier.md")
    assert config.agent_profile_description == "Verification-focused mode"
    assert config.agent_profile_instructions == profile_instructions
    assert config.deepagents_model == "gpt-5-mini"
    assert config.deepagents_subagents == "inline"
    assert config.deepagents_max_context_files == 2
    assert config.max_model_responses == 4
    assert config.max_model_tokens == 80000
    assert config.test_command == "pytest tests/test_target.py -q"
    assert config.context_paths == ("src/requested.py#entry", "src/profile_target.py#fix")


def test_agent_config_from_args_reports_missing_profile(tmp_path: Path) -> None:
    parser = _agent_parser()
    args = parser.parse_args(
        [
            "Fix target",
            "--repo",
            str(tmp_path),
            "--agent-profile",
            "missing",
        ]
    )

    config, error = agent_config_from_args(args)

    assert config.repo == str(tmp_path)
    assert error == "agent profile not found: missing"


def test_agent_issue_text_can_load_issue_file(tmp_path: Path) -> None:
    issue_file = tmp_path / "issue.md"
    issue_file.write_text("fix from file\n", encoding="utf-8")
    parser = _agent_parser()
    args = parser.parse_args(["--issue-file", str(issue_file), "--no-agent-instructions"])

    assert load_agent_initial_prompt(args) == "fix from file"
    assert load_agent_issue_text(args) == "fix from file"


def _agent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_agent_prompt_arg(parser)
    add_agent_options(parser)
    return parser
