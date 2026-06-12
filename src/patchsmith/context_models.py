from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from patchsmith.models import RepositoryIndex, RetrievedContext

ContextBudget = Literal["brief", "standard", "deep"]
ContextMode = Literal["bug-fix", "feature", "refactor", "review", "test", "explain"]


@dataclass(frozen=True)
class ContextBrokerRequest:
    repo_path: Path
    task: str
    mode: ContextMode = "bug-fix"
    budget: ContextBudget = "brief"
    active_paths: tuple[str, ...] = ()
    include_current_diff: bool = False
    semantic: bool = False


@dataclass(frozen=True)
class ContextTarget:
    path: str
    role: str
    rank: int
    confidence: float | None
    reason: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextBundle:
    provider: str
    provider_version: str | None
    targets: list[ContextTarget]
    related_tests: list[dict[str, Any]]
    validation_commands: list[str]
    diagnostics: list[dict[str, Any]]
    warnings: list[str]
    pack_uri: str | None
    source_text_logged: bool
    raw_artifact_path: str | None
    latency_ms: int
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "targets": [target.to_dict() for target in self.targets],
            "related_tests": self.related_tests,
            "validation_commands": self.validation_commands,
            "diagnostics": self.diagnostics,
            "warnings": self.warnings,
            "pack_uri": self.pack_uri,
            "source_text_logged": self.source_text_logged,
            "raw_artifact_path": self.raw_artifact_path,
            "latency_ms": self.latency_ms,
            "fallback_used": self.fallback_used,
        }


class ContextBroker(Protocol):
    def prepare(
        self,
        request: ContextBrokerRequest,
        *,
        repo_index: RepositoryIndex,
        artifact_dir: Path | None = None,
    ) -> ContextBundle:
        """Return normalized context evidence for an issue."""


class SupportsRetrieve(Protocol):
    def retrieve(
        self,
        *,
        repo_path: Path,
        repo_index: RepositoryIndex,
        issue_text: str,
        top_k: int = 5,
    ) -> list[RetrievedContext]:
        """Return ranked retrieved contexts for an issue."""


class ContextBrokerError(RuntimeError):
    pass


__all__ = [
    "ContextBroker",
    "ContextBrokerError",
    "ContextBrokerRequest",
    "ContextBudget",
    "ContextBundle",
    "ContextMode",
    "ContextTarget",
    "SupportsRetrieve",
]
