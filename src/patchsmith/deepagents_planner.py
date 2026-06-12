from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from patchsmith.deepagents_contract import (
    combine_plan_metadata,
    deepagents_planning_contract,
)
from patchsmith.deepagents_files import (
    _agent_files,
    _context_files,
    _read_only_filesystem_permissions,
    _repo_path_from_agent_path,
)
from patchsmith.deepagents_metadata import _metadata_from_result
from patchsmith.deepagents_payloads import (
    _last_ai_text,
    _normalize_patch_payload,
    _structured_payload,
)
from patchsmith.deepagents_prompts import (
    PATCHSMITH_DEEPAGENTS_MEMORY_PATH,
    PATCHSMITH_DEEPAGENTS_SKILL_DIR,
    deepagents_patch_review_subagents,
    deepagents_planner_prompt,
    deepagents_system_prompt,
)
from patchsmith.deepagents_schema import PatchPlan
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, configured_model_pricing
from patchsmith.models import RetrievedContext
from patchsmith.planning import (
    ModelCallMetadata,
    RepairPlan,
    _extract_json_object,
    _repair_plan_from_payload,
)

DEFAULT_DEEPAGENTS_MODEL = DEFAULT_OPENAI_MODEL
DEFAULT_DEEPAGENTS_MAX_FILE_CHARS = 20_000
DEEPAGENTS_PROVIDER = "deepagents_openai_chat"


@dataclass(frozen=True)
class DeepAgentsPlannerConfig:
    model: str = DEFAULT_DEEPAGENTS_MODEL
    max_output_tokens: int = 3200
    max_file_chars: int = DEFAULT_DEEPAGENTS_MAX_FILE_CHARS
    reasoning_effort: str | None = None
    use_responses_api: bool = True
    store: bool = False
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None


