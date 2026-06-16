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
from patchsmith.agent_cli import (
    AgentCliConfig,
    agent_preflight_payload,
    run_agent_once,
    run_result_payload,
    validate_agent_cli_config,
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
from patchsmith.cli.commands.chat import (
    dispatch_offline_session_action,
    has_session_gate_threshold,
    run_chat_from_args,
    validate_offline_session_actions,
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
    if has_session_gate_threshold(args) and not args.session_gate:
        print("session gate thresholds require --session-gate.", file=sys.stderr)
        return 2
    if args.script and not args.interactive:
        print("--script requires --interactive.", file=sys.stderr)
        return 2
    if args.interactive:
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
        initial_prompt = load_agent_initial_prompt(args)
        return run_chat_from_args(args=args, config=config, initial_prompt=initial_prompt)
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
