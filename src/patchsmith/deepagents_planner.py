from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.deepagents_prompts import (
    deepagents_patch_review_subagents,
    deepagents_planner_prompt,
    deepagents_system_prompt,
)
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, configured_model_pricing
from patchsmith.models import RetrievedContext
from patchsmith.planning import (
    ModelCallMetadata,
    RepairPlan,
    _extract_json_object,
    _repair_plan_from_payload,
)

DEFAULT_DEEPAGENTS_MODEL = DEFAULT_OPENAI_MODEL
DEEPAGENTS_PROVIDER = "deepagents_openai_chat"


@dataclass(frozen=True)
class DeepAgentsPlannerConfig:
    model: str = DEFAULT_DEEPAGENTS_MODEL
    max_output_tokens: int = 3200
    max_file_chars: int = 40_000
    reasoning_effort: str | None = None
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
        self._repo_path: Path | None = None

    def prepare_task(self, task: Any) -> None:
        repo_path = getattr(task, "repo_path", None)
        self._repo_path = Path(repo_path) if repo_path else None

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
                max_file_chars=_int_env(env, "PATCHSMITH_DEEPAGENTS_MAX_FILE_CHARS", 40_000),
                reasoning_effort=env.get("PATCHSMITH_DEEPAGENTS_REASONING_EFFORT", "").strip()
                or None,
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
        self.last_model_metadata = None
        if not retrieved_context:
            return None

        files, virtual_to_repo = _context_files(
            retrieved_context,
            repo_path=self._repo_path,
            max_file_chars=self.config.max_file_chars,
        )
        agent = self._build_agent(files=files)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": deepagents_planner_prompt(issue_text, virtual_to_repo),
                    }
                ],
                "files": files,
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
        )

    def _build_agent(self, *, files: dict[str, dict[str, str]]) -> Any:
        if self.agent_factory is not None:
            return self.agent_factory(config=self.config)

        try:
            from deepagents import FilesystemPermission, create_deep_agent
            from deepagents.backends import StateBackend
            from langchain_openai import ChatOpenAI
            from pydantic import BaseModel, Field
        except ImportError as error:
            raise RuntimeError(
                "DeepAgents native planner requires the `deepagents` extra: "
                'install with `python -m pip install -e ".[deepagents]"`.'
            ) from error

        class PatchPlan(BaseModel):
            path: str = Field(description="One provided repository path.")
            old: str = Field(description="Exact text span to replace.")
            new: str = Field(description="Replacement text.")
            summary: str = Field(description="Brief repair rationale.")

        model_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "use_responses_api": False,
            "max_completion_tokens": self.config.max_output_tokens,
        }
        if self.config.reasoning_effort:
            model_kwargs["reasoning_effort"] = self.config.reasoning_effort
        model = ChatOpenAI(**model_kwargs)
        return create_deep_agent(
            model=model,
            tools=[],
            system_prompt=deepagents_system_prompt(),
            subagents=deepagents_patch_review_subagents(),  # type: ignore[arg-type]
            backend=StateBackend(),
            permissions=_read_only_filesystem_permissions(
                files.keys(),
                permission_cls=FilesystemPermission,
            ),
            response_format=PatchPlan,
        )


def _context_files(
    retrieved_context: list[RetrievedContext],
    *,
    repo_path: Path | None = None,
    max_file_chars: int = 40_000,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    files: dict[str, dict[str, str]] = {}
    virtual_to_repo: dict[str, str] = {}
    for context in retrieved_context:
        virtual_path = "/" + context.path.lstrip("/")
        virtual_to_repo[virtual_path] = context.path
        content, modified_at = _context_file_content_and_timestamp(
            repo_path,
            context,
            max_file_chars=max_file_chars,
        )
        files[virtual_path] = {
            "content": content,
            "encoding": "utf-8",
            "created_at": modified_at,
            "modified_at": modified_at,
        }
    return files, virtual_to_repo


def _read_only_filesystem_permissions(
    paths: Iterable[str],
    *,
    permission_cls: Callable[..., Any],
) -> list[Any]:
    allowed_reads = sorted(
        {"/" + path.strip().lstrip("/") for path in paths if isinstance(path, str) and path.strip()}
    )
    return [
        permission_cls(operations=["read"], paths=allowed_reads, mode="allow"),
        permission_cls(operations=["read", "write"], paths=["/**"], mode="deny"),
    ]


def _context_file_content_and_timestamp(
    repo_path: Path | None,
    context: RetrievedContext,
    *,
    max_file_chars: int,
) -> tuple[str, str]:
    if repo_path is None:
        return _clean_context_excerpt(context.excerpt), _stable_timestamp()
    path = repo_path / context.path
    try:
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            return (
                _focused_file_content(content, context.excerpt, max_file_chars=max_file_chars),
                _path_modified_at(path),
            )
    except UnicodeDecodeError:
        pass
    return _clean_context_excerpt(context.excerpt), _stable_timestamp()


def _focused_file_content(content: str, excerpt: str, *, max_file_chars: int) -> str:
    if max_file_chars <= 0 or len(content) <= max_file_chars:
        return content
    cleaned_excerpt = _clean_context_excerpt(excerpt)
    if cleaned_excerpt.strip():
        return cleaned_excerpt[:max_file_chars]
    return content[:max_file_chars]


def _path_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _stable_timestamp() -> str:
    return "1970-01-01T00:00:00+00:00"


def _repo_path_from_agent_path(path: str, virtual_to_repo: dict[str, str]) -> str:
    normalized = "/" + path.strip().lstrip("/")
    return virtual_to_repo.get(normalized, normalized.lstrip("/"))


def _last_ai_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        if type(message).__name__ != "AIMessage":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content
    return ""


def _structured_payload(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    structured = result.get("structured_response")
    if structured is None:
        return None
    if isinstance(structured, dict):
        return structured
    model_dump = getattr(structured, "model_dump", None)
    if callable(model_dump):
        payload = model_dump()
        return payload if isinstance(payload, dict) else None
    return None


def _clean_context_excerpt(excerpt: str) -> str:
    lines = []
    for line in excerpt.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line))
    return "\n".join(lines)


