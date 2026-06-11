from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html import escape
from os.path import relpath
from pathlib import Path
from typing import Any

REPORT_FILENAMES = (
    "report.md",
    "repair_report.md",
    "validation_report.md",
    "scaffold_report.md",
    "patch_search_report.md",
)
SUMMARY_FILENAMES = (
    "summary.json",
    "repair_summary.json",
    "validation_summary.json",
    "scaffold_results.json",
    "patch_search_summary.json",
)
RESULT_FILENAMES = (
    "results.json",
    "repair_results.json",
    "validation_results.json",
    "scaffold_results.json",
    "patch_search_results.json",
)
RECENT_RUN_LIMIT = 25
GENERATED_EXPERIMENT_DIR_NAMES = {"run-details", "run_details"}


@dataclass(frozen=True)
class ExperimentArtifactIndexEntry:
    name: str
    kind: str
    report_path: str | None
    summary_path: str | None
    results_path: str | None
    result_count: int | None
    run_count: int
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunArtifactIndexEntry:
    run_id: str
    experiment: str | None
    variant: str | None
    report_path: str | None
    trace_path: str | None
    diff_path: str | None
    stdout_path: str | None
    stderr_path: str | None
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentMetricIndexEntry:
    experiment: str
    kind: str
    lane: str
    task_count: int | None
    completed_count: int | None
    primary_label: str
    primary_value: int | float | str | None
    secondary_label: str | None
    secondary_value: int | float | str | None
    avg_latency_ms: float | None
    estimated_cost_usd: float | None
    risk_note: str | None
    report_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactIndex:
    artifacts_dir: str
    generated_at: str
    experiment_count: int
    run_count: int
    experiments: list[ExperimentArtifactIndexEntry]
    metrics: list[ExperimentMetricIndexEntry]
    runs: list[RunArtifactIndexEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "experiments": [entry.to_dict() for entry in self.experiments],
            "metrics": [entry.to_dict() for entry in self.metrics],
            "runs": [run.to_dict() for run in self.runs],
        }


@dataclass(frozen=True)
class FailureRunInsight:
    run_id: str
    experiment: str | None
    variant: str | None
    updated_at: str | None
    report_path: str | None
    trace_path: str | None
    diff_path: str | None
    failure_category: str
    verdict: str | None
    status: str | None
    summary: str
    next_action: str
    patch_generated: bool | None
    tests_passed: bool | None
    test_exit_code: int | None
    failed_event_count: int
    failed_nodes: list[str]
    trace_event_count: int
    total_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailureArtifactReport:
    artifacts_dir: str
    generated_at: str
    runs_scanned: int
    runs_requiring_attention: int
    failed_event_count: int
    category_counts: dict[str, int]
    insights: list[FailureRunInsight]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "runs_scanned": self.runs_scanned,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failed_event_count": self.failed_event_count,
            "category_counts": self.category_counts,
            "insights": [insight.to_dict() for insight in self.insights],
        }


def build_artifact_index(*, artifacts_dir: Path) -> ArtifactIndex:
    artifacts_dir = artifacts_dir.resolve()
    experiments_dir = artifacts_dir / "experiments"
    entries: list[ExperimentArtifactIndexEntry] = []
    metrics: list[ExperimentMetricIndexEntry] = []
    if experiments_dir.exists():
        for experiment_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
            if experiment_dir.name in GENERATED_EXPERIMENT_DIR_NAMES:
                continue
            report_path = _first_existing(experiment_dir, REPORT_FILENAMES)
            summary_path = _first_existing(experiment_dir, SUMMARY_FILENAMES)
            results_path = _first_existing(experiment_dir, RESULT_FILENAMES)
            kind = _experiment_kind(experiment_dir.name, report_path)
            entry = ExperimentArtifactIndexEntry(
                name=experiment_dir.name,
                kind=kind,
                report_path=_relative_or_none(artifacts_dir, report_path),
                summary_path=_relative_or_none(artifacts_dir, summary_path),
                results_path=_relative_or_none(artifacts_dir, results_path),
                result_count=_result_count(results_path),
                run_count=_experiment_run_count(experiment_dir),
                updated_at=_updated_at(
                    experiment_dir,
                    report_path,
                    summary_path,
                    results_path,
                ),
            )
            entries.append(entry)
            metrics.extend(
                _experiment_metric_entries(
                    experiment=experiment_dir.name,
                    kind=kind,
                    report_path=entry.report_path,
                    summary_path=summary_path,
                    results_path=results_path,
                )
            )

    runs = _discover_runs(artifacts_dir)
    return ArtifactIndex(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_timestamp(datetime.now(UTC).timestamp()),
        experiment_count=len(entries),
        run_count=len(runs),
        experiments=entries,
        metrics=metrics,
        runs=runs,
    )


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


