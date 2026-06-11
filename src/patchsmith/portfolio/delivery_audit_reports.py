"""Portfolio delivery audit Markdown rendering."""

from __future__ import annotations

from patchsmith.portfolio._helpers import _markdown_cell
from patchsmith.portfolio.models import DeliveryAuditReport


def render_delivery_audit_report(report: DeliveryAuditReport) -> str:
    lines = [
        "# PatchSmith Delivery Audit",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Project root: `{report.project_root}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Delivery status: `{report.delivery_status}`",
        f"- Evidence-weighted completion: `{report.completion_percent:.1f}%`",
        f"- Items: `{report.item_count}`",
        f"- Passed: `{report.passed_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Blockers: `{report.blocked_count}`",
        f"- Missing: `{report.missing_count}`",
        "",
        "## Requirement Evidence",
        "",
        "| Requirement | Status | Evidence | Source | Next Action |",
        "|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            f"{item.requirement} | "
            f"{item.status} | "
            f"{_markdown_cell(item.evidence)} | "
            f"{_markdown_cell(item.source)} | "
            f"{_markdown_cell(item.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Scoring",
            "",
            "- Passed items count as 1.0.",
            "- Warning items count as 0.5 because evidence exists but is incomplete.",
            "- Blocked and missing items count as 0.0.",
            "- This audit is a delivery status artifact; it does not replace rerunning tests or live calibration.",
        ]
    )
    return "\n".join(lines) + "\n"
