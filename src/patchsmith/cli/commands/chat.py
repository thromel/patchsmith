"""Interactive chat CLI command and saved-session actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchsmith.agent_chat import run_chat_session
from patchsmith.agent_cli import AgentCliConfig, validate_agent_cli_config
from patchsmith.agent_commands import (
    custom_commands_payload,
    format_custom_commands,
    list_custom_commands,
)
from patchsmith.agent_hooks import (
    agent_hooks_payload,
    format_agent_hooks,
    list_agent_hooks,
)
from patchsmith.agent_instructions import (
    agent_instructions_payload,
    format_agent_instructions,
    load_agent_instruction_bundle,
)
from patchsmith.agent_profiles import (
    agent_profiles_payload,
    format_agent_profiles,
    list_agent_profiles,
)
from patchsmith.agent_session import (
    AgentSessionGateConfig,
    evaluate_session_gate,
    export_session_report,
    format_session_gate,
    format_session_metrics,
    format_session_recommendation,
    format_session_summaries,
    list_session_summaries,
    session_metrics,
    session_recommendation,
)
from patchsmith.cli._types import CommandHandler
from patchsmith.cli.agent_args import (
    add_agent_options,
    add_agent_prompt_arg,
    add_agent_session_options,
    agent_config_from_args,
    load_agent_initial_prompt,
)
from patchsmith.model_preflight import ModelPreflightResult, openai_model_preflight_from_env
from patchsmith.workflow import RepairRunner


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    chat = subparsers.add_parser(
        "chat",
        help="Start an interactive PatchSmith coding-agent session.",
    )
    add_agent_prompt_arg(chat)
    add_agent_options(chat)
    add_agent_session_options(chat)
    chat.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable output for offline session actions.",
    )
    return {"chat": _chat_command}


def _chat_command(args: argparse.Namespace) -> int:
    if args.issue_file and args.prompt:
        print("pass either a prompt or --issue-file, not both.", file=sys.stderr)
        return 2
    session_action_error = validate_offline_session_actions(args)
    if session_action_error:
        print(session_action_error, file=sys.stderr)
        return 2
    action_exit_code = dispatch_offline_session_action(args)
    if action_exit_code is not None:
        return action_exit_code
    config, profile_error = agent_config_from_args(args)
    if profile_error:
        print(profile_error, file=sys.stderr)
        return 2
    _, _, error = validate_agent_cli_config(config, require_apply_ready=False)
    if error:
        print(error, file=sys.stderr)
        return 2
    return run_chat_from_args(
        args=args,
        config=config,
        initial_prompt=load_agent_initial_prompt(args),
    )


def dispatch_offline_session_action(args: argparse.Namespace) -> int | None:
    if args.list_sessions:
        print(format_session_summaries(list_session_summaries(Path(args.artifacts_dir))))
        return 0
    if args.list_commands:
        _print_custom_commands(args)
        return 0
    if args.list_hooks:
        _print_agent_hooks(args)
        return 0
    if args.list_agents:
        _print_agent_profiles(args)
        return 0
    if args.list_instructions:
        _print_agent_instructions(args)
        return 0
    if args.session_metrics:
        return _print_saved_session_metrics(args)
    if args.session_gate:
        return _gate_saved_session(args)
    if args.session_next:
        return _print_saved_session_next(args)
    if args.export_session:
        return _export_saved_session(args)
    return None


def run_chat_from_args(
    *,
    args: argparse.Namespace,
    config: AgentCliConfig,
    initial_prompt: str,
) -> int:
    script_handle = None
    input_stream = sys.stdin
    if args.script:
        script_path = Path(args.script).expanduser()
        if not script_path.is_file():
            print(f"chat script not found: {script_path}", file=sys.stderr)
            return 2
        script_handle = script_path.open("r", encoding="utf-8")
        input_stream = script_handle
    try:
        return run_chat_session(
            config=config,
            initial_prompt=initial_prompt,
            input_stream=input_stream,
            output_stream=sys.stdout,
            runner_cls=RepairRunner,
            model_preflight_checker=(
                None
                if args.skip_model_preflight
                else _openai_model_preflight_for_config
            ),
            session_id=args.resume,
            resume=bool(args.resume),
        )
    finally:
        if script_handle is not None:
            script_handle.close()


def validate_offline_session_actions(args: argparse.Namespace) -> str | None:
    actions = [
        bool(args.list_sessions),
        bool(args.list_commands),
        bool(args.list_hooks),
        bool(args.list_agents),
        bool(args.list_instructions),
        bool(args.session_metrics),
        bool(args.session_gate),
        bool(args.session_next),
        bool(args.export_session),
    ]
    if sum(actions) > 1:
        return (
            "pass only one of --list-sessions, --list-commands, "
            "--list-hooks, --list-agents, --list-instructions, "
            "--session-metrics, --session-gate, --session-next, "
            "or --export-session."
        )
    if args.export_path and not args.export_session:
        return "--export-path requires --export-session."
    if not args.session_gate and has_session_gate_threshold(args):
        return "session gate thresholds require --session-gate."
    gate_error = _validate_session_gate_args(args)
    if gate_error:
        return gate_error
    return None


def has_session_gate_threshold(args: argparse.Namespace) -> bool:
    return any(
        [
            args.require_validated_run,
            args.require_diff_review,
            args.require_ready_apply_check,
            args.min_validation_rate is not None,
            args.min_preflight_to_run_rate is not None,
            args.min_apply_success_rate is not None,
            args.max_high_risk_diff_reviews is not None,
            args.max_cost_per_validated_run_usd is not None,
            args.max_run_errors is not None,
        ]
    )


def _openai_model_preflight_for_config(config: AgentCliConfig) -> ModelPreflightResult:
    return openai_model_preflight_from_env(model=config.deepagents_model)


def _print_custom_commands(args: argparse.Namespace) -> None:
    commands = list_custom_commands(args.repo)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "command_root": ".patchsmith/commands",
                    "commands": custom_commands_payload(commands),
                },
                indent=2,
            )
        )
        return
    print(format_custom_commands(commands))


def _print_agent_hooks(args: argparse.Namespace) -> None:
    hooks = list_agent_hooks(args.repo)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "hook_config": ".patchsmith/hooks.json",
                    "hooks": agent_hooks_payload(hooks),
                },
                indent=2,
            )
        )
        return
    print(format_agent_hooks(hooks))


def _print_agent_profiles(args: argparse.Namespace) -> None:
    profiles = list_agent_profiles(args.repo)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "profile_root": ".patchsmith/agents",
                    "profiles": agent_profiles_payload(profiles),
                },
                indent=2,
            )
        )
        return
    print(format_agent_profiles(profiles))


def _print_agent_instructions(args: argparse.Namespace) -> None:
    bundle = load_agent_instruction_bundle(
        args.repo,
        explicit_paths=tuple(args.instruction_path or ()),
        include_defaults=not args.no_agent_instructions,
    )
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "instruction_files": agent_instructions_payload(bundle),
                },
                indent=2,
            )
        )
        return
    print(format_agent_instructions(bundle))


def _print_saved_session_metrics(args: argparse.Namespace) -> int:
    transcript_path = _session_transcript_path(
        artifacts_dir=Path(args.artifacts_dir),
        session_id=args.session_metrics,
    )
    if not transcript_path.is_file():
        print(f"chat session not found: {args.session_metrics}", file=sys.stderr)
        print(f"Expected transcript: {transcript_path}", file=sys.stderr)
        return 2
    metrics = session_metrics(transcript_path)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "session_id": args.session_metrics,
                    "transcript_path": str(transcript_path),
                    "metrics": metrics.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(format_session_metrics(metrics))
    return 0


def _print_saved_session_next(args: argparse.Namespace) -> int:
    transcript_path = _session_transcript_path(
        artifacts_dir=Path(args.artifacts_dir),
        session_id=args.session_next,
    )
    if not transcript_path.is_file():
        print(f"chat session not found: {args.session_next}", file=sys.stderr)
        print(f"Expected transcript: {transcript_path}", file=sys.stderr)
        return 2
    recommendation = session_recommendation(transcript_path)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "session_id": args.session_next,
                    "transcript_path": str(transcript_path),
                    "recommendation": recommendation.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(format_session_recommendation(recommendation))
    return 0


def _export_saved_session(args: argparse.Namespace) -> int:
    transcript_path = _session_transcript_path(
        artifacts_dir=Path(args.artifacts_dir),
        session_id=args.export_session,
    )
    if not transcript_path.is_file():
        print(f"chat session not found: {args.export_session}", file=sys.stderr)
        print(f"Expected transcript: {transcript_path}", file=sys.stderr)
        return 2
    report_path = Path(args.export_path).expanduser() if args.export_path else None
    export = export_session_report(
        transcript_path=transcript_path,
        report_path=report_path,
    )
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "session_id": args.export_session,
                    "transcript_path": str(export.transcript_path),
                    "report_path": str(export.report_path),
                },
                indent=2,
            )
        )
    else:
        print(f"Exported session report: {export.report_path}")
    return 0


def _gate_saved_session(args: argparse.Namespace) -> int:
    transcript_path = _session_transcript_path(
        artifacts_dir=Path(args.artifacts_dir),
        session_id=args.session_gate,
    )
    if not transcript_path.is_file():
        print(f"chat session not found: {args.session_gate}", file=sys.stderr)
        print(f"Expected transcript: {transcript_path}", file=sys.stderr)
        return 2
    metrics = session_metrics(transcript_path)
    result = evaluate_session_gate(metrics, _session_gate_config_from_args(args))
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "session_id": args.session_gate,
                    "transcript_path": str(transcript_path),
                    "gate": result.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(format_session_gate(result))
    return 0 if result.status == "passed" else 1


def _session_gate_config_from_args(args: argparse.Namespace) -> AgentSessionGateConfig:
    return AgentSessionGateConfig(
        require_validated_run=args.require_validated_run,
        require_diff_review=args.require_diff_review,
        require_ready_apply_check=args.require_ready_apply_check,
        min_validation_rate=args.min_validation_rate,
        min_preflight_to_run_rate=args.min_preflight_to_run_rate,
        min_apply_success_rate=args.min_apply_success_rate,
        max_high_risk_diff_reviews=args.max_high_risk_diff_reviews,
        max_cost_per_validated_run_usd=args.max_cost_per_validated_run_usd,
        max_run_errors=args.max_run_errors,
    )


def _validate_session_gate_args(args: argparse.Namespace) -> str | None:
    for name in (
        "min_validation_rate",
        "min_preflight_to_run_rate",
        "min_apply_success_rate",
    ):
        value = getattr(args, name)
        if value is not None and not 0.0 <= value <= 1.0:
            return f"--{name.replace('_', '-')} must be between 0.0 and 1.0."
    if (
        args.max_cost_per_validated_run_usd is not None
        and args.max_cost_per_validated_run_usd < 0
    ):
        return "--max-cost-per-validated-run-usd must be non-negative."
    if args.max_run_errors is not None and args.max_run_errors < 0:
        return "--max-run-errors must be non-negative."
    if (
        args.max_high_risk_diff_reviews is not None
        and args.max_high_risk_diff_reviews < 0
    ):
        return "--max-high-risk-diff-reviews must be non-negative."
    return None


def _session_transcript_path(*, artifacts_dir: Path, session_id: str) -> Path:
    return artifacts_dir / "chat_sessions" / f"{session_id}.jsonl"