def write_artifact_index(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    html_output_path: Path | None = None,
    run_detail_output_dir: Path | None = None,
) -> ArtifactIndex:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    if run_detail_output_dir is not None:
        write_run_detail_pages(
            index=index,
            output_dir=run_detail_output_dir,
            dashboard_path=html_output_path,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_artifact_index(
            index,
            run_detail_output_dir=run_detail_output_dir,
        ),
        encoding="utf-8",
    )
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(index.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    if html_output_path is not None:
        html_output_path.parent.mkdir(parents=True, exist_ok=True)
        html_output_path.write_text(
            render_artifact_dashboard(
                index,
                output_path=html_output_path,
                run_detail_output_dir=run_detail_output_dir,
            ),
            encoding="utf-8",
        )
    return index


def write_run_detail_pages(
    *,
    index: ArtifactIndex,
    output_dir: Path,
    dashboard_path: Path | None = None,
    limit: int = RECENT_RUN_LIMIT,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in output_dir.glob("*.html"):
        stale_path.unlink()
    written: list[Path] = []
    artifacts_dir = Path(index.artifacts_dir)
    for run in index.runs[:limit]:
        output_path = _run_detail_output_path(output_dir, run)
        output_path.write_text(
            render_run_detail_page(
                run,
                artifacts_dir=artifacts_dir,
                output_path=output_path,
                dashboard_path=dashboard_path,
            ),
            encoding="utf-8",
        )
        written.append(output_path)
    return written


def render_artifact_index(
    index: ArtifactIndex,
    *,
    run_detail_output_dir: Path | None = None,
) -> str:
    lines = [
        "# PatchSmith Artifact Index",
        "",
        f"- Generated at: `{index.generated_at}`",
        f"- Artifacts directory: `{index.artifacts_dir}`",
        f"- Experiment count: `{index.experiment_count}`",
        f"- Run count: `{index.run_count}`",
        "",
        "## Experiments",
        "",
        ("| Experiment | Kind | Report | Summary | Results | Result Count | Runs | Updated |"),
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for entry in index.experiments:
        lines.append(
            "| "
            f"{entry.name} | "
            f"{entry.kind} | "
            f"{_markdown_path(entry.report_path)} | "
            f"{_markdown_path(entry.summary_path)} | "
            f"{_markdown_path(entry.results_path)} | "
            f"{entry.result_count if entry.result_count is not None else ''} | "
            f"{entry.run_count} | "
            f"{entry.updated_at or ''} |"
        )
    lines.extend(
        [
            "",
            f"## Research Metrics ({len(index.metrics)})",
            "",
            (
                "| Experiment | Kind | Lane | Tasks | Primary | Secondary | "
                "Latency | Cost | Risk | Report |"
            ),
            "|---|---|---|---:|---|---|---:|---:|---|---|",
        ]
    )
    for metric in index.metrics:
        lines.append(
            "| "
            f"{metric.experiment} | "
            f"{metric.kind} | "
            f"{metric.lane} | "
            f"{_metric_task_count(metric)} | "
            f"{_format_metric_pair(metric.primary_label, metric.primary_value)} | "
            f"{_format_metric_pair(metric.secondary_label, metric.secondary_value)} | "
            f"{_format_latency(metric.avg_latency_ms) if metric.avg_latency_ms is not None else ''} | "
            f"{_format_cost(metric.estimated_cost_usd)} | "
            f"{metric.risk_note or ''} | "
            f"{_markdown_path(metric.report_path)} |"
        )
    lines.extend(
        [
            "",
            f"## Recent Runs ({min(len(index.runs), RECENT_RUN_LIMIT)} of {len(index.runs)})",
            "",
            (
                "| Run | Experiment | Variant | Detail | Report | Trace | Diff | "
                "Stdout | Stderr | Updated |"
            ),
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in index.runs[:RECENT_RUN_LIMIT]:
        lines.append(
            "| "
            f"{run.run_id} | "
            f"{run.experiment or ''} | "
            f"{run.variant or ''} | "
            f"{_markdown_path(_run_detail_relative_path(index, run, run_detail_output_dir))} | "
            f"{_markdown_path(run.report_path)} | "
            f"{_markdown_path(run.trace_path)} | "
            f"{_markdown_path(run.diff_path)} | "
            f"{_markdown_path(run.stdout_path)} | "
            f"{_markdown_path(run.stderr_path)} | "
            f"{run.updated_at or ''} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This index is generated from saved local artifacts.",
            "- Reports remain the source of truth for metrics and decision notes.",
            "- Source-bearing raw context artifacts are not copied into this index.",
            "",
        ]
    )
    return "\n".join(lines)


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
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #606b7a;
      --line: #d9dee7;
      --accent: #147d75;
      --accent-2: #945f00;
      --accent-3: #8d3c61;
      --table: #fbfcfd;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.45;
      letter-spacing: 0;
      color: var(--text);
      background: var(--bg);
    }}
    .shell {{
      width: min(1280px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      font-weight: 720;
      line-height: 1.1;
    }}
    .meta {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin: 18px 0;
      border: 1px solid var(--line);
      background: var(--line);
    }}
    .summary-cell {{
      min-height: 84px;
      padding: 14px 16px;
      background: var(--panel);
    }}
    .summary-cell span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .summary-cell strong {{
      display: block;
      margin-top: 8px;
      font-size: 26px;
      line-height: 1.1;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(240px, 1fr) 180px;
      gap: 12px;
      margin: 18px 0 12px;
    }}
    input,
    select {{
      min-height: 40px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--text);
      background: var(--panel);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    th,
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
      background: var(--table);
      white-space: nowrap;
    }}
    td.numeric,
    th.numeric {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    .kind {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f7faf9;
      color: #145f59;
      font-size: 12px;
      white-space: nowrap;
    }}
    .bars {{
      display: grid;
      gap: 6px;
      min-width: 150px;
    }}
    .bar-track {{
      height: 8px;
      background: #edf0f4;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: var(--accent);
    }}
    .bar-fill.runs {{ background: var(--accent-2); }}
    .bar-label {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
    }}
    .section-heading {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      margin: 28px 0 10px;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
    }}
    .section-heading span {{
      color: var(--muted);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }}
    .empty {{
      display: none;
      padding: 24px;
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 0;
    }}
    @media (max-width: 820px) {{
      .shell {{ width: min(100% - 20px, 1280px); padding-top: 14px; }}
      header {{ grid-template-columns: 1fr; align-items: start; }}
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .toolbar {{ grid-template-columns: 1fr; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
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
    const search = document.getElementById("search");
    const kind = document.getElementById("kind");
    const experimentRows = Array.from(document.querySelectorAll("#experiments tr"));
    const metricRows = Array.from(document.querySelectorAll("#metrics tr"));
    const empty = document.getElementById("empty");
    const metricsEmpty = document.getElementById("metrics-empty");
    function filterRows(rows, emptyElement, needle, selectedKind) {{
      let visible = 0;
      for (const row of rows) {{
        const matchesText = !needle || row.dataset.name.includes(needle);
        const matchesKind = !selectedKind || row.dataset.kind === selectedKind;
        const show = matchesText && matchesKind;
        row.hidden = !show;
        if (show) visible += 1;
      }}
      emptyElement.style.display = visible ? "none" : "block";
    }}
    function applyFilters() {{
      const needle = search.value.trim().toLowerCase();
      const selectedKind = kind.value;
      filterRows(metricRows, metricsEmpty, needle, selectedKind);
      filterRows(experimentRows, empty, needle, selectedKind);
    }}
    search.addEventListener("input", applyFilters);
    kind.addEventListener("change", applyFilters);
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
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #606b7a;
      --line: #d9dee7;
      --accent: #147d75;
      --warn: #945f00;
      --bad: #a53d47;
      --code: #f1f4f8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.45;
      letter-spacing: 0;
      color: var(--text);
      background: var(--bg);
    }}
    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }}
    header {{
      display: grid;
      gap: 10px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      font-size: 26px;
      line-height: 1.15;
      font-weight: 720;
      overflow-wrap: anywhere;
    }}
    h2 {{
      margin: 26px 0 10px;
      font-size: 18px;
      line-height: 1.2;
    }}
    .meta,
    .links {{
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
    }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin: 18px 0;
      border: 1px solid var(--line);
      background: var(--line);
    }}
    .summary-cell {{
      min-height: 80px;
      padding: 14px 16px;
      background: var(--panel);
    }}
    .summary-cell span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .summary-cell strong {{
      display: block;
      margin-top: 8px;
      font-size: 24px;
      line-height: 1.1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    th,
    td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      white-space: nowrap;
    }}
    td.numeric {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .status {{
      display: inline-flex;
      min-height: 23px;
      align-items: center;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: #145f59;
      background: #f7faf9;
      font-size: 12px;
      white-space: nowrap;
    }}
    .status.failed,
    .status.error {{
      color: var(--bad);
      background: #fff5f5;
    }}
    .empty {{
      padding: 16px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
    }}
    pre {{
      margin: 0;
      padding: 14px;
      overflow: auto;
      border: 1px solid var(--line);
      background: var(--code);
      font-size: 13px;
      line-height: 1.45;
      max-height: 560px;
    }}
    @media (max-width: 820px) {{
      .shell {{ width: min(100% - 20px, 1180px); padding-top: 14px; }}
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
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


def _failure_run_insight(
    run: RunArtifactIndexEntry,
    *,
    artifacts_dir: Path,
) -> FailureRunInsight | None:
    events = _load_trace_events(run, artifacts_dir)
    failed_events = [event for event in events if _is_failure_status(event.get("status"))]
    outcome = _last_repair_outcome_event(events)
    outcome_payload = (
        outcome.get("payload")
        if outcome is not None and isinstance(outcome.get("payload"), dict)
        else {}
    )
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


def _compact_markdown_cell(value: str, *, max_chars: int = 160) -> str:
    normalized = " ".join(value.replace("|", "/").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


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


def _text_preview(
    path: str | None,
    *,
    artifacts_dir: Path,
    max_lines: int,
) -> str:
    if path is None:
        return ""
    try:
        lines = (artifacts_dir / path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    preview = lines[:max_lines]
    if len(lines) > max_lines:
        preview.append(f"... truncated {len(lines) - max_lines} lines ...")
    return "\n".join(preview)


def _joined(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _format_latency(latency_ms: float) -> str:
    if latency_ms >= 1000:
        return f"{latency_ms / 1000:.1f}s"
    return f"{latency_ms:.0f}ms"


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


def _bar_width(value: int, maximum: int) -> str:
    if value <= 0 or maximum <= 0:
        return "0"
    return f"{(value / maximum) * 100:.1f}"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _experiment_metric_entries(
    *,
    experiment: str,
    kind: str,
    report_path: str | None,
    summary_path: Path | None,
    results_path: Path | None,
) -> list[ExperimentMetricIndexEntry]:
    payload = _load_json(summary_path)
    if payload is None and summary_path != results_path:
        payload = _load_json(results_path)
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        return []

    metrics: list[ExperimentMetricIndexEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric = _metric_entry_from_row(
            experiment=experiment,
            kind=kind,
            report_path=report_path,
            row=row,
        )
        if metric is not None:
            metrics.append(metric)
    return metrics


def _metric_entry_from_row(
    *,
    experiment: str,
    kind: str,
    report_path: str | None,
    row: dict[str, Any],
) -> ExperimentMetricIndexEntry | None:
    if "avg_top5_touched_recall" in row:
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(row.get("provider") or "provider"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Top-5 Recall",
            primary_value=_number_or_none(row.get("avg_top5_touched_recall")),
            secondary_label="Related Tests",
            secondary_value=_number_or_none(row.get("avg_related_test_recall")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=None,
            risk_note=_count_note(
                (
                    (_int_or_none(row.get("failed_tasks")), "failed"),
                    (_int_or_none(row.get("fallback_count")), "fallback"),
                    (
                        _int_or_none(row.get("source_free_violation_count")),
                        "source-free violations",
                    ),
                )
            ),
            report_path=report_path,
        )

    if "targeted_test_pass_rate" in row:
        lane = row.get("scaffold") or "/".join(
            str(value)
            for value in (
                row.get("runtime"),
                row.get("planner"),
                row.get("context_provider"),
            )
            if value
        )
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(lane or "repair"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Targeted Tests Passed",
            primary_value=_number_or_none(row.get("targeted_test_pass_rate")),
            secondary_label="Patch Generated",
            secondary_value=_number_or_none(row.get("patch_generated_rate")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=_number_or_none(row.get("estimated_cost_usd")),
            risk_note=_count_note(
                (
                    (_incomplete_count(row), "incomplete"),
                    (
                        _int_or_none(row.get("failed_trace_event_count")),
                        "failed trace events",
                    ),
                )
            ),
            report_path=report_path,
        )

    if "success_at_k_rate" in row:
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=str(row.get("variant") or "patch_search"),
            task_count=_int_or_none(row.get("attempted_tasks")),
            completed_count=_int_or_none(row.get("completed_tasks")),
            primary_label="Success@k",
            primary_value=_number_or_none(row.get("success_at_k_rate")),
            secondary_label="Avg Test Runs",
            secondary_value=_number_or_none(row.get("avg_test_runs")),
            avg_latency_ms=_number_or_none(row.get("avg_latency_ms")),
            estimated_cost_usd=_number_or_none(row.get("estimated_cost_usd")),
            risk_note=_count_note(((_incomplete_count(row), "incomplete"),)),
            report_path=report_path,
        )

    if "valid_tasks" in row and "task_count" in row:
        task_count = _int_or_none(row.get("task_count"))
        valid_tasks = _int_or_none(row.get("valid_tasks"))
        valid_rate = valid_tasks / task_count if valid_tasks is not None and task_count else None
        return ExperimentMetricIndexEntry(
            experiment=experiment,
            kind=kind,
            lane=Path(str(row.get("dataset_dir") or experiment)).name,
            task_count=task_count,
            completed_count=valid_tasks,
            primary_label="Valid Tasks",
            primary_value=valid_rate,
            secondary_label="Errors",
            secondary_value=_int_or_none(row.get("error_count")),
            avg_latency_ms=None,
            estimated_cost_usd=None,
            risk_note=_count_note(
                (
                    (_int_or_none(row.get("invalid_tasks")), "invalid"),
                    (_int_or_none(row.get("warning_count")), "warnings"),
                )
            ),
            report_path=report_path,
        )

    return None


def _load_json(path: Path | None) -> Any:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _metric_task_count(metric: ExperimentMetricIndexEntry) -> str:
    if metric.task_count is None:
        return ""
    if metric.completed_count is None:
        return _format_int(metric.task_count)
    return f"{_format_int(metric.completed_count)}/{_format_int(metric.task_count)}"


def _format_metric_pair(label: str | None, value: int | float | str | None) -> str:
    if not label:
        return ""
    if value is None:
        return label
    return f"{label}: {_format_metric_value(label, value)}"


def _format_metric_value(label: str, value: int | float | str) -> str:
    if not isinstance(value, int | float):
        return str(value)
    normalized = label.lower()
    if any(
        token in normalized
        for token in (
            "recall",
            "related tests",
            "passed",
            "generated",
            "success",
            "valid",
        )
    ):
        return f"{value * 100:.0f}%"
    if isinstance(value, int):
        return _format_int(value)
    return f"{value:.1f}"


def _format_cost(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:.4f}" if 0 < value < 0.01 else f"${value:.2f}"


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


def _count_note(counts: tuple[tuple[int | None, str], ...]) -> str | None:
    parts = [f"{count} {label}" for count, label in counts if count is not None]
    return "; ".join(parts) if parts else None


def _incomplete_count(row: dict[str, Any]) -> int | None:
    attempted = _int_or_none(row.get("attempted_tasks"))
    completed = _int_or_none(row.get("completed_tasks"))
    if attempted is None or completed is None:
        return None
    return max(0, attempted - completed)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


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
    paths: list[Path | None],
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
