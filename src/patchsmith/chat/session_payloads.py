from __future__ import annotations

from dataclasses import replace as dataclass_replace

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import plan_items_from_payload, plan_items_payload
from patchsmith.chat.state import AgentChatRuntime


def config_payload(config: AgentCliConfig) -> dict[str, object]:
    return {
        "repo": config.repo,
        "commit": config.commit,
        "branch": config.branch,
        "issue_url": config.issue_url,
        "test_command": config.test_command,
        "context_provider": config.context_provider,
        "context_paths": list(config.context_paths),
        "top_k": config.top_k,
        "artifacts_dir": config.artifacts_dir,
        "sandbox_mode": config.sandbox_mode,
        "sandbox_image": config.sandbox_image,
        "apply": config.apply,
        "allow_dirty_apply": config.allow_dirty_apply,
        "max_retries": config.max_retries,
        "deepagents_max_context_files": config.deepagents_max_context_files,
        "deepagents_subagents": config.deepagents_subagents,
        "deepagents_model": config.deepagents_model,
        "max_model_responses": config.max_model_responses,
        "max_model_tokens": config.max_model_tokens,
        "agent_profile": config.agent_profile,
        "agent_profile_path": config.agent_profile_path,
        "agent_profile_description": config.agent_profile_description,
        "agent_profile_instructions": config.agent_profile_instructions,
        "agent_profile_instruction_chars": len(config.agent_profile_instructions or ""),
        "load_agent_instructions": config.load_agent_instructions,
        "instruction_paths": list(config.instruction_paths),
        "agent_instruction_files": list(config.agent_instruction_files),
        "agent_instructions": config.agent_instructions,
        "agent_instruction_chars": len(config.agent_instructions or ""),
    }


def checkpoint_state_payload(runtime: AgentChatRuntime) -> dict[str, object]:
    return {
        "config": config_payload(runtime.state.config),
        "chat_mode": runtime.chat_mode,
        "pending_planned_task": runtime.pending_planned_task,
        "history": list(runtime.history or []),
        "plan_items": plan_items_payload(runtime.plan_items or []),
        "feedback_items": list(runtime.feedback_items or []),
        "last_run_payload": runtime.last_run_payload,
        "last_apply": (
            runtime.last_apply.to_dict() if runtime.last_apply is not None else None
        ),
        "last_rewind": (
            runtime.last_rewind.to_dict() if runtime.last_rewind is not None else None
        ),
        "compaction_summary": runtime.compaction_summary,
    }


def restore_checkpoint_state(
    *,
    runtime: AgentChatRuntime,
    state: dict[str, object],
) -> None:
    config_payload_value = state.get("config")
    config = runtime.state.config
    if isinstance(config_payload_value, dict):
        config = config_from_payload(config_payload_value, config)
    runtime.state = dataclass_replace(runtime.state, config=config)
    runtime.chat_mode = chat_mode_from_payload(state.get("chat_mode"))
    runtime.pending_planned_task = optional_text(state.get("pending_planned_task"))
    runtime.last_run = None
    runtime.history = string_list_from_payload(state.get("history"))
    runtime.plan_items = plan_items_from_payload(state.get("plan_items"))
    runtime.feedback_items = string_list_from_payload(state.get("feedback_items"))
    runtime.last_run_payload = dict_or_none(state.get("last_run_payload"))
    runtime.last_apply = apply_result_from_state(state.get("last_apply"))
    runtime.last_rewind = apply_result_from_state(state.get("last_rewind"))
    runtime.compaction_summary = dict_or_none(state.get("compaction_summary"))


