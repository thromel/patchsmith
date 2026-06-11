from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from patchsmith.models import RepositoryIndex, RetrievedContext
from patchsmith.retrieval import KeywordRetriever

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


class PatchSmithNativeBroker:
    def __init__(
        self, retriever: SupportsRetrieve | None = None, *, provider_name: str = "patchsmith_native"
    ) -> None:
        self.retriever: SupportsRetrieve = retriever or KeywordRetriever()
        self.provider_name = provider_name

    def prepare(
        self,
        request: ContextBrokerRequest,
        *,
        repo_index: RepositoryIndex,
        artifact_dir: Path | None = None,
    ) -> ContextBundle:
        started = time.perf_counter()
        contexts = self.retriever.retrieve(
            repo_path=request.repo_path,
            repo_index=repo_index,
            issue_text=request.task,
            top_k=5,
        )
        return ContextBundle(
            provider=self.provider_name,
            provider_version=None,
            targets=[
                ContextTarget(
                    path=context.path,
                    role="source",
                    rank=context.rank,
                    confidence=context.score,
                    reason=", ".join(context.matched_terms),
                    source=context.method,
                )
                for context in contexts
            ],
            related_tests=[],
            validation_commands=[],
            diagnostics=[],
            warnings=[],
            pack_uri=None,
            source_text_logged=False,
            raw_artifact_path=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class CtxhelmCliBroker:
    def __init__(self, *, binary: str = "ctxhelm", timeout_seconds: int = 30) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds

    def prepare(
        self,
        request: ContextBrokerRequest,
        *,
        repo_index: RepositoryIndex,
        artifact_dir: Path | None = None,
    ) -> ContextBundle:
        started = time.perf_counter()
        if shutil.which(self.binary) is None:
            raise ContextBrokerError(f"ctxhelm binary not found: {self.binary}")

        artifact_dir = artifact_dir.resolve() if artifact_dir else None
        if artifact_dir:
            artifact_dir.mkdir(parents=True, exist_ok=True)

        doctor = self._run(
            [self.binary, "doctor", "--repo", str(request.repo_path), "--format", "json"]
        )
        doctor_json = _parse_json(doctor.stdout, "ctxhelm doctor")
        if artifact_dir:
            (artifact_dir / "ctxhelm_doctor.json").write_text(doctor.stdout, encoding="utf-8")

        command = [
            self.binary,
            "inspector",
            "export",
            request.task,
            "--repo",
            str(request.repo_path),
            "--mode",
            request.mode,
            "--budget",
            request.budget,
            "--format",
            "json",
        ]
        for path in request.active_paths:
            command.extend(["--path", path])
        if request.include_current_diff:
            command.append("--current-diff")
        if request.semantic:
            command.append("--semantic")

        exported = self._run(command)
        raw_artifact_path = None
        if artifact_dir:
            raw_path = artifact_dir / "ctxhelm_inspector_export.json"
            raw_path.write_text(exported.stdout, encoding="utf-8")
            raw_artifact_path = str(raw_path)

        exported_json = _parse_json(exported.stdout, "ctxhelm inspector export")
        bundle = normalize_ctxhelm_export(
            exported_json,
            repo_path=request.repo_path,
            provider_version=_ctxhelm_version_from_doctor(doctor_json),
            raw_artifact_path=raw_artifact_path,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return bundle

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()
            stdout = (error.stdout or "").strip()
            detail = stderr or stdout or f"exit code {error.returncode}"
            raise ContextBrokerError(f"ctxhelm command failed: {detail}") from error
        except subprocess.TimeoutExpired as error:
            raise ContextBrokerError(
                f"ctxhelm command timed out: {' '.join(command[:3])}"
            ) from error
        return completed


class NullBrokerForTests:
    def prepare(
        self,
        request: ContextBrokerRequest,
        *,
        repo_index: RepositoryIndex,
        artifact_dir: Path | None = None,
    ) -> ContextBundle:
        return ContextBundle(
            provider="null",
            provider_version=None,
            targets=[],
            related_tests=[],
            validation_commands=[],
            diagnostics=[],
            warnings=["null broker returned no context"],
            pack_uri=None,
            source_text_logged=False,
            raw_artifact_path=None,
            latency_ms=0,
        )


class ContextBrokerError(RuntimeError):
    pass


def normalize_ctxhelm_export(
    payload: dict[str, Any],
    *,
    repo_path: Path,
    provider_version: str | None,
    raw_artifact_path: str | None,
    latency_ms: int,
) -> ContextBundle:
    targets: list[ContextTarget] = []
    seen_paths: set[tuple[str, str]] = set()

    for item in payload.get("targetFiles", []):
        _append_ctxhelm_target(
            targets,
            seen_paths,
            item=item,
            repo_path=repo_path,
            rank=len(targets) + 1,
            default_role="source",
        )

    for item in payload.get("retrievalCandidates", []):
        if str(item.get("role") or item.get("kind") or "").lower() == "test":
            continue
        _append_ctxhelm_target(
            targets,
            seen_paths,
            item=item,
            repo_path=repo_path,
            rank=len(targets) + 1,
            default_role=str(item.get("role") or item.get("kind") or "candidate"),
        )

    related_tests = [
        item
        for item in payload.get("relatedTests", [])
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and _is_repo_relative_path(repo_path, item["path"])
    ]
    for item in payload.get("retrievalCandidates", []):
        if (
            isinstance(item, dict)
            and str(item.get("role") or item.get("kind") or "").lower() == "test"
            and isinstance(item.get("path"), str)
            and _is_repo_relative_path(repo_path, item["path"])
            and not any(test.get("path") == item["path"] for test in related_tests)
        ):
            related_tests.append(item)
    validation_commands = [
        command
        for command in payload.get("validationCommands", [])
        if isinstance(command, str) and command.strip()
    ]

    return ContextBundle(
        provider="ctxhelm_cli",
        provider_version=provider_version,
        targets=targets,
        related_tests=related_tests,
        validation_commands=validation_commands,
        diagnostics=[item for item in payload.get("diagnostics", []) if isinstance(item, dict)],
        warnings=[str(item) for item in payload.get("warnings", [])],
        pack_uri=str(payload.get("packId")) if payload.get("packId") else None,
        source_text_logged=bool(payload.get("sourceTextLogged", False)),
        raw_artifact_path=raw_artifact_path,
        latency_ms=latency_ms,
    )


def retrieved_context_from_bundle(
    *,
    bundle: ContextBundle,
    repo_path: Path,
    fallback_contexts: list[RetrievedContext],
    top_k: int,
) -> list[RetrievedContext]:
    contexts: list[RetrievedContext] = []
    seen: set[str] = set()
    fallback_by_path = {context.path: context for context in fallback_contexts}
    for target in bundle.targets:
        if target.path in seen:
            continue
        seen.add(target.path)
        fallback = fallback_by_path.get(target.path)
        contexts.append(
            RetrievedContext(
                path=target.path,
                rank=len(contexts) + 1,
                score=float(target.confidence or (fallback.score if fallback else 0.0)),
                method=bundle.provider,
                matched_terms=(
                    [target.role, target.source, *fallback.matched_terms]
                    if fallback
                    else [target.role, target.source]
                ),
                excerpt=(
                    fallback.excerpt
                    if fallback and fallback.excerpt.strip()
                    else _read_excerpt(repo_path / target.path)
                ),
            )
        )
        if len(contexts) >= top_k:
            return contexts

    for context in fallback_contexts:
        if context.path in seen:
            continue
        seen.add(context.path)
        contexts.append(
            RetrievedContext(
                path=context.path,
                rank=len(contexts) + 1,
                score=context.score,
                method=f"{context.method}_fallback",
                matched_terms=context.matched_terms,
                excerpt=context.excerpt,
            )
        )
        if len(contexts) >= top_k:
            break
    return contexts


def fallback_bundle(
    *,
    provider: str,
    reason: str,
    native_bundle: ContextBundle,
) -> ContextBundle:
    return ContextBundle(
        provider=f"{provider}_fallback",
        provider_version=None,
        targets=native_bundle.targets,
        related_tests=[],
        validation_commands=[],
        diagnostics=[{"code": "context_broker_fallback", "message": reason, "severity": "warning"}],
        warnings=[reason],
        pack_uri=None,
        source_text_logged=False,
        raw_artifact_path=None,
        latency_ms=native_bundle.latency_ms,
        fallback_used=True,
    )


def _append_ctxhelm_target(
    targets: list[ContextTarget],
    seen_paths: set[tuple[str, str]],
    *,
    item: dict[str, Any],
    repo_path: Path,
    rank: int,
    default_role: str,
) -> None:
    path = item.get("path")
    if not isinstance(path, str) or not _is_repo_relative_path(repo_path, path):
        return
    role = str(item.get("role") or default_role)
    key = (path, role)
    if key in seen_paths:
        return
    seen_paths.add(key)
    targets.append(
        ContextTarget(
            path=path,
            role=role,
            rank=rank,
            confidence=_optional_float(item.get("confidence")),
            reason=str(item.get("reason") or item.get("reasonCode") or item.get("kind") or ""),
            source="ctxhelm_cli",
        )
    )


def _is_repo_relative_path(repo_path: Path, path: str) -> bool:
    if path.startswith("/") or path.startswith("../") or "/../" in path:
        return False
    try:
        (repo_path / path).resolve().relative_to(repo_path.resolve())
    except ValueError:
        return False
    return True


def _parse_json(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ContextBrokerError(f"{label} did not return JSON") from error
    if not isinstance(parsed, dict):
        raise ContextBrokerError(f"{label} returned non-object JSON")
    return parsed


def _ctxhelm_version_from_doctor(payload: dict[str, Any]) -> str | None:
    binary = payload.get("binary")
    if isinstance(binary, dict):
        version = binary.get("version")
        if isinstance(version, str):
            return version
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _read_excerpt(path: Path, max_lines: int = 8) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return "\n".join(f"{index + 1}: {line}" for index, line in enumerate(lines[:max_lines]))
