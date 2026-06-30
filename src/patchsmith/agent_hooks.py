from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HOOK_CONFIG_PATH = ".patchsmith/hooks.json"
DEFAULT_HOOK_TIMEOUT_SECONDS = 30.0
_OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{20,}")


@dataclass(frozen=True)
class AgentHook:
    event: str
    command: str
    matcher: str
    name: str
    timeout_seconds: float
    path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "name": self.name,
            "matcher": self.matcher,
            "command": self.command,
            "timeout_seconds": self.timeout_seconds,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class AgentHookRun:
    hook: AgentHook
    status: str
    exit_code: int | None
    reason: str | None
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, object]:
        return {
            "hook": self.hook.to_dict(),
            "status": self.status,
            "exit_code": self.exit_code,
            "reason": self.reason,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class AgentHookResult:
    event: str
    status: str
    runs: list[AgentHookRun]

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def block_reason(self) -> str | None:
        for run in self.runs:
            if run.status == "blocked":
                return run.reason or f"{run.hook.name} blocked {self.event}"
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "status": self.status,
            "runs": [run.to_dict() for run in self.runs],
        }


def list_agent_hooks(repo: str) -> list[AgentHook]:
    config_path = _hook_config_path(repo)
    if config_path is None:
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    hooks_payload = payload.get("hooks", payload)
    if not isinstance(hooks_payload, dict):
        return []
    hooks: list[AgentHook] = []
    for raw_event, raw_entries in hooks_payload.items():
        if not isinstance(raw_event, str):
            continue
        event = raw_event.strip()
        if not event:
            continue
        entries = raw_entries if isinstance(raw_entries, list) else [raw_entries]
        for index, entry in enumerate(entries, start=1):
            hook = _hook_from_entry(
                event=event,
                entry=entry,
                index=index,
                path=config_path,
            )
            if hook is not None:
                hooks.append(hook)
    return hooks


def run_agent_hooks(
    *,
    repo: str,
    event: str,
    payload: dict[str, object],
) -> AgentHookResult:
    target = _matcher_target(payload)
    runs: list[AgentHookRun] = []
    for hook in list_agent_hooks(repo):
        if hook.event != event or not _matches_hook(hook.matcher, target):
            continue
        run = _run_hook(repo=repo, hook=hook, event=event, payload=payload)
        runs.append(run)
        if run.status == "blocked":
            return AgentHookResult(event=event, status="blocked", runs=runs)
    status = "passed" if runs else "skipped"
    return AgentHookResult(event=event, status=status, runs=runs)


def format_agent_hooks(hooks: list[AgentHook]) -> str:
    if not hooks:
        return "No project hooks found."
    lines = ["Project hooks:"]
    for hook in hooks:
        matcher = hook.matcher or "*"
        lines.append(
            f"- {hook.event}: {hook.name} [{matcher}] "
            f"timeout={hook.timeout_seconds:g}s ({hook.path})"
        )
    return "\n".join(lines)


def agent_hooks_payload(hooks: list[AgentHook]) -> list[dict[str, object]]:
    return [hook.to_dict() for hook in hooks]


def _hook_config_path(repo: str) -> Path | None:
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir():
        return None
    config_path = repo_path / HOOK_CONFIG_PATH
    if not config_path.is_file():
        return None
    return config_path


def _hook_from_entry(
    *,
    event: str,
    entry: object,
    index: int,
    path: Path,
) -> AgentHook | None:
    if isinstance(entry, str):
        command = entry.strip()
        if not command:
            return None
        return AgentHook(
            event=event,
            command=command,
            matcher="",
            name=f"{event.lower()}-{index}",
            timeout_seconds=DEFAULT_HOOK_TIMEOUT_SECONDS,
            path=path,
        )
    if not isinstance(entry, dict):
        return None
    command = _entry_str(entry, "command")
    if not command:
        return None
    return AgentHook(
        event=event,
        command=command,
        matcher=_entry_str(entry, "matcher"),
        name=_entry_str(entry, "name") or f"{event.lower()}-{index}",
        timeout_seconds=_entry_timeout(entry),
        path=path,
    )


