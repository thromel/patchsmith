from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any

from patchsmith.agent_apply import (
    AgentApplyResult,
    apply_agent_run_diff,
    preflight_agent_apply_target,
)
from patchsmith.agent_instructions import load_agent_instruction_bundle
from patchsmith.deepagents_config import DEFAULT_DEEPAGENTS_MODEL
from patchsmith.model_config import openai_model_supports_encrypted_reasoning
from patchsmith.models import RepairRunResult, RunRequest
from patchsmith.workflow import RepairRunner

RECOMMENDED_REASONING_TOKEN_HEADROOM = 25_000
RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM = 90_000


@dataclass(frozen=True)
class AgentCliConfig:
    repo: str = "."
    commit: str | None = None
    branch: str | None = None
    issue_url: str | None = None
    test_command: str | None = None
    context_provider: str = "native_hybrid"
    context_paths: tuple[str, ...] = ()
    top_k: int = 5
    artifacts_dir: str = "artifacts"
    sandbox_mode: str = "local"
    sandbox_image: str = "python:3.12-slim"
    apply: bool = False
    allow_dirty_apply: bool = False
    max_retries: int = 1
    deepagents_max_context_files: int = 0
    deepagents_subagents: str = "auto"
    deepagents_model: str | None = None
    max_model_responses: int = 12
    max_model_tokens: int = 200_000
    agent_profile: str | None = None
    agent_profile_path: str | None = None
    agent_profile_description: str | None = None
    agent_profile_instructions: str | None = None
    load_agent_instructions: bool = True
    instruction_paths: tuple[str, ...] = ()
    agent_instruction_files: tuple[str, ...] = ()
    agent_instructions: str | None = None


@dataclass(frozen=True)
class AgentCliRun:
    result: RepairRunResult
    apply_result: AgentApplyResult | None = None

    @property
    def exit_code(self) -> int:
        if self.apply_result is not None and not self.apply_result.applied:
            return 3
        return 0


def validate_agent_cli_config(
    config: AgentCliConfig,
    *,
    require_apply_ready: bool,
) -> tuple[dict[str, object], AgentApplyResult | None, str | None]:
    if config.deepagents_max_context_files < 0:
        return {}, None, "--deepagents-max-context-files must be non-negative."
    if config.max_model_responses < -1:
        return {}, None, "--max-model-responses must be -1 or non-negative."
    if config.max_model_tokens < -1:
        return {}, None, "--max-model-tokens must be -1 or non-negative."
    if config.allow_dirty_apply and not config.apply:
        return {}, None, "--allow-dirty-apply requires --apply."

    apply_preflight = (
        preflight_agent_apply_target(
            repo=config.repo,
            allow_dirty=config.allow_dirty_apply,
        )
        if config.apply
        else None
    )
    if (
        require_apply_ready
        and apply_preflight is not None
        and apply_preflight.status != "ready"
    ):
        return {}, apply_preflight, apply_preflight.message
    return agent_runtime_config(config), apply_preflight, None


def agent_runtime_config(config: AgentCliConfig) -> dict[str, object]:
    runtime_config: dict[str, object] = {"subagent_mode": config.deepagents_subagents}
    if config.deepagents_model:
        runtime_config["model"] = config.deepagents_model
    if config.deepagents_max_context_files > 0:
        runtime_config["max_context_files"] = config.deepagents_max_context_files
    resource_budget: dict[str, int] = {}
    if config.max_model_responses >= 0:
        resource_budget["max_model_responses"] = config.max_model_responses
    if config.max_model_tokens >= 0:
        resource_budget["max_model_tokens"] = config.max_model_tokens
    if resource_budget:
        runtime_config["resource_budget"] = resource_budget
    if config.agent_profile:
        runtime_config["agent_profile"] = {
            "name": config.agent_profile,
            "path": config.agent_profile_path,
            "description": config.agent_profile_description,
            "instruction_chars": len(config.agent_profile_instructions or ""),
        }
    if config.agent_instructions:
        runtime_config["project_instructions"] = {
            "files": list(config.agent_instruction_files),
            "instruction_chars": len(config.agent_instructions),
        }
    return runtime_config


def agent_run_request(
    *,
    config: AgentCliConfig,
    issue_text: str,
    runtime_config: dict[str, object],
) -> RunRequest:
    return RunRequest(
        repo=config.repo,
        issue_text=_issue_text_with_agent_context(config=config, issue_text=issue_text),
        issue_url=config.issue_url,
        commit=config.commit,
        branch=config.branch,
        test_command=config.test_command,
        runtime="deepagents",
        planner="deepagents",
        max_retries=config.max_retries,
        retrieval_strategy=config.context_provider,
        context_provider=config.context_provider,
        top_k=config.top_k,
        sandbox_mode=config.sandbox_mode,
        sandbox_image=config.sandbox_image,
        context_paths=config.context_paths,
        runtime_config=runtime_config,
    )


