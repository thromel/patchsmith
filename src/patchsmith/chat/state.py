from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.agent_cli import AgentCliConfig
from patchsmith.agent_plan import AgentPlanItem
from patchsmith.models import RepairRunResult


@dataclass(frozen=True)
class AgentChatState:
    session_id: str
    transcript_path: Path
    config: AgentCliConfig


@dataclass
class AgentChatRuntime:
    state: AgentChatState
    chat_mode: str = "act"
    pending_planned_task: str | None = None
    last_task: str | None = None
    last_run: RepairRunResult | None = None
    last_run_payload: dict[str, object] | None = None
    last_apply: AgentApplyResult | None = None
    last_rewind: AgentApplyResult | None = None
    compaction_summary: dict[str, object] | None = None
    history: list[str] | None = None
    plan_items: list[AgentPlanItem] | None = None
    feedback_items: list[str] | None = None

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []
        if self.plan_items is None:
            self.plan_items = []
        if self.feedback_items is None:
            self.feedback_items = []