def _normalize_patch_payload(
    payload: dict[str, Any],
    files: dict[str, dict[str, str]],
) -> dict[str, Any]:
    path = payload.get("path")
    old = payload.get("old")
    new = payload.get("new")
    if not isinstance(path, str) or not isinstance(old, str) or not isinstance(new, str):
        return payload
    content = files.get(path, {}).get("content")
    if not isinstance(content, str):
        return payload
    fallback: dict[str, Any] | None = None
    for old_candidate in [old, *_old_span_candidates(old)]:
        if old_candidate not in content:
            continue
        for new_candidate in [new, *_new_span_candidates(new)]:
            candidate_payload = {**payload, "old": old_candidate, "new": new_candidate}
            if not _requires_python_compile(path):
                return candidate_payload
            candidate_content = content.replace(old_candidate, new_candidate, 1)
            if _python_compiles(candidate_content, path):
                return candidate_payload
            if fallback is None:
                fallback = candidate_payload
    return fallback or payload


def _old_span_candidates(old: str) -> list[str]:
    candidates = [
        "\n".join(line.lstrip("\t") for line in old.splitlines()),
        "\n".join(re.sub(r"^\s*\d+\t", "", line) for line in old.splitlines()),
        _clean_context_excerpt(old),
    ]
    expanded = list(candidates)
    for candidate in candidates:
        expanded.append("\n".join(line.lstrip("\t") for line in candidate.splitlines()))
    return [candidate for candidate in dict.fromkeys(expanded) if candidate != old]


def _new_span_candidates(new: str) -> list[str]:
    candidates = [
        _clean_context_excerpt(new),
        "\n".join(re.sub(r"^\s*\d+\t", "", line) for line in new.splitlines()),
        "\n".join(line.lstrip("\t") for line in new.splitlines()),
        _strip_common_leading_tab(new),
    ]
    expanded = list(candidates)
    for candidate in candidates:
        expanded.append("\n".join(line.lstrip("\t") for line in candidate.splitlines()))
    return [candidate for candidate in dict.fromkeys(expanded) if candidate != new]


def _strip_common_leading_tab(text: str) -> str:
    lines = text.splitlines()
    nonblank = [line for line in lines if line.strip()]
    if not nonblank or not all(line.startswith("\t") for line in nonblank):
        return text
    return "\n".join(line[1:] if line.startswith("\t") else line for line in lines)


def _requires_python_compile(path: str) -> bool:
    return path.endswith(".py")


def _python_compiles(content: str, path: str) -> bool:
    try:
        compile(content, path, "exec")
    except SyntaxError:
        return False
    return True


def _metadata_from_result(
    *,
    result: Any,
    provider: str,
    configured_model: str,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> ModelCallMetadata:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    model = configured_model
    response_ids: list[str] = []
    saw_usage = False
    for message in messages:
        if type(message).__name__ != "AIMessage":
            continue
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            saw_usage = True
            input_tokens += _int_or_zero(usage.get("input_tokens"))
            output_tokens += _int_or_zero(usage.get("output_tokens"))
            total_tokens += _int_or_zero(usage.get("total_tokens"))
        response_metadata = getattr(message, "response_metadata", None)
        if isinstance(response_metadata, dict):
            model = str(response_metadata.get("model_name") or model)
            response_id = response_metadata.get("id")
            if isinstance(response_id, str) and response_id:
                response_ids.append(response_id)
    return ModelCallMetadata(
        provider=provider,
        model=model,
        response_id=",".join(response_ids) or None,
        input_tokens=input_tokens if saw_usage else None,
        output_tokens=output_tokens if saw_usage else None,
        total_tokens=total_tokens if saw_usage else None,
        estimated_cost_usd=(
            _estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_cost_per_1m=input_cost_per_1m,
                output_cost_per_1m=output_cost_per_1m,
            )
            if saw_usage
            else None
        ),
        status="completed" if messages else "missing_messages",
    )


def _estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> float | None:
    if input_cost_per_1m is None or output_cost_per_1m is None:
        return None
    return (input_tokens / 1_000_000 * input_cost_per_1m) + (
        output_tokens / 1_000_000 * output_cost_per_1m
    )


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, str(default)))
    except ValueError:
        return default


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0