def run_agent_once(
    *,
    config: AgentCliConfig,
    issue_text: str,
    runner_cls: type[RepairRunner] = RepairRunner,
) -> AgentCliRun:
    runtime_config, _apply_preflight, error = validate_agent_cli_config(
        config,
        require_apply_ready=True,
    )
    if error:
        raise ValueError(error)
    result = runner_cls(artifacts_dir=Path(config.artifacts_dir)).run(
        agent_run_request(
            config=config,
            issue_text=issue_text,
            runtime_config=runtime_config,
        )
    )
    apply_result = (
        apply_agent_run_diff(
            repo=config.repo,
            diff_path=result.final_diff_path,
            allow_dirty=config.allow_dirty_apply,
        )
        if config.apply
        else None
    )
    return AgentCliRun(result=result, apply_result=apply_result)


def agent_preflight_payload(
    *,
    config: AgentCliConfig,
    issue_text: str,
    runtime_config: dict[str, object],
    apply_preflight: AgentApplyResult | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        {
            "name": "prompt",
            "status": "passed",
            "message": f"loaded {len(issue_text)} characters of task text",
        },
        *_agent_diagnostic_checks(config=config, apply_preflight=apply_preflight),
    ]
    return {
        "status": _checks_status(checks),
        "runtime": "deepagents",
        "planner": "deepagents",
        "repo": config.repo,
        "issue_text_chars": len(issue_text),
        "test_command": config.test_command,
        "context_provider": config.context_provider,
        "context_paths": list(config.context_paths),
        "top_k": config.top_k,
        "sandbox_mode": config.sandbox_mode,
        "sandbox_image": config.sandbox_image,
        "artifacts_dir": config.artifacts_dir,
        "apply": config.apply,
        "allow_dirty_apply": config.allow_dirty_apply,
        "runtime_config": runtime_config,
        "agent_profile": _agent_profile_payload(config),
        "project_instructions": _agent_instructions_payload(config),
        "checks": checks,
    }


def agent_diagnostic_payload(
    *,
    config: AgentCliConfig,
    runtime_config: dict[str, object],
    apply_preflight: AgentApplyResult | None,
) -> dict[str, Any]:
    checks = _agent_diagnostic_checks(
        config=config,
        apply_preflight=apply_preflight,
    )
    return {
        "status": _checks_status(checks),
        "runtime": "deepagents",
        "planner": "deepagents",
        "repo": config.repo,
        "test_command": config.test_command,
        "context_provider": config.context_provider,
        "context_paths": list(config.context_paths),
        "top_k": config.top_k,
        "sandbox_mode": config.sandbox_mode,
        "sandbox_image": config.sandbox_image,
        "artifacts_dir": config.artifacts_dir,
        "apply": config.apply,
        "allow_dirty_apply": config.allow_dirty_apply,
        "runtime_config": runtime_config,
        "agent_profile": _agent_profile_payload(config),
        "project_instructions": _agent_instructions_payload(config),
        "checks": checks,
    }


def _agent_diagnostic_checks(
    *,
    config: AgentCliConfig,
    apply_preflight: AgentApplyResult | None,
) -> list[dict[str, Any]]:
    checks = [
        _deepagents_dependency_check(),
        _openai_api_key_check(),
        _model_selection_check(config),
        _budget_check(config),
        _deepagents_token_headroom_check(config),
        _reasoning_token_headroom_check(config),
    ]
    checks.append(_apply_target_check(apply_preflight))
    return checks


