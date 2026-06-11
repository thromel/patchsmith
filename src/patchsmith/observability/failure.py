"""Observability failure (split from observability.py)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchsmith.artifacts import dict_or_empty
from patchsmith.observability.discovery import (
    _bool_or_none,
    _int_or_none,
    _is_failure_status,
    _load_trace_events,
    _markdown_path,
    _string_or_none,
    _utc_timestamp,
)
from patchsmith.observability.index import build_artifact_index
from patchsmith.observability.models import (
    FailureArtifactReport,
    FailureRunInsight,
    RunArtifactIndexEntry,
)
from patchsmith.observability.render_md import _compact_markdown_cell


def build_failure_report(
    *,
    artifacts_dir: Path,
    max_runs: int | None = 100,
) -> FailureArtifactReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    runs = index.runs[:max_runs] if max_runs is not None else index.runs
    insights: list[FailureRunInsight] = []
    for run in runs:
        insight = _failure_run_insight(run, artifacts_dir=Path(index.artifacts_dir))
        if insight is not None:
            insights.append(insight)
    category_counts = Counter(insight.failure_category for insight in insights)
    return FailureArtifactReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_timestamp(datetime.now(UTC).timestamp()),
        runs_scanned=len(runs),
        runs_requiring_attention=len(insights),
        failed_event_count=sum(insight.failed_event_count for insight in insights),
        category_counts=dict(sorted(category_counts.items())),
        insights=insights,
    )


def write_failure_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_runs: int | None = 100,
) -> FailureArtifactReport:
    report = build_failure_report(artifacts_dir=artifacts_dir, max_runs=max_runs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_failure_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_failure_report(report: FailureArtifactReport) -> str:
    lines = [
        "# PatchSmith Failure Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Runs scanned: `{report.runs_scanned}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        f"- Failed trace events: `{report.failed_event_count}`",
        "",
        "## Failure Categories",
        "",
    ]
    if report.category_counts:
        lines.extend(
            [
                "| Category | Runs |",
                "|---|---:|",
            ]
        )
        for category, count in report.category_counts.items():
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("No failure categories found in the scanned runs.")

    lines.extend(
        [
            "",
            "## Runs Requiring Attention",
            "",
        ]
    )
    if report.insights:
        lines.extend(
            [
                (
                    "| Run | Experiment | Variant | Category | Verdict | Test Exit | "
                    "Failed Events | Failed Nodes | Next Action | Artifacts |"
                ),
                "|---|---|---|---|---|---:|---:|---|---|---|",
            ]
        )
        for insight in report.insights:
            lines.append(
                "| "
                f"{insight.run_id} | "
                f"{insight.experiment or ''} | "
                f"{insight.variant or ''} | "
                f"{insight.failure_category} | "
                f"{insight.verdict or ''} | "
                f"{insight.test_exit_code if insight.test_exit_code is not None else ''} | "
                f"{insight.failed_event_count} | "
                f"{', '.join(insight.failed_nodes)} | "
                f"{_compact_markdown_cell(insight.next_action)} | "
                f"{_failure_artifact_links(insight)} |"
            )
    else:
        lines.append("No runs requiring attention were found in the scanned artifact set.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            (
                "- This report is generated from saved `traces.jsonl` artifacts. "
                "It is a review aid, not a replacement for rerunning tests."
            ),
            (
                "- Repair-outcome events supply the primary failure category. "
                "When no repair outcome exists, failed trace events provide a fallback category."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _failure_run_insight(
    run: RunArtifactIndexEntry,
    *,
    artifacts_dir: Path,
) -> FailureRunInsight | None:
    events = _load_trace_events(run, artifacts_dir)
    failed_events = [event for event in events if _is_failure_status(event.get("status"))]
    outcome = _last_repair_outcome_event(events)
    outcome_payload = dict_or_empty(outcome.get("payload")) if outcome is not None else {}
    category = _repair_outcome_category(outcome, outcome_payload)
    if category is None and failed_events:
        category = _event_failure_category(failed_events[0])
    if category is None:
        return None

    failed_nodes = sorted(
        {
            str(event.get("node_name"))
            for event in failed_events
            if event.get("node_name") is not None
        }
    )
    first_failed = failed_events[0] if failed_events else None
    summary = _string_or_none(outcome_payload.get("summary"))
    if summary is None and outcome is not None:
        summary = _string_or_none(outcome.get("output_summary"))
    if summary is None and first_failed is not None:
        summary = _string_or_none(first_failed.get("output_summary"))
    next_action = _string_or_none(outcome_payload.get("next_action"))
    return FailureRunInsight(
        run_id=run.run_id,
        experiment=run.experiment,
        variant=run.variant,
        updated_at=run.updated_at,
        report_path=run.report_path,
        trace_path=run.trace_path,
        diff_path=run.diff_path,
        failure_category=category,
        verdict=_string_or_none(outcome_payload.get("verdict")),
        status=_string_or_none(outcome_payload.get("status"))
        or _string_or_none(outcome.get("status") if outcome else None),
        summary=summary or "Failure signal found in trace events.",
        next_action=next_action or _fallback_next_action(category),
        patch_generated=_bool_or_none(outcome_payload.get("patch_generated")),
        tests_passed=_bool_or_none(outcome_payload.get("tests_passed")),
        test_exit_code=_int_or_none(outcome_payload.get("test_exit_code")),
        failed_event_count=len(failed_events),
        failed_nodes=failed_nodes,
        trace_event_count=len(events),
        total_latency_ms=sum(
            float(value)
            for event in events
            if isinstance((value := event.get("latency_ms")), int | float)
        ),
    )


def _last_repair_outcome_event(
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") == "repair_outcome":
            return event
    return None


def _repair_outcome_category(
    event: dict[str, Any] | None,
    payload: dict[str, Any],
) -> str | None:
    failure_category = _string_or_none(payload.get("failure_category"))
    if failure_category:
        return failure_category
    verdict = _string_or_none(payload.get("verdict"))
    if verdict and verdict != "patch_validated":
        return verdict
    status = _string_or_none(payload.get("status"))
    if status in {"unresolved", "needs_followup", "ambiguous", "unvalidated"}:
        return status
    event_status = _string_or_none(event.get("status") if event else None)
    if event_status in {"unresolved", "needs_followup", "ambiguous", "unvalidated"}:
        return event_status
    return None


def _event_failure_category(event: dict[str, Any]) -> str:
    node = str(event.get("node_name") or "unknown")
    status = str(event.get("status") or "failed")
    if node == "test":
        return "sandbox_test_failed"
    if "runtime" in node:
        return "runtime_failure"
    return f"{node}_{status}"


def _fallback_next_action(category: str) -> str:
    if category in {"no_patch_generated", "runtime_failure"}:
        return "Inspect retrieval targets and runtime planning events before rerunning."
    if category in {"test_failure_after_patch", "sandbox_test_failed"}:
        return "Inspect sandbox stdout/stderr and retry with failure-specific context."
    if category == "missing_test_command":
        return "Provide or detect a targeted test command before judging repair quality."
    return "Open the run report and trace to classify the failure before retrying."


def _failure_artifact_links(insight: FailureRunInsight) -> str:
    links = [
        label
        for label in (
            f"report {_markdown_path(insight.report_path)}" if insight.report_path else "",
            f"trace {_markdown_path(insight.trace_path)}" if insight.trace_path else "",
            f"diff {_markdown_path(insight.diff_path)}" if insight.diff_path else "",
        )
        if label
    ]
    return "<br>".join(links)
