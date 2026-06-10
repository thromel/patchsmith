from __future__ import annotations

import shlex
from pathlib import Path

from patchsmith.models import CommandPolicyDecision

ALLOWED_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("pytest",),
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
    ("ruff",),
    ("mypy",),
    ("npm", "test"),
    ("pnpm", "test"),
)

BLOCKED_FRAGMENTS = (
    "&&",
    ";",
    "|",
    "`",
    "$(",
    "\n",
    ">",
    "<",
    "curl",
    "wget",
    "ssh",
    "scp",
    "sudo",
    "docker",
    "printenv",
    "/etc/passwd",
    ".ssh",
)


class CommandPolicy:
    """Conservative command allowlist for development and test runs."""

    def evaluate(self, command: str, *, workspace: Path) -> CommandPolicyDecision:
        stripped = command.strip()
        if not stripped:
            return CommandPolicyDecision(False, "empty command")

        lower_command = stripped.lower()
        for fragment in BLOCKED_FRAGMENTS:
            if fragment in lower_command:
                return CommandPolicyDecision(False, f"blocked command fragment: {fragment}")

        try:
            tokens = tuple(shlex.split(stripped))
        except ValueError as error:
            return CommandPolicyDecision(False, f"could not parse command: {error}")

        if not tokens:
            return CommandPolicyDecision(False, "empty command")

        if not _has_allowed_prefix(tokens):
            return CommandPolicyDecision(False, f"command is not allowlisted: {tokens[0]}")

        workspace = workspace.resolve()
        for token in tokens[1:]:
            path_decision = _validate_path_token(token, workspace)
            if path_decision:
                return path_decision

        return CommandPolicyDecision(True, "allowed", tokens)


class FocusedSetupCommandPolicy(CommandPolicy):
    """Command policy for dependency setup inside explicit disposable sandboxes."""

    def evaluate(self, command: str, *, workspace: Path) -> CommandPolicyDecision:
        stripped = command.strip()
        if not stripped:
            return CommandPolicyDecision(False, "empty command")

        lower_command = stripped.lower()
        for fragment in BLOCKED_FRAGMENTS:
            if fragment in lower_command:
                return CommandPolicyDecision(False, f"blocked command fragment: {fragment}")

        try:
            tokens = tuple(shlex.split(stripped))
        except ValueError as error:
            return CommandPolicyDecision(False, f"could not parse command: {error}")

        if _is_allowed_editable_setup_install(tokens):
            return CommandPolicyDecision(
                True,
                "allowed focused setup editable install",
                tokens,
            )

        return super().evaluate(command, workspace=workspace)


def _is_allowed_editable_setup_install(tokens: tuple[str, ...]) -> bool:
    editable_project_install = (
        len(tokens) == 6
        and tokens[0] in {"python", "python3"}
        and tokens[1:5] == ("-m", "pip", "install", "-e")
        and tokens[5] in {".", ".[test]"}
    )
    editable_project_dependency_group_install = (
        len(tokens) == 8
        and tokens[0] in {"python", "python3"}
        and tokens[1:5] == ("-m", "pip", "install", "-e")
        and tokens[5] == "."
        and tokens[6:] == ("--group", "test")
    )
    return editable_project_install or editable_project_dependency_group_install


def _has_allowed_prefix(tokens: tuple[str, ...]) -> bool:
    for prefix in ALLOWED_PREFIXES:
        if len(tokens) >= len(prefix) and tokens[: len(prefix)] == prefix:
            return True
    return False


def _validate_path_token(token: str, workspace: Path) -> CommandPolicyDecision | None:
    if token in {"..", "."}:
        return CommandPolicyDecision(False, f"unsafe path token: {token}")
    if token.startswith("../") or "/../" in token or token.endswith("/.."):
        return CommandPolicyDecision(False, f"path traversal is not allowed: {token}")

    token_path = Path(token)
    if token_path.is_absolute():
        try:
            token_path.resolve().relative_to(workspace)
        except ValueError:
            return CommandPolicyDecision(False, f"absolute path outside workspace: {token}")
    return None
