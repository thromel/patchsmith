"""Structured response schema for native DeepAgents planning."""

from __future__ import annotations

from pydantic import BaseModel, Field

PATCH_PLAN_FIELDS = ("path", "old", "new", "summary")


class PatchPlan(BaseModel):
    """One bounded PatchSmith repair edit returned by DeepAgents."""

    path: str = Field(description="One provided repository path.")
    old: str = Field(description="Exact text span to replace.")
    new: str = Field(description="Replacement text.")
    summary: str = Field(description="Brief repair rationale.")


def patch_plan_response_schema() -> dict[str, object]:
    return {
        "name": PatchPlan.__name__,
        "fields": list(PATCH_PLAN_FIELDS),
        "all_fields_required": True,
    }
