"""Readiness checks for live-provider calibration."""

from __future__ import annotations

from patchsmith.model_config import DEFAULT_OPENAI_MODEL, openai_model_pricing
from patchsmith.portfolio._helpers import (
    _live_providers,
    _package_available,
    _provider_summary,
)
from patchsmith.portfolio.models import LiveCalibrationCheck


def live_calibration_checks(
    *,
    model_providers: dict[str, int],
    deepagents_modes: dict[str, int],
    environment: dict[str, str],
    package_availability: dict[str, bool] | None,
) -> list[LiveCalibrationCheck]:
    live_providers = _live_providers(model_providers)
    openai_sdk_available = _package_available("openai", package_availability)
    deepagents_available = _package_available("deepagents", package_availability)
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


def live_calibration_status(
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
