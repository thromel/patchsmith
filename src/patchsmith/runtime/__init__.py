"""Agent runtime package; public API facade for the runtime adapters.

Attempt orchestration helpers live in ``patchsmith.runtime.attempts``.
"""

from __future__ import annotations

from patchsmith.runtime.core import (
    AgentlessRuntime,
    AgentResult,
    AgentRuntime,
    AgentTask,
    HeuristicRuntime,
)
from patchsmith.runtime.deepagents import DeepAgentsRuntime
from patchsmith.runtime.langgraph import LangGraphRuntime
from patchsmith.runtime.openai_agents import OpenAIAgentsRuntime

__all__ = [
    "AgentResult",
    "AgentRuntime",
    "AgentTask",
    "AgentlessRuntime",
    "DeepAgentsRuntime",
    "HeuristicRuntime",
    "LangGraphRuntime",
    "OpenAIAgentsRuntime",
]
