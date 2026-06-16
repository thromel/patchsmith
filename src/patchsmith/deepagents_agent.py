"""Native DeepAgents agent construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from patchsmith.deepagents_config import (
    DeepAgentsPlannerConfig,
    deepagents_encrypted_reasoning_enabled,
)
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


class DeepAgentsResourceBudgetExceeded(RuntimeError):
    """Raised when a live DeepAgents run crosses PatchSmith's resource budget."""

    def __init__(
        self,
        message: str,
        *,
        response_count: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        super().__init__(message)
        self.response_count = response_count
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


@dataclass(frozen=True)
class _TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


def build_deepagents_agent(
    *,
    config: DeepAgentsPlannerConfig,
    files: dict[str, dict[str, str]],
    subagents: list[dict[str, str]] | None = None,
) -> Any:
    configured_subagents = deepagents_patch_review_subagents() if subagents is None else subagents
    agent_files = _agent_files(
        files,
        subagents_enabled=bool(configured_subagents),
    )

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
        system_prompt=deepagents_system_prompt(
            subagents_enabled=bool(configured_subagents),
        ),
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
        if deepagents_encrypted_reasoning_enabled(config):
            model_kwargs["include"] = ["reasoning.encrypted_content"]
    if config.reasoning_effort:
        model_kwargs["reasoning_effort"] = config.reasoning_effort
    callbacks = _resource_budget_callbacks(config)
    if callbacks:
        model_kwargs["callbacks"] = callbacks
    return model_kwargs


def _resource_budget_callbacks(config: DeepAgentsPlannerConfig) -> list[Any]:
    if config.max_model_responses is None and config.max_model_tokens is None:
        return []
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except ImportError:
        return []

    class ResourceBudgetCallback(BaseCallbackHandler):
        raise_error = True

        def __init__(self) -> None:
            self.response_count = 0
            self.input_tokens = 0
            self.output_tokens = 0
            self.total_tokens = 0

        def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
            self._before_model_response()

        def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
            self._before_model_response()

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            token_usage = _llm_result_token_usage(response)
            if token_usage.input_tokens is not None:
                self.input_tokens += token_usage.input_tokens
            if token_usage.output_tokens is not None:
                self.output_tokens += token_usage.output_tokens
            if token_usage.total_tokens is not None:
                self.total_tokens += token_usage.total_tokens
            elif token_usage.input_tokens is not None or token_usage.output_tokens is not None:
                self.total_tokens += (token_usage.input_tokens or 0) + (
                    token_usage.output_tokens or 0
                )
            if config.max_model_tokens is not None and self.total_tokens > config.max_model_tokens:
                raise DeepAgentsResourceBudgetExceeded(
                    "DeepAgents model token budget exceeded: "
                    f"{self.total_tokens} > {config.max_model_tokens}",
                    response_count=self.response_count,
                    input_tokens=self.input_tokens or None,
                    output_tokens=self.output_tokens or None,
                    total_tokens=self.total_tokens,
                )

        def _before_model_response(self) -> None:
            if (
                config.max_model_responses is not None
                and self.response_count >= config.max_model_responses
            ):
                raise DeepAgentsResourceBudgetExceeded(
                    "DeepAgents model response budget exhausted before next call: "
                    f"{self.response_count} >= {config.max_model_responses}",
                    response_count=self.response_count,
                    input_tokens=self.input_tokens or None,
                    output_tokens=self.output_tokens or None,
                    total_tokens=self.total_tokens or None,
                )
            self.response_count += 1

    return [ResourceBudgetCallback()]


def _llm_result_token_usage(response: Any) -> _TokenUsage:
    usage = getattr(response, "llm_output", None)
    if isinstance(usage, dict):
        token_usage = usage.get("token_usage")
        if isinstance(token_usage, dict):
            parsed = _token_usage_from_mapping(token_usage)
            if parsed != _TokenUsage():
                return parsed
    generations = getattr(response, "generations", None)
    if not isinstance(generations, list):
        return _TokenUsage()
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    saw_input = False
    saw_output = False
    saw_usage = False
    for generation_group in generations:
        if not isinstance(generation_group, list):
            continue
        for generation in generation_group:
            message = getattr(generation, "message", None)
            usage_metadata = getattr(message, "usage_metadata", None)
            if isinstance(usage_metadata, dict):
                parsed = _token_usage_from_mapping(usage_metadata)
                if parsed.input_tokens is not None:
                    input_tokens += parsed.input_tokens
                    saw_input = True
                if parsed.output_tokens is not None:
                    output_tokens += parsed.output_tokens
                    saw_output = True
                if parsed.total_tokens is not None:
                    total_tokens += parsed.total_tokens
                    saw_usage = True
    return _TokenUsage(
        input_tokens=input_tokens if saw_input else None,
        output_tokens=output_tokens if saw_output else None,
        total_tokens=total_tokens if saw_usage else None,
    )


def _token_usage_from_mapping(usage: dict[Any, Any]) -> _TokenUsage:
    input_tokens = _optional_int(usage.get("input_tokens"))
    if input_tokens is None:
        input_tokens = _optional_int(usage.get("prompt_tokens"))
    output_tokens = _optional_int(usage.get("output_tokens"))
    if output_tokens is None:
        output_tokens = _optional_int(usage.get("completion_tokens"))
    total_tokens = _optional_int(usage.get("total_tokens"))
    return _TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
