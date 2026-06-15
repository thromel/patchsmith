from __future__ import annotations

from dataclasses import dataclass

PLAN_STATUSES = ("pending", "in_progress", "completed", "blocked", "skipped")


@dataclass(frozen=True)
class AgentPlanItem:
    text: str
    status: str = "pending"

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "status": self.status}


def plan_items_from_payload(value: object) -> list[AgentPlanItem]:
    if not isinstance(value, list):
        return []
    items: list[AgentPlanItem] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        status = item.get("status")
        if not isinstance(text, str) or not text.strip():
            continue
        items.append(
            AgentPlanItem(
                text=text.strip(),
                status=status if isinstance(status, str) and status in PLAN_STATUSES else "pending",
            )
        )
    return items


def plan_items_payload(items: list[AgentPlanItem]) -> list[dict[str, object]]:
    return [item.to_dict() for item in items]


def parse_plan_items(raw: str) -> list[AgentPlanItem]:
    parts = raw.replace("|", ";").split(";")
    return [AgentPlanItem(text=part.strip()) for part in parts if part.strip()]


def update_plan_item_status(
    items: list[AgentPlanItem],
    *,
    index: int,
    status: str,
) -> list[AgentPlanItem]:
    if status not in PLAN_STATUSES:
        raise ValueError(f"unsupported plan status: {status}")
    if index < 1 or index > len(items):
        raise IndexError(index)
    updated = list(items)
    updated[index - 1] = AgentPlanItem(text=updated[index - 1].text, status=status)
    return updated


def format_agent_plan(items: list[AgentPlanItem]) -> str:
    if not items:
        return "No session plan items."
    lines = [
        "Session plan:",
        "Index | Status | Task",
        "---: | --- | ---",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index} | {item.status} | {item.text}")
    return "\n".join(lines)


def agent_plan_context(items: list[AgentPlanItem]) -> str:
    if not items:
        return ""
    lines = [
        "PatchSmith session plan",
        "Use this transcripted plan as task context. Keep updates explicit with /plan; "
        "do not treat it as permission to bypass PatchSmith validation or apply policy.",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. [{item.status}] {item.text}")
    return "\n".join(lines)
