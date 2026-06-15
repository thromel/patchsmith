from __future__ import annotations

from dataclasses import dataclass

from patchsmith.agent_cli import AgentCliConfig


@dataclass(frozen=True)
class AgentPermissionState:
    repo: str
    apply_after_run: bool
    allow_dirty_apply: bool
    sandbox_mode: str
    test_command: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "apply_after_run": self.apply_after_run,
            "allow_dirty_apply": self.allow_dirty_apply,
            "sandbox_mode": self.sandbox_mode,
            "test_command": self.test_command,
        }


def permission_state(config: AgentCliConfig) -> AgentPermissionState:
    return AgentPermissionState(
        repo=config.repo,
        apply_after_run=config.apply,
        allow_dirty_apply=config.allow_dirty_apply,
        sandbox_mode=config.sandbox_mode,
        test_command=config.test_command,
    )


def format_permissions(config: AgentCliConfig) -> str:
    state = permission_state(config)
    lines = [
        "Permissions:",
        f"- Apply after run: {_mode_label(state.apply_after_run, enabled='auto', disabled='manual')}",
        f"- Dirty apply: {_mode_label(state.allow_dirty_apply, enabled='allowed', disabled='denied')}",
        "- Explicit /apply: uses the same dirty-worktree policy",
        f"- Sandbox mode: {state.sandbox_mode}",
        f"- Test command: {state.test_command or 'none'}",
    ]
    return "\n".join(lines)


def _mode_label(value: bool, *, enabled: str, disabled: str) -> str:
    return enabled if value else disabled
