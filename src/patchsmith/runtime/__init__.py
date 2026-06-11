"""Agent runtime package; public API facade for the runtime adapters."""

from __future__ import annotations

from patchsmith.runtime.attempts import (
    emit_agent_result_trace,
    issue_with_test_feedback,
    run_sandbox_attempt,
    should_retry_with_test_feedback,
    test_feedback_retry_budget,
)
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
    "emit_agent_result_trace",
    "issue_with_test_feedback",
    "run_sandbox_attempt",
    "should_retry_with_test_feedback",
    "test_feedback_retry_budget",
]
