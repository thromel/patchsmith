"""Demo media Markdown, SVG, and PNG rendering helpers."""

from __future__ import annotations

import struct
import zlib
from html import escape
from pathlib import Path

from patchsmith.portfolio.models import DemoMediaReport


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


def write_demo_media_png(report: DemoMediaReport, output_path: Path) -> None:
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


__all__ = [
    "render_demo_media_report",
    "render_demo_media_svg",
    "write_demo_media_png",
]
