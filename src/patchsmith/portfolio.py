from __future__ import annotations

import json
import subprocess
import struct
import zlib
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from patchsmith.observability import (
    ExperimentMetricIndexEntry,
    FailureArtifactReport,
    build_artifact_index,
    build_failure_report,
)


@dataclass(frozen=True)
class DemoReadinessGate:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoReadinessReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    experiment_count: int
    run_count: int
    metric_count: int
    runs_requiring_attention: int
    failure_categories: dict[str, int]
    model_providers: dict[str, int]
    gates: list[DemoReadinessGate]
    demo_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failure_categories": self.failure_categories,
            "model_providers": self.model_providers,
            "gates": [gate.to_dict() for gate in self.gates],
            "demo_commands": self.demo_commands,
        }


@dataclass(frozen=True)
class DemoScriptSection:
    title: str
    duration_seconds: int
    on_screen: str
    narration: str
    artifact: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoScriptReport:
    artifacts_dir: str
    generated_at: str
    target_duration_seconds: int
    readiness_status: str
    caveat: str
    sections: list[DemoScriptSection]
    rehearsal_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "target_duration_seconds": self.target_duration_seconds,
            "readiness_status": self.readiness_status,
            "caveat": self.caveat,
            "sections": [section.to_dict() for section in self.sections],
            "rehearsal_commands": self.rehearsal_commands,
        }


@dataclass(frozen=True)
class DemoMediaReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    width: int
    height: int
    markdown_path: str
    svg_path: str
    png_path: str
    highlights: list[str]
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalEvaluationMetric:
    experiment: str
    kind: str
    lane: str
    task_count: int | None
    completed_count: int | None
    primary_metric: str
    secondary_metric: str
    avg_latency_ms: float | None
    estimated_cost_usd: float | None
    risk_note: str | None
    report_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalEvaluationReport:
    artifacts_dir: str
    generated_at: str
    readiness_status: str
    experiment_count: int
    run_count: int
    metric_count: int
    runs_requiring_attention: int
    failure_categories: dict[str, int]
    model_providers: dict[str, int]
    metrics: list[FinalEvaluationMetric]
    decisions: list[str]
    limitations: list[str]
    review_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "experiment_count": self.experiment_count,
            "run_count": self.run_count,
            "metric_count": self.metric_count,
            "runs_requiring_attention": self.runs_requiring_attention,
            "failure_categories": self.failure_categories,
            "model_providers": self.model_providers,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "decisions": self.decisions,
            "limitations": self.limitations,
            "review_artifacts": self.review_artifacts,
        }


@dataclass(frozen=True)
class ReleaseHygieneCheck:
    name: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseHygieneReport:
    project_root: str
    artifacts_dir: str
    generated_at: str
    release_status: str
    passed_count: int
    warning_count: int
    blocked_count: int
    checks: list[ReleaseHygieneCheck]
    review_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifacts_dir": self.artifacts_dir,
            "generated_at": self.generated_at,
            "release_status": self.release_status,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocked_count": self.blocked_count,
            "checks": [check.to_dict() for check in self.checks],
            "review_artifacts": self.review_artifacts,
        }


def build_demo_readiness_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> DemoReadinessReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    failure_report = build_failure_report(
        artifacts_dir=artifacts_dir,
        max_runs=max_failure_runs,
    )
    model_providers = _discover_model_providers(Path(index.artifacts_dir))
    gates = _demo_readiness_gates(
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        metric_kinds={metric.kind for metric in index.metrics},
        failure_report=failure_report,
        model_providers=model_providers,
    )
    return DemoReadinessReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_now(),
        readiness_status=_readiness_status(gates),
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        runs_requiring_attention=failure_report.runs_requiring_attention,
        failure_categories=failure_report.category_counts,
        model_providers=model_providers,
        gates=gates,
        demo_commands=_demo_commands(),
    )


def build_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    project_root = project_root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    checks = _release_hygiene_checks(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        readiness=readiness,
    )
    status_counts = Counter(check.status for check in checks)
    return ReleaseHygieneReport(
        project_root=str(project_root),
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        release_status=_release_status(checks),
        passed_count=status_counts.get("passed", 0),
        warning_count=status_counts.get("warning", 0),
        blocked_count=status_counts.get("blocked", 0),
        checks=checks,
        review_artifacts=[
            "artifacts/experiments/index.html",
            "artifacts/experiments/failure_report.md",
            "artifacts/experiments/demo_readiness.md",
            "artifacts/experiments/demo_script.md",
            "artifacts/experiments/demo_media.svg",
            "artifacts/experiments/demo_media.png",
            "artifacts/experiments/final_evaluation.md",
            "artifacts/experiments/release_hygiene.md",
        ],
    )


def write_release_hygiene_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> ReleaseHygieneReport:
    report = build_release_hygiene_report(
        project_root=project_root,
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_release_hygiene_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_release_hygiene_report(report: ReleaseHygieneReport) -> str:
    lines = [
        "# PatchSmith Release Hygiene Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Release status: `{report.release_status}`",
        f"- Passed checks: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            _release_decision(report),
        ]
    )
    return "\n".join(lines) + "\n"


