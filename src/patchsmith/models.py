from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RunRequest:
    repo: str
    issue_text: str
    issue_url: str | None = None
    commit: str | None = None
    branch: str | None = None
    test_command: str | None = None
    runtime: str = "agentless"
    planner: str = "heuristic"
    max_retries: int = 0
    retrieval_strategy: str = "keyword"
    context_provider: str = "native"
    top_k: int = 5
    sandbox_mode: str = "local"
    sandbox_image: str = "python:3.12-slim"
    context_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class FileRecord:
    path: str
    size_bytes: int
    language: str
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepositoryIndex:
    files: list[FileRecord]
    language_summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_count": len(self.files),
            "language_summary": self.language_summary,
            "files": [file.to_dict() for file in self.files],
        }


@dataclass(frozen=True)
class RepositorySnapshot:
    repo_url: str
    repo_path: Path
    commit_hash: str
    branch: str | None
    file_count: int
    language_summary: dict[str, int]
    package_manager: str | None
    test_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "repo_path": str(self.repo_path),
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "file_count": self.file_count,
            "language_summary": self.language_summary,
            "package_manager": self.package_manager,
            "test_commands": self.test_commands,
        }


@dataclass(frozen=True)
class RetrievedContext:
    path: str
    rank: int
    score: float
    method: str
    matched_terms: list[str]
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackingMetadata:
    context_count: int
    source_context_count: int
    test_context_count: int
    excerpt_char_count: int
    approx_token_count: int
    method_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandPolicyDecision:
    allowed: bool
    reason: str
    tokens: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    policy_decision: CommandPolicyDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "policy_decision": self.policy_decision.to_dict(),
        }


@dataclass(frozen=True)
class PatchCandidate:
    candidate_id: str
    candidate_index: int
    generation_strategy: str
    diff: str
    files_changed: list[str]
    selected: bool
    status: str
    risk_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    run_id: str
    event_id: str
    node_name: str
    event_type: str
    status: str
    started_at: str
    completed_at: str
    latency_ms: int
    input_summary: str = ""
    output_summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairRunResult:
    run_id: str
    status: str
    run_dir: Path
    repo_path: Path
    report_path: Path
    trace_path: Path
    final_diff_path: Path
    snapshot: RepositorySnapshot
    retrieved_context: list[RetrievedContext]
    test_result: CommandResult | None