def config_from_payload(
    payload: dict[str, object],
    fallback: AgentCliConfig,
) -> AgentCliConfig:
    return AgentCliConfig(
        repo=payload_str(payload, "repo", fallback.repo),
        commit=payload_optional_str(payload, "commit", fallback.commit),
        branch=payload_optional_str(payload, "branch", fallback.branch),
        issue_url=payload_optional_str(payload, "issue_url", fallback.issue_url),
        test_command=payload_optional_str(
            payload,
            "test_command",
            fallback.test_command,
        ),
        context_provider=payload_str(
            payload,
            "context_provider",
            fallback.context_provider,
        ),
        context_paths=context_paths_from_payload(payload) or fallback.context_paths,
        top_k=payload_int(payload, "top_k", fallback.top_k),
        artifacts_dir=payload_str(payload, "artifacts_dir", fallback.artifacts_dir),
        sandbox_mode=payload_str(payload, "sandbox_mode", fallback.sandbox_mode),
        sandbox_image=payload_str(payload, "sandbox_image", fallback.sandbox_image),
        apply=payload_bool(payload, "apply", fallback.apply),
        allow_dirty_apply=payload_bool(
            payload,
            "allow_dirty_apply",
            fallback.allow_dirty_apply,
        ),
        max_retries=payload_int(payload, "max_retries", fallback.max_retries),
        deepagents_max_context_files=payload_int(
            payload,
            "deepagents_max_context_files",
            fallback.deepagents_max_context_files,
        ),
        deepagents_subagents=payload_str(
            payload,
            "deepagents_subagents",
            fallback.deepagents_subagents,
        ),
        deepagents_model=payload_optional_str(
            payload,
            "deepagents_model",
            fallback.deepagents_model,
        ),
        max_model_responses=payload_int(
            payload,
            "max_model_responses",
            fallback.max_model_responses,
        ),
        max_model_tokens=payload_int(
            payload,
            "max_model_tokens",
            fallback.max_model_tokens,
        ),
        agent_profile=payload_optional_str(
            payload,
            "agent_profile",
            fallback.agent_profile,
        ),
        agent_profile_path=payload_optional_str(
            payload,
            "agent_profile_path",
            fallback.agent_profile_path,
        ),
        agent_profile_description=payload_optional_str(
            payload,
            "agent_profile_description",
            fallback.agent_profile_description,
        ),
        agent_profile_instructions=payload_optional_str(
            payload,
            "agent_profile_instructions",
            fallback.agent_profile_instructions,
        ),
        load_agent_instructions=payload_bool(
            payload,
            "load_agent_instructions",
            fallback.load_agent_instructions,
        ),
        instruction_paths=tuple_str_field(
            payload,
            "instruction_paths",
            fallback.instruction_paths,
        ),
        agent_instruction_files=tuple_str_field(
            payload,
            "agent_instruction_files",
            fallback.agent_instruction_files,
        ),
        agent_instructions=payload_optional_str(
            payload,
            "agent_instructions",
            fallback.agent_instructions,
        ),
    )


def apply_config_update(
    config: AgentCliConfig,
    payload: dict[str, object],
) -> AgentCliConfig:
    field = payload.get("field")
    if field == "deepagents_model":
        value = payload.get("value")
        return dataclass_replace(
            config,
            deepagents_model=value if isinstance(value, str) else None,
        )
    if field == "resource_budget":
        return dataclass_replace(
            config,
            max_model_responses=payload_int(
                payload,
                "max_model_responses",
                config.max_model_responses,
            ),
            max_model_tokens=payload_int(
                payload,
                "max_model_tokens",
                config.max_model_tokens,
            ),
        )
    if field == "permissions":
        apply_after_run = payload_bool(payload, "apply", config.apply)
        return dataclass_replace(
            config,
            apply=apply_after_run,
            allow_dirty_apply=(
                payload_bool(
                    payload,
                    "allow_dirty_apply",
                    config.allow_dirty_apply,
                )
                if apply_after_run
                else False
            ),
        )
    if field == "agent_profile":
        return dataclass_replace(
            config,
            agent_profile=payload_optional_str(
                payload,
                "agent_profile",
                config.agent_profile,
            ),
            agent_profile_path=payload_optional_str(
                payload,
                "agent_profile_path",
                config.agent_profile_path,
            ),
            agent_profile_description=payload_optional_str(
                payload,
                "agent_profile_description",
                config.agent_profile_description,
            ),
            agent_profile_instructions=payload_optional_str(
                payload,
                "agent_profile_instructions",
                config.agent_profile_instructions,
            ),
            deepagents_model=payload_optional_str(
                payload,
                "deepagents_model",
                config.deepagents_model,
            ),
            deepagents_subagents=payload_str(
                payload,
                "deepagents_subagents",
                config.deepagents_subagents,
            ),
            deepagents_max_context_files=payload_int(
                payload,
                "deepagents_max_context_files",
                config.deepagents_max_context_files,
            ),
            max_model_responses=payload_int(
                payload,
                "max_model_responses",
                config.max_model_responses,
            ),
            max_model_tokens=payload_int(
                payload,
                "max_model_tokens",
                config.max_model_tokens,
            ),
            top_k=payload_int(payload, "top_k", config.top_k),
            test_command=payload_optional_str(
                payload,
                "test_command",
                config.test_command,
            ),
            context_paths=context_paths_from_payload(payload) or config.context_paths,
        )
    if field == "project_instructions":
        return dataclass_replace(
            config,
            load_agent_instructions=payload_bool(
                payload,
                "load_agent_instructions",
                config.load_agent_instructions,
            ),
            instruction_paths=tuple_str_field(
                payload,
                "instruction_paths",
                config.instruction_paths,
            ),
            agent_instruction_files=tuple_str_field(
                payload,
                "agent_instruction_files",
                config.agent_instruction_files,
            ),
            agent_instructions=payload_optional_str(
                payload,
                "agent_instructions",
                config.agent_instructions,
            ),
        )
    return config


