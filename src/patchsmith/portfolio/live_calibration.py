"""Portfolio live calibration (split from portfolio.py)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.model_config import DEFAULT_OPENAI_MODEL, openai_model_pricing
from patchsmith.portfolio._helpers import (
    _discover_deepagents_adapter_modes,
    _discover_model_providers,
    _discover_openai_agents_adapter_modes,
    _live_providers,
    _markdown_cell,
    _package_available,
    _payload_int,
    _provider_summary,
    _utc_now,
)
from patchsmith.portfolio.models import (
    LiveCalibrationCheck,
    LiveCalibrationPlanReport,
    LiveCalibrationPlanRun,
    LiveCalibrationReport,
)


def build_live_calibration_report(
    *,
    artifacts_dir: Path,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationReport:
    artifacts_dir = artifacts_dir.resolve()
    environment = dict(os.environ if environment is None else environment)
    model_providers = _discover_model_providers(artifacts_dir)
    live_providers = _live_providers(model_providers)
    deepagents_modes = _discover_deepagents_adapter_modes(artifacts_dir)
    openai_agents_modes = _discover_openai_agents_adapter_modes(artifacts_dir)
    checks = _live_calibration_checks(
        model_providers=model_providers,
        deepagents_modes=deepagents_modes,
        openai_agents_modes=openai_agents_modes,
        environment=environment,
        package_availability=package_availability,
    )
    return LiveCalibrationReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        calibration_status=_live_calibration_status(checks, live_providers),
        saved_live_provider_count=sum(model_providers[provider] for provider in live_providers),
        deepagents_package_run_count=deepagents_modes.get("package_available", 0),
        deepagents_compatibility_run_count=deepagents_modes.get("compatibility_mode", 0),
        openai_agents_package_run_count=openai_agents_modes.get("package_available", 0),
        openai_agents_compatibility_run_count=openai_agents_modes.get("compatibility_mode", 0),
        model_providers=model_providers,
        checks=checks,
        smoke_commands=_live_calibration_commands(),
    )


def write_live_calibration_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationReport:
    report = build_live_calibration_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    write_markdown(output_path, render_live_calibration_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_live_calibration_report(report: LiveCalibrationReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Readiness",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- DeepAgents package-backed runs: `{report.deepagents_package_run_count}`",
        f"- DeepAgents compatibility-mode runs: `{report.deepagents_compatibility_run_count}`",
        f"- OpenAI Agents package-backed runs: `{report.openai_agents_package_run_count}`",
        (
            "- OpenAI Agents compatibility-mode runs: "
            f"`{report.openai_agents_compatibility_run_count}`"
        ),
        f"- Model providers: `{_provider_summary(report.model_providers)}`",
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
    lines.extend(["", "## Smoke Commands", ""])
    for command in report.smoke_commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(["## Decision", "", _live_calibration_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def build_live_calibration_plan_report(
    *,
    artifacts_dir: Path,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationPlanReport:
    artifacts_dir = artifacts_dir.resolve()
    environment = dict(os.environ if environment is None else environment)
    readiness = build_live_calibration_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    credentials_configured = bool(environment.get("OPENAI_API_KEY"))
    openai_sdk_available = _package_available("openai", package_availability)
    cost_rates_configured = bool(
        environment.get("PATCHSMITH_OPENAI_INPUT_COST_PER_1M", "").strip()
        and environment.get("PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M", "").strip()
    )
    model = environment.get("PATCHSMITH_OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
    runs = _live_calibration_plan_runs(
        openai_sdk_available=openai_sdk_available,
        credentials_configured=credentials_configured,
        deepagents_available=_package_available("deepagents", package_availability),
        openai_agents_available=_package_available("agents", package_availability),
        saved_live_provider_count=readiness.saved_live_provider_count,
    )
    return LiveCalibrationPlanReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        plan_status=_live_calibration_plan_status(
            readiness=readiness,
            openai_sdk_available=openai_sdk_available,
            credentials_configured=credentials_configured,
        ),
        calibration_status=readiness.calibration_status,
        saved_live_provider_count=readiness.saved_live_provider_count,
        credentials_configured=credentials_configured,
        model=model,
        cost_rates_configured=cost_rates_configured,
        runs=runs,
        prerequisites=readiness.checks,
        claim_boundary=[
            "The plan artifact does not prove live model execution.",
            (
                "A publishable live-provider claim requires a saved run trace with "
                "non-offline model provider metadata and token usage."
            ),
            (
                "Run the single seeded smoke before the full seeded evaluation to "
                "control cost and failure blast radius."
            ),
        ],
    )


def write_live_calibration_plan_report(
    *,
    artifacts_dir: Path,
    output_path: Path,
    json_output_path: Path | None = None,
    environment: dict[str, str] | None = None,
    package_availability: dict[str, bool] | None = None,
) -> LiveCalibrationPlanReport:
    report = build_live_calibration_plan_report(
        artifacts_dir=artifacts_dir,
        environment=environment,
        package_availability=package_availability,
    )
    write_markdown(output_path, render_live_calibration_plan_report(report))
    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_output_path, report.to_dict(), trailing_newline=True)
    return report


def render_live_calibration_plan_report(report: LiveCalibrationPlanReport) -> str:
    lines = [
        "# PatchSmith Live Calibration Plan",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Artifacts directory: `{report.artifacts_dir}`",
        f"- Plan status: `{report.plan_status}`",
        f"- Calibration status: `{report.calibration_status}`",
        f"- Saved live-provider runs: `{report.saved_live_provider_count}`",
        f"- Credentials configured: `{str(report.credentials_configured).lower()}`",
        f"- Model: `{report.model}`",
        f"- Cost rates configured: `{str(report.cost_rates_configured).lower()}`",
        "",
        "## Prerequisites",
        "",
        "| Check | Status | Evidence | Next Action |",
        "|---|---|---|---|",
    ]
    for check in report.prerequisites:
        lines.append(
            "| "
            f"{check.name} | "
            f"{check.status} | "
            f"{_markdown_cell(check.evidence)} | "
            f"{_markdown_cell(check.next_action)} |"
        )
    lines.extend(
        [
            "",
            "## Planned Runs",
            "",
            "| Run | Stage | Status | Runtime | Planner | Context | Credentials | Output | Success Evidence | Claim Boundary |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in report.runs:
        lines.append(
            "| "
            f"{run.name} | "
            f"{run.stage} | "
            f"{run.status} | "
            f"{run.runtime} | "
            f"{run.planner} | "
            f"{run.context_provider} | "
            f"{str(run.requires_credentials).lower()} | "
            f"{_markdown_cell(run.output_path)} | "
            f"{_markdown_cell(run.success_evidence)} | "
            f"{_markdown_cell(run.claim_boundary)} |"
        )
    lines.extend(["", "## Commands", ""])
    for run in report.runs:
        lines.extend([f"### {run.name}", "", "```bash", run.command, "```", ""])
    lines.extend(["## Claim Boundary", ""])
    for claim in report.claim_boundary:
        lines.append(f"- {claim}")
    lines.extend(["", "## Decision", "", _live_calibration_plan_decision(report)])
    return "\n".join(lines).rstrip() + "\n"


def _calibration_plan_run_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    runs = payload.get("runs")
    if isinstance(runs, list):
        statuses = [str(run.get("status") or "") for run in runs if isinstance(run, dict)]
        return len(statuses), statuses.count("ready"), statuses.count("blocked")
    return (
        _payload_int(payload, "run_count"),
        _payload_int(payload, "ready_runs"),
        _payload_int(payload, "blocked_runs"),
    )


def _live_calibration_checks(
    *,
    model_providers: dict[str, int],
    deepagents_modes: dict[str, int],
    openai_agents_modes: dict[str, int],
    environment: dict[str, str],
    package_availability: dict[str, bool] | None,
) -> list[LiveCalibrationCheck]:
    live_providers = _live_providers(model_providers)
    openai_sdk_available = _package_available("openai", package_availability)
    deepagents_available = _package_available("deepagents", package_availability)
    openai_agents_available = _package_available("agents", package_availability)
    openai_key_present = bool(environment.get("OPENAI_API_KEY"))
    model_name = environment.get("PATCHSMITH_OPENAI_MODEL", "").strip()
    input_rate = environment.get("PATCHSMITH_OPENAI_INPUT_COST_PER_1M", "").strip()
    output_rate = environment.get("PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M", "").strip()
    selected_model = model_name or DEFAULT_OPENAI_MODEL
    selected_model_pricing = openai_model_pricing(selected_model)
    cost_rates_known = bool(input_rate and output_rate) or selected_model_pricing is not None
    deepagents_package_runs = deepagents_modes.get("package_available", 0)
    deepagents_compatibility_runs = deepagents_modes.get("compatibility_mode", 0)
    deepagents_live_runs = model_providers.get("deepagents_openai_chat", 0)
    deepagents_package_next_action = (
        "Run the DeepAgents adapter with the optional extra installed and save traces."
    )
    if deepagents_package_runs:
        deepagents_package_next_action = (
            "Use package-backed traces for adapter-import claims; use saved "
            "deepagents_openai_chat rows for live DeepAgents model claims."
            if deepagents_live_runs
            else "Use package-backed traces for adapter-import claims; still avoid live-model claims."
        )
    openai_agents_package_runs = openai_agents_modes.get("package_available", 0)
    openai_agents_compatibility_runs = openai_agents_modes.get("compatibility_mode", 0)

    return [
        LiveCalibrationCheck(
            name="OpenAI SDK",
            status="passed" if openai_sdk_available else "missing",
            evidence=(
                "`openai` package is importable."
                if openai_sdk_available
                else "`openai` package is not importable."
            ),
            next_action=(
                "No action needed."
                if openai_sdk_available
                else "Install runtime dependencies before attempting a live-provider run."
            ),
        ),
        LiveCalibrationCheck(
            name="OpenAI Credentials",
            status="passed" if openai_key_present else "missing",
            evidence="OPENAI_API_KEY is configured."
            if openai_key_present
            else "OPENAI_API_KEY is not set.",
            next_action=(
                "Run the live smoke command and save artifacts."
                if openai_key_present
                else "Set OPENAI_API_KEY only in the local shell used for calibration."
            ),
        ),
        LiveCalibrationCheck(
            name="OpenAI Model Selection",
            status="passed" if model_name else "warning",
            evidence=(
                f"PATCHSMITH_OPENAI_MODEL={model_name}."
                if model_name
                else f"PATCHSMITH_OPENAI_MODEL is not set; default `{DEFAULT_OPENAI_MODEL}` will be used."
            ),
            next_action=(
                "Keep the model name in the saved run metadata."
                if model_name
                else "Set PATCHSMITH_OPENAI_MODEL explicitly before a publishable calibration run."
            ),
        ),
        LiveCalibrationCheck(
            name="Cost Rate Configuration",
            status="passed" if cost_rates_known else "warning",
            evidence=(
                "Input and output cost rates are configured."
                if input_rate and output_rate
                else (
                    f"Using built-in pricing for `{selected_model}`."
                    if selected_model_pricing
                    else "Cost rates are not fully configured."
                )
            ),
            next_action=(
                "Report quality, token use, and estimated cost together."
                if cost_rates_known
                else (
                    "Set PATCHSMITH_OPENAI_INPUT_COST_PER_1M and "
                    "PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M when cost claims matter."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="DeepAgents Package",
            status="passed" if deepagents_available else "warning",
            evidence=(
                "`deepagents` package is importable."
                if deepagents_available
                else (
                    "`deepagents` package is not importable in the current shell; "
                    "use saved trace evidence for package-backed adapter claims."
                    if deepagents_package_runs
                    else (
                        "`deepagents` package is not importable; adapter evidence remains "
                        "compatibility-mode only."
                    )
                )
            ),
            next_action=(
                "Run the DeepAgents adapter under the installed package before making package-backed claims."
                if deepagents_available
                else (
                    "Install the optional `deepagents` extra in the active environment for "
                    "new package-backed runs."
                    if deepagents_package_runs
                    else "Install the optional `deepagents` extra before claiming real package execution."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved DeepAgents Package Evidence",
            status="passed" if deepagents_package_runs else "warning",
            evidence=(
                f"{deepagents_package_runs} package-backed run(s); "
                f"{deepagents_compatibility_runs} compatibility-mode run(s)."
                if deepagents_package_runs
                else f"0 package-backed runs; {deepagents_compatibility_runs} compatibility-mode run(s)."
            ),
            next_action=deepagents_package_next_action,
        ),
        LiveCalibrationCheck(
            name="OpenAI Agents Package",
            status="passed" if openai_agents_available else "warning",
            evidence=(
                "`agents` package is importable."
                if openai_agents_available
                else (
                    "`agents` package is not importable in the current shell; "
                    "use saved trace evidence for package-backed adapter claims."
                    if openai_agents_package_runs
                    else (
                        "`agents` package is not importable; adapter evidence remains "
                        "compatibility-mode only."
                    )
                )
            ),
            next_action=(
                (
                    "Run the OpenAI Agents adapter under the installed package before "
                    "making package-backed claims."
                )
                if openai_agents_available
                else (
                    "Install the optional `openai-agents` extra in the active environment for "
                    "new package-backed runs."
                    if openai_agents_package_runs
                    else (
                        "Install the optional `openai-agents` extra before claiming real "
                        "package execution."
                    )
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved OpenAI Agents Package Evidence",
            status="passed" if openai_agents_package_runs else "warning",
            evidence=(
                f"{openai_agents_package_runs} package-backed run(s); "
                f"{openai_agents_compatibility_runs} compatibility-mode run(s)."
                if openai_agents_package_runs
                else (
                    f"0 package-backed runs; "
                    f"{openai_agents_compatibility_runs} compatibility-mode run(s)."
                )
            ),
            next_action=(
                (
                    "Use package-backed traces for adapter-import claims; still avoid "
                    "live-model claims."
                )
                if openai_agents_package_runs
                else (
                    "Run the OpenAI Agents adapter with the optional extra installed and "
                    "save traces."
                )
            ),
        ),
        LiveCalibrationCheck(
            name="Saved Live Provider Evidence",
            status="passed" if live_providers else "missing",
            evidence=(
                _provider_summary(
                    {provider: model_providers[provider] for provider in live_providers}
                )
                if live_providers
                else "No non-offline model provider metadata found in saved artifacts."
            ),
            next_action=(
                "Use saved live-provider rows for calibrated claims."
                if live_providers
                else "Run and preserve at least one credential-gated live-provider smoke artifact."
            ),
        ),
    ]


def _live_calibration_status(
    checks: list[LiveCalibrationCheck],
    live_providers: list[str],
) -> str:
    if live_providers:
        return "calibrated"
    statuses = {check.name: check.status for check in checks}
    if statuses.get("OpenAI SDK") == "passed" and statuses.get("OpenAI Credentials") == "passed":
        return "ready_to_run"
    if "missing" in statuses.values():
        return "not_configured"
    return "needs_review"


def _live_calibration_plan_runs(
    *,
    openai_sdk_available: bool,
    credentials_configured: bool,
    deepagents_available: bool,
    openai_agents_available: bool,
    saved_live_provider_count: int,
) -> list[LiveCalibrationPlanRun]:
    live_smoke_status = "ready" if openai_sdk_available and credentials_configured else "blocked"
    live_suite_status = (
        "ready"
        if saved_live_provider_count
        else "waiting_for_smoke"
        if live_smoke_status == "ready"
        else "blocked"
    )
    return [
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph single-task smoke",
            stage="required",
            status=live_smoke_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/runs/<run_id>",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli run "
                "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
                "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
                '--test-command "python3 -m pytest" '
                "--runtime langgraph --planner openai --context-provider native_hybrid "
                "--artifacts-dir artifacts --json"
            ),
            success_evidence=(
                "Run trace contains model_provider `openai_responses`, response metadata, "
                "token counts, and a saved report."
            ),
            claim_boundary="Proves one bounded live planner smoke, not broad repair quality.",
        ),
        LiveCalibrationPlanRun(
            name="OpenAI LangGraph seeded-suite eval",
            stage="follow_up",
            status=live_suite_status,
            runtime="langgraph",
            planner="openai",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/live_openai_repair_eval_v1",
            requires_credentials=True,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime langgraph --planner openai --context-provider native_hybrid "
                "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
            ),
            success_evidence=(
                "Repair evaluation summary includes non-offline model provider metadata "
                "and token/cost rows."
            ),
            claim_boundary=(
                "Supports seeded-suite live-provider calibration only; public-issue "
                "repair claims still require separate artifacts."
            ),
        ),
        LiveCalibrationPlanRun(
            name="DeepAgents package-backed adapter refresh",
            stage="optional",
            status="ready" if deepagents_available else "setup_required",
            runtime="deepagents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/deepagents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime deepagents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
            ),
            success_evidence="Trace harness status is `package_available` for DeepAgents rows.",
            claim_boundary=(
                "Proves optional package import compatibility, not live DeepAgents model quality."
            ),
        ),
        LiveCalibrationPlanRun(
            name="OpenAI Agents package-backed adapter refresh",
            stage="optional",
            status="ready" if openai_agents_available else "setup_required",
            runtime="openai_agents",
            planner="heuristic",
            context_provider="native_hybrid",
            output_path="artifacts/experiments/openai_agents_package_smoke_v1",
            requires_credentials=False,
            command=(
                "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
                "--dataset evals/tasks/seeded_bugs_v1 "
                "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
                "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
            ),
            success_evidence=(
                "Trace harness status is `package_available` for OpenAI Agents SDK rows."
            ),
            claim_boundary=(
                "Proves optional package import compatibility, not live OpenAI Agents model quality."
            ),
        ),
    ]


def _live_calibration_plan_status(
    *,
    readiness: LiveCalibrationReport,
    openai_sdk_available: bool,
    credentials_configured: bool,
) -> str:
    if readiness.calibration_status == "calibrated":
        return "calibrated"
    if openai_sdk_available and credentials_configured:
        return "ready_to_run"
    return "blocked"


def _live_calibration_plan_decision(report: LiveCalibrationPlanReport) -> str:
    if report.plan_status == "calibrated":
        return "Live-provider evidence already exists; rerun only when recalibrating a new model or scaffold."
    if report.plan_status == "ready_to_run":
        return "Run the required single-task smoke first, then regenerate `live-calibration` before broader evals."
    return (
        "Live calibration is planned but blocked by missing prerequisites. Do not claim "
        "live LLM execution until a required run saves non-offline provider metadata."
    )


def _live_calibration_commands() -> list[str]:
    return [
        'python -m pip install -e ".[dev,deepagents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime deepagents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/deepagents_package_smoke_v1 --json"
        ),
        'python -m pip install -e ".[dev,openai-agents]"',
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime openai_agents --planner heuristic --context-provider native_hybrid "
            "--output artifacts/experiments/openai_agents_package_smoke_v1 --json"
        ),
        (
            "export OPENAI_API_KEY=...\n"
            "export PATCHSMITH_OPENAI_MODEL=<model>\n"
            "export PATCHSMITH_OPENAI_INPUT_COST_PER_1M=<input_rate>\n"
            "export PATCHSMITH_OPENAI_OUTPUT_COST_PER_1M=<output_rate>"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli run "
            "--repo evals/tasks/seeded_bugs_v1/task_001_logic_bug/repo "
            "--issue-file evals/tasks/seeded_bugs_v1/task_001_logic_bug/issue.md "
            '--test-command "python3 -m pytest" '
            "--runtime langgraph --planner openai --context-provider native_hybrid "
            "--artifacts-dir artifacts --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli eval-repair "
            "--dataset evals/tasks/seeded_bugs_v1 "
            "--runtime langgraph --planner openai --context-provider native_hybrid "
            "--output artifacts/experiments/live_openai_repair_eval_v1 --json"
        ),
        (
            "PYTHONPATH=src python3 -m patchsmith.cli live-calibration "
            "--artifacts-dir artifacts "
            "--output artifacts/experiments/calibration_readiness.md "
            "--json-output artifacts/experiments/calibration_readiness.json --json"
        ),
    ]


def _live_calibration_decision(report: LiveCalibrationReport) -> str:
    if report.calibration_status == "calibrated":
        return (
            "Saved non-offline provider evidence exists. Report it with token and cost "
            "metadata before making live-provider claims."
        )
    if report.calibration_status == "ready_to_run":
        return (
            "The environment appears ready for a live OpenAI smoke run, but saved "
            "live-provider artifacts are still missing."
        )
    if report.calibration_status == "not_configured":
        return (
            "Live calibration is not configured. Keep current public claims scoped to "
            "offline seeded-suite evidence."
        )
    return (
        "Live calibration needs review before publishable claims. Resolve warning checks "
        "and preserve the resulting run artifacts."
    )
