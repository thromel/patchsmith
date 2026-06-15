"""CLI run commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from patchsmith.agent_apply import (
    AgentApplyResult,
)
from patchsmith.agent_chat import run_chat_session
from patchsmith.agent_cli import (
    AgentCliConfig,
    agent_preflight_payload,
    run_agent_once,
    run_result_payload,
    validate_agent_cli_config,
)
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
from patchsmith.cli._args import (
    _add_issue_args,
    _add_repo_args,
    _add_sandbox_args,
    _load_issue_text,
)
from patchsmith.cli._types import CommandHandler
from patchsmith.cli.agent_args import (
    add_agent_options,
    add_agent_prompt_arg,
    add_agent_session_options,
    agent_config_from_args,
    load_agent_initial_prompt,
    load_agent_issue_text,
)
from patchsmith.model_preflight import ModelPreflightResult, openai_model_preflight_from_env
from patchsmith.models import RepairRunResult, RunRequest
from patchsmith.workflow import RepairRunner


def register(subparsers: argparse._SubParsersAction) -> dict[str, CommandHandler]:
    agent = subparsers.add_parser(
        "agent",
        help="Run PatchSmith as a terminal-first coding agent for the current repo.",
    )
    add_agent_prompt_arg(agent)
    add_agent_options(agent)
    agent.add_argument(
        "--preflight",
        action="store_true",
        help="Validate the agent run configuration without calling a model.",
    )
    agent.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive PatchSmith chat session.",
    )
    add_agent_session_options(agent)
    agent.add_argument("--json", action="store_true", help="Print machine-readable run summary.")

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

    run = subparsers.add_parser("run", help="Run the MVP issue-to-report lifecycle.")
    _add_repo_args(run)
    _add_issue_args(run)
    run.add_argument("--test-command", help="Allowed test command to run in the sandbox.")
    run.add_argument(
        "--runtime",
        choices=["agentless", "heuristic", "deepagents"],
        default="agentless",
        help="Runtime label for the run report.",
    )
    run.add_argument(
        "--planner",
        choices=["heuristic", "fake_model", "openai", "deepagents"],
        default="heuristic",
        help="Repair planner used by model-capable runtimes.",
    )
    run.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum extra DeepAgents feedback retries after the first attempt.",
    )
    run.add_argument(
        "--context-provider",
        choices=["native", "native_hybrid", "native_graph", "ctxhelm_cli", "auto"],
        default="native",
        help="Context broker to use before agent execution.",
    )
    run.add_argument(
        "--context-path",
        action="append",
        default=[],
        help=(
            "Repo-relative file to force into the repair context. Repeat for multiple files; "
            "an optional #symbol suffix is accepted for traceability."
        ),
    )
    run.add_argument("--top-k", type=int, default=5, help="Number of files to retrieve.")
    run.add_argument("--artifacts-dir", default="artifacts", help="Artifact output directory.")
    _add_sandbox_args(run)
    run.add_argument("--json", action="store_true", help="Print machine-readable run summary.")

    return {
        "agent": _agent_command,
        "chat": _chat_command,
        "run": _run_command,
    }


def _agent_command(args: argparse.Namespace) -> int:
    if args.issue_file and args.prompt:
        print("pass either a prompt or --issue-file, not both.", file=sys.stderr)
        return 2
    if args.interactive and args.preflight:
        print("pass either --interactive or --preflight, not both.", file=sys.stderr)
        return 2
    if args.resume and not args.interactive:
        print("--resume requires --interactive.", file=sys.stderr)
        return 2
    if args.list_sessions and not args.interactive:
        print("--list-sessions requires --interactive.", file=sys.stderr)
        return 2
    if args.list_commands and not args.interactive:
        print("--list-commands requires --interactive.", file=sys.stderr)
        return 2
    if args.list_hooks and not args.interactive:
        print("--list-hooks requires --interactive.", file=sys.stderr)
        return 2
    if args.list_agents and not args.interactive:
        print("--list-agents requires --interactive.", file=sys.stderr)
        return 2
    if args.list_instructions and not args.interactive:
        print("--list-instructions requires --interactive.", file=sys.stderr)
        return 2
    if args.session_metrics and not args.interactive:
        print("--session-metrics requires --interactive.", file=sys.stderr)
        return 2
    if args.session_gate and not args.interactive:
        print("--session-gate requires --interactive.", file=sys.stderr)
        return 2
    if args.session_next and not args.interactive:
        print("--session-next requires --interactive.", file=sys.stderr)
        return 2
    if args.export_session and not args.interactive:
        print("--export-session requires --interactive.", file=sys.stderr)
        return 2
    if args.export_path and not args.export_session:
        print("--export-path requires --export-session.", file=sys.stderr)
        return 2
    if _has_session_gate_threshold(args) and not args.session_gate:
        print("session gate thresholds require --session-gate.", file=sys.stderr)
        return 2
    if args.script and not args.interactive:
        print("--script requires --interactive.", file=sys.stderr)
        return 2
    if args.interactive:
        session_action_error = _validate_offline_session_actions(args)
        if session_action_error:
            print(session_action_error, file=sys.stderr)
            return 2
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
        config, profile_error = agent_config_from_args(args)
        if profile_error:
            print(profile_error, file=sys.stderr)
            return 2
        _, _, error = validate_agent_cli_config(config, require_apply_ready=False)
        if error:
            print(error, file=sys.stderr)
            return 2
        initial_prompt = load_agent_initial_prompt(args)
        return _run_chat_from_args(args=args, config=config, initial_prompt=initial_prompt)
    issue_text = load_agent_issue_text(args)
    if not issue_text:
        print(
            "patchsmith agent requires a prompt, --issue-file, or piped stdin.",
            file=sys.stderr,
        )
        return 2
    config, profile_error = agent_config_from_args(args)
    if profile_error:
        print(profile_error, file=sys.stderr)
        return 2
    runtime_config, apply_preflight, error = validate_agent_cli_config(
        config,
        require_apply_ready=not args.preflight,
    )
    if error:
        print(error, file=sys.stderr)
        return 2

    if args.preflight:
        payload = agent_preflight_payload(
            config=config,
            issue_text=issue_text,
            runtime_config=runtime_config,
            apply_preflight=apply_preflight,
        )
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            _print_agent_preflight(payload)
        return 0 if payload["status"] == "passed" else 2

    if not args.skip_model_preflight:
        model_preflight = _openai_model_preflight_for_config(config)
        if not model_preflight.available:
            if args.json:
                print(
                    json.dumps(
                        {
                            "status": "blocked",
                            "reason_code": "model_preflight_failed",
                            "model_preflight": model_preflight.to_dict(),
                        },
                        indent=2,
                    )
                )
            else:
                print(_format_model_preflight_block(model_preflight), file=sys.stderr)
            return 2

    run = run_agent_once(
        config=config,
        issue_text=issue_text,
        runner_cls=RepairRunner,
    )
    if args.json:
        print(
            json.dumps(
                run_result_payload(
                    run.result,
                    runtime="deepagents",
                    planner="deepagents",
                    apply_result=run.apply_result,
                ),
                indent=2,
            )
        )
    else:
        print("PatchSmith Agent")
        _print_run_result(run.result, apply_result=run.apply_result)
    return run.exit_code


def _chat_command(args: argparse.Namespace) -> int:
    if args.issue_file and args.prompt:
        print("pass either a prompt or --issue-file, not both.", file=sys.stderr)
        return 2
    session_action_error = _validate_offline_session_actions(args)
    if session_action_error:
        print(session_action_error, file=sys.stderr)
        return 2
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
    if args.export_path:
        print("--export-path requires --export-session.", file=sys.stderr)
        return 2
    config, profile_error = agent_config_from_args(args)
    if profile_error:
        print(profile_error, file=sys.stderr)
        return 2
    _, _, error = validate_agent_cli_config(config, require_apply_ready=False)
    if error:
        print(error, file=sys.stderr)
        return 2
    return _run_chat_from_args(
        args=args,
        config=config,
        initial_prompt=load_agent_initial_prompt(args),
    )


def _run_chat_from_args(
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


def _validate_offline_session_actions(args: argparse.Namespace) -> str | None:
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
    if not args.session_gate and _has_session_gate_threshold(args):
        return "session gate thresholds require --session-gate."
    gate_error = _validate_session_gate_args(args)
    if gate_error:
        return gate_error
    return None


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


def _has_session_gate_threshold(args: argparse.Namespace) -> bool:
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


def _run_command(args: argparse.Namespace) -> int:
    issue_text = _load_issue_text(args)
    request = RunRequest(
        repo=args.repo,
        issue_text=issue_text,
        issue_url=args.issue_url,
        commit=args.commit,
        branch=args.branch,
        test_command=args.test_command,
        runtime=args.runtime,
        planner=args.planner,
        max_retries=args.max_retries,
        retrieval_strategy=args.context_provider,
        context_provider=args.context_provider,
        top_k=args.top_k,
        sandbox_mode=args.sandbox_mode,
        sandbox_image=args.sandbox_image,
        context_paths=tuple(args.context_path or ()),
    )
    result = RepairRunner(artifacts_dir=Path(args.artifacts_dir)).run(request)
    if args.json:
        print(
            json.dumps(
                run_result_payload(result, runtime=args.runtime, planner=args.planner),
                indent=2,
            )
        )
    else:
        _print_run_result(result)
    return 0


def _openai_model_preflight_for_config(config: AgentCliConfig) -> ModelPreflightResult:
    return openai_model_preflight_from_env(model=config.deepagents_model)


def _format_model_preflight_block(result: ModelPreflightResult) -> str:
    lines = [
        f"model preflight blocked: {result.status} ({result.model})",
    ]
    if result.suggestions:
        lines.append("suggestions: " + ", ".join(result.suggestions))
    if result.error:
        lines.append(result.error)
    else:
        lines.append("requested model is unavailable for the configured provider.")
    return "\n".join(lines)


def _print_agent_preflight(payload: dict[str, Any]) -> None:
    print(f"PatchSmith Agent Preflight: {payload['status']}")
    for check in payload["checks"]:
        if isinstance(check, dict):
            print(f"- {check['name']}: {check['status']} - {check['message']}")


def _print_run_result(
    result: RepairRunResult,
    *,
    apply_result: AgentApplyResult | None = None,
) -> None:
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Report: {result.report_path}")
    print(f"Trace: {result.trace_path}")
    print(f"Diff: {result.final_diff_path}")
    if apply_result is not None:
        print(f"Apply status: {apply_result.status}")
        print(f"Apply message: {apply_result.message}")
    if result.test_result:
        print(f"Test exit code: {result.test_result.exit_code}")
    if result.retrieved_context:
        print("Top retrieved files:")
        for context in result.retrieved_context[:5]:
            print(f"  {context.rank}. {context.path} ({context.score:.2f})")
