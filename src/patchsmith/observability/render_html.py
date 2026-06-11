"""Observability render html (split from observability.py)."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from patchsmith.observability.discovery import (
    _is_failure_status,
    _load_trace_events,
    _relative_href,
    _run_detail_output_path,
)
from patchsmith.observability.models import (
    RECENT_RUN_LIMIT,
    ArtifactIndex,
    ExperimentArtifactIndexEntry,
    ExperimentMetricIndexEntry,
    RunArtifactIndexEntry,
)
from patchsmith.observability.render_html_assets import (
    DASHBOARD_SCRIPT,
    DASHBOARD_STYLE,
    RUN_DETAIL_STYLE,
)
from patchsmith.observability.render_md import (
    _format_cost,
    _format_int,
    _format_latency,
    _format_metric_pair,
    _joined,
    _metric_task_count,
    _text_preview,
)


def render_artifact_dashboard(
    index: ArtifactIndex,
    *,
    output_path: Path | None = None,
    run_detail_output_dir: Path | None = None,
) -> str:
    total_results = sum(entry.result_count or 0 for entry in index.experiments)
    kinds = sorted({entry.kind for entry in index.experiments})
    max_result_count = max((entry.result_count or 0 for entry in index.experiments), default=0)
    max_run_count = max((entry.run_count for entry in index.experiments), default=0)
    rows = "\n".join(
        _dashboard_row(
            entry,
            max_result_count=max_result_count,
            max_run_count=max_run_count,
            artifacts_dir=Path(index.artifacts_dir),
            output_path=output_path,
        )
        for entry in index.experiments
    )
    run_rows = "\n".join(
        _dashboard_run_row(
            run,
            artifacts_dir=Path(index.artifacts_dir),
            output_path=output_path,
            run_detail_output_dir=run_detail_output_dir,
        )
        for run in index.runs[:RECENT_RUN_LIMIT]
    )
    metric_rows = "\n".join(
        _dashboard_metric_row(
            metric,
            artifacts_dir=Path(index.artifacts_dir),
            output_path=output_path,
        )
        for metric in index.metrics
    )
    kind_options = "\n".join(
        f'<option value="{escape(kind)}">{escape(kind)}</option>' for kind in kinds
    )
    generated_at = escape(index.generated_at)
    artifacts_dir = escape(index.artifacts_dir)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PatchSmith Artifact Dashboard</title>
  <style>
{DASHBOARD_STYLE}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>PatchSmith Artifact Dashboard</h1>
        <div class="meta">Generated {generated_at} from {artifacts_dir}</div>
      </div>
    </header>

    <section class="summary" aria-label="Artifact summary">
      <div class="summary-cell"><span>Experiments</span><strong>{index.experiment_count}</strong></div>
      <div class="summary-cell"><span>Saved Runs</span><strong>{index.run_count}</strong></div>
      <div class="summary-cell"><span>Result Rows</span><strong>{total_results}</strong></div>
      <div class="summary-cell"><span>Kinds</span><strong>{len(kinds)}</strong></div>
    </section>

    <section class="toolbar" aria-label="Artifact filters">
      <input id="search" type="search" placeholder="Search experiments and metrics" autocomplete="off">
      <select id="kind">
        <option value="">All kinds</option>
        {kind_options}
      </select>
    </section>

    <section class="section-heading">
      <h2>Research Metrics</h2>
      <span>{len(index.metrics)} rows</span>
    </section>
    {_dashboard_metric_table(metric_rows)}

    <table>
      <thead>
        <tr>
          <th>Experiment</th>
          <th>Kind</th>
          <th class="numeric">Results</th>
          <th class="numeric">Runs</th>
          <th>Load</th>
          <th>Artifacts</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody id="experiments">
{rows}
      </tbody>
    </table>
    <div id="empty" class="empty">No experiments match the current filters.</div>

    <section class="section-heading">
      <h2>Recent Runs</h2>
      <span>{min(len(index.runs), RECENT_RUN_LIMIT)} of {index.run_count}</span>
    </section>
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Experiment</th>
          <th>Variant</th>
          <th>Artifacts</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
{run_rows}
      </tbody>
    </table>
  </main>
  <script>
{DASHBOARD_SCRIPT}
  </script>
</body>
</html>
"""


