from __future__ import annotations

from typing import TextIO

from patchsmith.agent_cli import (
    AgentCliConfig,
    agent_preflight_payload,
    validate_agent_cli_config,
)


def preflight_payload(
    *,
    config: AgentCliConfig,
    task: str,
) -> tuple[dict[str, object], str | None]:
    runtime_config, apply_preflight, error = validate_agent_cli_config(
        config,
        require_apply_ready=False,
    )
    if error:
        return {}, error
    return (
        agent_preflight_payload(
            config=config,
            issue_text=task,
            runtime_config=runtime_config,
            apply_preflight=apply_preflight,
        ),
        None,
    )


def print_checks(checks: object, output_stream: TextIO) -> None:
    if not isinstance(checks, list):
        return
    for check in checks:
        if isinstance(check, dict):
            _write_line(
                output_stream,
                f"- {check['name']}: {check['status']} - {check['message']}",
            )


def _write_line(output_stream: TextIO, message: str) -> None:
    output_stream.write(f"{message}\n")
    output_stream.flush()