def _deepagents_dependency_check() -> dict[str, Any]:
    required_modules = ("deepagents", "langchain_openai")
    missing = [
        module
        for module in required_modules
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        return {
            "name": "deepagents_dependency",
            "status": "blocked",
            "message": (
                "missing optional modules: "
                f"{', '.join(missing)}; install with python -m pip install -e \".[deepagents]\""
            ),
            "missing_modules": missing,
        }
    return {
        "name": "deepagents_dependency",
        "status": "passed",
        "message": "deepagents optional dependency is importable",
    }


def _openai_api_key_check() -> dict[str, Any]:
    return {
        "name": "openai_api_key",
        "status": "passed" if os.environ.get("OPENAI_API_KEY") else "blocked",
        "message": (
            "OPENAI_API_KEY is set"
            if os.environ.get("OPENAI_API_KEY")
            else "OPENAI_API_KEY is not set in the environment"
        ),
    }


def _model_selection_check(config: AgentCliConfig) -> dict[str, Any]:
    selected_model, selected_source = _selected_deepagents_model(config)
    if selected_source == "override":
        message = f"model override: {selected_model}"
    elif selected_source == "environment":
        message = f"model from environment: {selected_model}"
    else:
        message = "model from default DeepAgents/OpenAI configuration"
    return {"name": "model_selection", "status": "passed", "message": message}


def _selected_deepagents_model(config: AgentCliConfig) -> tuple[str, str]:
    env_model = (
        os.environ.get("PATCHSMITH_DEEPAGENTS_MODEL")
        or os.environ.get("PATCHSMITH_OPENAI_MODEL")
        or ""
    ).strip()
    if config.deepagents_model:
        return config.deepagents_model, "override"
    if env_model:
        return env_model, "environment"
    return DEFAULT_DEEPAGENTS_MODEL, "default"


def _budget_check(config: AgentCliConfig) -> dict[str, Any]:
    return {
        "name": "resource_budget",
        "status": "passed",
        "message": (
            "responses="
            f"{_budget_limit_label(config.max_model_responses)}, "
            f"tokens={_budget_limit_label(config.max_model_tokens)}"
        ),
    }


def _deepagents_token_headroom_check(config: AgentCliConfig) -> dict[str, Any]:
    token_cap = None if config.max_model_tokens < 0 else config.max_model_tokens
    if token_cap is None:
        return {
            "name": "deepagents_token_headroom",
            "status": "passed",
            "message": (
                "DeepAgents token cap is unlimited; monitor saved usage before "
                "widening benchmark claims"
            ),
            "recommended_min_tokens": RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM,
            "max_model_tokens": None,
        }
    if token_cap < RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM:
        return {
            "name": "deepagents_token_headroom",
            "status": "passed",
            "severity": "warning",
            "message": (
                f"DeepAgents token cap {token_cap} is below recommended initial "
                f"headroom {RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM}; native "
                "DeepAgents setup and tool prompts can exceed small caps before "
                "a patch is produced"
            ),
            "recommended_min_tokens": RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM,
            "max_model_tokens": token_cap,
        }
    return {
        "name": "deepagents_token_headroom",
        "status": "passed",
        "message": (
            f"DeepAgents token cap {token_cap} leaves initial prompt/tool headroom"
        ),
        "recommended_min_tokens": RECOMMENDED_DEEPAGENTS_TOKEN_HEADROOM,
        "max_model_tokens": token_cap,
    }


def _reasoning_token_headroom_check(config: AgentCliConfig) -> dict[str, Any]:
    model, _source = _selected_deepagents_model(config)
    reasoning_model = openai_model_supports_encrypted_reasoning(model)
    token_cap = None if config.max_model_tokens < 0 else config.max_model_tokens
    if not reasoning_model:
        return {
            "name": "reasoning_token_headroom",
            "status": "skipped",
            "message": f"{model} is not treated as a reasoning-model id",
            "model": model,
            "reasoning_model": False,
            "recommended_min_tokens": RECOMMENDED_REASONING_TOKEN_HEADROOM,
            "max_model_tokens": token_cap,
        }
    if token_cap is None:
        return {
            "name": "reasoning_token_headroom",
            "status": "passed",
            "message": (
                "reasoning-model token cap is unlimited; monitor saved usage "
                "before widening benchmark claims"
            ),
            "model": model,
            "reasoning_model": True,
            "recommended_min_tokens": RECOMMENDED_REASONING_TOKEN_HEADROOM,
            "max_model_tokens": None,
        }
    if token_cap < RECOMMENDED_REASONING_TOKEN_HEADROOM:
        return {
            "name": "reasoning_token_headroom",
            "status": "passed",
            "severity": "warning",
            "message": (
                f"{model} is reasoning-capable and token cap {token_cap} is below "
                f"recommended initial headroom {RECOMMENDED_REASONING_TOKEN_HEADROOM}; "
                "the run may spend tokens without producing a patch"
            ),
            "model": model,
            "reasoning_model": True,
            "recommended_min_tokens": RECOMMENDED_REASONING_TOKEN_HEADROOM,
            "max_model_tokens": token_cap,
        }
    return {
        "name": "reasoning_token_headroom",
        "status": "passed",
        "message": (
            f"{model} token cap {token_cap} leaves initial reasoning/output headroom"
        ),
        "model": model,
        "reasoning_model": True,
        "recommended_min_tokens": RECOMMENDED_REASONING_TOKEN_HEADROOM,
        "max_model_tokens": token_cap,
    }


def _apply_target_check(
    apply_preflight: AgentApplyResult | None,
) -> dict[str, Any]:
    if apply_preflight is None:
        return {
            "name": "apply_target",
            "status": "skipped",
            "message": "--apply was not requested",
        }
    return {
        "name": "apply_target",
        "status": "passed" if apply_preflight.status == "ready" else "blocked",
        "message": apply_preflight.message,
        "details": apply_preflight.to_dict(),
    }


def _checks_status(checks: list[dict[str, Any]]) -> str:
    return (
        "passed"
        if all(check["status"] in {"passed", "skipped"} for check in checks)
        else "blocked"
    )


def _budget_limit_label(value: int) -> str:
    return "unlimited" if value < 0 else str(value)


def config_with_loaded_agent_instructions(config: AgentCliConfig) -> AgentCliConfig:
    if not config.load_agent_instructions:
        return config
    bundle = load_agent_instruction_bundle(
        config.repo,
        explicit_paths=config.instruction_paths,
        include_defaults=True,
    )
    if not bundle.content:
        return config
    return dataclass_replace(
        config,
        agent_instruction_files=tuple(file.repo_relative_path for file in bundle.files),
        agent_instructions=bundle.content,
    )


def _issue_text_with_agent_context(*, config: AgentCliConfig, issue_text: str) -> str:
    sections: list[str] = []
    instructions = (config.agent_instructions or "").strip()
    if instructions:
        sections.extend(
            [
                "PatchSmith project instructions",
                instructions,
            ]
        )
    instructions = (config.agent_profile_instructions or "").strip()
    if instructions:
        sections.extend(
            [
                f"PatchSmith agent profile /{config.agent_profile or 'unnamed'}",
                f"Source: {config.agent_profile_path or 'session'}",
                "",
                "Profile instructions:",
                instructions,
            ]
        )
    if not sections:
        return issue_text
    return "\n".join(
        [
            *sections,
            "",
            "Task:",
            issue_text.strip(),
        ]
    ).rstrip()


def _agent_profile_payload(config: AgentCliConfig) -> dict[str, object] | None:
    if not config.agent_profile:
        return None
    return {
        "name": config.agent_profile,
        "path": config.agent_profile_path,
        "description": config.agent_profile_description,
        "instruction_chars": len(config.agent_profile_instructions or ""),
    }


def _agent_instructions_payload(config: AgentCliConfig) -> dict[str, object] | None:
    if not config.agent_instructions:
        return None
    return {
        "files": list(config.agent_instruction_files),
        "instruction_chars": len(config.agent_instructions),
    }


def run_result_payload(
    result: RepairRunResult,
    *,
    runtime: str,
    planner: str,
    apply_result: AgentApplyResult | None = None,
) -> dict[str, object]:
    model_usage = getattr(result, "model_usage", {}) or {}
    payload: dict[str, object] = {
        "run_id": result.run_id,
        "status": result.status,
        "runtime": runtime,
        "planner": planner,
        "report_path": str(result.report_path),
        "trace_path": str(result.trace_path),
        "final_diff_path": str(result.final_diff_path),
        "test_exit_code": result.test_result.exit_code if result.test_result else None,
        "retrieved_files": [context.path for context in result.retrieved_context],
    }
    payload.update(_repair_outcome_payload(result.trace_path))
    if isinstance(model_usage, dict) and model_usage:
        payload["model_usage"] = dict(model_usage)
        payload["model_call_count"] = model_usage.get("call_count")
        payload["model_response_count"] = model_usage.get("response_count")
        payload["model_total_tokens"] = model_usage.get("total_tokens")
        payload["estimated_cost_usd"] = model_usage.get("estimated_cost_usd")
    if apply_result is not None:
        payload["apply"] = apply_result.to_dict()
    return payload


def _repair_outcome_payload(trace_path: Path) -> dict[str, object]:
    payload = _latest_trace_payload(
        trace_path,
        node_name="analyze",
        event_type="repair_outcome",
    )
    if payload is None:
        return {}
    return {
        "repair_outcome_status": payload.get("status"),
        "repair_verdict": payload.get("verdict"),
        "repair_failure_category": payload.get("failure_category"),
        "repair_patch_generated": payload.get("patch_generated"),
        "repair_tests_passed": payload.get("tests_passed"),
        "repair_next_action": payload.get("next_action"),
    }


def _latest_trace_payload(
    trace_path: Path,
    *,
    node_name: str,
    event_type: str,
) -> dict[str, object] | None:
    if not trace_path.is_file():
        return None
    latest: dict[str, object] | None = None
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        if (
            row.get("node_name") == node_name
            and row.get("event_type") == event_type
            and isinstance(payload, dict)
        ):
            latest = payload
    return latest
