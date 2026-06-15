from __future__ import annotations

from patchsmith.chat.commands import ChatCommand, build_command_registry
from patchsmith.chat.handlers.checkpoints import checkpoint_commands
from patchsmith.chat.handlers.context import context_commands
from patchsmith.chat.handlers.diff_apply import diff_apply_commands
from patchsmith.chat.handlers.execution import execution_commands
from patchsmith.chat.handlers.memory import memory_instruction_commands
from patchsmith.chat.handlers.model_budget import model_budget_commands
from patchsmith.chat.handlers.permissions import permission_commands
from patchsmith.chat.handlers.project import project_commands
from patchsmith.chat.handlers.session_evidence import session_evidence_commands
from patchsmith.chat.handlers.session_plan import plan_feedback_commands
from patchsmith.chat.handlers.session_state import session_state_commands
from patchsmith.chat.handlers.system import system_commands


def chat_commands() -> tuple[ChatCommand, ...]:
    return (
        *system_commands(),
        *memory_instruction_commands(),
        *context_commands(),
        *model_budget_commands(),
        *permission_commands(),
        *plan_feedback_commands(),
        *project_commands(),
        *session_evidence_commands(),
        *diff_apply_commands(),
        *execution_commands(),
        *checkpoint_commands(),
        *session_state_commands(),
    )


def chat_command_registry() -> dict[str, ChatCommand]:
    return build_command_registry(chat_commands())
