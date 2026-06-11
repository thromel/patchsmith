"""Portfolio demo assets (split from portfolio.py)."""

from __future__ import annotations

import json
import struct
import zlib
from html import escape
from pathlib import Path

from patchsmith.portfolio._helpers import (
    _failure_summary,
    _format_duration,
    _markdown_cell,
    _provider_summary,
    _utc_now,
)
from patchsmith.portfolio.demo_readiness import build_demo_readiness_report
from patchsmith.portfolio.models import (
    DemoMediaReport,
    DemoReadinessReport,
    DemoScriptReport,
    DemoScriptSection,
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
    return (
        "\n".join(
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
        )
        + "\n"
    )


def render_demo_media_svg(report: DemoMediaReport) -> str:
    highlight_items = "\n".join(
        (f'<text x="92" y="{258 + index * 54}" class="metric">{escape(highlight)}</text>')
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
    return bytes(int(normalized[index : index + 2], 16) for index in range(0, 6, 2))


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
                "LangGraph fake-model, DeepAgents, and OpenAI Agents SDK adapters "
                "under the same seeded task set and context provider. The important "
                "interview story is that quality, latency, trace complexity, and "
                "debuggability are measured together instead of treated as separate "
                "anecdotes."
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
    ]