def build_final_evaluation_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    index = build_artifact_index(artifacts_dir=artifacts_dir)
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    metrics = [_final_metric(metric) for metric in index.metrics]
    return FinalEvaluationReport(
        artifacts_dir=index.artifacts_dir,
        generated_at=_utc_now(),
        readiness_status=readiness.readiness_status,
        experiment_count=index.experiment_count,
        run_count=index.run_count,
        metric_count=len(index.metrics),
        runs_requiring_attention=readiness.runs_requiring_attention,
        failure_categories=readiness.failure_categories,
        model_providers=readiness.model_providers,
        metrics=metrics,
        decisions=_final_evaluation_decisions(readiness, metrics),
        limitations=_final_evaluation_limitations(readiness),
        review_artifacts=_final_review_artifacts(),
    )


def write_final_evaluation_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> FinalEvaluationReport:
    report = build_final_evaluation_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_final_evaluation_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_final_evaluation_report(report: FinalEvaluationReport) -> str:
    lines = [
        "# PatchSmith Final Evaluation Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Experiment count: `{report.experiment_count}`",
        f"- Saved run count: `{report.run_count}`",
        f"- Normalized metric rows: `{report.metric_count}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        "",
        "## Executive Conclusion",
        "",
        _executive_conclusion(report),
        "",
        "## Metric Evidence",
        "",
        (
            "| Experiment | Kind | Lane | Tasks | Primary | Secondary | Latency | "
            "Cost | Risk Note | Report |"
        ),
        "|---|---|---|---:|---|---|---:|---:|---|---|",
    ]
    for metric in report.metrics:
        lines.append(
            "| "
            f"{metric.experiment} | "
            f"{metric.kind} | "
            f"{metric.lane} | "
            f"{_task_count_cell(metric)} | "
            f"{metric.primary_metric} | "
            f"{metric.secondary_metric} | "
            f"{_latency_cell(metric.avg_latency_ms)} | "
            f"{_cost_cell(metric.estimated_cost_usd)} | "
            f"{_markdown_cell(metric.risk_note or '')} | "
            f"{_path_cell(metric.report_path)} |"
        )

    lines.extend(["", "## Decisions", ""])
    for decision in report.decisions:
        lines.append(f"- {decision}")

    lines.extend(["", "## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")

    lines.extend(["", "## Review Artifacts", ""])
    for artifact in report.review_artifacts:
        lines.append(f"- `{artifact}`")

    lines.extend(
        [
            "",
            "## Public Claim Boundary",
            "",
            (
                "This report supports an offline seeded-suite portfolio demo. It does not "
                "claim live LLM quality unless saved artifacts include non-offline provider "
                "metadata and corresponding cost/token evidence."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def build_demo_script_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> DemoScriptReport:
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    sections = _demo_script_sections(readiness)
    return DemoScriptReport(
        artifacts_dir=readiness.artifacts_dir,
        generated_at=_utc_now(),
        target_duration_seconds=sum(section.duration_seconds for section in sections),
        readiness_status=readiness.readiness_status,
        caveat=_demo_script_caveat(readiness),
        sections=sections,
        rehearsal_commands=_demo_script_rehearsal_commands(),
    )


def build_demo_media_report(
    *,
    artifacts_dir: Path,
    markdown_path: Path,
    svg_path: Path,
    png_path: Path,
    max_failure_runs: int | None = None,
) -> DemoMediaReport:
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    highlights = [
        f"{readiness.experiment_count} experiments",
        f"{readiness.run_count} saved runs",
        f"{readiness.metric_count} metric rows",
        f"{readiness.runs_requiring_attention} runs requiring attention",
        f"providers: {_provider_summary(readiness.model_providers)}",
    ]
    return DemoMediaReport(
        artifacts_dir=str(Path(readiness.artifacts_dir)),
        generated_at=_utc_now(),
        readiness_status=readiness.readiness_status,
        width=1200,
        height=675,
        markdown_path=str(markdown_path),
        svg_path=str(svg_path),
        png_path=str(png_path),
        highlights=highlights,
        caveat=_demo_script_caveat(readiness),
    )


def write_demo_media_assets(
    *,
    artifacts_dir: Path,
    output_path: Path,
    svg_output_path: Path,
    png_output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoMediaReport:
    report = build_demo_media_report(
        artifacts_dir=artifacts_dir,
        markdown_path=output_path,
        svg_path=svg_output_path,
        png_path=png_output_path,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    svg_output_path.parent.mkdir(parents=True, exist_ok=True)
    png_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_media_report(report), encoding="utf-8")
    svg_output_path.write_text(render_demo_media_svg(report), encoding="utf-8")
    _write_demo_media_png(report, png_output_path)
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_media_report(report: DemoMediaReport) -> str:
    return "\n".join(
        [
            "# PatchSmith Demo Media",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Readiness status: `{report.readiness_status}`",
            f"- SVG asset: `{report.svg_path}`",
            f"- PNG asset: `{report.png_path}`",
            f"- Dimensions: `{report.width}x{report.height}`",
            f"- Caveat: {report.caveat}",
            "",
            "## Highlights",
            "",
            *[f"- {highlight}" for highlight in report.highlights],
            "",
            "## Usage",
            "",
            "Use the SVG for readable README or portfolio embedding. Use the PNG as a compact social or presentation preview.",
        ]
    ) + "\n"


def render_demo_media_svg(report: DemoMediaReport) -> str:
    highlight_items = "\n".join(
        (
            f'<text x="92" y="{258 + index * 54}" class="metric">'
            f"{escape(highlight)}</text>"
        )
        for index, highlight in enumerate(report.highlights)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{report.width}" height="{report.height}" viewBox="0 0 {report.width} {report.height}" role="img" aria-labelledby="title desc">
  <title id="title">PatchSmith demo summary</title>
  <desc id="desc">Portfolio demo summary generated from saved PatchSmith artifacts.</desc>
  <style>
    .bg {{ fill: #f7f8fa; }}
    .ink {{ fill: #1d2430; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    .muted {{ fill: #596579; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    .panel {{ fill: #ffffff; stroke: #d9dee7; stroke-width: 2; }}
    .accent {{ fill: #147d75; }}
    .warn {{ fill: #945f00; }}
    .title {{ font-size: 58px; font-weight: 760; }}
    .subtitle {{ font-size: 26px; }}
    .metric {{ fill: #1d2430; font-family: Inter, ui-sans-serif, system-ui, sans-serif; font-size: 30px; font-weight: 650; }}
    .small {{ font-size: 21px; }}
  </style>
  <rect class="bg" width="1200" height="675"/>
  <rect x="56" y="48" width="1088" height="579" rx="18" class="panel"/>
  <rect x="56" y="48" width="1088" height="122" rx="18" class="accent"/>
  <text x="92" y="125" class="ink title" fill="#ffffff">PatchSmith Research</text>
  <text x="94" y="207" class="muted subtitle">Issue-to-tested-patch agent lab with honest evaluation artifacts</text>
  {highlight_items}
  <rect x="676" y="244" width="380" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="314" width="460" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="384" width="325" height="40" rx="8" fill="#dcefed"/>
  <rect x="676" y="454" width="238" height="40" rx="8" fill="#f4e3bd"/>
  <text x="92" y="568" class="muted small">{escape(report.caveat)}</text>
  <text x="92" y="604" class="muted small">Open artifacts/experiments/demo_script.md to record the 3m10s walkthrough.</text>
</svg>
"""


def write_demo_script_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoScriptReport:
    report = build_demo_script_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_script_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_script_report(report: DemoScriptReport) -> str:
    lines = [
        "# PatchSmith Demo Script",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Target duration: `{_format_duration(report.target_duration_seconds)}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Caveat: {report.caveat}",
        "",
        "## Run Of Show",
        "",
        "| Segment | Duration | On Screen | Artifact |",
        "|---|---:|---|---|",
    ]
    for section in report.sections:
        lines.append(
            "| "
            f"{section.title} | "
            f"{_format_duration(section.duration_seconds)} | "
            f"{_markdown_cell(section.on_screen)} | "
            f"`{section.artifact}` |"
        )

    lines.extend(["", "## Narration", ""])
    for index, section in enumerate(report.sections, start=1):
        lines.extend(
            [
                f"### {index}. {section.title}",
                "",
                f"On screen: `{section.artifact}`",
                "",
                section.narration,
                "",
            ]
        )

    lines.extend(
        [
            "## Rehearsal Commands",
            "",
            "```bash",
            *report.rehearsal_commands,
            "```",
            "",
            "## Guardrails",
            "",
            "- Do not claim live LLM calibration unless the readiness report shows a non-offline provider.",
            "- Present failure cases as part of the research evidence, not as hidden defects.",
            "- Keep the demo on seeded or preselected repositories until public sandboxing is hardened.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_demo_readiness_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    max_failure_runs: int | None = None,
) -> DemoReadinessReport:
    report = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_readiness_report(report), encoding="utf-8")
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def render_demo_readiness_report(report: DemoReadinessReport) -> str:
    lines = [
        "# PatchSmith Demo Readiness Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Readiness status: `{report.readiness_status}`",
        f"- Experiment count: `{report.experiment_count}`",
        f"- Saved run count: `{report.run_count}`",
        f"- Normalized metric rows: `{report.metric_count}`",
        f"- Runs requiring attention: `{report.runs_requiring_attention}`",
        "",
        "## Gate Status",
        "",
        "| Gate | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for gate in report.gates:
        lines.append(
            "| "
            f"{gate.name} | "
            f"{gate.status} | "
            f"{_markdown_cell(gate.evidence)} | "
            f"{_markdown_cell(gate.next_action)} |"
        )

    lines.extend(["", "## Failure Categories", ""])
    if report.failure_categories:
        lines.extend(["| Category | Runs |", "|---|---:|"])
        for category, count in report.failure_categories.items():
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("No failure categories were found in the scanned run traces.")

    lines.extend(["", "## Model Provider Evidence", ""])
    if report.model_providers:
        lines.extend(["| Provider | Rows |", "|---|---:|"])
        for provider, count in report.model_providers.items():
            lines.append(f"| {provider} | {count} |")
    else:
        lines.append("No model-provider metadata was found in saved summaries/results.")

    lines.extend(
        [
            "",
            "## Reproducible Demo Commands",
            "",
            "Run these from the repository root after installing project dependencies.",
            "",
            "```bash",
            *report.demo_commands,
            "```",
            "",
            "## Review Path",
            "",
            "1. Open `artifacts/experiments/index.html` for metrics and run navigation.",
            "2. Open `artifacts/experiments/failure_report.md` to inspect failure cases.",
            "3. Use the scaffold and patch-search reports to explain quality versus cost.",
            "4. State clearly that current model evidence is offline unless live-provider rows exist.",
        ]
    )
    return "\n".join(lines) + "\n"


def _demo_readiness_gates(
    *,
    experiment_count: int,
    run_count: int,
    metric_count: int,
    metric_kinds: set[str],
    failure_report: FailureArtifactReport,
    model_providers: dict[str, int],
) -> list[DemoReadinessGate]:
    gates = [
        _gate(
            name="Experiment Evidence",
            passed=experiment_count >= 3,
            evidence=f"{experiment_count} experiment directories discovered.",
            missing_action="Run retrieval, scaffold, and patch-search evaluations.",
        ),
        _gate(
            name="Saved Run Artifacts",
            passed=run_count > 0,
            evidence=f"{run_count} saved run artifacts discovered.",
            missing_action="Run at least one seeded repair or scaffold evaluation.",
        ),
        _gate(
            name="Metrics Surface",
            passed=metric_count > 0,
            evidence=f"{metric_count} normalized metric rows discovered.",
            missing_action="Regenerate experiment summaries and artifact index.",
        ),
        _kind_gate(
            name="Retrieval Evidence",
            kind="retrieval",
            metric_kinds=metric_kinds,
            missing_action="Run `eval-retrieval` before demo review.",
        ),
        _kind_gate(
            name="Repair Or Scaffold Evidence",
            kind="repair",
            metric_kinds=metric_kinds,
            alternate_kind="scaffold",
            missing_action="Run `eval-repair` or `eval-scaffold` before demo review.",
        ),
        _kind_gate(
            name="Patch Search Evidence",
            kind="patch_search",
            metric_kinds=metric_kinds,
            missing_action="Run `eval-patch-search` before demo review.",
        ),
    ]
    if failure_report.runs_requiring_attention > 0:
        gates.append(
            DemoReadinessGate(
                name="Failure Visibility",
                status="passed",
                evidence=(
                    f"{failure_report.runs_requiring_attention} runs requiring attention "
                    "are visible in the failure report."
                ),
                next_action="Use failure cases in the demo narrative instead of hiding them.",
            )
        )
    else:
        gates.append(
            DemoReadinessGate(
                name="Failure Visibility",
                status="warning",
                evidence="No failure cases were found in saved run traces.",
                next_action="Add or preserve at least one failure example for public analysis.",
            )
        )
    live_providers = [
        provider
        for provider in model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        gates.append(
            DemoReadinessGate(
                name="Live LLM Calibration",
                status="passed",
                evidence=f"Live provider metadata found: {', '.join(live_providers)}.",
                next_action="Report cost and token usage next to quality metrics.",
            )
        )
    else:
        gates.append(
            DemoReadinessGate(
                name="Live LLM Calibration",
                status="warning",
                evidence="No non-offline model provider metadata found.",
                next_action=(
                    "Keep demo claims scoped to offline evidence or run a credential-gated "
                    "live-provider smoke test."
                ),
            )
        )
    return gates


def _gate(
    *,
    name: str,
    passed: bool,
    evidence: str,
    missing_action: str,
) -> DemoReadinessGate:
    return DemoReadinessGate(
        name=name,
        status="passed" if passed else "missing",
        evidence=evidence,
        next_action="No action needed for the current demo slice." if passed else missing_action,
    )


def _kind_gate(
    *,
    name: str,
    kind: str,
    metric_kinds: set[str],
    missing_action: str,
    alternate_kind: str | None = None,
) -> DemoReadinessGate:
    passed = kind in metric_kinds or (
        alternate_kind is not None and alternate_kind in metric_kinds
    )
    evidence_kind = (
        kind
        if kind in metric_kinds
        else alternate_kind if alternate_kind in metric_kinds else kind
    )
    return _gate(
        name=name,
        passed=passed,
        evidence=f"`{evidence_kind}` metric evidence {'found' if passed else 'missing'}.",
        missing_action=missing_action,
    )


def _readiness_status(gates: list[DemoReadinessGate]) -> str:
    statuses = {gate.status for gate in gates}
    if "missing" in statuses:
        return "not_ready"
    if "warning" in statuses:
        return "ready_with_caveats"
    return "ready"


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
            "demo_script.json",
            "demo_media.json",
            "final_evaluation.json",
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


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_demo_media_png(report: DemoMediaReport, output_path: Path) -> None:
    width = report.width
    height = report.height
    pixels = bytearray(_rgb("#f7f8fa") * width * height)
    _fill_rect(pixels, width, height, 56, 48, 1088, 579, _rgb("#ffffff"))
    _stroke_rect(pixels, width, height, 56, 48, 1088, 579, _rgb("#d9dee7"), 2)
    _fill_rect(pixels, width, height, 56, 48, 1088, 122, _rgb("#147d75"))
    _fill_rect(pixels, width, height, 92, 246, 456, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 316, 512, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 386, 398, 38, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 92, 456, 310, 38, _rgb("#f4e3bd"))
    _fill_rect(pixels, width, height, 676, 244, 380, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 314, 460, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 384, 325, 40, _rgb("#dcefed"))
    _fill_rect(pixels, width, height, 676, 454, 238, 40, _rgb("#f4e3bd"))
    _write_png(output_path, width, height, bytes(pixels))


def _write_png(path: Path, width: int, height: int, rgb_bytes: bytes) -> None:
    rows = bytearray()
    stride = width * 3
    for row in range(height):
        rows.append(0)
        start = row * stride
        rows.extend(rgb_bytes[start : start + stride])
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(payload)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: bytes,
) -> None:
    x_end = min(width, x + rect_width)
    y_end = min(height, y + rect_height)
    for row in range(max(0, y), y_end):
        for column in range(max(0, x), x_end):
            offset = (row * width + column) * 3
            pixels[offset : offset + 3] = color


def _stroke_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: bytes,
    thickness: int,
) -> None:
    _fill_rect(pixels, width, height, x, y, rect_width, thickness, color)
    _fill_rect(
        pixels,
        width,
        height,
        x,
        y + rect_height - thickness,
        rect_width,
        thickness,
        color,
    )
    _fill_rect(pixels, width, height, x, y, thickness, rect_height, color)
    _fill_rect(
        pixels,
        width,
        height,
        x + rect_width - thickness,
        y,
        thickness,
        rect_height,
        color,
    )


def _rgb(hex_color: str) -> bytes:
    normalized = hex_color.lstrip("#")
    return bytes(
        int(normalized[index : index + 2], 16)
        for index in range(0, 6, 2)
    )


def _release_hygiene_checks(
    *,
    project_root: Path,
    artifacts_dir: Path,
    readiness: DemoReadinessReport,
) -> list[ReleaseHygieneCheck]:
    required_docs = [
        "README.md",
        "docs/09_roadmap.md",
        "docs/12_release_and_portfolio_plan.md",
        "docs/17_sprint_plans.md",
        "docs/18_delivery_process.md",
        "docs/06_safety_and_sandboxing.md",
    ]
    required_artifacts = [
        "experiments/index.md",
        "experiments/index.json",
        "experiments/index.html",
        "experiments/failure_report.md",
        "experiments/failure_report.json",
        "experiments/demo_readiness.md",
        "experiments/demo_readiness.json",
        "experiments/demo_script.md",
        "experiments/demo_script.json",
        "experiments/final_evaluation.md",
        "experiments/final_evaluation.json",
    ]
    checks = [
        _path_check(
            name="Planning Docs",
            root=project_root,
            paths=required_docs,
            missing_action="Restore the missing planning, safety, release, or process docs.",
            blocked=True,
        ),
        _path_check(
            name="Generated Review Artifacts",
            root=artifacts_dir,
            paths=required_artifacts,
            missing_action="Regenerate index, failure, readiness, demo script, and final evaluation artifacts.",
            blocked=True,
        ),
        _release_check(
            name="Demo Readiness",
            status="passed" if readiness.readiness_status != "not_ready" else "blocked",
            evidence=(
                f"Readiness is {readiness.readiness_status}; "
                f"{readiness.experiment_count} experiments, {readiness.run_count} runs, "
                f"{readiness.metric_count} metric rows."
            ),
            next_action=(
                "Keep caveats visible in public claims."
                if readiness.readiness_status != "not_ready"
                else "Resolve missing readiness gates before launch."
            ),
        ),
        _release_check(
            name="Failure Visibility",
            status="passed" if readiness.runs_requiring_attention > 0 else "warning",
            evidence=(
                f"{readiness.runs_requiring_attention} runs requiring attention; "
                f"categories: {_failure_summary(readiness.failure_categories)}."
            ),
            next_action=(
                "Use failure cases in the final narrative."
                if readiness.runs_requiring_attention > 0
                else "Preserve at least one failure example for honest evaluation."
            ),
        ),
        _release_check(
            name="Live LLM Claim Boundary",
            status="warning"
            if not _live_providers(readiness.model_providers)
            else "passed",
            evidence=_provider_summary(readiness.model_providers),
            next_action=(
                "Do not claim live LLM calibration in release materials."
                if not _live_providers(readiness.model_providers)
                else "Report token usage and cost next to live-provider quality metrics."
            ),
        ),
        _git_repository_check(project_root),
        _release_check(
            name="CI Workflow",
            status="passed"
            if (project_root / ".github" / "workflows").exists()
            else "warning",
            evidence=(
                ".github/workflows exists."
                if (project_root / ".github" / "workflows").exists()
                else "No CI workflow directory found."
            ),
            next_action=(
                "Keep pytest and artifact checks in CI."
                if (project_root / ".github" / "workflows").exists()
                else "Add a CI workflow before public repository release."
            ),
        ),
        _release_check(
            name="Demo Media",
            status="passed" if _has_demo_media(project_root) else "warning",
            evidence=(
                "Demo media asset found."
                if _has_demo_media(project_root)
                else "No GIF, MP4, or screenshot asset found under docs, artifacts, or assets."
            ),
            next_action=(
                "Reference the media in README."
                if _has_demo_media(project_root)
                else "Capture a screenshot, GIF, or short video from the generated demo script."
            ),
        ),
        _release_check(
            name="Architecture Diagram Asset",
            status="passed" if _has_architecture_diagram(project_root) else "warning",
            evidence=(
                "Architecture diagram evidence found."
                if _has_architecture_diagram(project_root)
                else "No Mermaid block or diagram asset found in architecture surfaces."
            ),
            next_action=(
                "Keep diagram synchronized with architecture docs."
                if _has_architecture_diagram(project_root)
                else "Add a simple architecture diagram before public launch."
            ),
        ),
        _content_check(
            name="Public Claim Caveats",
            path=project_root / "README.md",
            needles=["ready_with_caveats", "offline", "live LLM calibration"],
            missing_action="Update README so live-provider and offline-demo caveats are visible.",
            blocked=False,
        ),
    ]
    return checks


def _path_check(
    *,
    name: str,
    root: Path,
    paths: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    missing = [path for path in paths if not (root / path).exists()]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    evidence = (
        f"Found {len(paths) - len(missing)}/{len(paths)} required paths."
        if missing
        else f"All {len(paths)} required paths found."
    )
    if missing:
        evidence += f" Missing: {', '.join(missing)}."
    return _release_check(
        name=name,
        status=status,
        evidence=evidence,
        next_action="No action needed." if not missing else missing_action,
    )


def _content_check(
    *,
    name: str,
    path: Path,
    needles: list[str],
    missing_action: str,
    blocked: bool,
) -> ReleaseHygieneCheck:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing = [needle for needle in needles if needle not in text]
    status = "blocked" if blocked and missing else "warning" if missing else "passed"
    return _release_check(
        name=name,
        status=status,
        evidence=(
            f"All {len(needles)} caveat markers found."
            if not missing
            else f"Missing markers: {', '.join(missing)}."
        ),
        next_action="No action needed." if not missing else missing_action,
    )


def _release_check(
    *,
    name: str,
    status: str,
    evidence: str,
    next_action: str,
) -> ReleaseHygieneCheck:
    return ReleaseHygieneCheck(
        name=name,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def _git_repository_check(project_root: Path) -> ReleaseHygieneCheck:
    if not (project_root / ".git").exists():
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="No .git directory found at project root.",
            next_action="Initialize or restore the Git repository before claiming a stable tagged release.",
        )

    head = _run_git(project_root, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence="Git repository exists but has no commit yet.",
            next_action="Create a verified baseline commit before claiming a stable tagged release.",
        )

    branch = _run_git(project_root, "branch", "--show-current")
    status = _run_git(project_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Could not inspect Git worktree: {status.stderr.strip() or status.stdout.strip()}",
            next_action="Fix Git metadata before claiming release readiness.",
        )
    if status.stdout.strip():
        changed_count = len([line for line in status.stdout.splitlines() if line.strip()])
        return _release_check(
            name="Git Repository",
            status="blocked",
            evidence=f"Git commit {head.stdout.strip()} has {changed_count} uncommitted file changes.",
            next_action="Commit, stash, or intentionally remove worktree changes before tagging a release.",
        )

    branch_name = branch.stdout.strip() or "detached HEAD"
    return _release_check(
        name="Git Repository",
        status="passed",
        evidence=f"Git commit {head.stdout.strip()} on {branch_name}; worktree clean.",
        next_action="Create a tag only after final verification.",
    )


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _release_status(checks: list[ReleaseHygieneCheck]) -> str:
    statuses = {check.status for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _release_decision(report: ReleaseHygieneReport) -> str:
    if report.release_status == "ready":
        return "Release hygiene is clean for the current scoped portfolio launch."
    if report.release_status == "ready_with_warnings":
        return (
            "Release hygiene has warnings. The offline demo can proceed if each warning "
            "is disclosed or deliberately deferred."
        )
    return (
        "Release hygiene is blocked. Resolve blocked checks before claiming a stable "
        "public or tagged release."
    )


def _live_providers(providers: dict[str, int]) -> list[str]:
    return [
        provider
        for provider in providers
        if provider and not provider.startswith("offline_")
    ]


def _has_demo_media(project_root: Path) -> bool:
    search_roots = [
        project_root / "docs",
        project_root / "artifacts",
        project_root / "assets",
    ]
    suffixes = {".gif", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}
    for root in search_roots:
        if not root.exists():
            continue
        if any(path.suffix.lower() in suffixes for path in root.rglob("*")):
            return True
    return False


def _has_architecture_diagram(project_root: Path) -> bool:
    architecture_path = project_root / "docs" / "03_architecture.md"
    try:
        architecture_text = architecture_path.read_text(encoding="utf-8")
    except OSError:
        architecture_text = ""
    if "```mermaid" in architecture_text:
        return True
    diagram_roots = [project_root / "docs", project_root / "assets"]
    suffixes = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
    for root in diagram_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if "arch" in path.name.lower() and path.suffix.lower() in suffixes:
                return True
    return False


def _final_metric(metric: ExperimentMetricIndexEntry) -> FinalEvaluationMetric:
    return FinalEvaluationMetric(
        experiment=metric.experiment,
        kind=metric.kind,
        lane=metric.lane,
        task_count=metric.task_count,
        completed_count=metric.completed_count,
        primary_metric=_metric_label_value(metric.primary_label, metric.primary_value),
        secondary_metric=_metric_label_value(
            metric.secondary_label,
            metric.secondary_value,
        ),
        avg_latency_ms=metric.avg_latency_ms,
        estimated_cost_usd=metric.estimated_cost_usd,
        risk_note=metric.risk_note,
        report_path=metric.report_path,
    )


def _metric_label_value(label: str | None, value: int | float | str | None) -> str:
    if label is None and value is None:
        return ""
    if label is None:
        return _metric_value("", value)
    return f"{label}: {_metric_value(label, value)}"


def _metric_value(label: str, value: int | float | str | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    normalized_label = label.lower()
    if "avg test runs" in normalized_label:
        if isinstance(value, int) or float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}"
    if any(
        token in normalized_label
        for token in (
            "recall",
            "related tests",
            "passed",
            "generated",
            "success",
            "valid",
        )
    ) and 0 <= value <= 1:
        return f"{value * 100:.0f}%"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _final_evaluation_decisions(
    readiness: DemoReadinessReport,
    metrics: list[FinalEvaluationMetric],
) -> list[str]:
    decisions = [
        (
            f"Portfolio evidence is `{readiness.readiness_status}` with "
            f"{readiness.experiment_count} experiments, {readiness.run_count} saved runs, "
            f"and {readiness.metric_count} normalized metric rows."
        ),
        (
            "Use the static dashboard, run-detail pages, failure report, readiness report, "
            "and demo script as the launch review surface before adding a hosted UI."
        ),
    ]
    retrieval_rows = [metric for metric in metrics if metric.kind == "retrieval"]
    if retrieval_rows:
        lanes = ", ".join(sorted({metric.lane for metric in retrieval_rows}))
        decisions.append(
            f"Retrieval evidence is available for these lanes: {lanes}."
        )
    repair_rows = [
        metric
        for metric in metrics
        if metric.kind in {"repair", "scaffold"}
        and "Targeted Tests Passed: 100%" in metric.primary_metric
    ]
    if repair_rows:
        lanes = ", ".join(sorted({metric.lane for metric in repair_rows}))
        decisions.append(
            f"Seeded repair/scaffold evidence shows targeted tests passing for: {lanes}."
        )
    patch_rows = [metric for metric in metrics if metric.kind == "patch_search"]
    if patch_rows:
        seen_test_run_lanes: set[str] = set()
        test_run_parts: list[str] = []
        for metric in patch_rows:
            if not metric.secondary_metric or metric.lane in seen_test_run_lanes:
                continue
            seen_test_run_lanes.add(metric.lane)
            test_run_parts.append(f"{metric.lane} {metric.secondary_metric}")
        test_runs = "; ".join(
            test_run_parts
        )
        decisions.append(
            "Patch-search evidence should be framed as a cost tradeoff; "
            f"current candidate lanes report {test_runs}."
        )
    if readiness.failure_categories:
        decisions.append(
            "Failure cases are preserved for review: "
            f"{_failure_summary(readiness.failure_categories)}."
        )
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        decisions.append(
            f"Live-provider evidence exists for {', '.join(live_providers)}; report cost "
            "and token usage next to any live-model quality claim."
        )
    else:
        decisions.append(
            "Do not claim live LLM calibration yet; saved provider metadata is offline-only."
        )
    return decisions


def _final_evaluation_limitations(readiness: DemoReadinessReport) -> list[str]:
    limitations = [
        "The seeded suite is intentionally small and controlled; it proves workflow plumbing and comparative instrumentation, not broad real-world coding-agent quality.",
        "Current public-demo mode should use seeded or preselected repositories until sandboxing is hardened for arbitrary untrusted repos.",
        "DeepAgents evidence is adapter compatibility evidence unless the optional package and live model provider are installed and reflected in saved artifacts.",
    ]
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if not live_providers:
        limitations.append(
            "No non-offline model provider metadata was found; live LLM quality, token use, and cost remain uncalibrated."
        )
    if readiness.runs_requiring_attention:
        limitations.append(
            f"{readiness.runs_requiring_attention} saved runs still require attention; use them as failure-analysis material, not as hidden exclusions."
        )
    return limitations


def _final_review_artifacts() -> list[str]:
    return [
        "artifacts/experiments/index.html",
        "artifacts/experiments/index.md",
        "artifacts/experiments/failure_report.md",
        "artifacts/experiments/demo_readiness.md",
        "artifacts/experiments/demo_script.md",
        "artifacts/experiments/demo_media.md",
        "artifacts/experiments/demo_media.svg",
        "artifacts/experiments/demo_media.png",
        "artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
        "artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
        "artifacts/experiments/retrieval_eval_v1/report.md",
    ]


def _executive_conclusion(report: FinalEvaluationReport) -> str:
    if report.readiness_status == "ready":
        return (
            "PatchSmith is ready for a portfolio demo with current saved evidence. "
            "Keep the demo scoped to the artifact set summarized here."
        )
    if report.readiness_status == "ready_with_caveats":
        return (
            "PatchSmith is ready for an offline portfolio demo with caveats. The saved "
            "artifacts support the issue-to-tested-patch research workflow, but live LLM "
            "calibration and arbitrary public execution should remain explicitly out of scope."
        )
    return (
        "PatchSmith is not ready for portfolio launch from the current saved artifacts; "
        "resolve the missing gates before recording a public demo."
    )


def _task_count_cell(metric: FinalEvaluationMetric) -> str:
    if metric.task_count is None:
        return ""
    if metric.completed_count is None:
        return str(metric.task_count)
    return f"{metric.completed_count}/{metric.task_count}"


def _latency_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.0f}ms"


def _cost_cell(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:.4f}"


def _path_cell(path: str | None) -> str:
    if path is None:
        return ""
    return f"`{path}`"


def _demo_commands() -> list[str]:
    return [
        "python3 -m pytest -q",
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-scaffold "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--variant agentless --variant heuristic --variant langgraph "
            "--variant langgraph_fake_model --variant deepagents "
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


def _demo_script_sections(readiness: DemoReadinessReport) -> list[DemoScriptSection]:
    failure_summary = _failure_summary(readiness.failure_categories)
    provider_summary = _provider_summary(readiness.model_providers)
    return [
        DemoScriptSection(
            title="Problem And Thesis",
            duration_seconds=25,
            on_screen="README project summary and architecture overview.",
            artifact="README.md",
            narration=(
                "PatchSmith is an AI software-maintenance agent and evaluation lab. "
                "The point of the demo is not a single lucky patch; it is a repeatable "
                "issue-to-tested-diff workflow with retrieval, orchestration, sandboxed "
                "tests, saved traces, and honest evaluation artifacts."
            ),
        ),
        DemoScriptSection(
            title="Evidence Dashboard",
            duration_seconds=35,
            on_screen="Open the static artifact dashboard and scan metrics.",
            artifact="artifacts/experiments/index.html",
            narration=(
                f"The current artifact set has {readiness.experiment_count} experiments, "
                f"{readiness.run_count} saved runs, and {readiness.metric_count} normalized "
                "metric rows. Use this screen to show retrieval, repair, scaffold, graph, "
                "and patch-search evidence from one review surface."
            ),
        ),
        DemoScriptSection(
            title="Runtime Comparison",
            duration_seconds=40,
            on_screen="Open scaffold comparison and explain the lanes.",
            artifact="artifacts/experiments/scaffold_comparison_v1/scaffold_report.md",
            narration=(
                "The scaffold comparison keeps Agentless, heuristic, LangGraph, "
                "LangGraph fake-model, and the DeepAgents adapter under the same seeded "
                "task set and context provider. The important interview story is that "
                "quality, latency, trace complexity, and debuggability are measured "
                "together instead of treated as separate anecdotes."
            ),
        ),
        DemoScriptSection(
            title="Patch Search Cost Tradeoff",
            duration_seconds=30,
            on_screen="Open patch-search report and compare one versus three candidates.",
            artifact="artifacts/experiments/patch_search_eval_v1/patch_search_report.md",
            narration=(
                "Patch search is included as a research mode. On the current easy seeded "
                "suite, three candidates do not improve success over one candidate, but "
                "they add test runs and latency. That result is useful because it prevents "
                "over-selling patch search before harder tasks justify the cost."
            ),
        ),
        DemoScriptSection(
            title="Failure Transparency",
            duration_seconds=35,
            on_screen="Open the failure report and show grouped failures.",
            artifact="artifacts/experiments/failure_report.md",
            narration=(
                f"The failure report keeps failure cases visible: {failure_summary}. "
                "For the current artifacts, most failures are expected Agentless control "
                "runs with no patch generated. This is exactly the kind of evidence a "
                "research demo should preserve rather than hide."
            ),
        ),
        DemoScriptSection(
            title="Caveats And Close",
            duration_seconds=25,
            on_screen="Open demo readiness report and state the launch status.",
            artifact="artifacts/experiments/demo_readiness.md",
            narration=(
                f"The readiness status is {readiness.readiness_status}. Provider evidence "
                f"is {provider_summary}. The correct closing claim is that the offline "
                "seeded-suite demo is coherent, while live LLM calibration remains a "
                "separate credential-gated step unless non-offline provider metadata is present."
            ),
        ),
    ]


def _demo_script_caveat(readiness: DemoReadinessReport) -> str:
    live_providers = [
        provider
        for provider in readiness.model_providers
        if provider and not provider.startswith("offline_")
    ]
    if live_providers:
        return f"Live provider metadata found: {', '.join(live_providers)}."
    return (
        "Current model evidence is offline only; live LLM calibration must be run "
        "separately before making live-provider claims."
    )


def _demo_script_rehearsal_commands() -> list[str]:
    return [
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
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
