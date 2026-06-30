from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

# Upper bound for local git invocations so a hung git process cannot block a run
# indefinitely.
GIT_COMMAND_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class AgentApplyResult:
    status: str
    repo_path: str
    diff_path: str
    message: str
    applied: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def preflight_agent_apply_target(
    *,
    repo: str,
    allow_dirty: bool = False,
) -> AgentApplyResult:
    repo_path = Path(repo).expanduser().resolve()
    placeholder_diff_path = "<pending>"
    repo_result = _local_git_repo_result(
        repo_path=repo_path,
        diff_path=placeholder_diff_path,
    )
    if repo_result is not None:
        return repo_result
    if not allow_dirty:
        dirty_result = _dirty_worktree_result(
            repo_path=repo_path,
            diff_path=placeholder_diff_path,
        )
        if dirty_result is not None:
            return dirty_result
    return AgentApplyResult(
        status="ready",
        repo_path=str(repo_path),
        diff_path=placeholder_diff_path,
        message="apply target is a clean local Git repository",
    )


def apply_agent_run_diff(
    *,
    repo: str,
    diff_path: Path,
    allow_dirty: bool = False,
) -> AgentApplyResult:
    check_result = check_agent_run_diff(
        repo=repo,
        diff_path=diff_path,
        allow_dirty=allow_dirty,
    )
    if check_result.status != "ready":
        return check_result
    repo_path = Path(repo).expanduser().resolve()
    diff_path = diff_path.resolve()
    apply = _git(repo_path, "apply", str(diff_path))
    if apply.returncode != 0:
        return AgentApplyResult(
            status="apply_failed",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=_command_message(apply),
        )
    return AgentApplyResult(
        status="applied",
        repo_path=str(repo_path),
        diff_path=str(diff_path),
        message="diff applied to working tree",
        applied=True,
    )


def check_agent_run_diff(
    *,
    repo: str,
    diff_path: Path,
    allow_dirty: bool = False,
) -> AgentApplyResult:
    repo_path = Path(repo).expanduser().resolve()
    diff_path = diff_path.resolve()
    repo_result = _local_git_repo_result(repo_path=repo_path, diff_path=str(diff_path))
    if repo_result is not None:
        return repo_result
    if not diff_path.is_file():
        return AgentApplyResult(
            status="missing_diff",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=f"diff file does not exist: {diff_path}",
        )
    if not diff_path.read_text(encoding="utf-8").strip():
        return AgentApplyResult(
            status="empty_diff",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message="generated diff is empty; nothing to apply",
        )
    if not allow_dirty:
        dirty_result = _dirty_worktree_result(repo_path=repo_path, diff_path=str(diff_path))
        if dirty_result is not None:
            return dirty_result
    check = _git(repo_path, "apply", "--check", str(diff_path))
    if check.returncode != 0:
        return AgentApplyResult(
            status="apply_check_failed",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=_command_message(check),
        )
    return AgentApplyResult(
        status="ready",
        repo_path=str(repo_path),
        diff_path=str(diff_path),
        message="diff can be applied to working tree",
    )


def reverse_agent_run_diff(
    *,
    repo: str,
    diff_path: Path,
) -> AgentApplyResult:
    repo_path = Path(repo).expanduser().resolve()
    diff_path = diff_path.resolve()
    repo_result = _local_git_repo_result(repo_path=repo_path, diff_path=str(diff_path))
    if repo_result is not None:
        return repo_result
    if not diff_path.is_file():
        return AgentApplyResult(
            status="missing_diff",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=f"diff file does not exist: {diff_path}",
        )
    if not diff_path.read_text(encoding="utf-8").strip():
        return AgentApplyResult(
            status="empty_diff",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message="generated diff is empty; nothing to reverse",
        )
    check = _git(repo_path, "apply", "--reverse", "--check", str(diff_path))
    if check.returncode != 0:
        return AgentApplyResult(
            status="reverse_check_failed",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=_command_message(check),
        )
    reverse = _git(repo_path, "apply", "--reverse", str(diff_path))
    if reverse.returncode != 0:
        return AgentApplyResult(
            status="reverse_failed",
            repo_path=str(repo_path),
            diff_path=str(diff_path),
            message=_command_message(reverse),
        )
    return AgentApplyResult(
        status="reverted",
        repo_path=str(repo_path),
        diff_path=str(diff_path),
        message="diff reversed from working tree",
        applied=True,
    )


def _local_git_repo_result(
    *,
    repo_path: Path,
    diff_path: str,
) -> AgentApplyResult | None:
    if not repo_path.exists() or not repo_path.is_dir():
        return AgentApplyResult(
            status="unsupported_repo",
            repo_path=str(repo_path),
            diff_path=diff_path,
            message="--apply requires --repo to be a local Git repository",
        )
    if not (repo_path / ".git").exists():
        return AgentApplyResult(
            status="unsupported_repo",
            repo_path=str(repo_path),
            diff_path=diff_path,
            message="--apply requires --repo to contain a .git directory",
        )
    return None


def _dirty_worktree_result(
    *,
    repo_path: Path,
    diff_path: str,
) -> AgentApplyResult | None:
    status = _git(repo_path, "status", "--porcelain")
    if status.returncode != 0:
        return AgentApplyResult(
            status="git_status_failed",
            repo_path=str(repo_path),
            diff_path=diff_path,
            message=_command_message(status),
        )
    if status.stdout.strip():
        return AgentApplyResult(
            status="dirty_worktree",
            repo_path=str(repo_path),
            diff_path=diff_path,
            message=(
                "target worktree has uncommitted changes; rerun after committing or "
                "pass --allow-dirty-apply"
            ),
        )
    return None


def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def _command_message(result: subprocess.CompletedProcess[str]) -> str:
    message = result.stderr.strip() or result.stdout.strip()
    return message or f"git command failed with exit code {result.returncode}"