def _entry_str(entry: dict[Any, Any], key: str) -> str:
    value = entry.get(key)
    return value.strip() if isinstance(value, str) else ""


def _entry_timeout(entry: dict[Any, Any]) -> float:
    value = entry.get("timeout_seconds", entry.get("timeout"))
    if isinstance(value, bool):
        return DEFAULT_HOOK_TIMEOUT_SECONDS
    if isinstance(value, int | float) and value > 0:
        return float(value)
    return DEFAULT_HOOK_TIMEOUT_SECONDS


def _matches_hook(matcher: str, target: str) -> bool:
    if not matcher:
        return True
    try:
        return re.search(matcher, target, flags=re.IGNORECASE) is not None
    except re.error:
        return matcher.lower() in target.lower()


def _matcher_target(payload: dict[str, object]) -> str:
    for key in ("matcher_target", "task", "command", "status", "diff_path", "run_id"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(payload, sort_keys=True, default=str)


def _run_hook(
    *,
    repo: str,
    hook: AgentHook,
    event: str,
    payload: dict[str, object],
) -> AgentHookRun:
    hook_input = {
        "event": event,
        "repo": repo,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    try:
        argv = shlex.split(hook.command)
    except ValueError as error:
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=None,
            reason=f"could not parse hook command: {error}",
            stdout="",
            stderr="",
        )
    if not argv:
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=None,
            reason="empty hook command",
            stdout="",
            stderr="",
        )
    try:
        # shell=False: hook commands are run as an explicit argv list so that
        # shell metacharacters in repo-provided config cannot chain commands.
        process = subprocess.run(
            argv,
            cwd=Path(repo).expanduser(),
            input=json.dumps(hook_input, sort_keys=True),
            text=True,
            shell=False,
            capture_output=True,
            timeout=hook.timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=None,
            reason=f"hook command not found: {argv[0]}",
            stdout="",
            stderr="",
        )
    except subprocess.TimeoutExpired as exc:
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=None,
            reason=f"timed out after {hook.timeout_seconds:g}s",
            stdout=_safe_output(exc.stdout),
            stderr=_safe_output(exc.stderr),
        )
    stdout = _safe_output(process.stdout)
    stderr = _safe_output(process.stderr)
    decision, reason = _hook_decision(stdout)
    if process.returncode != 0:
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=process.returncode,
            reason=reason or stderr or f"hook exited {process.returncode}",
            stdout=stdout,
            stderr=stderr,
        )
    if decision == "blocked":
        return AgentHookRun(
            hook=hook,
            status="blocked",
            exit_code=process.returncode,
            reason=reason or f"{hook.name} blocked {event}",
            stdout=stdout,
            stderr=stderr,
        )
    return AgentHookRun(
        hook=hook,
        status="passed",
        exit_code=process.returncode,
        reason=reason,
        stdout=stdout,
        stderr=stderr,
    )


def _hook_decision(stdout: str) -> tuple[str, str | None]:
    payload = _stdout_json(stdout)
    if payload is None:
        return "passed", None
    raw_decision = payload.get("decision", payload.get("status"))
    decision = raw_decision.lower() if isinstance(raw_decision, str) else ""
    reason = payload.get("reason", payload.get("message"))
    if decision in {"block", "blocked", "fail", "failed"}:
        return "blocked", reason if isinstance(reason, str) else None
    return "passed", reason if isinstance(reason, str) else None


def _stdout_json(stdout: str) -> dict[str, object] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _safe_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    redacted = _OPENAI_KEY_PATTERN.sub("sk-REDACTED", text.strip())
    if len(redacted) <= 4000:
        return redacted
    return redacted[:4000] + "\n...<truncated>"
