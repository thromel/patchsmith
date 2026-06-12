from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol

from patchsmith.model_clients import (
    OPENAI_RESPONSES_ENDPOINT,
    ModelCallMetadata,
    ModelClient,
    ModelClientError,
    ModelCompletion,
    OpenAIResponsesModelClient,
    StaticResponseModelClient,
    repair_plan_json_schema,
)
from patchsmith.models import RetrievedContext

__all__ = [
    "HEURISTIC_RULES",
    "OPENAI_RESPONSES_ENDPOINT",
    "HeuristicRepairPlanner",
    "HeuristicRule",
    "ModelBackedRepairPlanner",
    "ModelCallMetadata",
    "ModelClient",
    "ModelClientError",
    "ModelCompletion",
    "OpenAIResponsesModelClient",
    "RepairPlan",
    "RepairPlanner",
    "SeededFakeRepairModelClient",
    "StaticResponseModelClient",
    "repair_plan_json_schema",
]


@dataclass(frozen=True)
class RepairPlan:
    name: str
    path: str
    old: str
    new: str
    summary: str
    metadata: dict[str, Any] | None = None


class RepairPlanner(Protocol):
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        """Produce one bounded edit plan from issue text and retrieved context."""


class ModelBackedRepairPlanner:
    """Prompt/JSON repair planner with retrieval-bound output validation."""

    def __init__(
        self,
        model_client: ModelClient,
        *,
        name: str = "model_json_plan",
        max_contexts: int = 5,
        max_excerpt_chars: int = 1200,
    ) -> None:
        self.model_client = model_client
        self.name = name
        self.max_contexts = max_contexts
        self.max_excerpt_chars = max_excerpt_chars
        self.last_model_metadata: ModelCallMetadata | None = None

    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        self.last_model_metadata = None
        prompt = self._build_prompt(issue_text=issue_text, retrieved_context=retrieved_context)
        response = self.model_client.complete(prompt)
        self.last_model_metadata = response.metadata
        payload = _extract_json_object(response.text)
        if payload is None:
            return None
        return _repair_plan_from_payload(
            payload=payload,
            allowed_paths={context.path for context in retrieved_context},
            default_name=self.name,
            model_metadata=response.metadata,
        )

    def _build_prompt(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> str:
        lines = [
            "You are PatchSmith's repair planner.",
            "Return only one JSON object with string fields: path, old, new, summary.",
            "The path must be one of the retrieved source paths.",
            "The old field must be the exact text to replace and must not be empty.",
            "",
            "Issue:",
            issue_text.strip(),
            "",
            "Retrieved context:",
        ]
        for index, context in enumerate(retrieved_context[: self.max_contexts], start=1):
            excerpt = context.excerpt[: self.max_excerpt_chars]
            lines.extend(
                [
                    f"Context {index}",
                    f"Path: {context.path}",
                    f"Method: {context.method}",
                    "Excerpt:",
                    excerpt,
                    "",
                ]
            )
        return "\n".join(lines)


class HeuristicRepairPlanner:
    def plan(
        self,
        *,
        issue_text: str,
        retrieved_context: list[RetrievedContext],
    ) -> RepairPlan | None:
        issue = issue_text.lower()
        candidate_paths = [context.path for context in retrieved_context]

        for rule in HEURISTIC_RULES:
            if not rule.matches(issue):
                continue
            for path in candidate_paths:
                if not path.startswith("src/"):
                    continue
                return RepairPlan(
                    name=rule.name,
                    path=path,
                    old=rule.old,
                    new=rule.new,
                    summary=f"Apply heuristic rule `{rule.name}` to {path}.",
                )
        return None


@dataclass(frozen=True)
class HeuristicRule:
    name: str
    triggers: tuple[str, ...]
    old: str
    new: str

    def matches(self, issue: str) -> bool:
        return all(trigger in issue for trigger in self.triggers)


HEURISTIC_RULES: tuple[HeuristicRule, ...] = (
    HeuristicRule(
        name="addition_operator",
        triggers=("add", "wrong result"),
        old="return left - right",
        new="return left + right",
    ),
    HeuristicRule(
        name="missing_re_import",
        triggers=("slugify", "nameerror"),
        old="def slugify(value: str) -> str:\n",
        new="import re\n\n\ndef slugify(value: str) -> str:\n",
    ),
    HeuristicRule(
        name="moving_average_exact_window",
        triggers=("moving_average", "exact-window"),
        old="if len(values) <= window:",
        new="if len(values) < window:",
    ),
    HeuristicRule(
        name="integer_timeout_default",
        triggers=("default timeout", "wrong type"),
        old='DEFAULT_TIMEOUT_SECONDS = "30"',
        new="DEFAULT_TIMEOUT_SECONDS = 30",
    ),
    HeuristicRule(
        name="even_validator",
        triggers=("is_even", "opposite"),
        old="return value % 2 == 1",
        new="return value % 2 == 0",
    ),
    HeuristicRule(
        name="username_lowercase",
        triggers=("normalize_username", "uppercase"),
        old='return value.strip().replace(" ", "_")',
        new='return value.strip().lower().replace(" ", "_")',
    ),
    HeuristicRule(
        name="csv_ignore_empty_cells",
        triggers=("parse_csv_line", "empty cells"),
        old='return [part.strip() for part in line.split(",")]',
        new='return [part.strip() for part in line.split(",") if part.strip()]',
    ),
    HeuristicRule(
        name="gregorian_leap_year",
        triggers=("leap-year", "century"),
        old="return year % 4 == 0",
        new="return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)",
    ),
    HeuristicRule(
        name="unique_preserve_order",
        triggers=("unique_preserve_order", "preserving input order"),
        old="return sorted(set(values))",
        new="return list(dict.fromkeys(values))",
    ),
    HeuristicRule(
        name="format_cents_padding",
        triggers=("format_cents", "trailing cents"),
        old='return f"${dollars}.{remainder}"',
        new='return f"${dollars}.{remainder:02d}"',
    ),
)


class SeededFakeRepairModelClient:
    """Offline model double for seeded evals.

    It consumes the same prompt shape as a real model planner and emits the
    JSON contract that `ModelBackedRepairPlanner` validates. This keeps local
    evals deterministic and credential-free while exercising the model seam.
    """

    def complete(self, prompt: str) -> ModelCompletion:
        issue_and_context = prompt.lower()
        path = _first_retrieved_source_path(prompt)
        if path is None:
            return _fake_completion("{}")

        for rule in HEURISTIC_RULES:
            if rule.matches(issue_and_context):
                return _fake_completion(
                    json.dumps(
                        {
                            "name": f"fake_model_{rule.name}",
                            "path": path,
                            "old": rule.old,
                            "new": rule.new,
                            "summary": f"Offline fake model selected {rule.name} for {path}.",
                        }
                    )
                )
        return _fake_completion("{}")


def _extract_json_object(response: str) -> dict[str, Any] | None:
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _repair_plan_from_payload(
    *,
    payload: dict[str, Any],
    allowed_paths: set[str],
    default_name: str,
    model_metadata: ModelCallMetadata | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> RepairPlan | None:
    path = payload.get("path")
    old = payload.get("old")
    new = payload.get("new")
    summary = payload.get("summary")
    name = payload.get("name", default_name)
    if (
        not isinstance(path, str)
        or not isinstance(old, str)
        or not isinstance(new, str)
        or not isinstance(summary, str)
        or not isinstance(name, str)
    ):
        return None

    path = path.strip()
    if not path or not old.strip():
        return None
    if _unsafe_plan_path(path) or path not in allowed_paths:
        return None

    metadata: dict[str, Any] = {}
    if model_metadata:
        metadata["model_call"] = model_metadata.to_dict()
    if extra_metadata:
        metadata.update(dict(extra_metadata))

    return RepairPlan(
        name=name.strip() or default_name,
        path=path,
        old=old,
        new=new,
        summary=summary.strip() or f"Model planner selected {path}.",
        metadata=metadata or None,
    )


def _unsafe_plan_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.startswith("/") or "\\" in path or ".." in parts or path in {"", "."}


def _first_retrieved_source_path(prompt: str) -> str | None:
    paths = re.findall(r"^Path:\s*(\S+)\s*$", prompt, flags=re.MULTILINE)
    for path in paths:
        if path.startswith(("src/", "lib/", "patchsmith/")):
            return path
    return paths[0] if paths else None


def _fake_completion(text: str) -> ModelCompletion:
    return ModelCompletion(
        text=text,
        metadata=ModelCallMetadata(
            provider="offline_fake_model",
            model="seeded_repair_rules",
            estimated_cost_usd=0.0,
            status="completed",
        ),
    )
