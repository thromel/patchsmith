from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from patchsmith.agent_apply import AgentApplyResult
from patchsmith.chat.state import AgentChatRuntime


class ChatEventRecorder(Protocol):
    def __call__(
        self,
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
    ) -> None: ...


class ChatHookRunner(Protocol):
    def __call__(
        self,
        *,
        runtime: AgentChatRuntime,
        event: str,
        payload: dict[str, object],
        output_stream: TextIO,
        blocking: bool,
    ) -> bool: ...


class RunTaskHandler(Protocol):
    def __call__(
        self,
        *,
        runtime: AgentChatRuntime,
        task: str,
        output_stream: TextIO,
    ) -> None: ...


class ApplyDiff(Protocol):
    def __call__(
        self,
        *,
        repo: str,
        diff_path: Path,
        allow_dirty: bool = False,
    ) -> AgentApplyResult: ...


class ReverseDiff(Protocol):
    def __call__(
        self,
        *,
        repo: str,
        diff_path: Path,
    ) -> AgentApplyResult: ...


@dataclass(frozen=True)
class ChatCommandContext:
    record: ChatEventRecorder
    run_hooks: ChatHookRunner | None = None
    apply_agent_run_diff: ApplyDiff | None = None
    check_agent_run_diff: ApplyDiff | None = None
    reverse_agent_run_diff: ReverseDiff | None = None
    run_task: RunTaskHandler | None = None


class ChatCommandHandler(Protocol):
    def __call__(
        self,
        *,
        runtime: AgentChatRuntime,
        argument: str,
        output_stream: TextIO,
        context: ChatCommandContext,
    ) -> None: ...


@dataclass(frozen=True)
class ChatCommand:
    name: str
    handler: ChatCommandHandler
    aliases: tuple[str, ...] = ()
    usage: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


def build_command_registry(
    commands: Iterable[ChatCommand],
) -> dict[str, ChatCommand]:
    registry: dict[str, ChatCommand] = {}
    for command in commands:
        for name in command.names:
            key = name.strip().lower()
            if not key:
                raise ValueError("chat command names cannot be empty")
            if key in registry:
                raise ValueError(f"duplicate chat command: {key}")
            registry[key] = command
    return registry
