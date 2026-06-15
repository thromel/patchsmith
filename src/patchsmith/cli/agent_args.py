"""Shared agent and chat CLI argument helpers."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace as dataclass_replace
from pathlib import Path

from patchsmith.agent_cli import (
    AgentCliConfig,
    config_with_loaded_agent_instructions,
)
from patchsmith.agent_profiles import AgentProfile, load_agent_profile
from patchsmith.cli._args import _add_sandbox_args


def add_agent_prompt_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Task or issue text. If omitted, pass --issue-file or enter it in chat.",
    )


def add_agent_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo",
        default=".",
        help="Local path or public Git repository URL. Defaults to the current directory.",
    )
    parser.add_argument("--commit", help="Optional commit hash to check out.")
    parser.add_argument("--branch", help="Optional branch to check out.")
    parser.add_argument("--issue-file", help="Path to a file containing task text.")
    parser.add_argument("--issue-url", help="Optional source issue URL for the run report.")
    parser.add_argument("--test-command", help="Allowed test command to run in the sandbox.")
    parser.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native_hybrid",
        help="Context broker to use before agent execution.",
    )
    parser.add_argument(
        "--context-path",
        action="append",
        default=[],
        help=(
            "Repo-relative file to force into the repair context. Repeat for multiple "
            "files; an optional #symbol suffix is accepted for traceability."
        ),
    )
    parser.add_argument(
        "--agent-profile",
        help="Project agent profile from .patchsmith/agents to apply before running.",
    )
    parser.add_argument(
        "--instruction-path",
        action="append",
        default=[],
        help=(
            "Extra repo-relative project instruction file to load. Repeat for "
            "multiple files."
        ),
    )
    parser.add_argument(
        "--no-agent-instructions",
        action="store_true",
        help="Disable automatic AGENTS.md/CLAUDE.md-style project instruction loading.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Artifact output directory.")
    _add_sandbox_args(parser)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the generated diff back to the local target repo after the run.",
    )
    parser.add_argument(
        "--allow-dirty-apply",
        action="store_true",
        help="Allow --apply when the target repo has uncommitted changes.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Maximum extra DeepAgents feedback retries after the first attempt.",
    )
    parser.add_argument(
        "--deepagents-max-context-files",
        type=int,
        default=0,
        help=(
            "Cap mounted repository files for native DeepAgents. Use 0 to keep the "
            "default full retrieved context."
        ),
    )
    parser.add_argument(
        "--deepagents-subagents",
        choices=["full", "auto", "inline"],
        default="auto",
        help="Native DeepAgents subagent routing mode.",
    )
    parser.add_argument(
        "--deepagents-model",
        help="DeepAgents/OpenAI-compatible model override for this agent session.",
    )
    parser.add_argument(
        "--skip-model-preflight",
        action="store_true",
        help=(
            "Skip the live OpenAI model availability check before an actual agent run."
        ),
    )
    parser.add_argument(
        "--max-model-responses",
        type=int,
        default=12,
        help="Maximum DeepAgents model responses allowed for this run. Use -1 to disable.",
    )
    parser.add_argument(
        "--max-model-tokens",
        type=int,
        default=200000,
        help="Maximum DeepAgents model tokens allowed for this run. Use -1 to disable.",
    )


def add_agent_session_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="Resume an existing PatchSmith chat transcript by session id.",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List saved PatchSmith chat sessions under --artifacts-dir and exit.",
    )
    parser.add_argument(
        "--list-commands",
        action="store_true",
        help="List project custom slash commands under .patchsmith/commands and exit.",
    )
    parser.add_argument(
        "--list-hooks",
        action="store_true",
        help="List project lifecycle hooks under .patchsmith/hooks.json and exit.",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List project agent profiles under .patchsmith/agents and exit.",
    )
    parser.add_argument(
        "--list-instructions",
        action="store_true",
        help="List project instruction files that PatchSmith would load and exit.",
    )
    parser.add_argument(
        "--script",
        help="Read chat input from a command script file instead of stdin.",
    )
    parser.add_argument(
        "--session-metrics",
        metavar="SESSION_ID",
        help="Print saved transcript metrics for a PatchSmith chat session and exit.",
    )
    parser.add_argument(
        "--session-gate",
        metavar="SESSION_ID",
        help="Evaluate saved transcript metrics against process/cost thresholds and exit.",
    )
    parser.add_argument(
        "--session-next",
        metavar="SESSION_ID",
        help="Print the deterministic next recommendation for a saved chat session.",
    )
    parser.add_argument(
        "--export-session",
        metavar="SESSION_ID",
        help="Export a saved PatchSmith chat transcript as Markdown and exit.",
    )
    parser.add_argument(
        "--export-path",
        help="Output path for --export-session. Defaults beside the transcript.",
    )
    parser.add_argument(
        "--require-validated-run",
        action="store_true",
        help="Fail --session-gate unless the saved session has at least one validated run.",
    )
    parser.add_argument(
        "--require-diff-review",
        action="store_true",
        help="Fail --session-gate unless the saved session has a diff risk review.",
    )
    parser.add_argument(
        "--require-ready-apply-check",
        action="store_true",
        help="Fail --session-gate unless the saved session has a ready apply check.",
    )
    parser.add_argument(
        "--min-validation-rate",
        type=float,
        help="Fail --session-gate below this validation rate, from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--min-preflight-to-run-rate",
        type=float,
        help="Fail --session-gate below this preflight-to-run rate, from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--min-apply-success-rate",
        type=float,
        help="Fail --session-gate below this apply success rate, from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--max-cost-per-validated-run-usd",
        type=float,
        help="Fail --session-gate above this cost per validated run.",
    )
    parser.add_argument(
        "--max-run-errors",
        type=int,
        help="Fail --session-gate above this run-error count.",
    )
    parser.add_argument(
        "--max-high-risk-diff-reviews",
        type=int,
        help="Fail --session-gate above this high-risk diff review count.",
    )


def load_agent_issue_text(args: argparse.Namespace) -> str:
    if args.issue_file:
        return Path(args.issue_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def load_agent_initial_prompt(args: argparse.Namespace) -> str:
    if args.issue_file:
        return Path(args.issue_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt.strip()
    return ""


def agent_config_from_args(args: argparse.Namespace) -> tuple[AgentCliConfig, str | None]:
    config = AgentCliConfig(
        repo=args.repo,
        commit=args.commit,
        branch=args.branch,
        issue_url=args.issue_url,
        test_command=args.test_command,
        context_provider=args.context_provider,
        context_paths=tuple(args.context_path or ()),
        top_k=args.top_k,
        artifacts_dir=args.artifacts_dir,
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        apply=args.apply,
        allow_dirty_apply=args.allow_dirty_apply,
        max_retries=args.max_retries,
        deepagents_max_context_files=args.deepagents_max_context_files,
        deepagents_subagents=args.deepagents_subagents,
        deepagents_model=args.deepagents_model,
        max_model_responses=args.max_model_responses,
        max_model_tokens=args.max_model_tokens,
        load_agent_instructions=not args.no_agent_instructions,
        instruction_paths=tuple(args.instruction_path or ()),
    )
    profile_name = getattr(args, "agent_profile", None)
    if not profile_name:
        return config_with_loaded_agent_instructions(config), None
    profile = load_agent_profile(args.repo, profile_name)
    if profile is None:
        return config, f"agent profile not found: {profile_name}"
    return config_with_loaded_agent_instructions(
        config_with_agent_profile(config, profile)
    ), None


def config_with_agent_profile(
    config: AgentCliConfig,
    profile: AgentProfile,
) -> AgentCliConfig:
    return dataclass_replace(
        config,
        agent_profile=profile.name,
        agent_profile_path=str(profile.path),
        agent_profile_description=profile.description,
        agent_profile_instructions=profile.instructions,
        deepagents_model=profile.model or config.deepagents_model,
        deepagents_subagents=profile.subagents or config.deepagents_subagents,
        deepagents_max_context_files=(
            profile.max_context_files
            if profile.max_context_files is not None
            else config.deepagents_max_context_files
        ),
        max_model_responses=(
            profile.max_model_responses
            if profile.max_model_responses is not None
            else config.max_model_responses
        ),
        max_model_tokens=(
            profile.max_model_tokens
            if profile.max_model_tokens is not None
            else config.max_model_tokens
        ),
        top_k=profile.top_k if profile.top_k is not None else config.top_k,
        test_command=profile.test_command or config.test_command,
        context_paths=tuple(
            dict.fromkeys((*config.context_paths, *profile.context_paths))
        ),
    )
