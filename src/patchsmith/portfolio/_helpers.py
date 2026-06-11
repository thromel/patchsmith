"""Portfolio helpers (split from portfolio.py)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from patchsmith.artifacts import load_json as _load_json


def _path_exists(path: Path) -> bool:
    return path.exists()


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _package_available(
    package_name: str,
    package_availability: dict[str, bool] | None,
) -> bool:
    if package_availability is not None and package_name in package_availability:
        return package_availability[package_name]
    return find_spec(package_name) is not None


def _discover_deepagents_adapter_modes(artifacts_dir: Path) -> dict[str, int]:
    return _discover_adapter_modes(artifacts_dir, framework="deepagents")


def _discover_openai_agents_adapter_modes(artifacts_dir: Path) -> dict[str, int]:
    return _discover_adapter_modes(artifacts_dir, framework="openai_agents")


def _discover_adapter_modes(artifacts_dir: Path, *, framework: str) -> dict[str, int]:
    modes: dict[str, set[str]] = {
        "package_available": set(),
        "compatibility_mode": set(),
    }
    experiments_dir = artifacts_dir / "experiments"
    if not experiments_dir.exists():
        return {}
    for trace_path in sorted(experiments_dir.glob("**/traces.jsonl")):
        try:
            lines = trace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if (
                event.get("event_type") != "runtime_node"
                or payload.get("framework") != framework
                or payload.get("node") != "harness"
            ):
                continue
            mode = str(payload.get("status") or event.get("status") or "")
            run_id = str(event.get("run_id") or trace_path.parent.name)
            if mode in modes:
                modes[mode].add(run_id)
    return {mode: len(run_ids) for mode, run_ids in sorted(modes.items()) if run_ids}


def _discover_model_providers(artifacts_dir: Path) -> dict[str, int]:
    providers: Counter[str] = Counter()
    experiments_dir = artifacts_dir / "experiments"
    if not experiments_dir.exists():
        return {}
    for path in sorted(experiments_dir.glob("**/*.json")):
        if path.name in {
            "index.json",
            "failure_report.json",
            "demo_readiness.json",
            "calibration_readiness.json",
            "live_calibration_plan.json",
            "demo_script.json",
            "demo_media.json",
            "quality_gate.json",
            "final_evaluation.json",
            "delivery_audit.json",
            "release_hygiene.json",
        }:
            continue
        payload = _load_json(path)
        _collect_model_providers(payload, providers)
    return dict(sorted(providers.items()))


def _collect_model_providers(payload: Any, providers: Counter[str]) -> None:
    if isinstance(payload, dict):
        provider = payload.get("model_provider")
        if isinstance(provider, str) and provider:
            providers[provider] += 1
        for value in payload.values():
            if isinstance(value, dict | list):
                _collect_model_providers(value, providers)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict | list):
                _collect_model_providers(item, providers)


def _load_json_artifact(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _payload_int(payload: dict[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else default


def _payload_float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key)
    if isinstance(value, int | float):
        return float(value)
    return default


def _payload_string(payload: dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else default


def _payload_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _live_providers(providers: dict[str, int]) -> list[str]:
    return [provider for provider in providers if provider and not provider.startswith("offline_")]


def _demo_commands() -> list[str]:
    return [
        "python3 -m pytest -q",
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-scaffold "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--variant agentless --variant heuristic --variant langgraph "
            "--variant langgraph_fake_model --variant deepagents "
            "--variant openai_agents "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/scaffold_comparison_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-patch-search "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--candidate-count 1 --candidate-count 3 "
            "--context-provider native_hybrid "
            "--output artifacts/experiments/patch_search_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli index-artifacts "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/index.md "
            "--json-output artifacts/experiments/index.json "
            "--html-output artifacts/experiments/index.html "
            "--run-detail-output-dir artifacts/experiments/run-details --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli inspect-failures "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/failure_report.md "
            "--json-output artifacts/experiments/failure_report.json "
            "--max-runs 0 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-readiness "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_readiness.md "
            "--json-output artifacts/experiments/demo_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-script "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_script.md "
            "--json-output artifacts/experiments/demo_script.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli demo-media "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/demo_media.md "
            "--svg-output artifacts/experiments/demo_media.svg "
            "--png-output artifacts/experiments/demo_media.png "
            "--json-output artifacts/experiments/demo_media.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli final-evaluation "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/final_evaluation.md "
            "--json-output artifacts/experiments/final_evaluation.json --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli release-hygiene "
            "--project-root . "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/release_hygiene.md "
            "--json-output artifacts/experiments/release_hygiene.json --json"
        ),
    ]


def _failure_summary(categories: dict[str, int]) -> str:
    if not categories:
        return "no saved failure categories"
    return ", ".join(f"{name} {count}" for name, count in categories.items())


def _provider_summary(providers: dict[str, int]) -> str:
    if not providers:
        return "missing"
    return ", ".join(f"{name} {count}" for name, count in providers.items())


def _format_duration(seconds: int) -> str:
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s"
    return f"{remainder}s"


def _markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def _utc_now() -> str:
    return _format_utc(datetime.now(UTC).replace(microsecond=0))


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def _format_age_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"
