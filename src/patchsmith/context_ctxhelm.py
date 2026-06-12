from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from patchsmith.context_bundle import _is_repo_relative_path
from patchsmith.context_models import (
    ContextBrokerError,
    ContextBrokerRequest,
    ContextBundle,
    ContextTarget,
)
from patchsmith.models import RepositoryIndex


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


__all__ = ["CtxhelmCliBroker", "normalize_ctxhelm_export"]