class DeepAgentsRepairPlanner:
    """Native DeepAgents planner that still returns a bounded PatchSmith edit.

    DeepAgents gets the planning/scaffold responsibility: todo management,
    state-backed file reads, and a patch-review subagent. PatchSmith keeps the
    final safety boundary by accepting only one retrieval-bound text replacement.
    """

    def __init__(
        self,
        config: DeepAgentsPlannerConfig | None = None,
        *,
        agent_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or DeepAgentsPlannerConfig()
        self.agent_factory = agent_factory
        self.last_model_metadata: ModelCallMetadata | None = None
        self.last_plan_metadata: dict[str, Any] | None = None
        self._repo_path: Path | None = None

    def prepare_task(self, task: Any) -> None:
        repo_path = getattr(task, "repo_path", None)
        self._repo_path = Path(repo_path) if repo_path else None

    def plan_for_task(self, *, task: Any) -> RepairPlan | None:
        repo_path = getattr(task, "repo_path", None)
        return self._plan_with_repo_path(
            issue_text=str(getattr(task, "issue_text", "")),
            retrieved_context=list(getattr(task, "retrieved_context", [])),
            repo_path=Path(repo_path) if repo_path else None,
        )

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        agent_factory: Callable[..., Any] | None = None,
    ) -> DeepAgentsRepairPlanner:
        env = os.environ if environ is None else environ
        model = (
            env.get("PATCHSMITH_DEEPAGENTS_MODEL")
            or env.get("PATCHSMITH_OPENAI_MODEL")
            or DEFAULT_DEEPAGENTS_MODEL
        ).strip()
        model = model or DEFAULT_DEEPAGENTS_MODEL
        pricing = configured_model_pricing(
            env=env,
            model=model,
            input_key="PATCHSMITH_DEEPAGENTS_INPUT_COST_PER_1M",
            output_key="PATCHSMITH_DEEPAGENTS_OUTPUT_COST_PER_1M",
            input_fallback_key="PATCHSMITH_OPENAI_INPUT_COST_PER_1M",
            output_fallback_key="PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M",
        )
        return cls(
            DeepAgentsPlannerConfig(
                model=model,
                max_output_tokens=_int_env(env, "PATCHSMITH_DEEPAGENTS_MAX_OUTPUT_TOKENS", 3200),
                max_file_chars=_int_env(
                    env,
                    "PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS",
                    DEFAULT_DEEPAGENTS_MAX_FILE_CHARS,
                ),
                reasoning_effort=env.get("PATCHSMITH_DEEPAGENTS_REASONING_EFFORT", "").strip()
                or None,
                use_responses_api=_bool_env(
                    env,
                    "PATCHSMITH_DEEPAGENTS_USE_RESPONSES_API",
                    True,
                ),
                store=_bool_env(env, "PATCHSMITH_DEEPAGENTS_STORE", False),
                input_cost_per_1m=pricing.input_cost_per_1m if pricing else None,
                output_cost_per_1m=pricing.output_cost_per_1m if pricing else None,
            ),
            agent_factory=agent_factory,
        )

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        return self._plan_with_repo_path(
            issue_text=issue_text,
            retrieved_context=retrieved_context,
            repo_path=self._repo_path,
        )

    def _plan_with_repo_path(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
        repo_path: Path | None,
    ) -> RepairPlan | None:
        self.last_model_metadata = None
        self.last_plan_metadata = None
        if not retrieved_context:
            return None

        files, virtual_to_repo = _context_files(
            retrieved_context,
            repo_path=repo_path,
            max_file_chars=self.config.max_file_chars,
        )
        agent_files = _agent_files(files)
        subagents = deepagents_patch_review_subagents()
        contract = deepagents_planning_contract(
            config=self.config,
            virtual_file_paths=files.keys(),
            subagents=subagents,
            custom_agent_factory=self.agent_factory is not None,
        )
        self.last_plan_metadata = combine_plan_metadata(
            model_call=None,
            deepagents_contract=contract,
        )
        agent = self._build_agent(files=files, subagents=subagents)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": deepagents_planner_prompt(issue_text, virtual_to_repo),
                    }
                ],
                "files": agent_files,
            }
        )
        metadata = _metadata_from_result(
            result=result,
            provider=DEEPAGENTS_PROVIDER,
            configured_model=self.config.model,
            input_cost_per_1m=self.config.input_cost_per_1m,
            output_cost_per_1m=self.config.output_cost_per_1m,
        )
        self.last_model_metadata = metadata
        self.last_plan_metadata = combine_plan_metadata(
            model_call=metadata.to_dict(),
            deepagents_contract=contract,
        )

        payload = _structured_payload(result) or _extract_json_object(_last_ai_text(result))
        if payload is None:
            return None
        path = payload.get("path")
        if isinstance(path, str):
            virtual_path = "/" + path.strip().lstrip("/")
            payload = _normalize_patch_payload({**payload, "path": virtual_path}, files)
            payload = {**payload, "path": _repo_path_from_agent_path(virtual_path, virtual_to_repo)}
        return _repair_plan_from_payload(
            payload=payload,
            allowed_paths={context.path for context in retrieved_context},
            default_name="deepagents_native_json_plan",
            model_metadata=metadata,
            extra_metadata={"deepagents_contract": contract},
        )

    def _build_agent(
        self,
        *,
        files: dict[str, dict[str, str]],
        subagents: list[dict[str, str]] | None = None,
    ) -> Any:
        if self.agent_factory is not None:
            return self.agent_factory(config=self.config)
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

        model_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "use_responses_api": self.config.use_responses_api,
            "max_completion_tokens": self.config.max_output_tokens,
        }
        if self.config.use_responses_api:
            model_kwargs["store"] = self.config.store
            model_kwargs["include"] = ["reasoning.encrypted_content"]
        if self.config.reasoning_effort:
            model_kwargs["reasoning_effort"] = self.config.reasoning_effort
        model = ChatOpenAI(**model_kwargs)
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


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, str(default)))
    except ValueError:
        return default


def _bool_env(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
