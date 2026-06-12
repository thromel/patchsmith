"""HTML rendering for individual PatchSmith run details."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from patchsmith.observability.discovery import (
    _is_failure_status,
    _load_trace_events,
    _relative_href,
)
from patchsmith.observability.models import RunArtifactIndexEntry
from patchsmith.observability.render_html_assets import RUN_DETAIL_STYLE
from patchsmith.observability.render_md import (
    _format_latency,
    _joined,
    _text_preview,
)


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
        _run_artifact_link(
            "Report",
            run.report_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _run_artifact_link(
            "Trace JSONL",
            run.trace_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _run_artifact_link(
            "Final Diff",
            run.diff_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _run_artifact_link(
            "Stdout",
            run.stdout_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
        _run_artifact_link(
            "Stderr",
            run.stderr_path,
            artifacts_dir=artifacts_dir,
            output_path=output_path,
        ),
    ]
    return " ".join(link for link in links if link)


def _run_artifact_link(
    label: str,
    path: str | None,
    *,
    artifacts_dir: Path,
    output_path: Path,
) -> str:
    if path is None:
        return ""
    target = artifacts_dir / path
    try:
        href = _relative_href(target, output_path.parent.resolve())
    except ValueError:
        href = path
    return f'<a href="{escape(href)}">{escape(label)}</a>'


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


__all__ = ["render_run_detail_page"]
