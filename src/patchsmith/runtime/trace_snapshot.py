"""Single-pass extraction of the latest runtime-trace signals.

The retry-feedback code in :mod:`patchsmith.runtime.attempts` and
:mod:`patchsmith.runtime.feedback` historically each scanned the runtime trace
once per signal (latest patch plan, latest quality assessment, latest target
violation, and so on). Building all of those signals in a single reversed pass
removes the repeated scans and gives both modules one source of truth for how a
signal is located in the trace.

"Latest" means the most recent event (scanning from the end of the trace) that
matches each signal's shape; each field is resolved independently so the result
is identical to the previous per-signal helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeTraceSnapshot:
    patch_plan: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    no_op_patch_violation: dict[str, Any] | None = None
    target_history_violation: dict[str, Any] | None = None
    target_selection_violation: dict[str, Any] | None = None
    target_symbol_violation: dict[str, Any] | None = None
    safety_gate_rejection: dict[str, Any] | None = None
    patch_target: str = ""
    patch_old_hash: str = ""
    mounted_context_paths: list[str] = field(default_factory=list)

    @property
    def has_target_history_or_selection_violation(self) -> bool:
        return (
            self.target_history_violation is not None or self.target_selection_violation is not None
        )

    @property
    def patch_quality_severity(self) -> str:
        if not self.quality:
            return ""
        severity = self.quality.get("severity")
        return str(severity) if severity else ""

    @property
    def patch_quality_finding_codes(self) -> list[str]:
        if not self.quality:
            return []
        findings = self.quality.get("findings")
        if not isinstance(findings, list):
            return []
        codes: list[str] = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            code = finding.get("code")
            if isinstance(code, str) and code and code not in codes:
                codes.append(code)
        return codes


def build_runtime_trace_snapshot(
    runtime_trace: list[dict[str, Any]] | None,
) -> RuntimeTraceSnapshot:
    patch_plan: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    no_op: dict[str, Any] | None = None
    target_history: dict[str, Any] | None = None
    target_selection: dict[str, Any] | None = None
    target_symbol: dict[str, Any] | None = None
    safety_rejection: dict[str, Any] | None = None
    patch_target = ""
    patch_old_hash = ""
    mounted_context_paths: list[str] = []
    patch_target_found = False
    patch_old_hash_found = False
    mounted_found = False

    for event in reversed(runtime_trace or []):
        event_patch_plan = event.get("patch_plan")
        event_patch_plan = event_patch_plan if isinstance(event_patch_plan, dict) else None
        metadata = event.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else None

        if patch_plan is None and event_patch_plan is not None:
            patch_plan = event_patch_plan
        if quality is None:
            event_quality = event.get("quality")
            if isinstance(event_quality, dict):
                quality = event_quality
        if metadata is not None:
            if no_op is None and isinstance(metadata.get("no_op_patch_violation"), dict):
                no_op = metadata["no_op_patch_violation"]
            if target_history is None and isinstance(
                metadata.get("target_history_violation"), dict
            ):
                target_history = metadata["target_history_violation"]
            if target_selection is None and isinstance(
                metadata.get("target_selection_violation"), dict
            ):
                target_selection = metadata["target_selection_violation"]
            if target_symbol is None and isinstance(metadata.get("target_symbol_violation"), dict):
                target_symbol = metadata["target_symbol_violation"]
        if safety_rejection is None and _is_safety_rejection(event):
            safety_rejection = event

        if not patch_target_found:
            resolved = _resolve_patch_target(event_patch_plan, metadata)
            if resolved:
                patch_target = resolved
                patch_target_found = True
        if not patch_old_hash_found and event_patch_plan is not None:
            old = event_patch_plan.get("old")
            if isinstance(old, dict) and old.get("sha256_12"):
                patch_old_hash = str(old["sha256_12"])
                patch_old_hash_found = True
        if not mounted_found and metadata is not None:
            resolved_paths = _resolve_mounted_paths(metadata)
            if resolved_paths:
                mounted_context_paths = resolved_paths
                mounted_found = True

    return RuntimeTraceSnapshot(
        patch_plan=patch_plan,
        quality=quality,
        no_op_patch_violation=no_op,
        target_history_violation=target_history,
        target_selection_violation=target_selection,
        target_symbol_violation=target_symbol,
        safety_gate_rejection=safety_rejection,
        patch_target=patch_target,
        patch_old_hash=patch_old_hash,
        mounted_context_paths=mounted_context_paths,
    )


def _is_safety_rejection(event: dict[str, Any]) -> bool:
    if event.get("node") != "edit" or event.get("status") != "failed":
        return False
    summary = event.get("summary")
    return isinstance(summary, str) and bool(summary.strip())


def _resolve_patch_target(
    patch_plan: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> str:
    if patch_plan is not None:
        path = patch_plan.get("path")
        if path:
            return str(path)
    if metadata is not None:
        for key in ("target_history_violation", "target_selection_violation"):
            violation = metadata.get(key)
            if isinstance(violation, dict):
                path = violation.get("path")
                if path:
                    return str(path)
    return ""


def _resolve_mounted_paths(metadata: dict[str, Any]) -> list[str]:
    contract = metadata.get("deepagents_contract")
    if not isinstance(contract, dict):
        return []
    context_budget = contract.get("context_budget")
    if not isinstance(context_budget, dict):
        return []
    mounted_paths = context_budget.get("mounted_paths")
    if not isinstance(mounted_paths, list):
        return []
    paths: list[str] = []
    for path in mounted_paths:
        if not isinstance(path, str):
            continue
        normalized = path.strip().lstrip("/")
        if normalized and normalized not in paths:
            paths.append(normalized)
    return paths