def render_run_detail_page(
    run: RunArtifactIndexEntry,
    *,
    artifacts_dir: Path,
    output_path: Path,
    dashboard_path: Path | None = None,
) -> str:
    events = _load_trace_events(run, artifacts_dir)
    failed_events = [event for event in events if _is_failure_status(event.get("status"))]
    latency_ms = sum(
        value for event in events if isinstance((value := event.get("latency_ms")), int | float)
    )
    nodes = sorted(
        {str(event.get("node_name")) for event in events if event.get("node_name") is not None}
    )
    artifact_links = _run_detail_artifact_links(
        run,
        artifacts_dir=artifacts_dir,
        output_path=output_path,
    )
    back_link = (
        f'<a href="{escape(_relative_href(dashboard_path, output_path.parent))}">'
        "Back to dashboard</a>"
        if dashboard_path is not None
        else ""
    )
    timeline_rows = "\n".join(_trace_event_row(event) for event in events)
    retrieval_rows = "\n".join(
        _retrieval_context_row(context) for context in _trace_contexts(events)
    )
    target_rows = "\n".join(_context_target_row(target) for target in _trace_targets(events))
    diff_preview = _text_preview(run.diff_path, artifacts_dir=artifacts_dir, max_lines=140)
    stdout_preview = _text_preview(run.stdout_path, artifacts_dir=artifacts_dir, max_lines=80)
    stderr_preview = _text_preview(run.stderr_path, artifacts_dir=artifacts_dir, max_lines=80)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PatchSmith Run {escape(run.run_id)}</title>
  <style>
{RUN_DETAIL_STYLE}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="links">{back_link}</div>
      <h1>Run {escape(run.run_id)}</h1>
      <div class="meta">Experiment: {escape(run.experiment or "direct run")} | Variant: {escape(run.variant or "n/a")} | Updated: {escape(run.updated_at or "n/a")}</div>
      <div class="links">{artifact_links}</div>
    </header>

    <section class="summary" aria-label="Run summary">
      <div class="summary-cell"><span>Trace Events</span><strong>{len(events)}</strong></div>
      <div class="summary-cell"><span>Nodes</span><strong>{len(nodes)}</strong></div>
      <div class="summary-cell"><span>Failed Events</span><strong>{len(failed_events)}</strong></div>
      <div class="summary-cell"><span>Total Latency</span><strong>{_format_latency(latency_ms)}</strong></div>
    </section>

    <h2>Trace Timeline</h2>
    {_timeline_table(timeline_rows)}

    <h2>Retrieved Context</h2>
    {_retrieval_table(retrieval_rows)}

    <h2>Context Targets</h2>
    {_target_table(target_rows)}

    <h2>Diff Preview</h2>
    <pre>{escape(diff_preview or "No diff artifact found.")}</pre>

    <h2>Stdout Preview</h2>
    <pre>{escape(stdout_preview or "No stdout artifact found.")}</pre>

    <h2>Stderr Preview</h2>
    <pre>{escape(stderr_preview or "No stderr artifact found.")}</pre>
  </main>
