"""Portfolio live calibration."""

from __future__ import annotations

import os
from pathlib import Path

from patchsmith.artifacts import write_json, write_markdown
from patchsmith.model_config import DEFAULT_OPENAI_MODEL
from patchsmith.portfolio._helpers import (
    _discover_deepagents_adapter_modes,
    _discover_model_providers,
    _discover_openai_agents_adapter_modes,
    _live_providers,
    _package_available,
    _utc_now,
)
from patchsmith.portfolio.live_calibration_checks import (
    live_calibration_checks,
    live_calibration_status,
)
from patchsmith.portfolio.live_calibration_plan import (
    calibration_plan_run_counts as _calibration_plan_run_counts,
)
from patchsmith.portfolio.live_calibration_plan import (
    live_calibration_commands,
    live_calibration_plan_runs,
    live_calibration_plan_status,
)
from patchsmith.portfolio.live_calibration_reports import (
    render_live_calibration_plan_report,
    render_live_calibration_report,
)
from patchsmith.portfolio.models import (
    LiveCalibrationPlanReport,
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
    checks = live_calibration_checks(
        model_providers=model_providers,
        deepagents_modes=deepagents_modes,
        openai_agents_modes=openai_agents_modes,
        environment=environment,
        package_availability=package_availability,
    )
    return LiveCalibrationReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        calibration_status=live_calibration_status(checks, live_providers),
        saved_live_provider_count=sum(model_providers[provider] for provider in live_providers),
        deepagents_package_run_count=deepagents_modes.get("package_available", 0),
        deepagents_compatibility_run_count=deepagents_modes.get("compatibility_mode", 0),
        openai_agents_package_run_count=openai_agents_modes.get("package_available", 0),
        openai_agents_compatibility_run_count=openai_agents_modes.get("compatibility_mode", 0),
        model_providers=model_providers,
        checks=checks,
        smoke_commands=live_calibration_commands(),
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
    runs = live_calibration_plan_runs(
        openai_sdk_available=openai_sdk_available,
        credentials_configured=credentials_configured,
        deepagents_available=_package_available("deepagents", package_availability),
        openai_agents_available=_package_available("agents", package_availability),
        saved_live_provider_count=readiness.saved_live_provider_count,
    )
    return LiveCalibrationPlanReport(
        artifacts_dir=str(artifacts_dir),
        generated_at=_utc_now(),
        plan_status=live_calibration_plan_status(
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


__all__ = [
    "_calibration_plan_run_counts",
    "build_live_calibration_plan_report",
    "build_live_calibration_report",
    "render_live_calibration_plan_report",
    "render_live_calibration_report",
    "write_live_calibration_plan_report",
    "write_live_calibration_report",
]
