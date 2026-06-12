"""Portfolio demo assets (split from portfolio.py)."""

from __future__ import annotations

from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.portfolio._helpers import (
    _format_duration,
    _markdown_cell,
    _provider_summary,
    _utc_now,
)
from patchsmith.portfolio.demo_media_rendering import (
    render_demo_media_report,
    render_demo_media_svg,
    write_demo_media_png,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.demo_script_content import (
    demo_script_caveat,
    demo_script_rehearsal_commands,
    demo_script_sections,
)
from patchsmith.portfolio.models import (
    DemoMediaReport,
    DemoScriptReport,
)


def build_demo_script_report(
    *,
    artifacts_dir: Path,
    max_failure_runs: int | None = None,
) -> DemoScriptReport:
    readiness = build_demo_readiness_report(
        artifacts_dir=artifacts_dir,
        max_failure_runs=max_failure_runs,
    )
    sections = demo_script_sections(readiness)
    return DemoScriptReport(
        artifacts_dir=readiness.artifacts_dir,
        generated_at=_utc_now(),
        target_duration_seconds=sum(section.duration_seconds for section in sections),
        readiness_status=readiness.readiness_status,
        caveat=demo_script_caveat(readiness),
        sections=sections,
        rehearsal_commands=demo_script_rehearsal_commands(),
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
        caveat=demo_script_caveat(readiness),
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
    write_demo_media_png(report, png_output_path)
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


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
    write_markdown(output_path, render_demo_script_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
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