</body>
</html>
"""


def _run_detail_artifact_links(
    run: RunArtifactIndexEntry,
    *,
    artifacts_dir: Path,
    output_path: Path,
) -> str:
    links = [
        _dashboard_link(
            "Report",
            run.report_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _dashboard_link(
            "Trace JSONL",
            run.trace_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _dashboard_link(
            "Final Diff",
            run.diff_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _dashboard_link(
            "Stdout",
            run.stdout_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _dashboard_link(
            "Stderr",
            run.stderr_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
    ]
    return " ".join(link for link in links if link)


def _trace_event_row(event: dict[str, Any]) -> str:
    status = str(event.get("status") or "")
    latency = event.get("latency_ms")
    return f"""        <tr>
          <td>{escape(str(event.get("node_name") or ""))}</td>
          <td>{escape(str(event.get("event_type") or ""))}</td>
          <td><span class="status {escape(status.lower())}">{escape(status)}</span></td>
          <td class="numeric">{escape(str(latency if latency is not None else ""))}</td>
          <td>{escape(str(event.get("input_summary") or ""))}</td>
          <td>{escape(str(event.get("output_summary") or ""))}</td>
          <td>{escape(str(event.get("error") or ""))}</td>
        </tr>"""


def _timeline_table(rows: str) -> str:
    if not rows:
        return '<div class="empty">No trace events found.</div>'
    return f"""<table>
      <thead>
        <tr>
          <th>Node</th>
          <th>Event</th>
          <th>Status</th>
          <th class="numeric">Latency ms</th>
          <th>Input</th>
          <th>Output</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>"""


def _trace_contexts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        raw_contexts = payload.get("contexts")
        if not isinstance(raw_contexts, list):
            continue
        for context in raw_contexts:
            if isinstance(context, dict):
                contexts.append(context)
    return contexts


def _retrieval_context_row(context: dict[str, Any]) -> str:
    score = context.get("score")
    score_text = f"{score:.2f}" if isinstance(score, int | float) else ""
    return f"""        <tr>
          <td class="numeric">{escape(str(context.get("rank") or ""))}</td>
          <td>{escape(str(context.get("path") or ""))}</td>
          <td>{escape(str(context.get("method") or ""))}</td>
          <td class="numeric">{escape(score_text)}</td>
          <td>{escape(_joined(context.get("matched_terms")))}</td>
        </tr>"""


def _retrieval_table(rows: str) -> str:
    if not rows:
        return '<div class="empty">No retrieved context entries found.</div>'
    return f"""<table>
      <thead>
        <tr>
          <th class="numeric">Rank</th>
          <th>Path</th>
          <th>Method</th>
          <th class="numeric">Score</th>
          <th>Matched Terms</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>"""


def _trace_targets(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        provider = payload.get("provider")
        for key in ("targets", "related_tests"):
            raw_targets = payload.get(key)
            if not isinstance(raw_targets, list):
                continue
            for target in raw_targets:
                if isinstance(target, dict):
                    with_provider = dict(target)
                    with_provider["provider"] = provider
                    with_provider["target_kind"] = key
                    targets.append(with_provider)
    return targets


def _context_target_row(target: dict[str, Any]) -> str:
    confidence = target.get("confidence")
    confidence_text = f"{confidence:.2f}" if isinstance(confidence, int | float) else ""
    return f"""        <tr>
          <td>{escape(str(target.get("provider") or ""))}</td>
          <td>{escape(str(target.get("target_kind") or ""))}</td>
          <td>{escape(str(target.get("role") or ""))}</td>
          <td class="numeric">{escape(str(target.get("rank") or ""))}</td>
          <td class="numeric">{escape(confidence_text)}</td>
          <td>{escape(str(target.get("path") or ""))}</td>
          <td>{escape(str(target.get("reason") or ""))}</td>
        </tr>"""


def _target_table(rows: str) -> str:
    if not rows:
        return '<div class="empty">No context broker targets found.</div>'
    return f"""<table>
      <thead>
        <tr>
          <th>Provider</th>
          <th>Kind</th>
          <th>Role</th>
          <th class="numeric">Rank</th>
          <th class="numeric">Confidence</th>
          <th>Path</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>"""


def _dashboard_row(
    entry: ExperimentArtifactIndexEntry,
    *,
    max_result_count: int,
    max_run_count: int,
    artifacts_dir: Path,
    output_path: Path | None,
) -> str:
    result_count = entry.result_count or 0
    result_width = _bar_width(result_count, max_result_count)
    run_width = _bar_width(entry.run_count, max_run_count)
    links = " ".join(
        link
        for link in (
            _dashboard_link(
                "Report",
                entry.report_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Summary",
                entry.summary_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Results",
                entry.results_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
        )
        if link
    )
    return f"""        <tr data-name="{escape(entry.name.lower())}" data-kind="{escape(entry.kind)}">
          <td><strong>{escape(entry.name)}</strong></td>
          <td><span class="kind">{escape(entry.kind)}</span></td>
          <td class="numeric">{_format_int(result_count)}</td>
          <td class="numeric">{_format_int(entry.run_count)}</td>
          <td>
            <div class="bars">
              <div class="bar-label"><span>results</span><span>{_format_int(result_count)}</span></div>
              <div class="bar-track"><div class="bar-fill" style="width: {result_width}%"></div></div>
              <div class="bar-label"><span>runs</span><span>{_format_int(entry.run_count)}</span></div>
              <div class="bar-track"><div class="bar-fill runs" style="width: {run_width}%"></div></div>
            </div>
          </td>
          <td><div class="links">{links}</div></td>
          <td>{escape(entry.updated_at or "")}</td>
        </tr>"""


def _dashboard_run_row(
    run: RunArtifactIndexEntry,
    *,
    artifacts_dir: Path,
    output_path: Path | None,
    run_detail_output_dir: Path | None = None,
) -> str:
    links = " ".join(
        link
        for link in (
            _run_detail_link(
                run,
                run_detail_output_dir=run_detail_output_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Report",
                run.report_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Trace",
                run.trace_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Diff",
                run.diff_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Stdout",
                run.stdout_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
            _dashboard_link(
                "Stderr",
                run.stderr_path,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
            ),
        )
        if link
    )
    return f"""        <tr>
          <td><strong>{escape(run.run_id)}</strong></td>
          <td>{escape(run.experiment or "")}</td>
          <td>{escape(run.variant or "")}</td>
          <td><div class="links">{links}</div></td>
          <td>{escape(run.updated_at or "")}</td>
        </tr>"""


def _run_detail_link(
    run: RunArtifactIndexEntry,
    *,
    run_detail_output_dir: Path | None,
    output_path: Path | None,
) -> str:
    if run_detail_output_dir is None:
        return ""
    detail_path = _run_detail_output_path(run_detail_output_dir, run)
    href = (
        _relative_href(detail_path, output_path.parent)
        if output_path is not None
        else str(detail_path)
    )
    return f'<a href="{escape(href)}">Detail</a>'


def _dashboard_link(
    label: str,
    path: str | None,
    *,
    artifacts_dir: Path,
    output_path: Path | None,
) -> str:
    if path is None:
        return ""
    href = _dashboard_href(path, artifacts_dir=artifacts_dir, output_path=output_path)
    return f'<a href="{escape(href)}">{escape(label)}</a>'


def _dashboard_href(
    path: str,
    *,
    artifacts_dir: Path,
    output_path: Path | None,
) -> str:
    if output_path is None:
        return path
    target = artifacts_dir / path
    try:
        return _relative_href(target, output_path.parent.resolve())
    except ValueError:
        return path


def _bar_width(value: int, maximum: int) -> str:
    if value <= 0 or maximum <= 0:
        return "0"
    return f"{(value / maximum) * 100:.1f}"


def _dashboard_metric_table(rows: str) -> str:
    if not rows:
        return '<div class="empty">No normalized experiment metrics found.</div>'
    return f"""<table>
      <thead>
        <tr>
          <th>Experiment</th>
          <th>Kind</th>
          <th>Lane</th>
          <th class="numeric">Tasks</th>
          <th>Primary</th>
          <th>Secondary</th>
          <th class="numeric">Latency</th>
          <th class="numeric">Cost</th>
          <th>Risk</th>
          <th>Report</th>
        </tr>
      </thead>
      <tbody id="metrics">
{rows}
      </tbody>
    </table>
    <div id="metrics-empty" class="empty">No metrics match the current filters.</div>"""


def _dashboard_metric_row(
    metric: ExperimentMetricIndexEntry,
    *,
    artifacts_dir: Path,
    output_path: Path | None,
) -> str:
    report_link = _dashboard_link(
        "Report",
        metric.report_path,
        artifacts_dir=artifacts_dir,
        output_path=output_path,
    )
    latency = _format_latency(metric.avg_latency_ms) if metric.avg_latency_ms is not None else ""
    data_name = f"{metric.experiment} {metric.lane}".lower()
    return f"""        <tr data-name="{escape(data_name)}" data-kind="{escape(metric.kind)}">
          <td><strong>{escape(metric.experiment)}</strong></td>
          <td><span class="kind">{escape(metric.kind)}</span></td>
          <td>{escape(metric.lane)}</td>
          <td class="numeric">{escape(_metric_task_count(metric))}</td>
          <td>{escape(_format_metric_pair(metric.primary_label, metric.primary_value))}</td>
          <td>{escape(_format_metric_pair(metric.secondary_label, metric.secondary_value))}</td>
          <td class="numeric">{escape(latency)}</td>
          <td class="numeric">{escape(_format_cost(metric.estimated_cost_usd))}</td>
          <td>{escape(metric.risk_note or "")}</td>
          <td><div class="links">{report_link}</div></td>
        </tr>"""
