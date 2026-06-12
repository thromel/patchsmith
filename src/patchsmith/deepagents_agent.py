"""Native DeepAgents agent construction."""

from __future__ import annotations

from typing import Any

from patchsmith.deepagents_config import DeepAgentsPlannerConfig
from patchsmith.deepagents_files import (
    _agent_files,
    _read_only_filesystem_permissions,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
    deepagents_patch_review_subagents,
    deepagents_system_prompt,
)
from patchsmith.deepagents_schema import PatchPlan


def build_deepagents_agent(
    *,
    config: DeepAgentsPlannerConfig,
    files: dict[str, dict[str, str]],
    subagents: list[dict[str, str]] | None = None,
) -> Any:
    agent_files = _agent_files(files)
    configured_subagents = subagents or deepagents_patch_review_subagents()

    try:
        from deepagents import FilesystemPermission, create_deep_agent
        from deepagents.backends import StateBackend
        from langchain_openai import ChatOpenAI
    except ImportError as error:
        raise RuntimeError(
            "DeepAgents native planner requires the `deepagents` extra: "
            'install with `python -m pip install -e ".[deepagents]"`.'
        ) from error

    model = ChatOpenAI(**deepagents_model_kwargs(config))
    return create_deep_agent(
        model=model,
        tools=[],
        system_prompt=deepagents_system_prompt(),
        subagents=configured_subagents,  # type: ignore[arg-type]
        skills=[PATCHSMITH_DEEPAGENTS_SKILL_DIR],
        memory=[PATCHSMITH_DEEPAGENTS_MEMORY_PATH],
        backend=StateBackend(),
        permissions=_read_only_filesystem_permissions(
            agent_files.keys(),
            permission_cls=FilesystemPermission,
        ),
        response_format=PatchPlan,
    )


def deepagents_model_kwargs(config: DeepAgentsPlannerConfig) -> dict[str, Any]:
    model_kwargs: dict[str, Any] = {
        "model": config.model,
        "use_responses_api": config.use_responses_api,
        "max_completion_tokens": config.max_output_tokens,
    }
    if config.use_responses_api:
        model_kwargs["store"] = config.store
        model_kwargs["include"] = ["reasoning.encrypted_content"]
    if config.reasoning_effort:
        model_kwargs["reasoning_effort"] = config.reasoning_effort
    return model_kwargs
