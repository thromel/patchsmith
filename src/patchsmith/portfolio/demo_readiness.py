"""Portfolio demo readiness (split from portfolio.py)."""

from __future__ import annotations

import json
from pathlib import Path

from patchsmith.observability import (
    FailureArtifactReport,
    build_artifact_index,
    build_failure_report,
)
from patchsmith.portfolio._helpers import (
    _demo_commands,
    _discover_model_providers,
    _markdown_cell,
    _utc_now,
)
from patchsmith.portfolio.models import DemoReadinessGate, DemoReadinessReport


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
        provider for provider in model_providers if provider and not provider.startswith("offline_")
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
    passed = kind in metric_kinds or (alternate_kind is not None and alternate_kind in metric_kinds)
    evidence_kind = (
        kind if kind in metric_kinds else alternate_kind if alternate_kind in metric_kinds else kind
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
