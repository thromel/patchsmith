"""Evaluation helpers (split from evaluation.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from patchsmith.evaluation_models import (
    SeededTaskValidationResult,
)


def _ensure_git_repo(repo_path: Path) -> None:
    if (repo_path / ".git").exists():
        return
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=PatchSmith",
            "-c",
            "user.email=patchsmith@example.local",
            "commit",
            "-q",
            "-m",
            "seeded task snapshot",
        ],
        cwd=repo_path,
        check=True,
    )


def _path_has_text(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _load_json_record_list(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must contain a JSON list")
    records = [record for record in parsed if isinstance(record, dict)]
    if len(records) != len(parsed):
        raise ValueError(f"{label} records must be JSON objects")
    return records


def _records_by_task_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = _optional_string(record.get("task_id"))
        if task_id:
            by_task[task_id] = record
    return by_task


def _docker_smoke_status_from_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid"
    if not isinstance(parsed, dict):
        return "invalid"
    status = parsed.get("smoke_status")
    return status if isinstance(status, str) and status else "unknown"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _fixture_listing_command(focused_files: list[str]) -> str:
    if focused_files:
        return f"python3 -m pytest --fixtures {focused_files[0]}"
    return "python3 -m pytest --fixtures"


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _remove_artifact_dir(*, root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError(f"refusing to remove path outside artifact root: {target}") from error
    if target == root:
        raise ValueError("refusing to remove artifact root")
    shutil.rmtree(target)


def _required_entry_string(entry: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"entry missing non-empty string field: {key}")
        return None
    return value.strip()


def _entry_string_list(entry: dict[str, Any], key: str, errors: list[str]) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"entry missing non-empty string list field: {key}")
        return []
    results: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"entry field {key}[{index}] must be a non-empty string")
            continue
        results.append(item.strip())
    return results


def _expected_string(expected: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = expected.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"expected.json missing non-empty string field: {key}")
        return None
    return value.strip()


def _expected_string_list(
    expected: dict[str, Any],
    key: str,
    errors: list[str],
) -> list[str]:
    value = expected.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"expected.json missing non-empty string list field: {key}")
        return []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"expected.json field {key}[{index}] must be a non-empty string")
            continue
        paths.append(item.strip())
    return paths


def _manifest_string(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    field_name: str | None = None,
) -> str | None:
    value = manifest.get(key)
    name = field_name or key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return None
    return value.strip()


def _manifest_object(
    manifest: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _validate_expected_repo_file(
    repo_path: Path,
    relative_path: str,
    field_name: str,
    errors: list[str],
) -> None:
    if relative_path.startswith("/") or relative_path.startswith("../") or "/../" in relative_path:
        errors.append(f"{field_name} contains unsafe path: {relative_path}")
        return
    target = (repo_path / relative_path).resolve()
    try:
        target.relative_to(repo_path.resolve())
    except ValueError:
        errors.append(f"{field_name} escapes repo: {relative_path}")
        return
    if not target.is_file():
        errors.append(f"{field_name} path does not exist: {relative_path}")


def _duplicate_task_ids(results: list[SeededTaskValidationResult]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for result in results:
        if result.task_id is None:
            continue
        if result.task_id in seen:
            duplicates.add(result.task_id)
        seen.add(result.task_id)
    return sorted(duplicates)


def _with_validation_error(
    result: SeededTaskValidationResult,
    error: str,
) -> SeededTaskValidationResult:
    return SeededTaskValidationResult(
        task_dir=result.task_dir,
        task_id=result.task_id,
        status="invalid",
        errors=[*result.errors, error],
        warnings=result.warnings,
        issue_path=result.issue_path,
        repo_path=result.repo_path,
        expected_path=result.expected_path,
        expected_touched_files=result.expected_touched_files,
        expected_related_tests=result.expected_related_tests,
    )


def _model_usage_from_trace(trace_path: Path) -> dict[str, Any]:
    providers: list[str] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    total_tokens: list[int] = []
    estimated_costs: list[float] = []

    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event, dict) else None
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            continue
        model_call = metadata.get("model_call")
        if not isinstance(model_call, dict):
            continue
        provider = model_call.get("provider")
        if isinstance(provider, str) and provider not in providers:
            providers.append(provider)
        _append_int(input_tokens, model_call.get("input_tokens"))
        _append_int(output_tokens, model_call.get("output_tokens"))
        _append_int(total_tokens, model_call.get("total_tokens"))
        _append_float(estimated_costs, model_call.get("estimated_cost_usd"))

    return {
        "model_provider": ",".join(providers) if providers else None,
        "input_tokens": sum(input_tokens) if input_tokens else None,
        "output_tokens": sum(output_tokens) if output_tokens else None,
        "total_tokens": sum(total_tokens) if total_tokens else None,
        "estimated_cost_usd": sum(estimated_costs) if estimated_costs else None,
    }


def _trace_metrics_from_trace(trace_path: Path) -> dict[str, Any]:
    events = _trace_events(trace_path)
    node_names = {
        str(event.get("node_name")) for event in events if isinstance(event.get("node_name"), str)
    }
    event_types = {
        str(event.get("event_type")) for event in events if isinstance(event.get("event_type"), str)
    }
    runtime_node_count = sum(
        1 for event in events if str(event.get("node_name", "")).startswith("runtime.")
    )
    failed_event_count = sum(
        1
        for event in events
        if str(event.get("status", "")).lower() in {"failed", "error"}
        or event.get("error") is not None
    )
    retry_event_count = sum(
        1
        for event in events
        if str(event.get("node_name", "")) == "runtime.retry"
        or str(event.get("event_type", "")) == "retry"
    )
    debuggability_score = 0.0
    if events:
        debuggability_score += 1.0
    if "retrieve" in node_names or "context_broker" in node_names:
        debuggability_score += 1.0
    if runtime_node_count:
        debuggability_score += 1.0
    if "test" in node_names:
        debuggability_score += 1.0
    if "repair_outcome" in event_types:
        debuggability_score += 1.0

    return {
        "trace_event_count": len(events),
        "runtime_node_count": runtime_node_count,
        "failed_trace_event_count": failed_event_count,
        "retry_event_count": retry_event_count,
        "debuggability_score": debuggability_score,
    }


def _trace_events(trace_path: Path) -> list[dict[str, Any]]:
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _append_int(values: list[int], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        values.append(value)


def _append_float(values: list[float], value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        values.append(float(value))


def _sum_optional(values: Any) -> int | None:
    values_list = [value for value in values if value is not None]
    if not values_list:
        return None
    return sum(values_list)


def _average(values: Any) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)