def context_paths_from_payload(payload: dict[str, object]) -> tuple[str, ...] | None:
    value = payload.get("context_paths")
    if not isinstance(value, list):
        return None
    return tuple(item for item in value if isinstance(item, str))


def feedback_items_from_update(
    *,
    current: list[str],
    payload: dict[str, object],
) -> list[str]:
    action = payload.get("action")
    if action == "clear":
        return []
    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, str)]
    item = payload.get("item")
    if action == "add" and isinstance(item, str):
        return [*current, item]
    return current


def tuple_str_field(
    payload: dict[str, object],
    key: str,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list):
        return fallback
    return tuple(item for item in value if isinstance(item, str))


def apply_result_from_payload(payload: dict[str, object]) -> AgentApplyResult | None:
    status = payload.get("status")
    repo_path = payload.get("repo_path")
    diff_path = payload.get("diff_path")
    message = payload.get("message")
    if not isinstance(status, str):
        return None
    if not isinstance(repo_path, str):
        return None
    if not isinstance(diff_path, str):
        return None
    if not isinstance(message, str):
        return None
    return AgentApplyResult(
        status=status,
        repo_path=repo_path,
        diff_path=diff_path,
        message=message,
        applied=payload.get("applied") is True,
    )


def apply_result_from_state(value: object) -> AgentApplyResult | None:
    if not isinstance(value, dict):
        return None
    return apply_result_from_payload(value)


def dict_or_none(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, dict) else None


def chat_mode_from_payload(value: object) -> str:
    return value if value in {"act", "plan"} else "act"


def string_list_from_payload(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def payload_str(payload: dict[str, object], key: str, fallback: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else fallback


def payload_optional_str(
    payload: dict[str, object],
    key: str,
    fallback: str | None,
) -> str | None:
    value = payload.get(key)
    if value is None:
        return None if key in payload else fallback
    return value if isinstance(value, str) else fallback


def payload_int(payload: dict[str, object], key: str, fallback: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return fallback
    return value if isinstance(value, int) else fallback


def payload_bool(payload: dict[str, object], key: str, fallback: bool) -> bool:
    value = payload.get(key)
    return value if isinstance(value, bool) else fallback


def optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def last_run_value(runtime: AgentChatRuntime, key: str) -> object | None:
    if runtime.last_run is not None:
        value = getattr(runtime.last_run, _result_attribute_for_payload_key(key), None)
        if value is not None:
            return value
    if runtime.last_run_payload is None:
        return None
    return runtime.last_run_payload.get(key)


def _result_attribute_for_payload_key(key: str) -> str:
    if key == "final_diff_path":
        return "final_diff_path"
    if key == "report_path":
        return "report_path"
    if key == "trace_path":
        return "trace_path"
    return key
