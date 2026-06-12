"""Observability discovery (split from observability.py)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from os.path import relpath
from pathlib import Path
from typing import Any

from patchsmith.observability.discovery_metrics import (
    _experiment_metric_entries as _experiment_metric_entries,
)
from patchsmith.observability.discovery_metrics import (
    _int_or_none as _int_or_none,
)
from patchsmith.observability.discovery_metrics import (
    _number_or_none as _number_or_none,
)
from patchsmith.observability.models import (
    ArtifactIndex,
    RunArtifactIndexEntry,
)


def _load_trace_events(
    run: RunArtifactIndexEntry,
    artifacts_dir: Path,
) -> list[dict[str, Any]]:
    if run.trace_path is None:
        return []
    trace_path = artifacts_dir / run.trace_path
    events: list[dict[str, Any]] = []
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _is_failure_status(status: Any) -> bool:
    normalized = str(status or "").lower()
    if normalized in {
        "",
        "completed",
        "created",
        "patch_generated",
        "ready_for_test",
        "not_needed",
        "validated",
    }:
        return False
    return any(marker in normalized for marker in ("fail", "error", "timeout", "rejected"))


def _run_detail_output_path(
    output_dir: Path,
    run: RunArtifactIndexEntry,
) -> Path:
    return output_dir / f"{run.run_id}.html"


def _run_detail_relative_path(
    index: ArtifactIndex,
    run: RunArtifactIndexEntry,
    run_detail_output_dir: Path | None,
) -> str | None:
    if run_detail_output_dir is None:
        return None
    detail_path = _run_detail_output_path(run_detail_output_dir, run)
    return _relative_or_none(Path(index.artifacts_dir), detail_path)


def _relative_href(target: Path, source_dir: Path) -> str:
    return relpath(target, source_dir).replace("\\", "/")


def _discover_runs(artifacts_dir: Path) -> list[RunArtifactIndexEntry]:
    run_dirs: list[Path] = []
    direct_runs = artifacts_dir / "runs"
    if direct_runs.exists():
        run_dirs.extend(path for path in direct_runs.iterdir() if path.is_dir())
    experiments_dir = artifacts_dir / "experiments"
    if experiments_dir.exists():
        run_dirs.extend(
            path for path in experiments_dir.glob("**/run_artifacts/runs/*") if path.is_dir()
        )
    runs = [_run_entry(artifacts_dir, run_dir) for run_dir in run_dirs]
    return sorted(
        runs,
        key=lambda run: (run.updated_at or "", run.run_id),
        reverse=True,
    )


def _run_entry(artifacts_dir: Path, run_dir: Path) -> RunArtifactIndexEntry:
    report_path = run_dir / "report.md"
    trace_path = run_dir / "traces.jsonl"
    diff_path = run_dir / "final.diff"
    stdout_path = run_dir / "logs" / "stdout.txt"
    stderr_path = run_dir / "logs" / "stderr.txt"
    artifact_paths = [
        path
        for path in (report_path, trace_path, diff_path, stdout_path, stderr_path)
        if path.exists()
    ]
    experiment, variant = _run_experiment_variant(artifacts_dir, run_dir)
    return RunArtifactIndexEntry(
        run_id=run_dir.name,
        experiment=experiment,
        variant=variant,
        report_path=_relative_or_none(
            artifacts_dir,
            report_path if report_path.exists() else None,
        ),
        trace_path=_relative_or_none(
            artifacts_dir,
            trace_path if trace_path.exists() else None,
        ),
        diff_path=_relative_or_none(
            artifacts_dir,
            diff_path if diff_path.exists() else None,
        ),
        stdout_path=_relative_or_none(
            artifacts_dir,
            stdout_path if stdout_path.exists() else None,
        ),
        stderr_path=_relative_or_none(
            artifacts_dir,
            stderr_path if stderr_path.exists() else None,
        ),
        updated_at=_updated_at_from_paths(run_dir, artifact_paths),
    )


def _run_experiment_variant(
    artifacts_dir: Path,
    run_dir: Path,
) -> tuple[str | None, str | None]:
    experiments_dir = artifacts_dir / "experiments"
    try:
        relative = run_dir.relative_to(experiments_dir)
    except ValueError:
        return None, None
    parts = relative.parts
    if not parts:
        return None, None
    try:
        run_artifacts_index = parts.index("run_artifacts")
    except ValueError:
        return parts[0], None
    variant_parts = parts[1:run_artifacts_index]
    variant = "/".join(variant_parts) if variant_parts else None
    return parts[0], variant


def _first_existing(directory: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = directory / name
        if path.exists():
            return path
    return None


def _relative_or_none(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _result_count(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("result_count", "attempted_tasks", "task_count"):
            value = payload.get(key)
            if isinstance(value, int):
                return value
    return None


def _run_count(artifacts_dir: Path) -> int:
    count = 0
    direct_runs = artifacts_dir / "runs"
    if direct_runs.exists():
        count += sum(1 for path in direct_runs.iterdir() if path.is_dir())
    experiments_dir = artifacts_dir / "experiments"
    if experiments_dir.exists():
        count += sum(1 for path in experiments_dir.glob("**/run_artifacts/runs/*") if path.is_dir())
    return count


def _experiment_run_count(experiment_dir: Path) -> int:
    return sum(1 for path in experiment_dir.glob("**/run_artifacts/runs/*") if path.is_dir())


def _updated_at(
    experiment_dir: Path,
    report_path: Path | None,
    summary_path: Path | None,
    results_path: Path | None,
) -> str | None:
    return _updated_at_from_paths(
        experiment_dir,
        [report_path, summary_path, results_path],
    )


def _updated_at_from_paths(
    directory: Path,
    paths: Sequence[Path | None],
) -> str | None:
    candidates = [path for path in paths if path is not None]
    if not candidates:
        candidates = [directory]
    try:
        return _utc_timestamp(max(path.stat().st_mtime for path in candidates))
    except OSError:
        return None


def _utc_timestamp(epoch_seconds: float) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _experiment_kind(name: str, report_path: Path | None) -> str:
    if "validation" in name:
        return "validation"
    if "retrieval" in name:
        return "retrieval"
    if "repair" in name:
        return "repair"
    if "scaffold" in name:
        return "scaffold"
    if "patch_search" in name:
        return "patch_search"
    if report_path is not None:
        return report_path.stem.replace("_report", "")
    return "unknown"


def _markdown_path(path: str | None) -> str:
    if not path:
        return ""
    return f"`{path}`"
